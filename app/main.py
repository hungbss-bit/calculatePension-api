from __future__ import annotations

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from .auth import get_auth_diagnostics, verify_api_key
from .engine import BusinessError, calculate, validate_request
from .models import (
    ErrorResponse,
    PensionCalculationRequest,
    PensionCalculationResponse,
    ValidationResponse,
)
from .privacy_vi import get_privacy_policy_html
from .swagger_vi import get_swagger_ui_vi_html

API_VERSION = "1.0.7"

MAX_REQUEST_BODY_BYTES = int(__import__("os").getenv("MAX_REQUEST_BODY_BYTES", "2097152"))

app = FastAPI(
    title="calculatePension API",
    version=API_VERSION,
    description=(
        "API dự tính lương hưu BHXH Việt Nam V1.0, "
        "bao gồm trợ cấp một lần khi nghỉ hưu. Kết quả chỉ mang tính ước tính."
    ),
    docs_url=None,
    redoc_url=None,
)


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_REQUEST_BODY_BYTES:
                return JSONResponse(
                    status_code=413,
                    content=ErrorResponse(
                        error_code="REQUEST_BODY_TOO_LARGE",
                        detail="Kích thước yêu cầu vượt giới hạn cho phép.",
                        fields=["content-length"],
                    ).model_dump(mode="json"),
                )
        except ValueError:
            return JSONResponse(
                status_code=400,
                content=ErrorResponse(
                    error_code="INVALID_CONTENT_LENGTH",
                    detail="Header Content-Length không hợp lệ.",
                    fields=["content-length"],
                ).model_dump(mode="json"),
            )

    # Also enforce the limit for chunked/streamed requests that omit Content-Length.
    # FastAPI/Starlette caches request.body(), so downstream validation can reuse it.
    if request.method in {"POST", "PUT", "PATCH"}:
        body = await request.body()
        if len(body) > MAX_REQUEST_BODY_BYTES:
            return JSONResponse(
                status_code=413,
                content=ErrorResponse(
                    error_code="REQUEST_BODY_TOO_LARGE",
                    detail="Kích thước yêu cầu vượt giới hạn cho phép.",
                    fields=["request.body"],
                ).model_dump(mode="json"),
            )

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
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - Swagger UI",
        swagger_ui_parameters={
            "deepLinking": True,
            "displayRequestDuration": True,
            "filter": True,
            "persistAuthorization": True,
        },
    )


@app.get("/privacy-policy", include_in_schema=False, response_class=HTMLResponse)
def privacy_policy() -> HTMLResponse:
    return HTMLResponse(content=get_privacy_policy_html())


@app.get("/health", include_in_schema=False)
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "calculatePension",
        "version": API_VERSION,
        "schema_version": "V1.0",
    }


@app.get("/v1/authDiagnostics", include_in_schema=False)
def auth_diagnostics(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict[str, object]:
    return get_auth_diagnostics(x_api_key)


@app.post(
    "/v1/validateContributionHistory",
    operation_id="validateContributionHistory",
    response_model=ValidationResponse,
    responses={400: {"model": ErrorResponse}},
    dependencies=[Depends(verify_api_key)],
    summary="Kiểm tra và chuẩn hóa lịch sử đóng BHXH",
)
def validate_history(
    request: PensionCalculationRequest,
) -> ValidationResponse:
    return validate_request(request).response


@app.post(
    "/v1/calculatePension",
    operation_id="calculatePension",
    response_model=PensionCalculationResponse,
    response_model_exclude_none=True,
    responses={400: {"model": ErrorResponse}},
    dependencies=[Depends(verify_api_key)],
    summary="Tính dự tính lương hưu và trợ cấp một lần",
)
def calculate_pension(
    request: PensionCalculationRequest,
) -> PensionCalculationResponse:
    return calculate(request)




@app.exception_handler(HTTPException)
async def http_exception_handler(
    _: Request,
    exc: HTTPException,
) -> JSONResponse:
    if isinstance(exc.detail, dict):
        error_code = str(exc.detail.get("error_code", f"HTTP_{exc.status_code}"))
        detail = str(
            exc.detail.get("detail")
            or exc.detail.get("message_vi")
            or "Yêu cầu HTTP không hợp lệ."
        )
        fields = list(exc.detail.get("fields", []))
    else:
        error_code = f"HTTP_{exc.status_code}"
        detail = str(exc.detail)
        fields = []
    payload = ErrorResponse(
        error_code=error_code,
        detail=detail,
        fields=fields,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=payload.model_dump(mode="json"),
        headers=exc.headers,
    )


@app.exception_handler(BusinessError)
async def business_error_handler(
    _: Request,
    exc: BusinessError,
) -> JSONResponse:
    payload = ErrorResponse(
        error_code=exc.error_code,
        detail=exc.detail,
        fields=exc.fields,
    )
    return JSONResponse(status_code=400, content=payload.model_dump(mode="json"))


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(
    _: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    fields: list[str] = []
    details: list[str] = []
    for error in exc.errors():
        loc = ".".join(str(item) for item in error.get("loc", ()) if item != "body")
        if loc:
            fields.append(loc)
        details.append(f"{loc or 'request'}: {error.get('msg', 'Dữ liệu không hợp lệ')}")
    payload = ErrorResponse(
        error_code="REQUEST_VALIDATION_ERROR",
        detail="; ".join(details),
        fields=sorted(set(fields)),
    )
    return JSONResponse(status_code=400, content=payload.model_dump(mode="json"))


@app.exception_handler(Exception)
async def unhandled_exception_handler(
    _: Request,
    exc: Exception,
) -> JSONResponse:
    # Do not expose exception class/module names to clients.
    # Detailed diagnostics belong in platform logs/monitoring only.
    payload = ErrorResponse(
        error_code="INTERNAL_CALCULATION_ERROR",
        detail="Đã xảy ra lỗi nội bộ trong quá trình tính toán.",
        fields=[],
    )
    return JSONResponse(status_code=500, content=payload.model_dump(mode="json"))
