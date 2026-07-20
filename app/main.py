from __future__ import annotations

import os
import secrets
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from .engine import calculate_pension
from .models import PensionRequest, PensionResponse
from .swagger_vi import get_swagger_ui_vi_html
from .privacy_vi import get_privacy_policy_html


OPENAPI_TAGS = [
    {
        "name": "Hệ thống",
        "description": "Các chức năng kiểm tra trạng thái hoạt động của dịch vụ.",
    },
    {
        "name": "Tính lương hưu",
        "description": (
            "Tiếp nhận thông tin cá nhân và quá trình đóng BHXH để dự tính "
            "điều kiện hưởng, tỷ lệ hưởng và mức lương hưu hằng tháng."
        ),
    },
]


app = FastAPI(
    title="API tính lương hưu BHXH",
    version="1.2.0",
    description=(
        "Công cụ dự tính lương hưu cho người tham gia bảo hiểm xã hội Việt Nam "
        "theo Luật Bảo hiểm xã hội năm 2024 và các quy định triển khai hiện hành. "
        "Kết quả chỉ mang tính tham khảo; hồ sơ được cơ quan BHXH xác nhận là căn cứ cuối cùng."
    ),
    contact={"name": "Quản trị viên API calculatePension"},
    openapi_tags=OPENAPI_TAGS,
    docs_url=None,
    redoc_url=None,
)


SCHEMA_NAME_MAP = {
    "AdjustmentInput": "DuLieuDieuChinh",
    "AverageBasisResult": "KetQuaMucBinhQuan",
    "ContributionPeriod": "GiaiDoanDongBHXH",
    "ContributionSummary": "TongHopThoiGianDong",
    "ContributionType": "LoaiHinhDongBHXH",
    "EligibilityResult": "KetQuaDieuKienHuong",
    "HTTPValidationError": "LoiKiemTraDuLieu",
    "PensionRateResult": "KetQuaTyLeHuong",
    "PensionRequest": "YeuCauTinhLuongHuu",
    "PensionResponse": "KetQuaTinhLuongHuu",
    "Person": "ThongTinCaNhan",
    "RetirementCase": "TruongHopNghiHuu",
    "Sex": "GioiTinh",
    "ValidationError": "ChiTietLoiDuLieu",
}


def _replace_schema_refs(value: Any) -> None:
    if isinstance(value, dict):
        ref = value.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
            old_name = ref.rsplit("/", 1)[-1]
            new_name = SCHEMA_NAME_MAP.get(old_name)
            if new_name:
                value["$ref"] = f"#/components/schemas/{new_name}"
        for child in value.values():
            _replace_schema_refs(child)
    elif isinstance(value, list):
        for child in value:
            _replace_schema_refs(child)


def custom_openapi() -> dict[str, Any]:
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        tags=app.openapi_tags,
        contact=app.contact,
    )

    schemas = schema.get("components", {}).get("schemas", {})
    renamed_schemas: dict[str, Any] = {}
    for old_name, schema_value in schemas.items():
        new_name = SCHEMA_NAME_MAP.get(old_name, old_name)
        renamed_schemas[new_name] = schema_value

    if "components" in schema and "schemas" in schema["components"]:
        schema["components"]["schemas"] = renamed_schemas

    _replace_schema_refs(schema)
    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi


def verify_api_key(x_api_key: str | None = Header(default=None)) -> None:
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
    """Tài liệu Swagger UI đã Việt hóa."""
    return get_swagger_ui_vi_html()


@app.get("/docs-en", include_in_schema=False)
def docs_en():
    """Giữ lại giao diện tiếng Anh cho lập trình viên khi cần đối chiếu."""
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


@app.get(
    "/privacy-policy",
    include_in_schema=False,
    response_class=HTMLResponse,
)
def privacy_policy() -> HTMLResponse:
    """Chính sách quyền riêng tư công khai dùng khi cấu hình hoặc xuất bản GPT."""
    return HTMLResponse(content=get_privacy_policy_html())


@app.get(
    "/health",
    tags=["Hệ thống"],
    summary="Kiểm tra trạng thái API",
    description="Kiểm tra nhanh dịch vụ calculatePension có đang hoạt động hay không.",
    response_description="Trạng thái hoạt động của dịch vụ.",
)
def health() -> dict[str, str]:
    return {"status": "ok", "service": "calculatePension"}


@app.post(
    "/v1/calculatePension",
    operation_id="calculatePension",
    response_model=PensionResponse,
    tags=["Tính lương hưu"],
    summary="Dự tính mức lương hưu",
    description=(
        "Tính điều kiện hưởng, mức bình quân làm căn cứ, tỷ lệ hưởng, "
        "lương hưu dự kiến và trợ cấp một lần dựa trên dữ liệu người dùng cung cấp. "
        "Không được tự suy đoán dữ liệu còn thiếu."
    ),
    response_description="Kết quả dự tính lương hưu và các cảnh báo liên quan.",
    dependencies=[Depends(verify_api_key)],
)
def calculate(request: PensionRequest) -> PensionResponse:
    try:
        return calculate_pension(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.exception_handler(Exception)
async def unhandled_exception_handler(_, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Đã xảy ra lỗi nội bộ trong quá trình tính toán.",
            "error_type": type(exc).__name__,
        },
    )
