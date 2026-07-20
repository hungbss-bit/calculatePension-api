from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from dateutil.relativedelta import relativedelta

from .models import (
    AverageBasisResult,
    ContributionSummary,
    ContributionType,
    EligibilityResult,
    PensionRateResult,
    PensionRequest,
    PensionResponse,
    RetirementCase,
)
from .rules import (
    COEFFICIENTS_2026,
    LEGAL_RULE_VERSION,
    coefficient_for_year,
    normal_retirement_threshold,
    state_average_years,
)


MONEY = Decimal("1")
PERCENT = Decimal("0.01")


@dataclass(frozen=True)
class MonthlyRecord:
    month: date
    basis: Decimal
    contribution_type: ContributionType
    coefficient_override: Decimal | None


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


def expand_contributions(request: PensionRequest) -> list[MonthlyRecord]:
    seen: set[tuple[int, int]] = set()
    rows: list[MonthlyRecord] = []

    for period in request.contributions:
        current = parse_year_month(period.from_month)
        end = parse_year_month(period.to_month)
        while current <= end:
            key = (current.year, current.month)
            if key in seen:
                raise ValueError(
                    f"Overlapping contribution history at {current.year:04d}-{current.month:02d}."
                )
            seen.add(key)
            rows.append(
                MonthlyRecord(
                    month=current,
                    basis=period.monthly_basis_vnd,
                    contribution_type=period.contribution_type,
                    coefficient_override=period.coefficient_override,
                )
            )
            current = next_month(current)

    rows.sort(key=lambda row: row.month)
    return rows


def rounded_years_for_rate(total_months: int) -> Decimal:
    full_years, remaining = divmod(total_months, 12)
    if remaining == 0:
        fraction = Decimal("0")
    elif remaining <= 6:
        fraction = Decimal("0.5")
    else:
        fraction = Decimal("1")
    return Decimal(full_years) + fraction


def exact_duration(total_months: int) -> str:
    years, months = divmod(total_months, 12)
    return f"{years} years {months} months"


def base_rate(sex: str, rounded_years: Decimal) -> Decimal:
    if rounded_years < Decimal("15"):
        raise ValueError("At least 15 full contribution years are required.")

    if sex == "female":
        rate = Decimal("45") + (rounded_years - Decimal("15")) * Decimal("2")
    elif rounded_years < Decimal("20"):
        rate = Decimal("40") + (rounded_years - Decimal("15"))
    else:
        rate = Decimal("45") + (rounded_years - Decimal("20")) * Decimal("2")

    return min(Decimal("75"), rate)


def complete_months_between(earlier: date, later: date) -> int:
    """Whole calendar months from earlier to later; never negative."""
    if later <= earlier:
        return 0
    delta = relativedelta(later, earlier)
    months = delta.years * 12 + delta.months
    if delta.days < 0:
        months -= 1
    return max(0, months)


def early_reduction_percent(retirement_end: date, normal_threshold: date) -> Decimal:
    if retirement_end >= normal_threshold:
        return Decimal("0")
    early_months = complete_months_between(retirement_end, normal_threshold)
    full_years, remainder = divmod(early_months, 12)
    reduction = Decimal(full_years * 2)
    if remainder >= 6:
        reduction += Decimal("1")
    return reduction


def get_tables(request: PensionRequest) -> tuple[dict[int, Decimal], dict[int, Decimal]]:
    custom_salary = request.adjustment.salary_coefficients
    custom_voluntary = request.adjustment.voluntary_income_coefficients

    if request.adjustment.coefficient_year == 2026:
        salary = custom_salary or COEFFICIENTS_2026
        voluntary = custom_voluntary or COEFFICIENTS_2026
        return salary, voluntary

    if not custom_salary or not custom_voluntary:
        raise ValueError(
            "Built-in adjustment coefficients are available only for benefit year 2026. "
            "For another year, provide both salary_coefficients and "
            "voluntary_income_coefficients."
        )
    return custom_salary, custom_voluntary


