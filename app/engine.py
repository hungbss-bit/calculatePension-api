from __future__ import annotations

import calendar
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from dateutil.relativedelta import relativedelta

from .models import (
    AverageBasisResult,
    BasisInputType,
    CapabilitiesResponse,
    ConfirmationStatus,
    ContributionSummary,
    ContributionType,
    GapPeriod,
    HistoryIssue,
    HistoryValidationResult,
    LegalReference,
    PensionRateResult,
    PensionRegime,
    PensionRequest,
    PensionResponse,
    ParticipationStatus,
    RetirementCase,
    SourceDocumentType,
    YearlyAdjustmentBreakdown,
    EligibilityResult,
)
from .rules import (
    COEFFICIENTS_2026,
    VOLUNTARY_COEFFICIENTS_2026,
    LEGAL_REFERENCES,
    LEGAL_RULE_VERSION,
    age_after_offset,
    coefficient_for_year,
    earliest_threshold_for_schedule,
    state_average_years,
    threshold_date_for_retirement_year,
)

MONEY = Decimal("1")


@dataclass(frozen=True)
class MonthlyRecord:
    month: date
    basis: Decimal | None
    contribution_type: ContributionType
    participation_status: ParticipationStatus
    basis_input_type: BasisInputType
    coefficient_override: Decimal | None
    source_row_id: str | None
    qualifying_hazardous: bool
    qualifying_especially_hazardous: bool
    qualifying_underground_coal: bool

    @property
    def included_in_average(self) -> bool:
        return self.participation_status == ParticipationStatus.contributed



def parse_year_month(value: str) -> date:
    year, month = map(int, value.split("-"))
    return date(year, month, 1)


def format_year_month(value: date) -> str:
    return f"{value.year:04d}-{value.month:02d}"


def month_end(value: date) -> date:
    return date(value.year, value.month, calendar.monthrange(value.year, value.month)[1])


def next_month(value: date) -> date:
    return value + relativedelta(months=1)


def previous_month_end(first_of_month: date) -> date:
    return first_of_month - relativedelta(days=1)


def months_inclusive(start: date, end: date) -> int:
    return (end.year - start.year) * 12 + end.month - start.month + 1


def exact_duration(total_months: int) -> str:
    years, months = divmod(total_months, 12)
    return f"{years} năm {months} tháng"


def rounded_years_for_rate(total_months: int) -> Decimal:
    years, rem = divmod(total_months, 12)
    fraction = Decimal("0") if rem == 0 else Decimal("0.5") if rem <= 6 else Decimal("1")
    return Decimal(years) + fraction


def resolve_period_basis(period) -> Decimal | None:
    if period.participation_status != ParticipationStatus.contributed:
        return None
    if period.monthly_basis_vnd is not None:
        return period.monthly_basis_vnd
    if period.basis_input_type == BasisInputType.component_sum_vnd and period.basis_components:
        total = period.basis_components.total()
        return total if total > 0 else None
    return None


