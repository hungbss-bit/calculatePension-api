from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

YEAR_MONTH_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"


class Sex(str, Enum):
    male = "male"
    female = "female"


class ContributionType(str, Enum):
    compulsory_state = "compulsory_state"
    compulsory_employer = "compulsory_employer"
    voluntary = "voluntary"


class ParticipationStatus(str, Enum):
    contributed = "contributed"
    credited_duration_only = "credited_duration_only"
    not_participating = "not_participating"


class DurationOnlyReason(str, Enum):
    pre1995_no_salary_or_living_allowance = "pre1995_no_salary_or_living_allowance"


class RetirementCase(str, Enum):
    normal = "normal"
    hazardous_or_special_region = "hazardous_or_special_region"
    underground_coal = "underground_coal"
    reduced_capacity = "reduced_capacity"
    occupational_hiv = "occupational_hiv"
    armed_forces = "armed_forces"


class SourceDocumentType(str, Enum):
    direct_input = "direct_input"
    mau_07_sbh = "mau_07_sbh"
    vssid = "vssid"
    other = "other"


class BasisInputType(str, Enum):
    total_vnd = "total_vnd"
    converted_state_vnd = "converted_state_vnd"
    component_sum_vnd = "component_sum_vnd"
    mau_07_sbh_components = "mau_07_sbh_components"
    salary_coefficient = "salary_coefficient"
    unknown = "unknown"


class SbhComponentUnit(str, Enum):
    coefficient = "coefficient"
    vnd = "vnd"


class ConfirmationStatus(str, Enum):
    confirmed = "confirmed"
    unconfirmed = "unconfirmed"
    unclear = "unclear"


class PensionRegime(str, Enum):
    compulsory = "compulsory"
    voluntary = "voluntary"
    mixed_compulsory_policy = "mixed_compulsory_policy"
    mixed_voluntary_policy = "mixed_voluntary_policy"
    undetermined = "undetermined"


class Person(BaseModel):
    model_config = ConfigDict(title="Thông tin cá nhân")
    date_of_birth: date = Field(title="Ngày sinh", examples=["1969-09-01"])
    sex: Sex = Field(title="Giới tính", description="male = Nam; female = Nữ")


class BasisComponents(BaseModel):
    model_config = ConfigDict(title="Các thành phần làm căn cứ đóng")
    main_salary_vnd: Annotated[Decimal | None, Field(ge=0)] = None
    salary_allowance_vnd: Annotated[Decimal | None, Field(ge=0)] = None
    other_supplement_vnd: Annotated[Decimal | None, Field(ge=0)] = None

    def total(self) -> Decimal:
        return sum(
            (v or Decimal("0"))
            for v in (
                self.main_salary_vnd,
                self.salary_allowance_vnd,
                self.other_supplement_vnd,
            )
        )


class Mau07SbhBasisComponents(BaseModel):
    model_config = ConfigDict(title="Các thành phần Mẫu 07/SBH")
    unit: SbhComponentUnit = Field(
        title="Đơn vị thành phần",
        description="coefficient = hệ số; vnd = đồng/tháng. Tất cả thành phần phải cùng đơn vị.",
    )
    base_value: Annotated[Decimal, Field(ge=0)] = Field(
        title="Mức đóng gốc",
        description="Giá trị tại cột Mức đóng của Mẫu 07/SBH.",
    )
    position_allowance: Annotated[Decimal, Field(ge=0)] = Field(default=Decimal("0"), title="Phụ cấp chức vụ")
    seniority_beyond_frame_allowance: Annotated[Decimal, Field(ge=0)] = Field(default=Decimal("0"), title="Phụ cấp thâm niên vượt khung")
    professional_seniority_allowance: Annotated[Decimal, Field(ge=0)] = Field(default=Decimal("0"), title="Phụ cấp thâm niên nghề")
    regional_allowance: Annotated[Decimal, Field(ge=0)] = Field(default=Decimal("0"), title="Phụ cấp khu vực")
    other_allowance: Annotated[Decimal, Field(ge=0)] = Field(default=Decimal("0"), title="Phụ cấp khác")
    reelection_allowance: Annotated[Decimal, Field(ge=0)] = Field(default=Decimal("0"), title="Phụ cấp tái cử")
    base_salary_vnd_override: Annotated[Decimal | None, Field(gt=0)] = Field(
        default=None,
        title="Mức lương cơ sở dùng quy đổi",
        description=(
            "Tùy chọn. Dùng khi thành phần là hệ số và cần chỉ định lương cơ sở cho toàn bộ giai đoạn. "
            "Nếu bỏ trống với lương Nhà nước, API dùng lương cơ sở theo từng tháng; trước năm 2016 dùng mức tại tháng hưởng."
        ),
    )

    def allowance_total(self) -> Decimal:
        return sum((
            self.position_allowance,
            self.seniority_beyond_frame_allowance,
            self.professional_seniority_allowance,
            self.regional_allowance,
            self.other_allowance,
            self.reelection_allowance,
        ), Decimal("0"))

    def total_component_value(self) -> Decimal:
        return self.base_value + self.allowance_total()


