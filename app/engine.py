from __future__ import annotations

import calendar
import re
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

from dateutil.relativedelta import relativedelta

from .models import (
    AverageExclusionReason,
    AverageInclusion,
    BasisInputType,
    BenefitCalculationScope,
    CalculationIdentity,
    CalculationMeta,
    CalculationTrace,
    Contribution,
    ContributionType,
    DurationOnlyReason,
    NormalizedSummary,
    OneTimeRetirementAllowance,
    ParticipationStatus,
    PensionCalculationRequest,
    PensionCalculationResponse,
    RetirementCase,
    RetirementPolicy,
    SbhComponentUnit,
    Sex,
    ValidationResponse,
)
from .rules import (
    LEGAL_RULE_VERSION,
    SUPPORTED_BENEFIT_YEAR,
    adjustment_tables,
    base_salary_for_month,
    coefficient_for_year,
    earliest_threshold_date,
    state_average_months,
)

MONEY = Decimal("1")
PRE1995_CUTOFF = date(1995, 1, 1)
ENGINE_VERSION = "1.0.10-rc"
POLICY_VERSION = "VN-BHXH-PENSION-V1.0-2026"
VIETNAM_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
DISCLAIMER = (
    "Đây là kết quả ước tính, không thay thế quyết định giải quyết chế độ "
    "của cơ quan BHXH."
)


class BusinessError(Exception):
    def __init__(self, error_code: str, detail: str, fields: list[str] | None = None):
        super().__init__(detail)
        self.error_code = error_code
        self.detail = detail
        self.fields = fields or []


@dataclass(frozen=True)
class Issue:
    code: str
    message: str
    fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class ValidationDiagnostics:
    response: ValidationResponse
    issues: tuple[Issue, ...]


@dataclass(frozen=True)
class MonthlyRecord:
    month: date
    contribution_type: ContributionType
    participation_status: ParticipationStatus
    duration_only_reason: DurationOnlyReason | None
    basis_input_type: BasisInputType | None
    basis_vnd: Decimal | None
    component_unit: SbhComponentUnit | None
    average_included: bool
    after_retirement_age_period: bool


@dataclass(frozen=True)
class Eligibility:
    retirement_threshold: date
    normal_threshold: date
    early_retirement_months: int
    early_retirement_reduction: Decimal
    warnings: tuple[str, ...] = ()


def parse_year_month(value: str) -> date:
    year, month = map(int, value.split("-"))
    return date(year, month, 1)


def format_year_month(value: date) -> str:
    return f"{value.year:04d}-{value.month:02d}"


def next_month(value: date) -> date:
    return value + relativedelta(months=1)


def previous_month_end(value: date) -> date:
    previous = value - relativedelta(months=1)
    return date(previous.year, previous.month, calendar.monthrange(previous.year, previous.month)[1])


def month_range(start: date, end: date) -> Iterable[date]:
    current = start
    while current <= end:
        yield current
        current = next_month(current)


def months_difference(later: date, earlier: date) -> int:
    return max(0, (later.year - earlier.year) * 12 + later.month - earlier.month)


def _append(issues: list[Issue], code: str, message: str, *fields: str) -> None:
    issues.append(Issue(code=code, message=message, fields=tuple(fields)))


def resolve_identity(request: PensionCalculationRequest) -> CalculationIdentity:
    raw = request.identity.so_bhxh if request.identity else None
    value = raw.strip() if isinstance(raw, str) else None
    # Số sổ bị che, để trắng hoặc không cung cấp: tạo mã tạm 12 chữ số
    # theo thời điểm tiếp nhận đến phút; calculation_id vẫn là UUID để phân biệt
    # nhiều lần gọi trong cùng một phút.
    if not value or not re.fullmatch(r"\d+", value):
        temporary_id = datetime.now(VIETNAM_TZ).strftime("%Y%m%d%H%M")
        return CalculationIdentity(type="TEMPORARY", temporary_id=temporary_id)
    return CalculationIdentity(type="REAL", so_bhxh=value)