def validate_contribution_history(request: PensionRequest) -> HistoryValidationResult:
    issues: list[HistoryIssue] = []
    overlaps: list[str] = []
    counted_owner: dict[tuple[int, int], str] = {}
    non_participation_owner: dict[tuple[int, int], str] = {}
    covered_months: set[date] = set()
    counted_months: set[date] = set()
    average_basis_months: set[date] = set()
    credited_duration_only_months: set[date] = set()
    excluded_non_participation_months: set[date] = set()
    pension_start = parse_year_month(request.pension_start_month)

    if (
        request.source_document_type != SourceDocumentType.direct_input
        and not request.history_confirmed
    ):
        issues.append(HistoryIssue(
            code="HISTORY_NOT_CONFIRMED",
            severity="error",
            message_vi="Bảng dữ liệu trích xuất từ hồ sơ chưa được người dùng xác nhận.",
        ))

    for index, period in enumerate(request.contributions, start=1):
        row_id = period.source_row_id or str(index)
        start = parse_year_month(period.from_month)
        end = parse_year_month(period.to_month)

        # Dòng ghi rõ không tham gia BHXH được chấp nhận và loại khỏi phép tính;
        # không yêu cầu mức đóng hoặc xác nhận lại.
        if period.participation_status == ParticipationStatus.not_participating:
            current = start
            while current <= end:
                key = (current.year, current.month)
                covered_months.add(current)
                excluded_non_participation_months.add(current)
                non_participation_owner.setdefault(key, row_id)
                if key in counted_owner:
                    label = format_year_month(current)
                    issues.append(HistoryIssue(
                        code="CONFLICTING_PARTICIPATION_STATUS",
                        severity="error",
                        message_vi=(
                            f"Tháng {label} vừa được ghi là có thời gian BHXH ở dòng "
                            f"{counted_owner[key]}, vừa ghi không tham gia ở dòng {row_id}."
                        ),
                        source_row_id=row_id,
                        from_month=label,
                        to_month=label,
                    ))
                current = next_month(current)
            continue

        if period.confirmation_status != ConfirmationStatus.confirmed:
            issues.append(HistoryIssue(
                code="ROW_NOT_CONFIRMED",
                severity="error",
                message_vi=f"Dòng {row_id} chưa được xác nhận rõ ràng.",
                source_row_id=row_id,
                from_month=period.from_month,
                to_month=period.to_month,
            ))

        if period.contribution_type is None:
            issues.append(HistoryIssue(
                code="MISSING_CONTRIBUTION_TYPE",
                severity="error",
                message_vi=f"Dòng {row_id} chưa xác định loại quá trình đóng BHXH.",
                source_row_id=row_id,
                from_month=period.from_month,
                to_month=period.to_month,
            ))

        if period.participation_status == ParticipationStatus.contributed:
            if period.basis_input_type in {BasisInputType.salary_coefficient, BasisInputType.unknown}:
                issues.append(HistoryIssue(
                    code="BASIS_NOT_NORMALIZED_TO_VND",
                    severity="error",
                    message_vi=(
                        f"Dòng {row_id} chưa có mức căn cứ đóng bằng đồng Việt Nam; "
                        "không được gửi hệ số lương thô để tính."
                    ),
                    source_row_id=row_id,
                    from_month=period.from_month,
                    to_month=period.to_month,
                ))
            elif resolve_period_basis(period) is None:
                issues.append(HistoryIssue(
                    code="MISSING_MONTHLY_BASIS",
                    severity="error",
                    message_vi=f"Dòng {row_id} thiếu tổng mức làm căn cứ đóng BHXH.",
                    source_row_id=row_id,
                    from_month=period.from_month,
                    to_month=period.to_month,
                ))

        if start >= pension_start or end >= pension_start:
            issues.append(HistoryIssue(
                code="CONTRIBUTION_AFTER_PENSION_START",
                severity="error",
                message_vi=(
                    f"Dòng {row_id} có thời gian được tính BHXH từ tháng bắt đầu hưởng "
                    "lương hưu hoặc sau tháng đó."
                ),
                source_row_id=row_id,
                from_month=period.from_month,
                to_month=period.to_month,
            ))

        current = start
        while current <= end:
            key = (current.year, current.month)
            covered_months.add(current)
            if key in non_participation_owner:
                label = format_year_month(current)
                issues.append(HistoryIssue(
                    code="CONFLICTING_PARTICIPATION_STATUS",
                    severity="error",
                    message_vi=(
                        f"Tháng {label} vừa được ghi không tham gia ở dòng "
                        f"{non_participation_owner[key]}, vừa được tính BHXH ở dòng {row_id}."
                    ),
                    source_row_id=row_id,
                    from_month=label,
                    to_month=label,
                ))
            if key in counted_owner:
                label = format_year_month(current)
                overlaps.append(label)
                issues.append(HistoryIssue(
                    code="OVERLAPPING_MONTH",
                    severity="error",
                    message_vi=(
                        f"Tháng {label} bị trùng giữa dòng {counted_owner[key]} và dòng {row_id}."
                    ),
                    source_row_id=row_id,
                    from_month=label,
                    to_month=label,
                ))
            else:
                counted_owner[key] = row_id
                counted_months.add(current)
                if period.participation_status == ParticipationStatus.contributed:
                    average_basis_months.add(current)
                else:
                    credited_duration_only_months.add(current)
            current = next_month(current)

    gaps: list[GapPeriod] = []
    if covered_months:
        ordered = sorted(covered_months)
        cursor = ordered[0]
        last = ordered[-1]
        while cursor <= last:
            if cursor not in covered_months:
                gap_start = cursor
                while cursor <= last and cursor not in covered_months:
                    cursor = next_month(cursor)
                gap_end = cursor - relativedelta(months=1)
                gaps.append(GapPeriod(
                    from_month=format_year_month(gap_start),
                    to_month=format_year_month(gap_end),
                    months=months_inclusive(gap_start, gap_end),
                ))
            else:
                cursor = next_month(cursor)

    if gaps:
        severity = "warning" if request.gaps_confirmed_as_non_contribution else "error"
        code = "CONFIRMED_NON_CONTRIBUTION_GAPS" if severity == "warning" else "UNCONFIRMED_GAPS"
        gap_text = ", ".join(
            f"{g.from_month}–{g.to_month} ({g.months} tháng)" for g in gaps
        )
        issues.append(HistoryIssue(
            code=code,
            severity=severity,
            message_vi=(
                "Các khoảng trống đã được xác nhận là thời gian không đóng: "
                if severity == "warning"
                else "Cần xác nhận các khoảng trống không được ghi rõ trạng thái: "
            ) + gap_text,
        ))

    error_exists = any(i.severity == "error" for i in issues)
    return HistoryValidationResult(
        valid_for_calculation=not error_exists,
        total_unique_months=len(counted_months),
        average_basis_months=len(average_basis_months),
        credited_duration_only_months=len(credited_duration_only_months),
        excluded_non_participation_months=len(excluded_non_participation_months),
        gaps=gaps,
        overlaps=sorted(set(overlaps)),
        issues=issues,
    )


