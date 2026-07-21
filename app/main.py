from __future__ import annotations

import os
import secrets

from fastapi import Depends, FastAPI, HTTPException, Security, status
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.security import APIKeyHeader

from .engine import calculate_pension, capabilities, validate_contribution_history
from .models import (
    CapabilitiesResponse,
    HistoryValidationResult,
    PensionRequest,
    PensionResponse,
)
from .privacy_vi import get_privacy_policy_html
from .swagger_vi import get_swagger_ui_vi_html

OPENAPI_TAGS = [
    {"name": "Hệ thống", "description": "Trạng thái và khả năng của dịch vụ."},
    {"name": "Kiểm tra hồ sơ", "description": "Kiểm tra dữ liệu chuẩn hóa từ Mẫu 07/SBH."},
    {"name": "Tính lương hưu", "description": "Dự tính điều kiện và mức lương hưu."},
]

app = FastAPI(
    title="API calculatePension - Tính lương hưu BHXH",
    version="2.1.0",
    description=(
        "API dự tính lương hưu BHXH Việt Nam, hỗ trợ dữ liệu chuẩn hóa từ Mẫu 07/SBH, "
        "kiểm tra tháng trống/trùng, trạng thái không tham gia, thời gian chỉ cộng thời gian, quá trình hỗn hợp và bộ hệ số theo năm hưởng. "
        "Kết quả chỉ mang tính tham khảo."
    ),
    contact={"name": "Quản trị viên calculatePension"},
    openapi_tags=OPENAPI_TAGS,
    docs_url=None,
    redoc_url=None,
)


api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(x_api_key: str | None = Security(api_key_header)) -> None:
    expected = os.getenv("API_KEY")
    if not expected:
        return
    if not x_api_key or not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Thiếu hoặc sai khóa X-API-Key.",
        )


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
        title=f"{app.title} - English Swagger UI",
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


@app.get(
    "/health",
    tags=["Hệ thống"],
    summary="Kiểm tra trạng thái API",
)
def health() -> dict[str, str]:
    return {"status": "ok", "service": "calculatePension", "version": "2.1.0"}


@app.get(
    "/v1/capabilities",
    operation_id="getPensionCapabilities",
    response_model=CapabilitiesResponse,
    tags=["Hệ thống"],
    summary="Xem phạm vi tính toán hiện được hỗ trợ",
    dependencies=[Depends(verify_api_key)],
)
def get_capabilities() -> CapabilitiesResponse:
    return capabilities()


@app.post(
    "/v1/validateContributionHistory",
    operation_id="validateContributionHistory",
    response_model=HistoryValidationResult,
    tags=["Kiểm tra hồ sơ"],
    summary="Kiểm tra dữ liệu quá trình BHXH trước khi tính",
    description=(
        "Kiểm tra xác nhận Mẫu 07/SBH, đơn vị mức đóng, tháng trống, tháng trùng "
        "và giai đoạn sau tháng bắt đầu hưởng."
    ),
    dependencies=[Depends(verify_api_key)],
)
def validate_history(request: PensionRequest) -> HistoryValidationResult:
    return validate_contribution_history(request)


@app.post(
    "/v1/calculatePension",
    operation_id="calculatePension",
    response_model=PensionResponse,
    tags=["Tính lương hưu"],
    summary="Dự tính mức lương hưu",
    description=(
        "Tính điều kiện hưởng, mức bình quân, tỷ lệ, giảm do nghỉ trước tuổi, "
        "lương hưu dự tính và trợ cấp một lần. Dữ liệu Mẫu 07/SBH phải được "
        "chuẩn hóa và xác nhận trước."
    ),
    dependencies=[Depends(verify_api_key)],
)
def calculate(request: PensionRequest) -> PensionResponse:
    return calculate_pension(request)


@app.exception_handler(Exception)
async def unhandled_exception_handler(_, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "error_code": "INTERNAL_CALCULATION_ERROR",
            "message_vi": "Đã xảy ra lỗi nội bộ trong quá trình tính toán.",
            "error_type": type(exc).__name__,
        },
    )