def validate_request(request: PensionCalculationRequest) -> ValidationDiagnostics:
    issues: list[Issue] = []
    warnings: list[str] = []
    pension_start = parse_year_month(request.pension_start_month)

    if pension_start.year != SUPPORTED_BENEFIT_YEAR:
        _append(
            issues,
            "COEFFICIENT_YEAR_UNAVAILABLE",
            (
                f"Gói dữ liệu tích hợp chỉ có hệ số điều chỉnh cho năm hưởng "
                f"{SUPPORTED_BENEFIT_YEAR}; không được dùng cho năm "
                f"{pension_start.year}."
            ),
            "pension_start_month",
        )

    # V1.0.9 bổ sung đúng hai nhánh nghỉ hưu trước tuổi đã được thống nhất:
    # (1) reduced_capacity: suy giảm khả năng lao động;
    # (2) normal + decree_154_streamlining: tinh giản biên chế theo NĐ 154/2025/NĐ-CP.
    # Các nhánh nghề nặng nhọc/đặc thù và hầm lò vẫn ngoài phạm vi V1.x.
    supported_case = request.retirement_case in {
        RetirementCase.normal,
        RetirementCase.reduced_capacity,
    }
    supported_policy = request.retirement_policy in {
        RetirementPolicy.none,
        RetirementPolicy.decree_154_streamlining,
    }
    valid_pair = (
        request.retirement_case == RetirementCase.normal
        and request.retirement_policy in {
            RetirementPolicy.none,
            RetirementPolicy.decree_154_streamlining,
        }
    ) or (
        request.retirement_case == RetirementCase.reduced_capacity
        and request.retirement_policy == RetirementPolicy.none
    )
    if not supported_case:
        _append(
            issues,
            "OUT_OF_SCOPE_RETIREMENT_CASE",
            (
                "V1.x chỉ hỗ trợ nghỉ hưu bình thường hoặc suy giảm khả năng lao động; "
                "nghề nặng nhọc/đặc thù và hầm lò chưa được tự động hóa."
            ),
            "retirement_case",
        )
    if not supported_policy:
        _append(
            issues,
            "OUT_OF_SCOPE_RETIREMENT_POLICY",
            "Chính sách nghỉ hưu đặc thù này chưa được tự động hóa.",
            "retirement_policy",
        )
    if supported_case and supported_policy and not valid_pair:
        _append(
            issues,
            "RETIREMENT_CASE_POLICY_CONFLICT",
            (
                "Cặp retirement_case/retirement_policy không hợp lệ. Dùng normal+none, "
                "normal+decree_154_streamlining hoặc reduced_capacity+none."
            ),
            "retirement_case",
            "retirement_policy",
        )

    if request.retirement_case == RetirementCase.reduced_capacity:
        if request.impairment_percent is None:
            _append(
                issues,
                "IMPAIRMENT_PERCENT_REQUIRED",
                "Trường hợp reduced_capacity phải có impairment_percent.",
                "impairment_percent",
            )
        elif request.impairment_percent < Decimal("61"):
            _append(
                issues,
                "IMPAIRMENT_PERCENT_TOO_LOW",
                "Tỷ lệ suy giảm khả năng lao động phải từ 61% trong phạm vi tự động hóa này.",
                "impairment_percent",
            )
    elif request.impairment_percent is not None:
        warnings.append(
            "impairment_percent được cung cấp nhưng không dùng vì retirement_case không phải reduced_capacity."
        )

    month_owner: dict[date, int] = {}
    counted_months: set[date] = set()
    excluded_months: set[date] = set()
    covered_months: set[date] = set()
    pre1995_excluded_months = 0
    maternity_months = 0
    eligible_month = (
        parse_year_month(request.retirement_age_eligible_month)
        if request.retirement_age_eligible_month
        else None
    )
    pending_age_issues: list[Issue] = []

    for index, period in enumerate(request.contributions):
        prefix = f"contributions[{index}]"
        start = parse_year_month(period.from_month)
        end = parse_year_month(period.to_month)

        if start > end:
            _append(
                issues,
                "REVERSED_PERIOD",
                f"Dòng {index + 1}: from_month phải nhỏ hơn hoặc bằng to_month.",
                f"{prefix}.from_month",
                f"{prefix}.to_month",
            )
            continue

        if start < PRE1995_CUTOFF <= end:
            _append(
                issues,
                "PRE1995_PERIOD_MUST_BE_SPLIT",
                (
                    f"Dòng {index + 1} đi qua mốc 01/1995; phải tách thành giai đoạn "
                    "trước 1995 và từ 1995 trở đi."
                ),
                f"{prefix}.from_month",
                f"{prefix}.to_month",
            )

        if end >= pension_start:
            _append(
                issues,
                "CONTRIBUTION_AFTER_PENSION_START",
                (
                    f"Dòng {index + 1} có tháng từ thời điểm bắt đầu hưởng lương hưu "
                    "trở đi."
                ),
                f"{prefix}.to_month",
                "pension_start_month",
            )

        is_pre1995 = end < PRE1995_CUTOFF
        has_monthly = period.monthly_basis_vnd is not None
        has_components = period.sbh_components is not None

        if period.participation_status == ParticipationStatus.not_participating:
            if has_monthly or has_components or period.basis_input_type is not None:
                warnings.append(
                    f"Dòng {index + 1} là not_participating; mọi mức đóng/thành phần được bỏ qua."
                )
        elif period.participation_status == ParticipationStatus.credited_duration_only:
            reason = period.duration_only_reason

            if reason in {
                DurationOnlyReason.pre1995_no_salary_or_living_allowance,
                DurationOnlyReason.pre1995_duration_excluded_from_average_basis,
            }:
                if not is_pre1995:
                    _append(
                        issues,
                        "CREDITED_DURATION_ONLY_AFTER_1994",
                        (
                            "Căn cứ duration-only PRE-1995 chỉ hợp lệ cho thời gian "
                            "kết thúc trước 01/1995."
                        ),
                        f"{prefix}.participation_status",
                        f"{prefix}.duration_only_reason",
                        f"{prefix}.to_month",
                    )
                if period.contribution_type is None:
                    _append(
                        issues,
                        "CONTRIBUTION_TYPE_REQUIRED",
                        "Giai đoạn được cộng thời gian phải có contribution_type.",
                        f"{prefix}.contribution_type",
                    )
                if has_monthly or has_components or period.basis_input_type is not None:
                    _append(
                        issues,
                        "DURATION_ONLY_BASIS_NOT_ALLOWED",
                        "credited_duration_only PRE-1995 không được mang mức đóng vào bình quân.",
                        f"{prefix}.monthly_basis_vnd",
                        f"{prefix}.sbh_components",
                        f"{prefix}.basis_input_type",
                    )
                if period.average_inclusion == AverageInclusion.included:
                    _append(
                        issues,
                        "DURATION_ONLY_AVERAGE_INCLUDED",
                        "credited_duration_only PRE-1995 không được đưa trực tiếp vào tính mức bình quân.",
                        f"{prefix}.average_inclusion",
                    )

            elif reason == DurationOnlyReason.maternity_leave:
                # Nghỉ hưởng chế độ thai sản được tính là thời gian tham gia BHXH.
                # Mẫu 07/SBH thường không ghi mức đóng/hệ số cho các tháng này;
                # engine sẽ kế thừa mức đóng của tháng liền kề ngay trước kỳ nghỉ.
                if period.contribution_type is None:
                    _append(
                        issues,
                        "CONTRIBUTION_TYPE_REQUIRED",
                        "Giai đoạn nghỉ thai sản phải có contribution_type để giữ đúng nhóm tiền lương.",
                        f"{prefix}.contribution_type",
                    )
                if has_monthly or has_components or period.basis_input_type is not None:
                    _append(
                        issues,
                        "MATERNITY_BASIS_MUST_BE_INHERITED",
                        (
                            "Giai đoạn nghỉ hưởng chế độ thai sản không nhập mức đóng/hệ số trực tiếp; "
                            "API tự kế thừa mức đóng của tháng liền kề trước khi nghỉ."
                        ),
                        f"{prefix}.monthly_basis_vnd",
                        f"{prefix}.sbh_components",
                        f"{prefix}.basis_input_type",
                    )
                if (
                    not is_pre1995
                    and period.average_inclusion == AverageInclusion.excluded
                ):
                    _append(
                        issues,
                        "MATERNITY_AVERAGE_EXCLUSION_NOT_ALLOWED",
                        (
                            "Thời gian nghỉ hưởng chế độ thai sản từ 01/1995 trở đi "
                            "phải được đưa vào mức bình quân bằng mức đóng kế thừa."
                        ),
                        f"{prefix}.average_inclusion",
                    )
                maternity_months += sum(1 for _ in month_range(start, end))

            else:
                _append(
                    issues,
                    "DURATION_ONLY_REASON_REQUIRED",
                    (
                        "credited_duration_only phải có duration_only_reason hợp lệ: "
                        "pre1995_duration_excluded_from_average_basis, "
                        "pre1995_no_salary_or_living_allowance (legacy) hoặc maternity_leave."
                    ),
                    f"{prefix}.duration_only_reason",
                )
                if period.contribution_type is None:
                    _append(
                        issues,
                        "CONTRIBUTION_TYPE_REQUIRED",
                        "Giai đoạn được cộng thời gian phải có contribution_type.",
                        f"{prefix}.contribution_type",
                    )
        else:
            if period.contribution_type is None:
                _append(
                    issues,
                    "CONTRIBUTION_TYPE_REQUIRED",
                    "Giai đoạn contributed phải có contribution_type.",
                    f"{prefix}.contribution_type",
                )
            elif (
                period.contribution_type == ContributionType.voluntary
                and start < date(2008, 1, 1)
            ):
                _append(
                    issues,
                    "VOLUNTARY_PERIOD_BEFORE_2008",
                    (
                        "Giai đoạn BHXH tự nguyện trước 01/2008 không có hệ số "
                        "thu nhập trong bộ dữ liệu 2026."
                    ),
                    f"{prefix}.contribution_type",
                    f"{prefix}.from_month",
                )

            if is_pre1995:
                if period.average_inclusion != AverageInclusion.excluded:
                    _append(
                        issues,
                        "PRE1995_AVERAGE_EXCLUSION_REQUIRED",
                        (
                            "Giai đoạn contributed trước 01/1995 phải có "
                            "average_inclusion=excluded."
                        ),
                        f"{prefix}.average_inclusion",
                    )
                if (
                    period.average_exclusion_reason
                    != AverageExclusionReason.pre1995_policy
                ):
                    _append(
                        issues,
                        "PRE1995_EXCLUSION_REASON_REQUIRED",
                        (
                            "Giai đoạn contributed trước 01/1995 phải có "
                            "average_exclusion_reason=pre1995_policy."
                        ),
                        f"{prefix}.average_exclusion_reason",
                    )
                if has_monthly or has_components:
                    warnings.append(
                        f"Dòng {index + 1} trước 01/1995: mức đóng/phụ cấp được giữ để kiểm toán nhưng bị loại khỏi mức bình quân."
                    )
            else:
                if period.average_inclusion == AverageInclusion.excluded:
                    _append(
                        issues,
                        "AVERAGE_EXCLUSION_NOT_ALLOWED",
                        "average_inclusion=excluded chỉ hỗ trợ cho chính sách trước 01/1995.",
                        f"{prefix}.average_inclusion",
                    )

                if has_monthly == has_components:
                    _append(
                        issues,
                        "EXACTLY_ONE_BASIS_REQUIRED",
                        (
                            "Mỗi giai đoạn contributed từ 01/1995 phải có đúng một "
                            "phương thức mức đóng: monthly_basis_vnd hoặc sbh_components."
                        ),
                        f"{prefix}.monthly_basis_vnd",
                        f"{prefix}.sbh_components",
                    )
                if period.basis_input_type is None:
                    _append(
                        issues,
                        "BASIS_INPUT_TYPE_REQUIRED",
                        "Giai đoạn contributed từ 01/1995 phải có basis_input_type.",
                        f"{prefix}.basis_input_type",
                    )
                elif (
                    period.basis_input_type == BasisInputType.monthly_basis_vnd
                    and not has_monthly
                ):
                    _append(
                        issues,
                        "MONTHLY_BASIS_MISSING",
                        "basis_input_type=monthly_basis_vnd phải có monthly_basis_vnd.",
                        f"{prefix}.monthly_basis_vnd",
                    )
                elif (
                    period.basis_input_type == BasisInputType.mau_07_sbh_components
                    and not has_components
                ):
                    _append(
                        issues,
                        "SBH_COMPONENTS_MISSING",
                        "basis_input_type=mau_07_sbh_components phải có sbh_components.",
                        f"{prefix}.sbh_components",
                    )

                if has_monthly and (period.monthly_basis_vnd or Decimal("0")) <= 0:
                    _append(
                        issues,
                        "MONTHLY_BASIS_MUST_BE_POSITIVE",
                        "monthly_basis_vnd phải lớn hơn 0.",
                        f"{prefix}.monthly_basis_vnd",
                    )
                if has_components:
                    assert period.sbh_components is not None
                    if period.sbh_components.total() <= 0:
                        _append(
                            issues,
                            "SBH_COMPONENT_TOTAL_MUST_BE_POSITIVE",
                            "Tổng Mức đóng và phụ cấp Mẫu 07/SBH phải lớn hơn 0.",
                            f"{prefix}.sbh_components",
                        )
                    if (
                        period.sbh_components.unit == SbhComponentUnit.coefficient
                        and period.contribution_type
                        != ContributionType.compulsory_state
                    ):
                        _append(
                            issues,
                            "COEFFICIENT_ONLY_FOR_STATE_SALARY",
                            (
                                "sbh_components.unit=coefficient chỉ được tự động quy đổi "
                                "cho contribution_type=compulsory_state."
                            ),
                            f"{prefix}.sbh_components.unit",
                            f"{prefix}.contribution_type",
                        )

        if eligible_month is None and period.after_retirement_age_period:
            pending_age_issues.append(Issue(
                code="RETIREMENT_AGE_MONTH_REQUIRED_FOR_MARKER",
                message=(
                    "Có after_retirement_age_period=true nhưng thiếu "
                    "retirement_age_eligible_month."
                ),
                fields=(
                    "retirement_age_eligible_month",
                    f"{prefix}.after_retirement_age_period",
                ),
            ))

        if eligible_month is not None and period.participation_status != ParticipationStatus.not_participating:
            if start <= eligible_month < end:
                pending_age_issues.append(Issue(
                    code="RETIREMENT_AGE_PERIOD_MUST_BE_SPLIT",
                    message=(
                        f"Dòng {index + 1} đi qua tháng đủ tuổi nghỉ hưu; phải tách "
                        "giai đoạn trước/sau để xác định trợ cấp một lần."
                    ),
                    fields=(
                        f"{prefix}.from_month",
                        f"{prefix}.to_month",
                        "retirement_age_eligible_month",
                    ),
                ))
            if period.after_retirement_age_period and start <= eligible_month:
                pending_age_issues.append(Issue(
                    code="AFTER_RETIREMENT_AGE_MARKER_CONFLICT",
                    message=(
                        f"Dòng {index + 1} được đánh dấu sau tuổi nghỉ hưu nhưng bắt đầu "
                        "không muộn hơn retirement_age_eligible_month."
                    ),
                    fields=(
                        f"{prefix}.after_retirement_age_period",
                        "retirement_age_eligible_month",
                    ),
                ))

        for month in month_range(start, end):
            covered_months.add(month)
            if month in month_owner:
                owner = month_owner[month]
                _append(
                    issues,
                    "OVERLAPPING_MONTH",
                    (
                        f"Tháng {format_year_month(month)} bị trùng giữa dòng "
                        f"{owner + 1} và dòng {index + 1}."
                    ),
                    f"contributions[{owner}]",
                    prefix,
                )
            else:
                month_owner[month] = index

            if period.participation_status == ParticipationStatus.not_participating:
                excluded_months.add(month)
            else:
                counted_months.add(month)
                if is_pre1995:
                    pre1995_excluded_months += 1

    if covered_months:
        current = min(covered_months)
        last = max(covered_months)
        gap_start: date | None = None
        while current <= last:
            if current not in covered_months and gap_start is None:
                gap_start = current
            if current in covered_months and gap_start is not None:
                gap_end = current - relativedelta(months=1)
                _append(
                    issues,
                    "UNDECLARED_GAP",
                    (
                        f"Khoảng trống {format_year_month(gap_start)}–"
                        f"{format_year_month(gap_end)} chưa có dòng "
                        "not_participating."
                    ),
                    "contributions",
                )
                gap_start = None
            current = next_month(current)
        if gap_start is not None:
            _append(
                issues,
                "UNDECLARED_GAP",
                (
                    f"Khoảng trống {format_year_month(gap_start)}–"
                    f"{format_year_month(last)} chưa có dòng not_participating."
                ),
                "contributions",
            )

    threshold_months = 360 if request.person.sex == Sex.female else 420
    if (
        request.benefit_calculation_scope
        == BenefitCalculationScope.pension_and_one_time_allowance
        and len(counted_months) > threshold_months
    ):
        issues.extend(pending_age_issues)

    if (
        request.benefit_calculation_scope
        == BenefitCalculationScope.pension_and_one_time_allowance
        and len(counted_months) > threshold_months
        and eligible_month is not None
    ):
        for index, period in enumerate(request.contributions):
            if (
                period.participation_status != ParticipationStatus.not_participating
                and parse_year_month(period.from_month) > eligible_month
                and not period.after_retirement_age_period
            ):
                _append(
                    issues,
                    "POST_RETIREMENT_PERIOD_NOT_MARKED",
                    (
                        f"Dòng {index + 1} phát sinh sau tháng đủ tuổi nghỉ hưu nhưng "
                        "after_retirement_age_period chưa được đặt true."
                    ),
                    f"contributions[{index}].after_retirement_age_period",
                )

    # Kiểm tra khả năng kế thừa mức đóng cho các tháng nghỉ thai sản.
    # Chỉ chạy khi các kiểm tra cấu trúc cơ bản đã hợp lệ để tránh che lấp lỗi gốc.
    if maternity_months and not issues:
        try:
            expand_records(request)
        except BusinessError as exc:
            _append(issues, exc.error_code, exc.detail, *exc.fields)

    if maternity_months and not issues:
        warnings.append(
            f"Đã tính {maternity_months} tháng nghỉ hưởng chế độ thai sản vào thời gian BHXH "
            "và kế thừa mức đóng của tháng liền kề trước kỳ nghỉ."
        )

    if excluded_months:
        warnings.append(
            f"Đã loại {len(excluded_months)} tháng not_participating/BHTN khỏi thời gian và mức bình quân."
        )
    if pre1995_excluded_months:
        warnings.append(
            f"Đã tính {pre1995_excluded_months} tháng tham gia BHXH trước 01/1995 vào thời gian nhưng loại toàn bộ mức/hệ số nguồn khỏi mức bình quân."
        )

    validation = not issues
    if issues:
        warnings.extend(f"[{issue.code}] {issue.message}" for issue in issues)

    return ValidationDiagnostics(
        response=ValidationResponse(
            validation=validation,
            normalized_summary=NormalizedSummary(
                total_contribution_months=len(counted_months),
                excluded_bhtn_months=len(excluded_months),
                contribution_count=len(request.contributions),
            ),
            warnings=warnings,
        ),
        issues=tuple(issues),
    )