def expand_contributions(request: PensionRequest) -> list[MonthlyRecord]:
    rows: list[MonthlyRecord] = []
    seen: set[tuple[int, int]] = set()
    for period in request.contributions:
        if period.participation_status == ParticipationStatus.not_participating:
            continue
        if period.contribution_type is None:
            continue
        basis = resolve_period_basis(period)
        current = parse_year_month(period.from_month)
        end = parse_year_month(period.to_month)
        while current <= end:
            key = (current.year, current.month)
            if key not in seen:
                seen.add(key)
                rows.append(MonthlyRecord(
                    month=current,
                    basis=basis,
                    contribution_type=period.contribution_type,
                    participation_status=period.participation_status,
                    basis_input_type=period.basis_input_type,
                    coefficient_override=period.coefficient_override,
                    source_row_id=period.source_row_id,
                    qualifying_hazardous=period.qualifying_hazardous,
                    qualifying_especially_hazardous=period.qualifying_especially_hazardous,
                    qualifying_underground_coal=period.qualifying_underground_coal,
                ))
            current = next_month(current)
    return sorted(rows, key=lambda r: r.month)


def base_rate(sex: str, years: Decimal) -> Decimal:
    if years < Decimal("15"):
        raise ValueError("Chưa đủ 15 năm để tính tỷ lệ lương hưu.")
    if sex == "female":
        rate = Decimal("45") + (years - Decimal("15")) * Decimal("2")
    elif years < Decimal("20"):
        rate = Decimal("40") + (years - Decimal("15"))
    else:
        rate = Decimal("45") + (years - Decimal("20")) * Decimal("2")
    return min(Decimal("75"), rate)


def completed_age_months(dob: date, on_date: date) -> int:
    delta = relativedelta(on_date, dob)
    return max(0, delta.years * 12 + delta.months)


def early_reduction(
    dob: date,
    sex: str,
    retirement_end: date,
    reference_offset_years: int,
) -> tuple[int, Decimal, str]:
    age_years, age_months = age_after_offset(
        sex, retirement_end.year, reference_offset_years
    )
    reference_months = age_years * 12 + age_months
    actual_months = completed_age_months(dob, retirement_end)
    early_months = max(0, reference_months - actual_months)
    full_years, remainder = divmod(early_months, 12)
    reduction = Decimal(full_years * 2) + (Decimal("1") if remainder >= 6 else Decimal("0"))
    label = f"{age_years} tuổi" + (f" {age_months} tháng" if age_months else "")
    return early_months, reduction, label


def get_coefficient_tables(request: PensionRequest) -> tuple[dict[int, Decimal], dict[int, Decimal]]:
    benefit_year = int(request.pension_start_month[:4])
    coefficient_year = request.adjustment.coefficient_year
    if coefficient_year != benefit_year:
        raise ValueError(
            f"Năm bộ hệ số {coefficient_year} không trùng năm bắt đầu hưởng {benefit_year}."
        )
    if coefficient_year == 2026:
        return (
            request.adjustment.salary_coefficients or COEFFICIENTS_2026,
            request.adjustment.voluntary_income_coefficients or VOLUNTARY_COEFFICIENTS_2026,
        )
    if not request.adjustment.salary_coefficients or not request.adjustment.voluntary_income_coefficients:
        raise ValueError(
            f"Chưa có đầy đủ bảng hệ số tiền lương và thu nhập tự nguyện cho năm {coefficient_year}."
        )
    return request.adjustment.salary_coefficients, request.adjustment.voluntary_income_coefficients


def adjust_record(
    row: MonthlyRecord,
    salary_table: dict[int, Decimal],
    voluntary_table: dict[int, Decimal],
    first_state_year: int | None,
    state_values_converted: bool,
) -> tuple[Decimal, Decimal | None]:
    if row.basis is None:
        raise ValueError("Giai đoạn chỉ cộng thời gian không có mức đóng để tính bình quân.")
    if row.coefficient_override is not None:
        return row.basis * row.coefficient_override, row.coefficient_override
    if row.contribution_type == ContributionType.voluntary:
        coeff = coefficient_for_year(voluntary_table, row.month.year)
        return row.basis * coeff, coeff
    if row.contribution_type == ContributionType.compulsory_employer:
        coeff = coefficient_for_year(salary_table, row.month.year)
        return row.basis * coeff, coeff

    if row.month.year < 2016:
        if not state_values_converted and row.basis_input_type != BasisInputType.converted_state_vnd:
            raise ValueError(
                "Tháng lương Nhà nước trước năm 2016 được dùng tính bình quân nhưng chưa được quy đổi theo quy định."
            )
        return row.basis, None

    coeff = coefficient_for_year(salary_table, row.month.year)
    return row.basis * coeff, coeff


