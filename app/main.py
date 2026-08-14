from __future__ import annotations

import os
from pathlib import Path
import yaml

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from .auth import get_auth_diagnostics, verify_api_key
from .engine import BusinessError, calculate, validate_request, calculate_average_salary, expand_records
from .models import ErrorResponse
from .privacy_vi import get_privacy_policy_html
from .swagger_vi import get_swagger_ui_vi_html
from .v2_adapter import validate_v2_payload, to_internal, build_v2_response

API_VERSION = "2.3.0"
ACTION_SCHEMA_VERSION = "2.0.0"
ADAPTER_RELEASE = "R1.9"
MAX_REQUEST_BODY_BYTES = int(os.getenv("MAX_REQUEST_BODY_BYTES", "2097152"))

app = FastAPI(
    title="calculatePension API",
    version=API_VERSION,
    description=(
        "API dự tính lương hưu BHXH Việt Nam 2.3.0; contract GPT Action V2.0. "
        "Kết quả chỉ mang tính ước tính."
    ),
    docs_url=None,
    redoc_url=None,
)

# Static contract is the single source for the public API documentation.
_CONTRACT_PATH = Path(__file__).resolve().parent.parent / "contracts" / "02_API_V2.3.0.yaml"
_CONTRACT = yaml.safe_load(_CONTRACT_PATH.read_text(encoding="utf-8"))


def custom_openapi():
    return _CONTRACT
app.openapi = custom_openapi


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_REQUEST_BODY_BYTES:
                return JSONResponse(status_code=413, content={"error_code":"REQUEST_BODY_TOO_LARGE","detail":"Kích thước yêu cầu vượt giới hạn cho phép.","fields":["content-length"]})
        except ValueError:
            return JSONResponse(status_code=400, content={"error_code":"INVALID_CONTENT_LENGTH","detail":"Header Content-Length không hợp lệ.","fields":["content-length"]})
    if request.method in {"POST", "PUT", "PATCH"}:
        body = await request.body()
        if len(body) > MAX_REQUEST_BODY_BYTES:
            return JSONResponse(status_code=413, content={"error_code":"REQUEST_BODY_TOO_LARGE","detail":"Kích thước yêu cầu vượt giới hạn cho phép.","fields":["request.body"]})
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.get("/", include_in_schema=False)
def home() -> RedirectResponse:
    return RedirectResponse(url="/docs")

@app.get("/docs", include_in_schema=False)
def docs_vi():
    return get_swagger_ui_vi_html()

@app.get("/docs-en", include_in_schema=False)
def docs_en():
    return get_swagger_ui_html(openapi_url=app.openapi_url, title=f"{app.title} - Swagger UI", swagger_ui_parameters={"deepLinking":True,"displayRequestDuration":True,"filter":True,"persistAuthorization":True})

@app.get("/privacy-policy", include_in_schema=False, response_class=HTMLResponse)
def privacy_policy() -> HTMLResponse:
    return HTMLResponse(content=get_privacy_policy_html())

@app.get("/health", include_in_schema=False)
def health() -> dict[str, str]:
    return {"status":"ok","service":"calculatePension","version":API_VERSION,"action_schema_version":ACTION_SCHEMA_VERSION,"schema_version":"2.3.0","engine_version":"1.0.10-rc","adapter_release":ADAPTER_RELEASE,"policy_version":"VN-BHXH-PENSION-V1.0-2026"}

@app.get("/version", include_in_schema=False)
def version() -> dict[str, str]:
    return {"api_version":API_VERSION,"action_schema_version":ACTION_SCHEMA_VERSION,"engine_version":"1.0.10-rc","adapter_release":ADAPTER_RELEASE,"policy_version":"VN-BHXH-PENSION-V1.0-2026","contract":"02_API_V2.3.0.yaml"}

@app.get("/v1/authDiagnostics", include_in_schema=False)
def auth_diagnostics(x_api_key: str | None = Header(default=None, alias="X-API-Key")):
    return get_auth_diagnostics(x_api_key)