def adjusted_value(
    row: MonthlyRecord,
    salary_table: dict[int, Decimal],
    voluntary_table: dict[int, Decimal],
    first_state_year: int | None,
    state_values_converted: bool,
) -> Decimal:
    if row.coefficient_override is not None:
        return row.basis * row.coefficient_override

    if row.contribution_type == ContributionType.voluntary:
        coefficient = coefficient_for_year(voluntary_table, row.month.year)
        return row.basis * coefficient

    if row.contribution_type == ContributionType.compulsory_employer:
        coefficient = coefficient_for_year(salary_table, row.month.year)
        return row.basis * coefficient

    # State salary records beginning before 2016 are adjusted according to
    # the reference-level/salary-scale mechanism. The API requires converted
    # values (or a per-period override) rather than silently approximating.
    if first_state_year is not None and first_state_year < 2016:
        if not state_values_converted:
            raise ValueError(
                "State-sector salary history began before 2016. Set "
                "state_salary_values_are_converted=true only after supplying "
                "salary values already converted under the applicable salary-scale/"
                "reference-level rules, or provide coefficient_override."
            )
        return row.basis

    coefficient = coefficient_for_year(salary_table, row.month.year)
    return row.basis * coefficient


def calculate_average_basis(
    request: PensionRequest, rows: list[MonthlyRecord]
) -> tuple[Decimal, str, int, list[str]]:
    salary_table, voluntary_table = get_tables(request)
    state_rows = [
        row for row in rows if row.contribution_type == ContributionType.compulsory_state
    ]
    employer_rows = [
        row for row in rows if row.contribution_type == ContributionType.compulsory_employer
    ]
    voluntary_rows = [
        row for row in rows if row.contribution_type == ContributionType.voluntary
    ]

    first_state_year = state_rows[0].month.year if state_rows else None
    adjusted: dict[MonthlyRecord, Decimal] = {}
    for row in rows:
        adjusted[row] = adjusted_value(
            row,
            salary_table,
            voluntary_table,
            first_state_year,
            request.state_salary_values_are_converted,
        )

    state_average = Decimal("0")
    state_months_used = 0
    if state_rows:
        years = state_average_years(first_state_year)
        selected = state_rows if years is None else state_rows[-years * 12 :]
        state_months_used = len(selected)
        state_average = sum(adjusted[row] for row in selected) / Decimal(len(selected))

    employer_sum = sum((adjusted[row] for row in employer_rows), Decimal("0"))
    voluntary_sum = sum((adjusted[row] for row in voluntary_rows), Decimal("0"))

    compulsory_months = len(state_rows) + len(employer_rows)
    total_months = len(rows)
    assumptions: list[str] = []

    if compulsory_months:
        compulsory_total_equivalent = (
            state_average * Decimal(len(state_rows)) + employer_sum
        )
        compulsory_average = compulsory_total_equivalent / Decimal(compulsory_months)
    else:
        compulsory_average = Decimal("0")

    if voluntary_rows and compulsory_months:
        average = (
            compulsory_average * Decimal(compulsory_months) + voluntary_sum
        ) / Decimal(total_months)
        method = "Combined compulsory-and-voluntary adjusted average"
    elif voluntary_rows:
        average = voluntary_sum / Decimal(len(voluntary_rows))
        method = "All-period adjusted voluntary-income average"
    elif state_rows and employer_rows:
        average = (
            state_average * Decimal(len(state_rows)) + employer_sum
        ) / Decimal(compulsory_months)
        method = "Combined state-sector and employer-decided salary average"
    elif state_rows:
        average = state_average
        method = "State-sector statutory final-period average"
    else:
        average = employer_sum / Decimal(len(employer_rows))
        method = "All-period adjusted employer-decided salary average"

    if request.adjustment.coefficient_year != int(request.pension_start_month[:4]):
        assumptions.append(
            "The adjustment coefficient year differs from the pension-start year; "
            "the caller explicitly supplied/selected that coefficient set."
        )

    return average, method, state_months_used, assumptions


def minimum_age_threshold(
    request: PensionRequest,
    normal_threshold: date,
) -> tuple[date | None, list[str], list[str]]:
    reasons: list[str] = []
    missing: list[str] = []

    if request.retirement_case == RetirementCase.normal:
        return normal_threshold, reasons, missing

    if request.retirement_case == RetirementCase.hazardous_or_special_region:
        if request.hazardous_or_special_region_months < 180:
            reasons.append(
                "Fewer than 180 qualifying hazardous/special-region contribution months."
            )
        return normal_threshold - relativedelta(years=5), reasons, missing

    if request.retirement_case == RetirementCase.underground_coal:
        if request.underground_coal_months < 180:
            reasons.append("Fewer than 180 underground-coal contribution months.")
        return normal_threshold - relativedelta(years=10), reasons, missing

    if request.retirement_case == RetirementCase.reduced_capacity:
        if request.impairment_percent is None:
            missing.append("impairment_percent")
            return None, reasons, missing
        if (
            request.impairment_percent >= Decimal("61")
            and request.especially_hazardous_months >= 180
        ):
            reasons.append(
                "The especially-hazardous reduced-capacity pathway requires "
                "manual legal verification; no automatic minimum-age conclusion "
                "is returned."
            )
            return None, reasons, missing
        if request.impairment_percent >= Decimal("81"):
            return normal_threshold - relativedelta(years=10), reasons, missing
        if request.impairment_percent >= Decimal("61"):
            return normal_threshold - relativedelta(years=5), reasons, missing
        reasons.append("Impairment percentage is below 61%.")
        return None, reasons, missing

    reasons.append(
        "This retirement category is routed to manual review because its "
        "occupation/status conditions are not fully represented by this API."
    )
    return None, reasons, missing