def calculate_average_basis(
    request: PensionRequest, rows: list[MonthlyRecord]
) -> tuple[Decimal, str, int, int, list[YearlyAdjustmentBreakdown]]:
    salary_table, voluntary_table = get_coefficient_tables(request)

    # Thời gian chỉ cộng thời gian vẫn có thể xác định mốc bắt đầu chế độ Nhà nước,
    # nhưng không được đưa vào tử số hoặc mẫu số mức bình quân.
    state_counted_rows = [
        r for r in rows if r.contribution_type == ContributionType.compulsory_state
    ]
    basis_rows = [r for r in rows if r.included_in_average]
    state_basis_rows = [
        r for r in basis_rows if r.contribution_type == ContributionType.compulsory_state
    ]
    employer_rows = [
        r for r in basis_rows if r.contribution_type == ContributionType.compulsory_employer
    ]
    voluntary_rows = [
        r for r in basis_rows if r.contribution_type == ContributionType.voluntary
    ]

    if not basis_rows:
        raise ValueError(
            "Không có tháng tiền lương/thu nhập hợp lệ để tính mức đóng bình quân BHXH."
        )

    first_state_year = state_counted_rows[0].month.year if state_counted_rows else None
    state_selected: list[MonthlyRecord] = []
    if state_basis_rows:
        years = state_average_years(first_state_year) if first_state_year is not None else None
        state_selected = state_basis_rows if years is None else state_basis_rows[-years * 12:]

    adjusted: dict[MonthlyRecord, Decimal] = {}
    yearly = defaultdict(lambda: {
        "months": 0, "original": Decimal("0"),
        "adjusted": Decimal("0"), "coeffs": set()
    })

    rows_directly_used = state_selected + employer_rows + voluntary_rows
    for row in rows_directly_used:
        value, coeff = adjust_record(
            row, salary_table, voluntary_table, first_state_year,
            request.state_salary_values_are_converted,
        )
        adjusted[row] = value
        key = (row.month.year, row.contribution_type)
        yearly[key]["months"] += 1
        yearly[key]["original"] += row.basis or Decimal("0")
        yearly[key]["adjusted"] += value
        yearly[key]["coeffs"].add(coeff)

    state_average = Decimal("0")
    state_months_used = len(state_selected)
    if state_selected:
        state_average = sum((adjusted[r] for r in state_selected), Decimal("0")) / Decimal(len(state_selected))

    state_weight_months = len(state_basis_rows)
    employer_sum = sum((adjusted[r] for r in employer_rows), Decimal("0"))
    voluntary_sum = sum((adjusted[r] for r in voluntary_rows), Decimal("0"))
    mandatory_basis_months = state_weight_months + len(employer_rows)
    all_basis_months = mandatory_basis_months + len(voluntary_rows)

    if mandatory_basis_months:
        mandatory_total_equivalent = state_average * Decimal(state_weight_months) + employer_sum
        mandatory_average = mandatory_total_equivalent / Decimal(mandatory_basis_months)
    else:
        mandatory_average = Decimal("0")

    if voluntary_rows and mandatory_basis_months:
        average = (
            mandatory_average * Decimal(mandatory_basis_months) + voluntary_sum
        ) / Decimal(all_basis_months)
        method = "Bình quân chung các tháng có mức đóng BHXH bắt buộc và tự nguyện sau điều chỉnh"
    elif voluntary_rows:
        average = voluntary_sum / Decimal(len(voluntary_rows))
        method = "Bình quân toàn bộ tháng có thu nhập BHXH tự nguyện sau điều chỉnh"
    elif state_basis_rows and employer_rows:
        average = (
            state_average * Decimal(state_weight_months) + employer_sum
        ) / Decimal(mandatory_basis_months)
        method = "Bình quân chung lương Nhà nước và lương doanh nghiệp; loại thời gian chỉ cộng thời gian"
    elif state_basis_rows:
        average = state_average
        method = "Bình quân thời kỳ cuối theo chế độ tiền lương Nhà nước"
    else:
        average = employer_sum / Decimal(len(employer_rows))
        method = "Bình quân toàn bộ tháng lương doanh nghiệp sau điều chỉnh"

    breakdown: list[YearlyAdjustmentBreakdown] = []
    for (year, ctype), data in sorted(yearly.items(), key=lambda x: (x[0][0], x[0][1].value)):
        coeff_values = data["coeffs"]
        coeff = next(iter(coeff_values)) if len(coeff_values) == 1 else None
        breakdown.append(YearlyAdjustmentBreakdown(
            year=year,
            contribution_type=ctype,
            months=data["months"],
            original_total_vnd=data["original"].quantize(MONEY, rounding=ROUND_HALF_UP),
            adjusted_total_vnd=data["adjusted"].quantize(MONEY, rounding=ROUND_HALF_UP),
            coefficient=coeff,
        ))
    return average, method, state_months_used, len(rows_directly_used), breakdown