def _basis_for_month(
    request: PensionCalculationRequest,
    period: Contribution,
    month: date,
) -> tuple[Decimal | None, SbhComponentUnit | None]:
    if period.participation_status != ParticipationStatus.contributed:
        return None, None
    if (
        month < PRE1995_CUTOFF
        and period.average_inclusion == AverageInclusion.excluded
    ):
        return None, None

    if period.basis_input_type == BasisInputType.monthly_basis_vnd:
        return period.monthly_basis_vnd, None

    if (
        period.basis_input_type == BasisInputType.mau_07_sbh_components
        and period.sbh_components is not None
    ):
        total = period.sbh_components.total()
        if period.sbh_components.unit == SbhComponentUnit.vnd:
            return total, SbhComponentUnit.vnd

        # Mẫu 07/SBH ghi lương Nhà nước bằng HỆ SỐ. Khi tính mức bình quân,
        # hệ số phải nhân với mức lương cơ sở/mức tham chiếu tại thời điểm
        # hưởng lương hưu, không phải mức lương cơ sở của từng năm đóng.
        pension_month = parse_year_month(request.pension_start_month)
        reference = base_salary_for_month(pension_month)
        return total * reference, SbhComponentUnit.coefficient

    return None, None

def expand_records(request: PensionCalculationRequest) -> list[MonthlyRecord]:
    records: list[MonthlyRecord] = []
    seen: set[date] = set()
    eligible_month = (
        parse_year_month(request.retirement_age_eligible_month)
        if request.retirement_age_eligible_month
        else None
    )
    for period in request.contributions:
        if period.participation_status == ParticipationStatus.not_participating:
            continue
        assert period.contribution_type is not None
        start = parse_year_month(period.from_month)
        end = parse_year_month(period.to_month)
        for month in month_range(start, end):
            if month in seen:
                continue
            seen.add(month)
            basis, unit = _basis_for_month(request, period, month)
            average_included = (
                period.participation_status == ParticipationStatus.contributed
                and not (
                    month < PRE1995_CUTOFF
                    and period.average_inclusion == AverageInclusion.excluded
                )
            )
            after_age = period.after_retirement_age_period or (
                eligible_month is not None and month > eligible_month
            )
            records.append(
                MonthlyRecord(
                    month=month,
                    contribution_type=period.contribution_type,
                    participation_status=period.participation_status,
                    duration_only_reason=period.duration_only_reason,
                    basis_input_type=period.basis_input_type,
                    basis_vnd=basis,
                    component_unit=unit,
                    average_included=average_included,
                    after_retirement_age_period=after_age,
                )
            )

    # Giải quyết mức đóng của thời gian nghỉ hưởng chế độ thai sản theo đúng
    # mức đóng của tháng liền kề ngay trước kỳ nghỉ. Các tháng thai sản liên tiếp
    # tiếp tục kế thừa cùng mức đã được giải quyết từ tháng trước.
    ordered = sorted(records, key=lambda row: row.month)
    resolved: list[MonthlyRecord] = []
    for row in ordered:
        if row.duration_only_reason == DurationOnlyReason.maternity_leave:
            if not resolved or next_month(resolved[-1].month) != row.month:
                raise BusinessError(
                    "MATERNITY_PREVIOUS_BASIS_MISSING",
                    (
                        f"Không xác định được tháng liền kề trước tháng thai sản "
                        f"{format_year_month(row.month)} để kế thừa mức đóng."
                    ),
                    ["contributions"],
                )

            previous = resolved[-1]
            if previous.basis_vnd is None:
                raise BusinessError(
                    "MATERNITY_PREVIOUS_BASIS_MISSING",
                    (
                        f"Tháng liền kề trước tháng thai sản {format_year_month(row.month)} "
                        "không có mức đóng/hệ số hợp lệ để kế thừa."
                    ),
                    ["contributions"],
                )

            if previous.contribution_type != row.contribution_type:
                raise BusinessError(
                    "MATERNITY_CONTRIBUTION_TYPE_MISMATCH",
                    (
                        f"Nhóm đóng BHXH của tháng thai sản {format_year_month(row.month)} "
                        "không khớp với tháng liền kề trước kỳ nghỉ; không thể tự kế thừa mức đóng."
                    ),
                    ["contributions"],
                )

            row = replace(
                row,
                basis_input_type=previous.basis_input_type,
                basis_vnd=previous.basis_vnd,
                component_unit=previous.component_unit,
                average_included=row.month >= PRE1995_CUTOFF,
            )

        resolved.append(row)

    return resolved