@app.get("/v1/capabilities", include_in_schema=False, dependencies=[Depends(verify_api_key)])
def capabilities():
    return {"api_version":API_VERSION,"action_schema_version":ACTION_SCHEMA_VERSION,"adapter_release":ADAPTER_RELEASE,"supports":["validateContributionHistory","calculatePension","mau_07_sbh_components","nd154_2025_streamlining"],"scope_excludes":["armed_forces"],"nd154_state_budget_allowance_excluded":True}


def _read_payload(request: Request):
    # FastAPI dependency injection is intentionally avoided so the public request
    # contract can remain exactly the externally supplied V2.0/2.3.0 JSON Schema.
    return request.json()

@app.post("/v1/validateContributionHistory", operation_id="validateContributionHistory", dependencies=[Depends(verify_api_key)], summary="Kiểm tra dữ liệu quá trình BHXH trước khi tính")
async def validate_history(request: Request):
    try:
        payload = await request.json()
        validate_v2_payload(payload)
        internal = to_internal(payload)
        diag = validate_request(internal)
        total = diag.response.normalized_summary.total_contribution_months if diag.response.normalized_summary else 0
        excluded = diag.response.normalized_summary.excluded_bhtn_months if diag.response.normalized_summary else 0
        avg_months = 0
        credited_duration_only_months = 0
        if diag.response.validation:
            records = expand_records(internal)
            _, _, avg_months, _ = calculate_average_salary(internal, records)
            # Count normalized monthly records instead of reading non-existent
            # Contribution.to_date/from_date attributes. The old R1.8 code raised
            # AttributeError as soon as a credited_duration_only PRE-1995 row was
            # present, which surfaced to GPT as INTERNAL_CALCULATION_ERROR.
            credited_duration_only_months = sum(
                1
                for r in records
                if r.participation_status.value == "credited_duration_only"
            )
        return {"valid_for_calculation":diag.response.validation,"total_unique_months":total,"average_basis_months":avg_months,"credited_duration_only_months":credited_duration_only_months,"excluded_non_participation_months":excluded,"gaps":[],"overlaps":[],"issues":list(diag.response.warnings)}
    except ValueError as exc:
        return JSONResponse(status_code=422, content={"detail":[{"loc":["body"],"msg":str(exc),"type":"value_error"}]})
    except BusinessError as exc:
        return JSONResponse(status_code=422, content={"detail":[{"loc":["body"],"msg":exc.detail,"type":exc.error_code}]})

@app.post("/v1/calculatePension", operation_id="calculatePension", dependencies=[Depends(verify_api_key)], summary="Dự tính mức lương hưu")
async def calculate_pension(request: Request):
    try:
        payload = await request.json()
        validate_v2_payload(payload)
        internal = to_internal(payload)
        diagnostics = validate_request(internal)
        if not diagnostics.response.validation:
            fields = sorted({f for issue in diagnostics.issues for f in issue.fields})
            detail = "; ".join(issue.message for issue in diagnostics.issues[:6])
            return JSONResponse(status_code=422, content={"detail":[{"loc":["body"],"msg":detail,"type":"CONTRIBUTION_HISTORY_INVALID","fields":fields}]})
        result = calculate(internal)
        return build_v2_response(payload, result, diagnostics, internal)
    except ValueError as exc:
        return JSONResponse(status_code=422, content={"detail":[{"loc":["body"],"msg":str(exc),"type":"value_error"}]})
    except BusinessError as exc:
        return JSONResponse(status_code=422, content={"detail":[{"loc":["body"],"msg":exc.detail,"type":exc.error_code,"fields":exc.fields}]})

@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content=exc.detail if isinstance(exc.detail, dict) else {"error_code":f"HTTP_{exc.status_code}","detail":str(exc.detail),"fields":[]}, headers=exc.headers)

@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"error_code":"INTERNAL_CALCULATION_ERROR","detail":"Đã xảy ra lỗi nội bộ trong quá trình tính toán.","fields":[]})