def contribution_completion_month(
    rows: list[MonthlyRecord], required: int, compulsory_only: bool
) -> date | None:
    count = 0
    for row in rows:
        if compulsory_only and row.contribution_type == ContributionType.voluntary:
            continue
        count += 1
        if count >= required:
            return row.month
    return None


def determine_eligibility(
    request: PensionRequest,
    rows: list[MonthlyRecord],
    retirement_end: date,
) -> tuple[EligibilityResult, date | None, int, list[str]]:
    total = len(rows)
    compulsory = sum(1 for r in rows if r.contribution_type != ContributionType.voluntary)
    voluntary = total - compulsory
    reasons: list[str] = []
    missing: list[str] = []
    warnings: list[str] = []
    regime = PensionRegime.undetermined
    required_total: int | None = None
    required_compulsory: int | None = None
    age_threshold: date | None = None
    reference_offset = 0

    flagged_hazardous = sum(1 for r in rows if r.qualifying_hazardous)
    flagged_especially = sum(1 for r in rows if r.qualifying_especially_hazardous)
    flagged_coal = sum(1 for r in rows if r.qualifying_underground_coal)
    hazardous = max(request.hazardous_or_special_region_months, flagged_hazardous)
    especially = max(request.especially_hazardous_months, flagged_especially)
    coal = max(request.underground_coal_months, flagged_coal)

    if request.retirement_case in {RetirementCase.occupational_hiv, RetirementCase.armed_forces}:
        reasons.append("Trường hợp đặc thù này chưa được tự động hóa đầy đủ.")
        return EligibilityResult(
            eligible=False, case=request.retirement_case, regime=regime,
            reasons=reasons, missing_fields=missing,
        ), None, reference_offset, warnings

    if request.retirement_case == RetirementCase.normal:
        required_total = 180
        if compulsory >= 180:
            regime = PensionRegime.compulsory if voluntary == 0 else PensionRegime.mixed_compulsory_policy
            required_compulsory = 180
        elif total >= 180 and voluntary > 0:
            regime = PensionRegime.voluntary if compulsory == 0 else PensionRegime.mixed_voluntary_policy
        else:
            regime = PensionRegime.compulsory if voluntary == 0 else PensionRegime.mixed_voluntary_policy
            if voluntary == 0:
                required_compulsory = 180
            reasons.append(f"Chưa đủ 180 tháng đóng BHXH; hiện có {total} tháng.")
        age_threshold, _ = threshold_date_for_retirement_year(
            request.person.date_of_birth, request.person.sex.value, retirement_end.year, 0
        )

    elif request.retirement_case == RetirementCase.hazardous_or_special_region:
        regime = PensionRegime.compulsory if voluntary == 0 else PensionRegime.mixed_compulsory_policy
        required_compulsory = 180
        if compulsory < 180:
            reasons.append(f"Cần ít nhất 180 tháng BHXH bắt buộc; hiện có {compulsory} tháng.")
        if hazardous < 180:
            reasons.append(f"Cần ít nhất 180 tháng nghề/địa bàn đủ điều kiện; hiện có {hazardous} tháng.")
        age_threshold, _ = threshold_date_for_retirement_year(
            request.person.date_of_birth, request.person.sex.value, retirement_end.year, 5
        )

    elif request.retirement_case == RetirementCase.underground_coal:
        regime = PensionRegime.compulsory if voluntary == 0 else PensionRegime.mixed_compulsory_policy
        required_compulsory = 180
        if compulsory < 180:
            reasons.append(f"Cần ít nhất 180 tháng BHXH bắt buộc; hiện có {compulsory} tháng.")
        if coal < 180:
            reasons.append(f"Cần ít nhất 180 tháng khai thác than hầm lò; hiện có {coal} tháng.")
        age_threshold, _ = threshold_date_for_retirement_year(
            request.person.date_of_birth, request.person.sex.value, retirement_end.year, 10
        )

    elif request.retirement_case == RetirementCase.reduced_capacity:
        regime = PensionRegime.compulsory if voluntary == 0 else PensionRegime.mixed_compulsory_policy
        required_compulsory = 240
        if compulsory < 240:
            reasons.append(f"Cần ít nhất 240 tháng BHXH bắt buộc; hiện có {compulsory} tháng.")
        if request.impairment_percent is None:
            missing.append("impairment_percent")
        elif request.impairment_percent < 61:
            reasons.append("Tỷ lệ suy giảm khả năng lao động dưới 61%.")
        elif especially >= 180:
            age_threshold = None
            reference_offset = 5
            if request.impairment_assessment_month is None:
                warnings.append(
                    "Chưa có tháng kết luận giám định; trợ cấp một lần sau thời điểm đủ điều kiện không thể tách chính xác."
                )
        elif request.impairment_percent >= 81:
            age_threshold, _ = threshold_date_for_retirement_year(
                request.person.date_of_birth, request.person.sex.value, retirement_end.year, 10
            )
        else:
            age_threshold, _ = threshold_date_for_retirement_year(
                request.person.date_of_birth, request.person.sex.value, retirement_end.year, 5
            )

    if age_threshold is not None and retirement_end < age_threshold:
        reasons.append(
            f"Ngày nghỉ {retirement_end.isoformat()} chưa đạt ngưỡng tuổi {age_threshold.isoformat()} của trường hợp này."
        )

    months_short = 0
    if required_compulsory is not None and compulsory < required_compulsory:
        months_short = required_compulsory - compulsory
    elif required_total is not None and total < required_total:
        months_short = required_total - total

    can_pay_missing = (
        request.retirement_case == RetirementCase.normal
        and required_compulsory == 180
        and 1 <= months_short <= 6
        and age_threshold is not None
        and retirement_end >= age_threshold
    ) or (
        request.retirement_case == RetirementCase.reduced_capacity
        and 1 <= months_short <= 6
        and (age_threshold is None or retirement_end >= age_threshold)
    )

    eligible = not reasons and not missing
    return EligibilityResult(
        eligible=eligible,
        case=request.retirement_case,
        regime=regime,
        reasons=reasons,
        missing_fields=missing,
        required_total_months=required_total,
        required_compulsory_months=required_compulsory,
        months_short=months_short,
        can_pay_missing_months_once=can_pay_missing,
    ), age_threshold, reference_offset, warnings


