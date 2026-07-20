from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


YEAR_MONTH_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"


class Sex(str, Enum):
    """Giới tính dùng để xác định lộ trình tuổi nghỉ hưu."""

    male = "male"
    female = "female"


class ContributionType(str, Enum):
    """Loại tiền lương hoặc thu nhập làm căn cứ đóng BHXH."""

    compulsory_state = "compulsory_state"
    compulsory_employer = "compulsory_employer"
    voluntary = "voluntary"


class RetirementCase(str, Enum):
    """Nhóm điều kiện nghỉ hưu cần áp dụng."""

    normal = "normal"
    hazardous_or_special_region = "hazardous_or_special_region"
    underground_coal = "underground_coal"
    reduced_capacity = "reduced_capacity"
    occupational_hiv = "occupational_hiv"
    armed_forces = "armed_forces"


class Person(BaseModel):
    model_config = ConfigDict(title="Thông tin cá nhân")

    date_of_birth: date = Field(
        title="Ngày sinh",
        description="Ngày, tháng, năm sinh theo định dạng YYYY-MM-DD.",
        examples=["1969-09-01"],
    )
    sex: Sex = Field(
        title="Giới tính",
        description="Chọn male = Nam hoặc female = Nữ.",
        examples=["female"],
    )


class ContributionPeriod(BaseModel):
    model_config = ConfigDict(title="Giai đoạn đóng BHXH")

    from_month: str = Field(
        pattern=YEAR_MONTH_PATTERN,
        title="Từ tháng",
        description="Tháng bắt đầu của giai đoạn đóng, định dạng YYYY-MM; tính cả tháng này.",
        examples=["1996-10"],
    )
    to_month: str = Field(
        pattern=YEAR_MONTH_PATTERN,
        title="Đến tháng",
        description="Tháng kết thúc của giai đoạn đóng, định dạng YYYY-MM; tính cả tháng này.",
        examples=["2026-09"],
    )
    monthly_basis_vnd: Annotated[
        Decimal,
        Field(
            gt=0,
            title="Mức đóng hằng tháng",
            description=(
                "Tiền lương hoặc thu nhập tháng làm căn cứ đóng BHXH, đơn vị đồng Việt Nam."
            ),
            examples=[10800000],
        ),
    ]
    contribution_type: ContributionType = Field(
        title="Loại quá trình đóng",
        description=(
            "compulsory_state = lương do Nhà nước quy định; "
            "compulsory_employer = lương do người sử dụng lao động quyết định; "
            "voluntary = BHXH tự nguyện."
        ),
        examples=["compulsory_employer"],
    )
    coefficient_override: Annotated[
        Decimal | None,
        Field(
            gt=0,
            title="Hệ số điều chỉnh riêng",
            description=(
                "Không bắt buộc. Chỉ nhập khi có hệ số chính thức cần áp dụng riêng "
                "cho toàn bộ giai đoạn này."
            ),
            examples=[1],
        ),
    ] = None
    note: str | None = Field(
        default=None,
        title="Ghi chú",
        description="Thông tin giải thích thêm về giai đoạn đóng BHXH.",
    )

    @model_validator(mode="after")
    def validate_period(self) -> "ContributionPeriod":
        if self.from_month > self.to_month:
            raise ValueError("Từ tháng phải nhỏ hơn hoặc bằng đến tháng.")
        return self


class AdjustmentInput(BaseModel):
    model_config = ConfigDict(title="Dữ liệu điều chỉnh")

    coefficient_year: int = Field(
        default=2026,
        ge=2025,
        le=2100,
        title="Năm áp dụng hệ số",
        description=(
            "Năm của bộ hệ số điều chỉnh tiền lương và thu nhập đóng BHXH. "
            "Ứng dụng tích hợp sẵn bộ hệ số năm 2026."
        ),
        examples=[2026],
    )
    salary_coefficients: dict[int, Annotated[Decimal, Field(gt=0)]] | None = Field(
        default=None,
        title="Bảng hệ số tiền lương",
        description=(
            "Bảng hệ số điều chỉnh tiền lương theo năm đóng. Chỉ cần cung cấp khi "
            "tính cho năm chưa được tích hợp sẵn."
        ),
    )
    voluntary_income_coefficients: dict[
        int, Annotated[Decimal, Field(gt=0)]
    ] | None = Field(
        default=None,
        title="Bảng hệ số thu nhập BHXH tự nguyện",
        description=(
            "Bảng hệ số điều chỉnh thu nhập đóng BHXH tự nguyện theo năm đóng."
        ),
    )