class ContributionPeriod(BaseModel):
    model_config = ConfigDict(title="Giai đoạn trong quá trình BHXH")
    from_month: str = Field(pattern=YEAR_MONTH_PATTERN, title="Từ tháng")
    to_month: str = Field(pattern=YEAR_MONTH_PATTERN, title="Đến tháng")
    participation_status: ParticipationStatus = Field(
        default=ParticipationStatus.contributed,
        title="Trạng thái tham gia",
        description=(
            "contributed = có đóng và dùng tính thời gian, mức bình quân; "
            "credited_duration_only = chỉ cộng thời gian, không dùng mức lương; "
            "not_participating = không tham gia, loại khỏi toàn bộ phép tính."
        ),
    )
    duration_only_reason: DurationOnlyReason | None = Field(
        default=None,
        title="Căn cứ chỉ cộng thời gian",
        description=(
            "Bắt buộc khi participation_status = credited_duration_only. "
            "Hiện API chỉ hỗ trợ thời gian trước 01/01/1995 được công nhận nhưng "
            "không hưởng tiền lương hoặc sinh hoạt phí."
        ),
    )
    monthly_basis_vnd: Annotated[Decimal | None, Field(gt=0)] = Field(
        default=None,
        title="Tổng mức làm căn cứ đóng (đồng/tháng)",
        description="Chỉ bắt buộc với trạng thái contributed; phải là VND, không phải hệ số thô.",
    )
    contribution_type: ContributionType | None = Field(
        default=None,
        title="Loại quá trình đóng",
        description="Không bắt buộc khi participation_status = not_participating.",
    )
    basis_input_type: BasisInputType = Field(
        default=BasisInputType.total_vnd,
        title="Kiểu dữ liệu mức đóng",
    )
    basis_components: BasisComponents | None = None
    sbh_components: Mau07SbhBasisComponents | None = Field(
        default=None,
        title="Các thành phần cột Mẫu 07/SBH",
        description=(
            "Tổng hệ số/mức đóng = Mức đóng + Chức vụ + TN VK + TN Nghề + "
            "Khu vực + Khác + Tái cử. Chỉ dùng khi basis_input_type=mau_07_sbh_components."
        ),
    )
    source_value: Decimal | None = Field(
        default=None,
        title="Giá trị đọc từ hồ sơ",
        description="Dùng kiểm toán Mẫu 07/SBH; không tự dùng để tính nếu chưa chuẩn hóa.",
    )
    source_unit: str | None = None
    source_row_id: str | None = None
    source_text: str | None = None
    confirmation_status: ConfirmationStatus = ConfirmationStatus.confirmed
    coefficient_override: Annotated[Decimal | None, Field(gt=0)] = None
    note: str | None = None

    qualifying_hazardous: bool = False
    qualifying_especially_hazardous: bool = False
    qualifying_underground_coal: bool = False

    @model_validator(mode="after")
    def validate_period(self) -> "ContributionPeriod":
        if self.from_month > self.to_month:
            raise ValueError("Từ tháng phải nhỏ hơn hoặc bằng đến tháng.")

        if self.participation_status == ParticipationStatus.not_participating:
            return self

        if self.contribution_type is None:
            raise ValueError(
                "Giai đoạn có tính thời gian BHXH phải có contribution_type."
            )

        if self.participation_status == ParticipationStatus.credited_duration_only:
            if self.to_month >= "1995-01":
                raise ValueError(
                    "credited_duration_only chỉ dùng cho thời gian được công nhận trước 01/01/1995; "
                    "hãy tách riêng giai đoạn từ 1995 trở đi."
                )
            if (
                self.duration_only_reason
                != DurationOnlyReason.pre1995_no_salary_or_living_allowance
            ):
                raise ValueError(
                    "credited_duration_only phải có duration_only_reason="
                    "pre1995_no_salary_or_living_allowance."
                )
            return self

        if self.basis_input_type == BasisInputType.component_sum_vnd:
            if self.monthly_basis_vnd is None and (
                self.basis_components is None or self.basis_components.total() <= 0
            ):
                raise ValueError(
                    "Dữ liệu component_sum_vnd phải có monthly_basis_vnd hoặc các thành phần tiền lương."
                )

        if self.basis_input_type == BasisInputType.mau_07_sbh_components:
            if self.sbh_components is None:
                raise ValueError(
                    "mau_07_sbh_components phải có sbh_components."
                )
            if self.monthly_basis_vnd is not None or self.basis_components is not None:
                raise ValueError(
                    "Không gửi monthly_basis_vnd/basis_components cùng sbh_components để tránh cộng hai lần."
                )
            if self.sbh_components.total_component_value() <= 0:
                raise ValueError("Tổng Mức đóng và các phụ cấp phải lớn hơn 0.")
            if (
                self.sbh_components.unit == SbhComponentUnit.coefficient
                and self.contribution_type != ContributionType.compulsory_state
                and self.sbh_components.base_salary_vnd_override is None
            ):
                raise ValueError(
                    "Thành phần hệ số ngoài chế độ lương Nhà nước phải có base_salary_vnd_override."
                )
        return self