def _normal_threshold(request: PensionCalculationRequest) -> date:
    return earliest_threshold_date(
        request.person.date_of_birth,
        request.person.sex.value,
        0,
    )


def determine_eligibility(
    request: PensionCalculationRequest,
    records: list[MonthlyRecord],
) -> Eligibility:
    """Xác định điều kiện hưởng theo 3 nhánh: bình thường, suy giảm KNLĐ, NĐ154."""
    pension_start = parse_year_month(request.pension_start_month)
    retirement_end = previous_month_end(pension_start)
    normal = _normal_threshold(request)
    compulsory_months = sum(
        1
        for row in records
        if row.contribution_type
        in {ContributionType.compulsory_state, ContributionType.compulsory_employer}
    )

    # Nghỉ hưu bình thường.
    if request.retirement_case == RetirementCase.normal and request.retirement_policy == RetirementPolicy.none:
        if len(records) < 180:
            raise BusinessError(
                "INSUFFICIENT_CONTRIBUTION",
                f"Cần ít nhất 180 tháng đóng BHXH; hiện có {len(records)} tháng.",
                ["contributions"],
            )
        if retirement_end < normal:
            raise BusinessError(
                "RETIREMENT_AGE_NOT_REACHED",
                (
                    f"Ngày nghỉ {retirement_end.isoformat()} chưa đạt tuổi nghỉ hưu "
                    f"bình thường tại {normal.isoformat()}."
                ),
                ["person.date_of_birth", "pension_start_month"],
            )
        return Eligibility(normal, normal, 0, Decimal("0"))

    # Case 1: suy giảm khả năng lao động. V1.x chỉ tự động hóa ngưỡng từ 61%
    # và thời gian nghỉ trước tuổi không quá 5 năm. Theo Điều 66 Luật BHXH 2024:
    # mỗi năm giảm 2%; dưới 6 tháng không giảm; từ đủ 6 đến dưới 12 tháng giảm 1%.
    if request.retirement_case == RetirementCase.reduced_capacity:
        if compulsory_months < 240:
            raise BusinessError(
                "INSUFFICIENT_COMPULSORY_CONTRIBUTION_REDUCED_CAPACITY",
                (
                    f"Trường hợp suy giảm khả năng lao động cần ít nhất 240 tháng "
                    f"BHXH bắt buộc; hồ sơ hiện có {compulsory_months} tháng."
                ),
                ["contributions"],
            )
        if retirement_end >= normal:
            return Eligibility(normal, normal, 0, Decimal("0"), (
                "Hồ sơ đã đủ tuổi nghỉ hưu bình thường; không áp dụng giảm tỷ lệ do nghỉ trước tuổi.",
            ))
        early_months = months_difference(normal, pension_start)
        if early_months > 60:
            raise BusinessError(
                "EARLY_RETIREMENT_OVER_5_YEARS",
                (
                    f"Thời điểm hưởng lương hưu sớm khoảng {early_months} tháng, "
                    "vượt quá phạm vi V1.x là không quá 5 năm."
                ),
                ["pension_start_month", "person.date_of_birth"],
            )
        full_years, remainder = divmod(early_months, 12)
        reduction = Decimal(full_years * 2)
        if remainder >= 6:
            reduction += Decimal("1")
        return Eligibility(
            retirement_threshold=normal,
            normal_threshold=normal,
            early_retirement_months=early_months,
            early_retirement_reduction=reduction,
            warnings=(
                f"Case 1 – suy giảm khả năng lao động: nghỉ trước khoảng {early_months} tháng; "
                f"giảm {reduction}% theo quy tắc hiện hành.",
            ),
        )

    # Case 2: tinh giản biên chế theo NĐ 154/2025/NĐ-CP. Trong V1.x chỉ tự động
    # hóa điều kiện lao động bình thường; không suy đoán các nhánh nghề nặng nhọc,
    # vùng đặc biệt khó khăn hoặc lực lượng đặc thù. Chính sách này không trừ tỷ lệ
    # lương hưu do nghỉ trước tuổi.
    if request.retirement_case == RetirementCase.normal and request.retirement_policy == RetirementPolicy.decree_154_streamlining:
        if pension_start.year < 2025 or pension_start > date(2030, 12, 1):
            raise BusinessError(
                "DECREE_154_OUTSIDE_POLICY_PERIOD",
                "NĐ 154/2025/NĐ-CP được áp dụng đến hết ngày 31/12/2030 trong phạm vi tích hợp này.",
                ["pension_start_month"],
            )
        if compulsory_months < 180:
            raise BusinessError(
                "INSUFFICIENT_COMPULSORY_CONTRIBUTION_DECREE_154",
                (
                    f"Trường hợp tinh giản biên chế cần đủ thời gian đóng BHXH bắt buộc "
                    f"để hưởng lương hưu; hồ sơ hiện có {compulsory_months} tháng."
                ),
                ["contributions"],
            )
        if retirement_end >= normal:
            return Eligibility(normal, normal, 0, Decimal("0"), (
                "Case 2 – NĐ 154/2025/NĐ-CP: không giảm tỷ lệ do nghỉ trước tuổi.",
            ))
        early_months = months_difference(normal, pension_start)
        if early_months > 60:
            raise BusinessError(
                "DECREE_154_EARLY_OVER_5_YEARS",
                (
                    f"Thời điểm hưởng lương hưu sớm khoảng {early_months} tháng; "
                    "V1.x chỉ tự động hóa nhánh nghỉ trước tuổi không quá 5 năm "
                    "trong điều kiện lao động bình thường."
                ),
                ["pension_start_month", "person.date_of_birth"],
            )
        return Eligibility(
            retirement_threshold=normal,
            normal_threshold=normal,
            early_retirement_months=early_months,
            early_retirement_reduction=Decimal("0"),
            warnings=(
                f"Case 2 – tinh giản biên chế theo NĐ 154/2025/NĐ-CP: nghỉ trước khoảng {early_months} tháng; "
                "không trừ tỷ lệ lương hưu do nghỉ trước tuổi.",
            ),
        )

    raise BusinessError(
        "RETIREMENT_CASE_POLICY_CONFLICT",
        "Cặp retirement_case/retirement_policy không được hỗ trợ.",
        ["retirement_case", "retirement_policy"],
    )