class PensionRequest(BaseModel):
    model_config = ConfigDict(
        title="Yêu cầu tính lương hưu",
        json_schema_extra={
            "examples": [
                {
                    "person": {
                        "date_of_birth": "1969-09-01",
                        "sex": "female",
                    },
                    "pension_start_month": "2026-10",
                    "retirement_case": "normal",
                    "contributions": [
                        {
                            "from_month": "1996-10",
                            "to_month": "2026-09",
                            "monthly_basis_vnd": 10800000,
                            "contribution_type": "compulsory_employer",
                        }
                    ],
                    "adjustment": {"coefficient_year": 2026},
                }
            ]
        },
    )

    person: Person = Field(
        title="Thông tin người lao động",
        description="Ngày sinh và giới tính của người cần dự tính lương hưu.",
    )
    pension_start_month: str = Field(
        pattern=YEAR_MONTH_PATTERN,
        title="Tháng bắt đầu hưởng lương hưu",
        description=(
            "Tháng đầu tiên dự kiến nhận lương hưu, định dạng YYYY-MM. "
            "Ứng dụng hiểu ngày nghỉ việc là ngày cuối cùng của tháng trước đó."
        ),
        examples=["2026-10"],
    )
    retirement_case: RetirementCase = Field(
        default=RetirementCase.normal,
        title="Trường hợp nghỉ hưu",
        description=(
            "normal = nghỉ đúng điều kiện thông thường; "
            "hazardous_or_special_region = nghề nặng nhọc hoặc vùng đặc biệt; "
            "underground_coal = khai thác than hầm lò; "
            "reduced_capacity = suy giảm khả năng lao động; "
            "occupational_hiv và armed_forces được chuyển sang kiểm tra thủ công."
        ),
    )
    contributions: list[ContributionPeriod] = Field(
        min_length=1,
        title="Quá trình tham gia BHXH",
        description=(
            "Danh sách các giai đoạn đóng BHXH. Các giai đoạn không được trùng tháng."
        ),
    )

    impairment_percent: Annotated[
        Decimal | None,
        Field(
            ge=0,
            le=100,
            title="Tỷ lệ suy giảm khả năng lao động",
            description="Chỉ nhập đối với trường hợp nghỉ hưu do suy giảm khả năng lao động.",
            examples=[81],
        ),
    ] = None
    hazardous_or_special_region_months: int = Field(
        default=0,
        ge=0,
        title="Số tháng nghề nặng nhọc hoặc vùng đặc biệt",
        description="Tổng số tháng thuộc nhóm nghề, công việc hoặc địa bàn đủ điều kiện.",
    )
    especially_hazardous_months: int = Field(
        default=0,
        ge=0,
        title="Số tháng nghề đặc biệt nặng nhọc",
        description="Tổng số tháng làm nghề hoặc công việc đặc biệt nặng nhọc, độc hại, nguy hiểm.",
    )
    underground_coal_months: int = Field(
        default=0,
        ge=0,
        title="Số tháng khai thác than hầm lò",
        description="Tổng số tháng làm công việc khai thác than trong hầm lò.",
    )

    state_salary_values_are_converted: bool = Field(
        default=False,
        title="Tiền lương Nhà nước đã được quy đổi",
        description=(
            "Đặt true chỉ khi các mức lương khu vực Nhà nước trước năm 2016 đã được "
            "quy đổi đúng theo quy định về mức tham chiếu hoặc thang bảng lương."
        ),
    )
    reference_level_vnd: Annotated[
        Decimal | None,
        Field(
            gt=0,
            title="Mức tham chiếu",
            description=(
                "Mức tham chiếu bằng đồng dùng để kiểm tra mức lương hưu tối thiểu "
                "trong trường hợp chuyển tiếp, nếu có."
            ),
        ),
    ] = None
    adjustment: AdjustmentInput = Field(
        default_factory=AdjustmentInput,
        title="Thông tin hệ số điều chỉnh",
    )

    @field_validator("contributions")
    @classmethod
    def reject_empty_notes_only(
        cls, value: list[ContributionPeriod]
    ) -> list[ContributionPeriod]:
        if not value:
            raise ValueError("Phải có ít nhất một giai đoạn đóng BHXH.")
        return value