def count_post_eligibility_contributions(
    rows: list[MonthlyRecord], eligibility_date: date
) -> int:
    eligibility_month = date(eligibility_date.year, eligibility_date.month, 1)
    return sum(1 for row in rows if row.month > eligibility_month)


def one_time_allowance(
    sex: str,
    rounded_years: Decimal,
    average_basis: Decimal,
    rows: list[MonthlyRecord],
    eligibility_date: date,
) -> Decimal:
    threshold = Decimal("35") if sex == "male" else Decimal("30")
    total_excess = max(Decimal("0"), rounded_years - threshold)
    if total_excess == 0:
        return Decimal("0")

    post_months = count_post_eligibility_contributions(rows, eligibility_date)
    post_years = min(total_excess, rounded_years_for_rate(post_months))
    pre_years = max(Decimal("0"), total_excess - post_years)
    amount = average_basis * (
        Decimal("0.5") * pre_years + Decimal("2") * post_years
    )
    return amount.quantize(MONEY, rounding=ROUND_HALF_UP)


def calculate_pension(request: PensionRequest) -> PensionResponse:
    rows = expand_contributions(request)
    total_months = len(rows)
    compulsory_months = sum(
        1 for row in rows if row.contribution_type != ContributionType.voluntary
    )
    voluntary_months = total_months - compulsory_months

    rounded_years = rounded_years_for_rate(total_months)
    start_month = parse_year_month(request.pension_start_month)
    retirement_end = previous_month_end(start_month)

    normal_threshold, (age_years, age_months) = normal_retirement_threshold(
        request.person.date_of_birth,
        request.person.sex.value,
    )
    earliest_normal_start = next_month(
        date(normal_threshold.year, normal_threshold.month, 1)
    )

    age_threshold, case_reasons, missing_fields = minimum_age_threshold(
        request, normal_threshold
    )

    reasons = list(case_reasons)
    warnings: list[str] = []
    assumptions: list[str] = []
    audit_steps: list[str] = []

    if total_months < 180:
        reasons.append("Fewer than 180 total contribution months (15 full years).")

    if request.retirement_case in {
        RetirementCase.hazardous_or_special_region,
        RetirementCase.underground_coal,
    } and compulsory_months < 180:
        reasons.append(
            "This lower-age compulsory-pension pathway requires at least "
            "180 compulsory contribution months."
        )

    if request.retirement_case == RetirementCase.reduced_capacity:
        if compulsory_months < 240:
            reasons.append(
                "Reduced-capacity pension requires at least 240 compulsory "
                "contribution months."
            )
        if request.impairment_percent is not None and request.impairment_percent < 61:
            reasons.append("Impairment percentage must be at least 61%.")

    if age_threshold is not None and retirement_end < age_threshold:
        reasons.append(
            f"Retirement end date {retirement_end.isoformat()} is earlier than "
            f"the minimum age threshold {age_threshold.isoformat()} for this case."
        )

    manual_categories = {
        RetirementCase.occupational_hiv,
        RetirementCase.armed_forces,
    }
    is_manual = request.retirement_case in manual_categories or (
        request.retirement_case == RetirementCase.reduced_capacity
        and request.impairment_percent is not None
        and request.impairment_percent >= Decimal("61")
        and request.especially_hazardous_months >= 180
    )

    missing_only = bool(missing_fields)
    eligible = not reasons and not missing_only and not is_manual

    average_value: Decimal | None = None
    average_method: str | None = None
    state_months_used = 0
    base_percent: Decimal | None = None
    reduction = Decimal("0")
    final_percent: Decimal | None = None
    monthly_pension: Decimal | None = None
    allowance: Decimal | None = None
    floor_applied = False

    if not missing_only and total_months >= 180:
        try:
            (
                average_value,
                average_method,
                state_months_used,
                average_assumptions,
            ) = calculate_average_basis(request, rows)
            assumptions.extend(average_assumptions)

            base_percent = base_rate(request.person.sex.value, rounded_years)
            if request.retirement_case == RetirementCase.reduced_capacity:
                reduction = early_reduction_percent(retirement_end, normal_threshold)
            final_percent = max(Decimal("0"), base_percent - reduction)
            monthly_pension = (
                average_value * final_percent / Decimal("100")
            ).quantize(MONEY, rounding=ROUND_HALF_UP)

            eligibility_for_allowance = age_threshold or normal_threshold
            allowance = one_time_allowance(
                request.person.sex.value,
                rounded_years,
                average_value,
                rows,
                eligibility_for_allowance,
            )

            joined_compulsory_before_2025_07 = any(
                row.contribution_type != ContributionType.voluntary
                and row.month < date(2025, 7, 1)
                for row in rows
            )
            if (
                request.reference_level_vnd is not None
                and joined_compulsory_before_2025_07
                and compulsory_months >= 240
                and monthly_pension < request.reference_level_vnd
            ):
                monthly_pension = request.reference_level_vnd.quantize(
                    MONEY, rounding=ROUND_HALF_UP
                )
                floor_applied = True
            elif joined_compulsory_before_2025_07 and compulsory_months >= 240:
                warnings.append(
                    "A transitional minimum-pension floor may apply. Supply "
                    "reference_level_vnd to let the API test and apply that floor."
                )

        except ValueError as exc:
            missing_fields.append("calculation_input")
            reasons.append(str(exc))
            missing_only = True

    if request.pension_start_month > "2026-12":
        warnings.append(
            "The retirement date is after 2026. Annual adjustment coefficients "
            "and legal parameters must be refreshed before production use."
        )

    if is_manual:
        status = "manual_review"
        eligible = False
    elif missing_only:
        status = "needs_more_data"
        eligible = False
    elif eligible:
        status = "eligible"
    else:
        status = "not_eligible"

    if not eligible:
        monthly_pension = None
        allowance = None

    audit_steps.extend(
        [
            f"Expanded contribution history to {total_months} unique months.",
            f"Rounded contribution duration for rate calculation to {rounded_years} years.",
            (
                f"Calculated normal retirement threshold as "
                f"{normal_threshold.isoformat()} at age {age_years} years "
                f"{age_months} months."
            ),
        ]
    )
    if average_value is not None:
        audit_steps.append(
            f"Calculated adjusted average pension basis using: {average_method}."
        )
    if final_percent is not None:
        audit_steps.append(
            f"Applied base rate {base_percent}% and early-retirement reduction "
            f"{reduction}%, yielding {final_percent}%."
        )

    assumptions.append(
        "pension_start_month is interpreted as the first month receiving pension; "
        "employment/retirement ends on the final day of the preceding month."
    )
    assumptions.append(
        "Each contribution range is inclusive and monthly_basis_vnd is the monthly "
        "salary/income basis for every month in that range."
    )
    warnings.append(
        "This is a rules-based estimate, not an administrative pension decision. "
        "The social-insurance authority's verified record and the law effective "
        "on the entitlement date control."
    )

    return PensionResponse(
        calculation_id=str(uuid4()),
        status=status,
        legal_rule_version=LEGAL_RULE_VERSION,
        requested_pension_start_month=request.pension_start_month,
        retirement_end_date=retirement_end,
        normal_retirement_age=f"{age_years} years {age_months} months",
        normal_retirement_threshold_date=normal_threshold,
        earliest_normal_pension_start_month=format_year_month(earliest_normal_start),
        contribution_summary=ContributionSummary(
            total_months=total_months,
            compulsory_months=compulsory_months,
            voluntary_months=voluntary_months,
            exact_duration=exact_duration(total_months),
            rounded_years_for_rate=rounded_years,
        ),
        eligibility=EligibilityResult(
            eligible=eligible,
            case=request.retirement_case,
            reasons=reasons,
            missing_fields=sorted(set(missing_fields)),
        ),
        average_basis=AverageBasisResult(
            amount_vnd=(
                average_value.quantize(MONEY, rounding=ROUND_HALF_UP)
                if average_value is not None
                else None
            ),
            method=average_method,
            coefficient_year=request.adjustment.coefficient_year,
            state_average_months_used=state_months_used,
        ),
        pension_rate=PensionRateResult(
            base_rate_percent=base_percent,
            early_retirement_reduction_percent=reduction,
            final_rate_percent=final_percent,
        ),
        estimated_monthly_pension_vnd=monthly_pension,
        one_time_retirement_allowance_vnd=allowance,
        minimum_floor_applied=floor_applied,
        assumptions=assumptions,
        warnings=warnings,
        audit_steps=audit_steps,
    )