def _adjusted_value(
    row: MonthlyRecord,
    salary_table: dict[int, Decimal],
    voluntary_table: dict[int, Decimal],
) -> Decimal:
    if row.basis_vnd is None:
        raise BusinessError(
            "AVERAGE_BASIS_MISSING",
            f"Không có mức đóng hợp lệ tại tháng {format_year_month(row.month)}.",
            ["contributions"],
        )

    if row.contribution_type == ContributionType.voluntary:
        try:
            coefficient = coefficient_for_year(voluntary_table, row.month.year)
        except ValueError as exc:
            raise BusinessError(
                "VOLUNTARY_COEFFICIENT_MISSING",
                str(exc),
                ["pension_start_month", "contributions"],
            ) from exc
        return row.basis_vnd * coefficient

    if row.contribution_type == ContributionType.compulsory_employer:
        try:
            coefficient = coefficient_for_year(salary_table, row.month.year)
        except ValueError as exc:
            raise BusinessError(
                "SALARY_COEFFICIENT_MISSING",
                str(exc),
                ["pension_start_month", "contributions"],
            ) from exc
        return row.basis_vnd * coefficient

    # Lương Nhà nước ghi theo HỆ SỐ đã được _basis_for_month() quy đổi
    # thành VND theo mức lương cơ sở/mức tham chiếu tại tháng hưởng.
    # Không nhân thêm hệ số điều chỉnh theo năm đóng để tránh điều chỉnh 2 lần.
    if (
        row.contribution_type == ContributionType.compulsory_state
        and row.component_unit == SbhComponentUnit.coefficient
    ):
        return row.basis_vnd

    # Nếu hồ sơ Nhà nước cung cấp trực tiếp bằng VND, đây là giá trị tiền
    # theo lịch sử đóng và cần áp dụng hệ số điều chỉnh tiền lương theo năm
    # đóng, giống dữ liệu tiền lương của người hưởng lương do Nhà nước quy định.
    if row.contribution_type == ContributionType.compulsory_state:
        if row.month.year < 2016:
            return row.basis_vnd
        try:
            coefficient = coefficient_for_year(salary_table, row.month.year)
        except ValueError as exc:
            raise BusinessError(
                "SALARY_COEFFICIENT_MISSING",
                str(exc),
                ["pension_start_month", "contributions"],
            ) from exc
        return row.basis_vnd * coefficient

    return row.basis_vnd