def determine_eligibility_achieved_month(
    request: PensionRequest,
    rows: list[MonthlyRecord],
    eligibility: EligibilityResult,
    age_threshold: date | None,
) -> date | None:
    if request.eligibility_achieved_month:
        return parse_year_month(request.eligibility_achieved_month)

    candidates: list[date] = []
    if age_threshold is not None:
        candidates.append(date(age_threshold.year, age_threshold.month, 1))

    if eligibility.required_compulsory_months:
        completion = contribution_completion_month(
            rows, eligibility.required_compulsory_months, compulsory_only=True
        )
        if completion:
            candidates.append(completion)
    elif eligibility.required_total_months:
        completion = contribution_completion_month(rows, eligibility.required_total_months, False)
        if completion:
            candidates.append(completion)

    if request.retirement_case == RetirementCase.reduced_capacity:
        if not request.impairment_assessment_month:
            return None
        candidates.append(parse_year_month(request.impairment_assessment_month))

    return max(candidates) if candidates else None


def calculate_one_time_allowance(
    request: PensionRequest,
    rows: list[MonthlyRecord],
    eligibility: EligibilityResult,
    age_threshold: date | None,
    average: Decimal,
) -> tuple[Decimal | None, str | None]:
    rounded_years = rounded_years_for_rate(len(rows))
    threshold = Decimal("35") if request.person.sex == "male" else Decimal("30")
    excess = max(Decimal("0"), rounded_years - threshold)
    if excess == 0:
        return Decimal("0"), None

    achieved = determine_eligibility_achieved_month(request, rows, eligibility, age_threshold)
    if achieved is None:
        return None, (
            "Không đủ dữ liệu xác định thời điểm đã đồng thời đáp ứng mọi điều kiện để tách mức 0,5 và 2 lần."
        )
    post_months = sum(1 for r in rows if r.month > achieved)
    post_years = min(excess, rounded_years_for_rate(post_months))
    pre_years = max(Decimal("0"), excess - post_years)
    amount = average * (Decimal("0.5") * pre_years + Decimal("2") * post_years)
    return amount.quantize(MONEY, rounding=ROUND_HALF_UP), None


def empty_average(request: PensionRequest) -> AverageBasisResult:
    return AverageBasisResult(
        amount_vnd=None,
        average_monthly_basis_vnd=None,
        basis_months_used=0,
        method=None,
        coefficient_year=request.adjustment.coefficient_year,
        state_average_months_used=0,
        yearly_breakdown=[],
    )


def empty_rate() -> PensionRateResult:
    return PensionRateResult(
        rounded_years=None,
        base_rate_percent=None,
        early_retirement_months=0,
        early_retirement_reduction_percent=Decimal("0"),
        final_rate_percent=None,
    )