class AdjustmentInput(BaseModel):
    model_config = ConfigDict(title="Bộ hệ số điều chỉnh")
    coefficient_year: int = Field(default=2026, ge=2025, le=2100)
    salary_coefficients: dict[int, Annotated[Decimal, Field(gt=0)]] | None = None
    voluntary_income_coefficients: dict[int, Annotated[Decimal, Field(gt=0)]] | None = None


class PensionRequest(BaseModel):
    model_config = ConfigDict(
        title="Yêu cầu tính lương hưu",
        json_schema_extra={
            "examples": [{
                "person": {"date_of_birth": "1969-09-01", "sex": "female"},
                "pension_start_month": "2026-10",
                "retirement_case": "normal",
                "source_document_type": "mau_07_sbh",
                "history_confirmed": True,
                "gaps_confirmed_as_non_contribution": True,
                "contributions": [{
                    "from_month": "1996-10",
                    "to_month": "2026-09",
                    "participation_status": "contributed",
                    "monthly_basis_vnd": 10800000,
                    "contribution_type": "compulsory_employer",
                    "basis_input_type": "total_vnd",
                    "confirmation_status": "confirmed"
                }],
                "adjustment": {"coefficient_year": 2026}
            }]
        },
    )

    person: Person
    pension_start_month: str = Field(pattern=YEAR_MONTH_PATTERN)
    retirement_case: RetirementCase = RetirementCase.normal
    contributions: list[ContributionPeriod] = Field(min_length=1)

    source_document_type: SourceDocumentType = SourceDocumentType.direct_input
    history_confirmed: bool = True
    gaps_confirmed_as_non_contribution: bool = False

    impairment_percent: Annotated[Decimal | None, Field(ge=0, le=100)] = None
    impairment_assessment_month: str | None = Field(default=None, pattern=YEAR_MONTH_PATTERN)
    eligibility_achieved_month: str | None = Field(default=None, pattern=YEAR_MONTH_PATTERN)

    hazardous_or_special_region_months: int = Field(default=0, ge=0)
    especially_hazardous_months: int = Field(default=0, ge=0)
    underground_coal_months: int = Field(default=0, ge=0)

    state_salary_values_are_converted: bool = False
    transitional_minimum_floor_eligible: bool = False
    reference_level_vnd: Annotated[Decimal | None, Field(gt=0)] = None
    adjustment: AdjustmentInput = Field(default_factory=AdjustmentInput)


class HistoryIssue(BaseModel):
    code: str
    severity: str
    message_vi: str
    source_row_id: str | None = None
    from_month: str | None = None
    to_month: str | None = None


class GapPeriod(BaseModel):
    from_month: str
    to_month: str
    months: int