def calculate_average_salary(
    request: PensionCalculationRequest,
    records: list[MonthlyRecord],
) -> tuple[Decimal, list[str], int, str]:
    salary_table, voluntary_table = adjustment_tables()
    basis_rows = [row for row in records if row.average_included]
    if not basis_rows:
        raise BusinessError(
            "NO_AVERAGE_BASIS",
            "Không có tháng mức đóng hợp lệ dùng tính mức bình quân.",
            ["contributions"],
        )

    state_counted = [
        row for row in records if row.contribution_type == ContributionType.compulsory_state
    ]
    state_basis = [
        row for row in basis_rows if row.contribution_type == ContributionType.compulsory_state
    ]
    employer = [
        row for row in basis_rows if row.contribution_type == ContributionType.compulsory_employer
    ]
    voluntary = [
        row for row in basis_rows if row.contribution_type == ContributionType.voluntary
    ]

    selected_state: list[MonthlyRecord] = []
    state_window: int | None = None
    if state_basis:
        first_state = format_year_month(state_counted[0].month)
        state_window = state_average_months(first_state)
        selected_state = state_basis if state_window is None else state_basis[-state_window:]

    state_adjusted = [_adjusted_value(row, salary_table, voluntary_table) for row in selected_state]
    employer_adjusted = [_adjusted_value(row, salary_table, voluntary_table) for row in employer]
    voluntary_adjusted = [_adjusted_value(row, salary_table, voluntary_table) for row in voluntary]

    state_average = (
        sum(state_adjusted, Decimal("0")) / Decimal(len(state_adjusted))
        if state_adjusted
        else Decimal("0")
    )

    # HỒ SƠ HỖN HỢP NHÀ NƯỚC + DOANH NGHIỆP (Ground Truth O_Quy2):
    # phần Nhà nước được xác định mức bình quân trên cửa sổ riêng (ví dụ 60 tháng),
    # sau đó mức bình quân này được nhân với TOÀN BỘ số tháng công tác thuộc nhóm
    # Nhà nước, bao gồm cả thời gian trước 01/1995 đã được tính vào thời gian BHXH
    # nhưng bị loại khỏi cửa sổ mức bình quân. Sau đó mới cộng với tổng tiền đã
    # điều chỉnh của nhóm doanh nghiệp và chia cho tổng số tháng của hai nhóm.
    #
    # Với hồ sơ O_Quy1/O_Quy2: 277 tháng Nhà nước (26 tháng trước 1995) +
    # 126 tháng doanh nghiệp = 403 tháng; không được dùng 251 tháng có tiền
    # trong nhóm Nhà nước làm trọng số.
    #
    # GIỮ NGUYÊN LOGIC B_HUONG1: khi hồ sơ chỉ có tiền lương Nhà nước,
    # state_weight_months vẫn bằng số tháng có căn cứ tính bình quân (state_basis).
    if state_basis and employer:
        state_weight_months = len(state_counted)
    else:
        state_weight_months = len(state_basis)

    mandatory_months = state_weight_months + len(employer)
    total_basis_months = mandatory_months + len(voluntary)

    mandatory_equivalent = (
        state_average * Decimal(state_weight_months)
        + sum(employer_adjusted, Decimal("0"))
    )
    total_equivalent = mandatory_equivalent + sum(voluntary_adjusted, Decimal("0"))
    average = total_equivalent / Decimal(total_basis_months)

    if state_basis and employer:
        method = (
            "Bình quân chung hồ sơ hỗn hợp Nhà nước + doanh nghiệp; phần lương Nhà nước "
            "lấy bình quân theo cửa sổ quy định rồi nhân với toàn bộ số tháng thuộc nhóm "
            "Nhà nước (kể cả thời gian trước 01/1995 chỉ tính thời gian), sau đó kết hợp "
            "với tổng tiền lương doanh nghiệp đã điều chỉnh."
        )
    elif state_basis and voluntary:
        method = (
            "Bình quân chung quá trình hỗn hợp Nhà nước + BHXH tự nguyện; phần lương Nhà nước "
            "lấy bình quân theo cửa sổ quy định rồi kết hợp theo quy tắc tương ứng."
        )
    elif state_basis:
        method = "Bình quân thời kỳ cuối theo chế độ tiền lương Nhà nước."
    elif employer and voluntary:
        method = "Bình quân chung lương doanh nghiệp và thu nhập BHXH tự nguyện sau điều chỉnh."
    elif voluntary:
        method = "Bình quân toàn bộ thu nhập BHXH tự nguyện sau điều chỉnh."
    else:
        method = "Bình quân toàn bộ lương doanh nghiệp sau điều chỉnh."

    warnings = [
        f"Phương pháp mức bình quân: {method}",
        (
            f"Số tháng dữ liệu trực tiếp dùng trong phép bình quân: "
            f"{len(selected_state) + len(employer) + len(voluntary)}; "
            f"tổng số tháng dữ liệu của các nhóm tham gia được xử lý theo Rule: {total_basis_months}. "
            "Không diễn giải tổng số tháng dữ liệu này là mẫu số của phép bình quân nếu average_basis.basis_months_used có giá trị riêng."
        ),
    ]
    if state_window is not None and len(state_basis) < state_window:
        warnings.append(
            f"Quá trình lương Nhà nước có {len(state_basis)} tháng có mức đóng, ít hơn cửa sổ {state_window} tháng; API dùng toàn bộ tháng hiện có."
        )
    # Contract V2.0: basis_months_used là số tháng thực tế trực tiếp làm mẫu số
    # của phép bình quân. Với hồ sơ Nhà nước thuần túy, đây là cửa sổ cuối
    # (ví dụ 60 tháng), không phải tổng số tháng tham gia sau khi loại PRE-1995.
    # Với hồ sơ hỗn hợp, giữ tổng số tháng quy đổi trọng số theo Rule hỗn hợp.
    if state_basis and not employer and not voluntary:
        basis_months_used = len(selected_state)
    else:
        basis_months_used = total_basis_months
    return average, warnings, basis_months_used, method