def calculate_pension(request: PensionRequest) -> PensionResponse:
    calculation_id = str(uuid4())
    history = validate_contribution_history(request)
    rows = expand_contributions(request)
    total = len(rows)
    compulsory = sum(1 for r in rows if r.contribution_type != ContributionType.voluntary)
    voluntary = total - compulsory
    rounded_years = rounded_years_for_rate(total)
    start_month = parse_year_month(request.pension_start_month)
    retirement_end = previous_month_end(start_month)

    normal_threshold, normal_age = threshold_date_for_retirement_year(
        request.person.date_of_birth,
        request.person.sex.value,
        retirement_end.year,
        0,
    )
    earliest_normal_threshold, _ = earliest_threshold_for_schedule(
        request.person.date_of_birth, request.person.sex.value, 0
    )
    earliest_normal_start = next_month(date(
        earliest_normal_threshold.year, earliest_normal_threshold.month, 1
    ))
    normal_age_label = f"{normal_age[0]} tuổi" + (
        f" {normal_age[1]} tháng" if normal_age[1] else ""
    )

    average_basis_months = sum(1 for r in rows if r.included_in_average)
    credited_duration_only_months = sum(
        1 for r in rows if r.participation_status == ParticipationStatus.credited_duration_only
    )
    summary = ContributionSummary(
        total_months=total,
        compulsory_months=compulsory,
        voluntary_months=voluntary,
        average_basis_months=average_basis_months,
        credited_duration_only_months=credited_duration_only_months,
        excluded_non_participation_months=history.excluded_non_participation_months,
        exact_duration=exact_duration(total),
        rounded_years_for_rate=rounded_years,
    )

    assumptions = [
        "pension_start_month là tháng đầu tiên hưởng; ngày nghỉ được hiểu là ngày cuối tháng trước.",
        "Mỗi khoảng đóng bao gồm cả tháng bắt đầu và tháng kết thúc.",
        "Dòng ghi rõ không tham gia BHXH được loại khỏi cả thời gian và mức bình quân.",
        "Giai đoạn credited_duration_only chỉ cộng thời gian hưởng, không đưa mức lương vào bình quân.",
    ]
    warnings = [
        "Kết quả là ước tính; hồ sơ được cơ quan BHXH xác nhận và quy định có hiệu lực tại thời điểm giải quyết là căn cứ cuối cùng."
    ]
    audit = [
        f"Chuẩn hóa được {total} tháng được tính là thời gian tham gia BHXH.",
        f"Có {average_basis_months} tháng có mức đóng dùng tính bình quân; "
        f"{credited_duration_only_months} tháng chỉ cộng thời gian; "
        f"{history.excluded_non_participation_months} tháng không tham gia đã loại bỏ.",
        f"Thời gian dùng tính tỷ lệ sau làm tròn: {rounded_years} năm.",
    ]

    if not history.valid_for_calculation:
        missing = sorted({i.code for i in history.issues if i.severity == "error"})
        eligibility = EligibilityResult(
            eligible=False,
            case=request.retirement_case,
            regime=PensionRegime.undetermined,
            reasons=[i.message_vi for i in history.issues if i.severity == "error"],
            missing_fields=missing,
        )
        return PensionResponse(
            calculation_id=calculation_id,
            status="needs_more_data",
            error_code="CONTRIBUTION_HISTORY_INVALID",
            legal_rule_version=LEGAL_RULE_VERSION,
            requested_pension_start_month=request.pension_start_month,
            retirement_end_date=retirement_end,
            normal_retirement_age_in_retirement_year=normal_age_label,
            normal_retirement_threshold_date=normal_threshold,
            earliest_normal_pension_start_month=format_year_month(earliest_normal_start),
            history_validation=history,
            contribution_summary=summary,
            eligibility=eligibility,
            average_basis=empty_average(request),
            pension_rate=empty_rate(),
            estimated_monthly_pension_vnd=None,
            pension_calculation_formula=None,
            one_time_retirement_allowance_vnd=None,
            assumptions=assumptions,
            warnings=warnings,
            audit_steps=audit,
            legal_references=[LegalReference(**ref) for ref in LEGAL_REFERENCES],
        )

    eligibility, age_threshold, reduction_reference_offset, eligibility_warnings = determine_eligibility(
        request, rows, retirement_end
    )
    warnings.extend(eligibility_warnings)

    manual = request.retirement_case in {
        RetirementCase.occupational_hiv,
        RetirementCase.armed_forces,
    }
    status = "manual_review" if manual else "eligible" if eligibility.eligible else (
        "needs_more_data" if eligibility.missing_fields else "not_eligible"
    )

    average_result = empty_average(request)
    rate_result = empty_rate()
    estimated_pension: Decimal | None = None
    pension_formula: str | None = None
    allowance: Decimal | None = None
    floor_applied = False
    error_code: str | None = None

    if total >= 180:
        try:
            average, method, state_months, basis_months_used, breakdown = calculate_average_basis(request, rows)
            rounded_average = average.quantize(MONEY, rounding=ROUND_HALF_UP)
            average_result = AverageBasisResult(
                amount_vnd=rounded_average,
                average_monthly_basis_vnd=rounded_average,
                basis_months_used=basis_months_used,
                method=method,
                coefficient_year=request.adjustment.coefficient_year,
                state_average_months_used=state_months,
                yearly_breakdown=breakdown,
            )
            base = base_rate(request.person.sex.value, rounded_years)
            early_months = 0
            reduction = Decimal("0")
            reduction_age = None
            if request.retirement_case == RetirementCase.reduced_capacity:
                early_months, reduction, reduction_age = early_reduction(
                    request.person.date_of_birth,
                    request.person.sex.value,
                    retirement_end,
                    reduction_reference_offset,
                )
            final = max(Decimal("0"), base - reduction)
            rate_result = PensionRateResult(
                rounded_years=rounded_years,
                base_rate_percent=base,
                early_retirement_months=early_months,
                early_retirement_reduction_percent=reduction,
                final_rate_percent=final,
                reduction_reference_age=reduction_age,
            )
            audit.append(f"Tính mức bình quân theo phương pháp: {method}.")
            audit.append(f"Tỷ lệ cơ bản {base}%, giảm {reduction}%, còn {final}%.")

            if eligibility.eligible:
                estimated_pension = (average * final / Decimal("100")).quantize(
                    MONEY, rounding=ROUND_HALF_UP
                )
                pension_formula = (
                    f"{average_result.average_monthly_basis_vnd} × {final}% = "
                    f"{estimated_pension} đồng/tháng"
                )
                allowance, allowance_warning = calculate_one_time_allowance(
                    request, rows, eligibility, age_threshold, average
                )
                if allowance_warning:
                    warnings.append(allowance_warning)

                joined_before_transition = any(
                    r.contribution_type != ContributionType.voluntary
                    and r.month < date(2025, 7, 1)
                    for r in rows
                )
                if request.transitional_minimum_floor_eligible:
                    if not request.reference_level_vnd:
                        warnings.append(
                            "Đã chọn áp dụng mức sàn chuyển tiếp nhưng chưa cung cấp mức tham chiếu."
                        )
                    elif compulsory >= 240 and joined_before_transition and estimated_pension < request.reference_level_vnd:
                        estimated_pension = request.reference_level_vnd.quantize(MONEY, rounding=ROUND_HALF_UP)
                        floor_applied = True
                elif compulsory >= 240 and joined_before_transition:
                    warnings.append(
                        "API không tự áp dụng mức sàn chuyển tiếp nếu chưa xác nhận transitional_minimum_floor_eligible."
                    )

        except ValueError as exc:
            status = "needs_more_data"
            error_code = "CALCULATION_INPUT_INCOMPLETE"
            eligibility.eligible = False
            eligibility.missing_fields.append("calculation_input")
            eligibility.reasons.append(str(exc))
            warnings.append(str(exc))
            estimated_pension = None
            allowance = None
    elif eligibility.can_pay_missing_months_once:
        warnings.append(
            "Có thể thuộc trường hợp được đóng một lần cho số tháng còn thiếu theo quy định; API chưa tự cộng thời gian giả định này."
        )

    if not eligibility.eligible:
        estimated_pension = None
        pension_formula = None
        allowance = None

    if status == "not_eligible" and eligibility.can_pay_missing_months_once:
        warnings.append(
            f"Thiếu {eligibility.months_short} tháng; cần cơ quan BHXH xác định quyền đóng một lần cho phần thiếu."
        )

    return PensionResponse(
        calculation_id=calculation_id,
        status=status,
        error_code=error_code,
        legal_rule_version=LEGAL_RULE_VERSION,
        requested_pension_start_month=request.pension_start_month,
        retirement_end_date=retirement_end,
        normal_retirement_age_in_retirement_year=normal_age_label,
        normal_retirement_threshold_date=normal_threshold,
        earliest_normal_pension_start_month=format_year_month(earliest_normal_start),
        history_validation=history,
        contribution_summary=summary,
        eligibility=eligibility,
        average_basis=average_result,
        pension_rate=rate_result,
        estimated_monthly_pension_vnd=estimated_pension,
        pension_calculation_formula=pension_formula,
        one_time_retirement_allowance_vnd=allowance,
        minimum_floor_applied=floor_applied,
        assumptions=assumptions,
        warnings=warnings,
        audit_steps=audit,
        legal_references=[LegalReference(**ref) for ref in LEGAL_REFERENCES],
    )