class EligibilityResult(BaseModel):
    model_config = ConfigDict(title="Kết quả điều kiện hưởng")

    eligible: bool = Field(title="Đủ điều kiện hưởng")
    case: RetirementCase = Field(title="Trường hợp nghỉ hưu đã xét")
    reasons: list[str] = Field(
        default_factory=list,
        title="Lý do",
        description="Các lý do chưa đủ điều kiện hoặc cần kiểm tra thêm.",
    )
    missing_fields: list[str] = Field(
        default_factory=list,
        title="Dữ liệu còn thiếu",
    )


class ContributionSummary(BaseModel):
    model_config = ConfigDict(title="Tổng hợp thời gian đóng")

    total_months: int = Field(title="Tổng số tháng đóng")
    compulsory_months: int = Field(title="Số tháng BHXH bắt buộc")
    voluntary_months: int = Field(title="Số tháng BHXH tự nguyện")
    exact_duration: str = Field(title="Thời gian đóng thực tế")
    rounded_years_for_rate: Decimal = Field(
        title="Số năm sau khi làm tròn để tính tỷ lệ"
    )


class AverageBasisResult(BaseModel):
    model_config = ConfigDict(title="Kết quả mức bình quân")

    amount_vnd: Decimal | None = Field(title="Mức bình quân, đồng")
    method: str | None = Field(title="Phương pháp tính mức bình quân")
    coefficient_year: int = Field(title="Năm của bộ hệ số điều chỉnh")
    state_average_months_used: int = Field(
        default=0,
        title="Số tháng khu vực Nhà nước dùng để bình quân",
    )


class PensionRateResult(BaseModel):
    model_config = ConfigDict(title="Kết quả tỷ lệ hưởng")

    base_rate_percent: Decimal | None = Field(title="Tỷ lệ hưởng cơ bản, %")
    early_retirement_reduction_percent: Decimal = Field(
        title="Tỷ lệ giảm do nghỉ hưu trước tuổi, %"
    )
    final_rate_percent: Decimal | None = Field(title="Tỷ lệ hưởng cuối cùng, %")


class PensionResponse(BaseModel):
    model_config = ConfigDict(title="Kết quả tính lương hưu")

    calculation_id: str = Field(title="Mã lần tính")
    status: str = Field(
        title="Trạng thái kết quả",
        description=(
            "eligible = đủ điều kiện; not_eligible = chưa đủ điều kiện; "
            "needs_more_data = cần bổ sung dữ liệu; manual_review = cần kiểm tra thủ công."
        ),
    )
    legal_rule_version: str = Field(title="Phiên bản bộ quy tắc pháp lý")
    requested_pension_start_month: str = Field(title="Tháng hưởng đã yêu cầu")

    retirement_end_date: date = Field(title="Ngày kết thúc làm việc hoặc nghỉ hưu")
    normal_retirement_age: str = Field(title="Tuổi nghỉ hưu thông thường")
    normal_retirement_threshold_date: date = Field(
        title="Ngày đạt tuổi nghỉ hưu thông thường"
    )
    earliest_normal_pension_start_month: str = Field(
        title="Tháng sớm nhất hưởng theo diện thông thường"
    )

    contribution_summary: ContributionSummary = Field(
        title="Tổng hợp quá trình đóng"
    )
    eligibility: EligibilityResult = Field(title="Kết quả xét điều kiện")
    average_basis: AverageBasisResult = Field(title="Mức bình quân làm căn cứ")
    pension_rate: PensionRateResult = Field(title="Tỷ lệ hưởng lương hưu")

    estimated_monthly_pension_vnd: Decimal | None = Field(
        title="Lương hưu dự kiến hằng tháng, đồng"
    )
    one_time_retirement_allowance_vnd: Decimal | None = Field(
        title="Trợ cấp một lần khi nghỉ hưu, đồng"
    )
    minimum_floor_applied: bool = Field(
        default=False,
        title="Đã áp dụng mức lương hưu tối thiểu",
    )

    assumptions: list[str] = Field(default_factory=list, title="Các giả định")
    warnings: list[str] = Field(default_factory=list, title="Các cảnh báo")
    audit_steps: list[str] = Field(
        default_factory=list,
        title="Các bước kiểm tra phép tính",
    )
