from decimal import Decimal

from app.engine import calculate_pension
from app.models import PensionRequest


def make_request(payload: dict) -> PensionRequest:
    return PensionRequest.model_validate(payload)


def test_female_30_years_reaches_75_percent():
    request = make_request(
        {
            "person": {"date_of_birth": "1969-09-01", "sex": "female"},
            "pension_start_month": "2026-10",
            "retirement_case": "normal",
            "contributions": [
                {
                    "from_month": "1996-10",
                    "to_month": "2026-09",
                    "monthly_basis_vnd": 10_000_000,
                    "contribution_type": "compulsory_employer",
                    "coefficient_override": 1,
                }
            ],
        }
    )
    result = calculate_pension(request)
    assert result.status == "eligible"
    assert result.pension_rate.final_rate_percent == Decimal("75")
    assert result.estimated_monthly_pension_vnd == Decimal("7500000")


def test_male_15_years_rate_is_40_percent():
    request = make_request(
        {
            "person": {"date_of_birth": "1964-01-01", "sex": "male"},
            "pension_start_month": "2026-08",
            "retirement_case": "normal",
            "contributions": [
                {
                    "from_month": "2011-08",
                    "to_month": "2026-07",
                    "monthly_basis_vnd": 10_000_000,
                    "contribution_type": "compulsory_employer",
                    "coefficient_override": 1,
                }
            ],
        }
    )
    result = calculate_pension(request)
    assert result.status == "eligible"
    assert result.pension_rate.base_rate_percent == Decimal("40")


def test_rounding_six_extra_months_to_half_year():
    request = make_request(
        {
            "person": {"date_of_birth": "1969-01-01", "sex": "female"},
            "pension_start_month": "2026-08",
            "retirement_case": "normal",
            "contributions": [
                {
                    "from_month": "2006-02",
                    "to_month": "2026-07",
                    "monthly_basis_vnd": 10_000_000,
                    "contribution_type": "compulsory_employer",
                    "coefficient_override": 1,
                }
            ],
        }
    )
    result = calculate_pension(request)
    assert result.contribution_summary.rounded_years_for_rate == Decimal("20.5")
    assert result.pension_rate.base_rate_percent == Decimal("56.0")


def test_normal_case_not_old_enough():
    request = make_request(
        {
            "person": {"date_of_birth": "1980-01-01", "sex": "female"},
            "pension_start_month": "2026-08",
            "retirement_case": "normal",
            "contributions": [
                {
                    "from_month": "2006-08",
                    "to_month": "2026-07",
                    "monthly_basis_vnd": 10_000_000,
                    "contribution_type": "compulsory_employer",
                    "coefficient_override": 1,
                }
            ],
        }
    )
    result = calculate_pension(request)
    assert result.status == "not_eligible"
    assert result.estimated_monthly_pension_vnd is None


def test_reduced_capacity_early_penalty():
    request = make_request(
        {
            "person": {"date_of_birth": "1969-01-01", "sex": "female"},
            "pension_start_month": "2022-02",
            "retirement_case": "reduced_capacity",
            "impairment_percent": 81,
            "contributions": [
                {
                    "from_month": "2002-02",
                    "to_month": "2022-01",
                    "monthly_basis_vnd": 10_000_000,
                    "contribution_type": "compulsory_employer",
                    "coefficient_override": 1,
                }
            ],
        }
    )
    result = calculate_pension(request)
    assert result.status == "eligible"
    assert result.pension_rate.early_retirement_reduction_percent > 0


def test_state_salary_before_2016_requires_converted_values():
    request = make_request(
        {
            "person": {"date_of_birth": "1969-01-01", "sex": "female"},
            "pension_start_month": "2026-08",
            "retirement_case": "normal",
            "contributions": [
                {
                    "from_month": "2000-01",
                    "to_month": "2026-07",
                    "monthly_basis_vnd": 10_000_000,
                    "contribution_type": "compulsory_state",
                }
            ],
        }
    )
    result = calculate_pension(request)
    assert result.status == "needs_more_data"
    assert result.estimated_monthly_pension_vnd is None