def calculate_rate(
    sex: Sex,
    total_months: int,
    early_reduction: Decimal,
) -> tuple[Decimal, Decimal, Decimal]:
    if total_months < 180:
        raise BusinessError(
            "INSUFFICIENT_CONTRIBUTION",
            f"Cần ít nhất 180 tháng; hiện có {total_months} tháng.",
            ["contributions"],
        )
    full_years, remainder = divmod(total_months, 12)
    # Tháng lẻ phải quy đổi theo đúng mức tăng của từng nhóm tỷ lệ:
    # - 01–06 tháng = 0,5 năm
    # - 07–11 tháng = 1 năm
    # Vì vậy phần tăng thêm khác nhau giữa nữ/nam 15–<20 năm (1%/năm)
    # và các trường hợp tăng 2%/năm.
    remainder_years = (
        Decimal("0") if remainder == 0
        else Decimal("0.5") if remainder <= 6
        else Decimal("1")
    )

    if sex == Sex.female:
        remainder_rate = remainder_years * Decimal("2")
        before = Decimal("45") + Decimal(max(0, full_years - 15) * 2) + remainder_rate
    elif full_years < 20:
        remainder_rate = remainder_years * Decimal("1")
        before = Decimal("40") + Decimal(max(0, full_years - 15)) + remainder_rate
    else:
        remainder_rate = remainder_years * Decimal("2")
        before = Decimal("45") + Decimal(max(0, full_years - 20) * 2) + remainder_rate

    before = min(Decimal("75"), before)
    after = max(Decimal("0"), before - early_reduction)
    return before, remainder_rate, after