def capabilities() -> CapabilitiesResponse:
    return CapabilitiesResponse(
        service="calculatePension",
        version="2.1.0",
        legal_rule_version=LEGAL_RULE_VERSION,
        built_in_coefficient_years=[2026],
        supported_retirement_cases=[
            RetirementCase.normal,
            RetirementCase.hazardous_or_special_region,
            RetirementCase.underground_coal,
            RetirementCase.reduced_capacity,
        ],
        manual_review_cases=[RetirementCase.occupational_hiv, RetirementCase.armed_forces],
        supported_source_documents=list(SourceDocumentType),
        notes=[
            "Mẫu 07/SBH phải được chuẩn hóa thành tiền VND/tháng trước khi tính.",
            "Bộ hệ số tích hợp sẵn chỉ áp dụng cho năm hưởng 2026.",
            "Dòng ghi rõ không tham gia BHXH được tự động loại khỏi thời gian và mức bình quân.",
            "Thời gian được công nhận trước 01/01/1995 nhưng không có lương/sinh hoạt phí dùng credited_duration_only: cộng thời gian, không tính bình quân.",
            "Không loại toàn bộ thời gian trước 1995: tháng có đóng và có tiền lương vẫn xử lý theo chế độ tiền lương tương ứng.",
            "Khoảng trống không có dòng trạng thái vẫn phải được xác nhận.",
        ],
    )