class HistoryValidationResult(BaseModel):
    valid_for_calculation: bool
    total_unique_months: int = Field(description="Tổng tháng được tính là thời gian tham gia BHXH.")
    average_basis_months: int = Field(default=0, description="Số tháng có mức đóng được dùng tính bình quân.")
    credited_duration_only_months: int = Field(default=0, description="Số tháng chỉ cộng thời gian, không dùng tính bình quân.")
    excluded_non_participation_months: int = Field(default=0, description="Số tháng ghi rõ không tham gia BHXH và đã loại khỏi phép tính.")
    gaps: list[GapPeriod] = Field(default_factory=list)
    overlaps: list[str] = Field(default_factory=list)
    issues: list[HistoryIssue] = Field(default_factory=list)


class EligibilityResult(BaseModel):
    eligible: bool
    case: RetirementCase
    regime: PensionRegime = PensionRegime.undetermined
    reasons: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    required_total_months: int | None = None
    required_compulsory_months: int | None = None
    months_short: int = 0
    can_pay_missing_months_once: bool = False


class ContributionSummary(BaseModel):
    total_months: int
    compulsory_months: int
    voluntary_months: int
    average_basis_months: int = 0
    credited_duration_only_months: int = 0
    excluded_non_participation_months: int = 0
    exact_duration: str
    rounded_years_for_rate: Decimal


class YearlyAdjustmentBreakdown(BaseModel):
    year: int
    contribution_type: ContributionType
    months: int
    original_total_vnd: Decimal
    adjusted_total_vnd: Decimal
    coefficient: Decimal | None


class BasisComponentAudit(BaseModel):
    source_row_id: str | None = None
    from_month: str
    to_month: str
    component_unit: SbhComponentUnit
    base_value: Decimal
    position_allowance: Decimal
    seniority_beyond_frame_allowance: Decimal
    professional_seniority_allowance: Decimal
    regional_allowance: Decimal
    other_allowance: Decimal
    reelection_allowance: Decimal
    allowance_total: Decimal
    total_component_value: Decimal
    base_salary_values_used_vnd: list[Decimal] = Field(default_factory=list)
    monthly_basis_min_vnd: Decimal | None = None
    monthly_basis_max_vnd: Decimal | None = None
    formula_vi: str


class AverageBasisResult(BaseModel):
    amount_vnd: Decimal | None = Field(description="Trường tương thích ngược; bằng average_monthly_basis_vnd.")
    average_monthly_basis_vnd: Decimal | None = Field(description="Mức bình quân tiền lương/thu nhập làm căn cứ đóng BHXH trước khi nhân tỷ lệ hưởng.")
    basis_months_used: int = Field(default=0, description="Số tháng dữ liệu tiền lương/thu nhập trực tiếp dùng trong phép bình quân.")
    method: str | None
    coefficient_year: int
    state_average_months_used: int = 0
    yearly_breakdown: list[YearlyAdjustmentBreakdown] = Field(default_factory=list)


class PensionRateResult(BaseModel):
    rounded_years: Decimal | None = None
    base_rate_percent: Decimal | None
    early_retirement_months: int = 0
    early_retirement_reduction_percent: Decimal
    final_rate_percent: Decimal | None
    reduction_reference_age: str | None = None


class LegalReference(BaseModel):
    document: str
    provisions: str
    purpose: str


class PensionResponse(BaseModel):
    calculation_id: str
    status: str
    error_code: str | None = None
    legal_rule_version: str
    requested_pension_start_month: str
    retirement_end_date: date
    normal_retirement_age_in_retirement_year: str
    normal_retirement_threshold_date: date
    earliest_normal_pension_start_month: str

    history_validation: HistoryValidationResult
    contribution_summary: ContributionSummary
    eligibility: EligibilityResult
    average_basis: AverageBasisResult
    basis_component_audit: list[BasisComponentAudit] = Field(default_factory=list)
    pension_rate: PensionRateResult

    estimated_monthly_pension_vnd: Decimal | None
    pension_calculation_formula: str | None = None
    one_time_retirement_allowance_vnd: Decimal | None
    minimum_floor_applied: bool = False

    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    audit_steps: list[str] = Field(default_factory=list)
    legal_references: list[LegalReference] = Field(default_factory=list)


class CapabilitiesResponse(BaseModel):
    service: str
    version: str
    legal_rule_version: str
    built_in_coefficient_years: list[int]
    supported_retirement_cases: list[RetirementCase]
    manual_review_cases: list[RetirementCase]
    supported_source_documents: list[SourceDocumentType]
    notes: list[str]