def calculate_one_time_allowance(
    request: PensionCalculationRequest,
    records: list[MonthlyRecord],
    average: Decimal,
    eligibility: Eligibility,
) -> OneTimeRetirementAllowance | None:
    if request.benefit_calculation_scope == BenefitCalculationScope.pension_only:
        return None

    threshold_months = 360 if request.person.sex == Sex.female else 420
    total_months = len(records)
    total_excess = max(0, total_months - threshold_months)
    warnings: list[str] = []

    derived_eligible_month = date(
        eligibility.retirement_threshold.year,
        eligibility.retirement_threshold.month,
        1,
    )
    eligible_month = (
        parse_year_month(request.retirement_age_eligible_month)
        if request.retirement_age_eligible_month
        else derived_eligible_month
    )
    if request.retirement_age_eligible_month is None:
        warnings.append(
            "retirement_age_eligible_month không được cung cấp; API suy ra từ ngày sinh, giới tính và retirement_case."
        )
    elif total_excess > 0 and eligible_month != derived_eligible_month:
        raise BusinessError(
            "RETIREMENT_AGE_MONTH_MISMATCH",
            (
                f"retirement_age_eligible_month={format_year_month(eligible_month)} "
                f"không khớp tháng API tra theo lộ trình là "
                f"{format_year_month(derived_eligible_month)}."
            ),
            ["retirement_age_eligible_month", "person.date_of_birth", "retirement_case"],
        )

    if total_excess == 0:
        return OneTimeRetirementAllowance(
            eligible=False,
            threshold_months=threshold_months,
            total_excess_months=0,
            excess_before_retirement_age_months=0,
            excess_after_retirement_age_months=0,
            standard_allowance_amount=0.0,
            post_retirement_allowance_amount=0.0,
            total_allowance_amount=0.0,
            average_basis=float(average.quantize(MONEY, rounding=ROUND_HALF_UP)),
            warnings=warnings,
        )

    months_to_age = sum(1 for row in records if row.month <= eligible_month)
    excess_before = max(0, months_to_age - threshold_months)
    excess_before = min(excess_before, total_excess)
    excess_after = total_excess - excess_before

    def allowance_years(months: int) -> Decimal:
        # Quy đổi thời gian vượt theo năm để tính trợ cấp:
        # 01–06 tháng = 0,5 năm; 07–11 tháng = 1 năm.
        full_years, remainder = divmod(months, 12)
        if remainder == 0:
            return Decimal(full_years)
        if remainder <= 6:
            return Decimal(full_years) + Decimal("0.5")
        return Decimal(full_years + 1)

    excess_before_years = allowance_years(excess_before)
    excess_after_years = allowance_years(excess_after)
    # Ground-truth hồ sơ NĐ154 tính trợ cấp trên mức bình quân đã làm tròn đến đồng.
    # Giữ nguyên engine hiện hành cho các case khác; chỉ áp dụng quy tắc này cho Case 2.
    allowance_average = (
        average.quantize(MONEY, rounding=ROUND_HALF_UP)
        if request.retirement_policy == RetirementPolicy.decree_154_streamlining
        else average
    )
    standard = allowance_average * excess_before_years * Decimal("0.5")
    post = allowance_average * excess_after_years * Decimal("2")
    total = standard + post
    standard_rounded = standard.quantize(MONEY, rounding=ROUND_HALF_UP)
    post_rounded = post.quantize(MONEY, rounding=ROUND_HALF_UP)
    total_rounded = total.quantize(MONEY, rounding=ROUND_HALF_UP)

    warnings.append(
        "Thời gian vượt được quy đổi theo năm khi tính trợ cấp: 01–06 tháng = 0,5 năm; 07–11 tháng = 1 năm."
    )
    return OneTimeRetirementAllowance(
        eligible=True,
        threshold_months=threshold_months,
        total_excess_months=total_excess,
        excess_before_retirement_age_months=excess_before,
        excess_after_retirement_age_months=excess_after,
        standard_allowance_amount=float(standard_rounded),
        post_retirement_allowance_amount=float(post_rounded),
        total_allowance_amount=float(total_rounded),
        average_basis=float(average.quantize(MONEY, rounding=ROUND_HALF_UP)),
        warnings=warnings,
    )


def calculate(request: PensionCalculationRequest) -> PensionCalculationResponse:
    diagnostics = validate_request(request)
    if not diagnostics.response.validation:
        fields = sorted(
            {
                field
                for issue in diagnostics.issues
                for field in issue.fields
            }
        )
        detail = "; ".join(issue.message for issue in diagnostics.issues[:6])
        if len(diagnostics.issues) > 6:
            detail += f"; và {len(diagnostics.issues) - 6} lỗi khác."
        raise BusinessError(
            "CONTRIBUTION_HISTORY_INVALID",
            detail,
            fields,
        )

    records = expand_records(request)
    eligibility = determine_eligibility(request, records)
    average, average_warnings, average_basis_months, average_basis_method = calculate_average_salary(request, records)
    before_rate, remainder_rate, after_rate = calculate_rate(
        request.person.sex,
        len(records),
        eligibility.early_retirement_reduction,
    )

    estimated = (
        average * after_rate / Decimal("100")
    ).quantize(MONEY, rounding=ROUND_HALF_UP)
    average_rounded = average.quantize(MONEY, rounding=ROUND_HALF_UP)
    allowance = calculate_one_time_allowance(
        request,
        records,
        average,
        eligibility,
    )

    allowance_formula = None
    if allowance is not None:
        allowance_formula = (
            "0.5 × mức bình quân × số tháng vượt trước/sát tuổi / 12 "
            "+ 2 × mức bình quân × số tháng vượt sau tuổi / 12"
        )

    warnings = list(diagnostics.response.warnings)
    warnings.extend(eligibility.warnings)
    warnings.extend(average_warnings)
    warnings.append(f"Phiên bản Engine: {ENGINE_VERSION}; Policy V1.0: {POLICY_VERSION}.")
    warnings.append(DISCLAIMER)

    identity = resolve_identity(request)
    return PensionCalculationResponse(
        calculation=CalculationMeta(
            calculation_id=str(uuid.uuid4()),
            engine_version=ENGINE_VERSION,
            policy_version=POLICY_VERSION,
            trace=CalculationTrace(
                duration_months=len(records),
                average_basis_months=average_basis_months,
                average_basis_method=average_basis_method,
                pension_rate_percent=float(after_rate),
                monthly_pension_formula=(
                    "mức bình quân tiền lương/thu nhập làm căn cứ tính hưởng × tỷ lệ %"
                ),
                one_time_allowance_formula=allowance_formula,
            ),
        ),
        identity=identity,
        total_months=len(records),
        average_salary=float(average_rounded),
        replacement_rate=float(after_rate),
        rate_before_early_reduction=float(before_rate),
        contribution_month_remainder_rate=float(remainder_rate),
        early_retirement_months=eligibility.early_retirement_months,
        early_retirement_reduction=float(eligibility.early_retirement_reduction),
        rate_after_reduction=float(after_rate),
        estimated_pension=float(estimated),
        warnings=warnings,
        one_time_retirement_allowance=allowance,
    )
