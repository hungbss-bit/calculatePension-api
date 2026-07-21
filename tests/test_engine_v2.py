from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.engine import calculate_pension, validate_contribution_history
from app.models import PensionRequest, PensionRegime


def req(payload):
    return PensionRequest.model_validate(payload)


def coeffs(start, end):
    return {year: 1 for year in range(start, end + 1)}


def test_reference_female_30_years_2026():
    result = calculate_pension(req({
        "person": {"date_of_birth": "1969-09-01", "sex": "female"},
        "pension_start_month": "2026-10",
        "retirement_case": "normal",
        "source_document_type": "mau_07_sbh",
        "history_confirmed": True,
        "contributions": [{
            "from_month": "1996-10", "to_month": "2026-09",
            "monthly_basis_vnd": 10_800_000,
            "contribution_type": "compulsory_employer",
            "source_row_id": "1",
        }],
        "adjustment": {"coefficient_year": 2026},
    }))
    assert result.status == "eligible"
    assert result.contribution_summary.total_months == 360
    assert result.pension_rate.final_rate_percent == Decimal("75")
    assert result.average_basis.amount_vnd == Decimal("24628500")
    assert result.estimated_monthly_pension_vnd == Decimal("18471375")
    assert result.history_validation.valid_for_calculation is True


def test_reduced_capacity_reduction_uses_retirement_year_age():
    table = coeffs(2005, 2025)
    result = calculate_pension(req({
        "person": {"date_of_birth": "1970-09-30", "sex": "female"},
        "pension_start_month": "2025-10",
        "retirement_case": "reduced_capacity",
        "impairment_percent": 81,
        "impairment_assessment_month": "2025-09",
        "contributions": [{
            "from_month": "2005-10", "to_month": "2025-09",
            "monthly_basis_vnd": 10_000_000,
            "contribution_type": "compulsory_employer",
        }],
        "adjustment": {
            "coefficient_year": 2025,
            "salary_coefficients": table,
            "voluntary_income_coefficients": table,
        },
    }))
    assert result.status == "eligible"
    assert result.pension_rate.early_retirement_months == 20
    assert result.pension_rate.early_retirement_reduction_percent == Decimal("3")
    assert result.pension_rate.base_rate_percent == Decimal("55")
    assert result.pension_rate.final_rate_percent == Decimal("52")


def test_mixed_10_compulsory_5_voluntary_uses_voluntary_policy():
    result = calculate_pension(req({
        "person": {"date_of_birth": "1969-09-01", "sex": "female"},
        "pension_start_month": "2026-10",
        "retirement_case": "normal",
        "contributions": [
            {"from_month": "2011-10", "to_month": "2021-09", "monthly_basis_vnd": 8_000_000, "contribution_type": "compulsory_employer"},
            {"from_month": "2021-10", "to_month": "2026-09", "monthly_basis_vnd": 8_000_000, "contribution_type": "voluntary"},
        ],
        "adjustment": {"coefficient_year": 2026},
    }))
    assert result.status == "eligible"
    assert result.eligibility.regime == PensionRegime.mixed_voluntary_policy
    assert result.contribution_summary.compulsory_months == 120
    assert result.pension_rate.base_rate_percent == Decimal("45")


def test_mixed_15_compulsory_5_voluntary_uses_compulsory_policy_and_total_rate():
    result = calculate_pension(req({
        "person": {"date_of_birth": "1969-09-01", "sex": "female"},
        "pension_start_month": "2026-10",
        "retirement_case": "normal",
        "contributions": [
            {"from_month": "2006-10", "to_month": "2021-09", "monthly_basis_vnd": 8_000_000, "contribution_type": "compulsory_employer"},
            {"from_month": "2021-10", "to_month": "2026-09", "monthly_basis_vnd": 8_000_000, "contribution_type": "voluntary"},
        ],
        "adjustment": {"coefficient_year": 2026},
    }))
    assert result.status == "eligible"
    assert result.eligibility.regime == PensionRegime.mixed_compulsory_policy
    assert result.contribution_summary.total_months == 240
    assert result.pension_rate.base_rate_percent == Decimal("55")


def test_hazardous_requires_15_years_compulsory_not_total_only():
    result = calculate_pension(req({
        "person": {"date_of_birth": "1973-01-01", "sex": "female"},
        "pension_start_month": "2026-10",
        "retirement_case": "hazardous_or_special_region",
        "hazardous_or_special_region_months": 180,
        "contributions": [
            {"from_month": "2011-10", "to_month": "2021-09", "monthly_basis_vnd": 8_000_000, "contribution_type": "compulsory_employer"},
            {"from_month": "2021-10", "to_month": "2026-09", "monthly_basis_vnd": 8_000_000, "contribution_type": "voluntary"},
        ],
        "adjustment": {"coefficient_year": 2026},
    }))
    assert result.status == "not_eligible"
    assert any("180 tháng BHXH bắt buộc" in reason for reason in result.eligibility.reasons)
    assert result.estimated_monthly_pension_vnd is None


def test_unconfirmed_gap_blocks_calculation():
    payload = {
        "person": {"date_of_birth": "1969-09-01", "sex": "female"},
        "pension_start_month": "2026-10",
        "retirement_case": "normal",
        "contributions": [
            {"from_month": "2006-09", "to_month": "2015-09", "monthly_basis_vnd": 8_000_000, "contribution_type": "compulsory_employer"},
            {"from_month": "2015-11", "to_month": "2026-09", "monthly_basis_vnd": 8_000_000, "contribution_type": "compulsory_employer"},
        ],
        "adjustment": {"coefficient_year": 2026},
    }
    result = calculate_pension(req(payload))
    assert result.status == "needs_more_data"
    assert result.error_code == "CONTRIBUTION_HISTORY_INVALID"
    assert result.history_validation.gaps[0].from_month == "2015-10"

    payload["gaps_confirmed_as_non_contribution"] = True
    validated = validate_contribution_history(req(payload))
    assert validated.valid_for_calculation is True


def test_overlap_blocks_as_business_status_not_http_error():
    result = calculate_pension(req({
        "person": {"date_of_birth": "1969-09-01", "sex": "female"},
        "pension_start_month": "2026-10",
        "retirement_case": "normal",
        "contributions": [
            {"from_month": "2010-01", "to_month": "2020-12", "monthly_basis_vnd": 8_000_000, "contribution_type": "compulsory_employer"},
            {"from_month": "2020-12", "to_month": "2026-09", "monthly_basis_vnd": 9_000_000, "contribution_type": "compulsory_employer"},
        ],
        "adjustment": {"coefficient_year": 2026},
    }))
    assert result.status == "needs_more_data"
    assert "2020-12" in result.history_validation.overlaps


def test_salary_coefficient_source_must_be_converted_to_vnd():
    result = calculate_pension(req({
        "person": {"date_of_birth": "1969-09-01", "sex": "female"},
        "pension_start_month": "2026-10",
        "retirement_case": "normal",
        "contributions": [{
            "from_month": "2000-01", "to_month": "2026-09",
            "monthly_basis_vnd": None,
            "source_value": 3.33,
            "source_unit": "hệ số",
            "basis_input_type": "salary_coefficient",
            "contribution_type": "compulsory_state",
        }],
        "adjustment": {"coefficient_year": 2026},
    }))
    assert result.status == "needs_more_data"
    assert any(i.code == "BASIS_NOT_NORMALIZED_TO_VND" for i in result.history_validation.issues)


def test_coefficient_year_mismatch_is_needs_more_data():
    result = calculate_pension(req({
        "person": {"date_of_birth": "1969-09-01", "sex": "female"},
        "pension_start_month": "2026-10",
        "retirement_case": "normal",
        "contributions": [{
            "from_month": "2006-10", "to_month": "2026-09",
            "monthly_basis_vnd": 10_000_000,
            "contribution_type": "compulsory_employer",
        }],
        "adjustment": {"coefficient_year": 2025, "salary_coefficients": coeffs(2006, 2026), "voluntary_income_coefficients": coeffs(2006, 2026)},
    }))
    assert result.status == "needs_more_data"
    assert result.error_code == "CALCULATION_INPUT_INCOMPLETE"
    assert any("không trùng" in reason for reason in result.eligibility.reasons)


def test_state_started_before_2016_uses_only_statutory_final_period():
    result = calculate_pension(req({
        "person": {"date_of_birth": "1969-09-01", "sex": "female"},
        "pension_start_month": "2026-10",
        "retirement_case": "normal",
        "contributions": [{
            "from_month": "2000-01", "to_month": "2026-09",
            "monthly_basis_vnd": 10_000_000,
            "basis_input_type": "total_vnd",
            "contribution_type": "compulsory_state",
        }],
        "adjustment": {"coefficient_year": 2026},
    }))
    assert result.status == "eligible"
    assert result.average_basis.state_average_months_used == 72
    assert result.average_basis.amount_vnd > Decimal("10000000")


def test_one_time_allowance_uses_explicit_eligibility_month():
    result = calculate_pension(req({
        "person": {"date_of_birth": "1969-09-01", "sex": "female"},
        "pension_start_month": "2026-10",
        "retirement_case": "normal",
        "eligibility_achieved_month": "2025-09",
        "contributions": [{
            "from_month": "1995-10", "to_month": "2026-09",
            "monthly_basis_vnd": 10_000_000,
            "contribution_type": "compulsory_employer",
            "coefficient_override": 1,
        }],
        "adjustment": {"coefficient_year": 2026},
    }))
    assert result.status == "eligible"
    assert result.contribution_summary.total_months == 372
    assert result.one_time_retirement_allowance_vnd == Decimal("20000000")


def test_174_months_shows_missing_payment_advisory():
    result = calculate_pension(req({
        "person": {"date_of_birth": "1969-09-01", "sex": "female"},
        "pension_start_month": "2026-10",
        "retirement_case": "normal",
        "contributions": [{
            "from_month": "2012-04", "to_month": "2026-09",
            "monthly_basis_vnd": 10_000_000,
            "contribution_type": "compulsory_employer",
        }],
        "adjustment": {"coefficient_year": 2026},
    }))
    assert result.status == "not_eligible"
    assert result.eligibility.months_short == 6
    assert result.eligibility.can_pay_missing_months_once is True


def test_explicit_not_participating_period_is_excluded_without_reconfirmation():
    result = calculate_pension(req({
        "person": {"date_of_birth": "1969-01-01", "sex": "female"},
        "pension_start_month": "2026-08",
        "retirement_case": "normal",
        "source_document_type": "mau_07_sbh",
        "history_confirmed": True,
        "contributions": [
            {
                "from_month": "2000-01", "to_month": "2009-12",
                "participation_status": "contributed",
                "monthly_basis_vnd": 10_000_000,
                "contribution_type": "compulsory_employer",
                "coefficient_override": 1,
            },
            {
                "from_month": "2010-01", "to_month": "2010-12",
                "participation_status": "not_participating",
                "source_text": "Không tham gia BHXH",
                "confirmation_status": "unconfirmed",
            },
            {
                "from_month": "2011-01", "to_month": "2015-12",
                "participation_status": "contributed",
                "monthly_basis_vnd": 10_000_000,
                "contribution_type": "compulsory_employer",
                "coefficient_override": 1,
            },
        ],
        "adjustment": {"coefficient_year": 2026},
    }))
    assert result.history_validation.valid_for_calculation is True
    assert result.contribution_summary.total_months == 180
    assert result.contribution_summary.excluded_non_participation_months == 12
    assert result.contribution_summary.average_basis_months == 180
    assert result.average_basis.average_monthly_basis_vnd == Decimal("10000000")


def test_pre_1995_duration_only_counts_time_but_not_average():
    result = calculate_pension(req({
        "person": {"date_of_birth": "1969-01-01", "sex": "female"},
        "pension_start_month": "2026-08",
        "retirement_case": "normal",
        "contributions": [
            {
                "from_month": "1990-01", "to_month": "1994-12",
                "participation_status": "credited_duration_only",
                "duration_only_reason": "pre1995_no_salary_or_living_allowance",
                "contribution_type": "compulsory_state",
                "source_text": "Thời gian công tác được công nhận, không hưởng lương/sinh hoạt phí",
            },
            {
                "from_month": "1995-01", "to_month": "2004-12",
                "participation_status": "contributed",
                "monthly_basis_vnd": 10_000_000,
                "contribution_type": "compulsory_employer",
                "coefficient_override": 1,
            },
        ],
        "adjustment": {"coefficient_year": 2026},
    }))
    assert result.status == "eligible"
    assert result.contribution_summary.total_months == 180
    assert result.contribution_summary.credited_duration_only_months == 60
    assert result.contribution_summary.average_basis_months == 120
    assert result.average_basis.average_monthly_basis_vnd == Decimal("10000000")
    assert result.pension_rate.final_rate_percent == Decimal("45")
    assert result.estimated_monthly_pension_vnd == Decimal("4500000")
    assert "10000000" in result.pension_calculation_formula


def test_actual_pre_1995_employer_salary_remains_in_average():
    result = calculate_pension(req({
        "person": {"date_of_birth": "1969-01-01", "sex": "female"},
        "pension_start_month": "2026-08",
        "retirement_case": "normal",
        "contributions": [
            {
                "from_month": "1990-01", "to_month": "1994-12",
                "participation_status": "contributed",
                "monthly_basis_vnd": 1_000_000,
                "contribution_type": "compulsory_employer",
                "coefficient_override": 1,
            },
            {
                "from_month": "1995-01", "to_month": "2004-12",
                "participation_status": "contributed",
                "monthly_basis_vnd": 10_000_000,
                "contribution_type": "compulsory_employer",
                "coefficient_override": 1,
            },
        ],
        "adjustment": {"coefficient_year": 2026},
    }))
    assert result.status == "eligible"
    assert result.contribution_summary.average_basis_months == 180
    assert result.average_basis.average_monthly_basis_vnd == Decimal("7000000")


def test_average_basis_is_explicit_before_rate_application():
    result = calculate_pension(req({
        "person": {"date_of_birth": "1969-09-01", "sex": "female"},
        "pension_start_month": "2026-10",
        "retirement_case": "normal",
        "contributions": [{
            "from_month": "2011-10", "to_month": "2026-09",
            "monthly_basis_vnd": 10_000_000,
            "contribution_type": "compulsory_employer",
            "coefficient_override": 1,
        }],
        "adjustment": {"coefficient_year": 2026},
    }))
    assert result.average_basis.amount_vnd == result.average_basis.average_monthly_basis_vnd
    assert result.pension_calculation_formula == "10000000 × 45% = 4500000 đồng/tháng"



def test_duration_only_requires_specific_legal_reason():
    with pytest.raises(ValidationError):
        req({
            "person": {"date_of_birth": "1969-01-01", "sex": "female"},
            "pension_start_month": "2026-08",
            "retirement_case": "normal",
            "contributions": [{
                "from_month": "1990-01",
                "to_month": "1994-12",
                "participation_status": "credited_duration_only",
                "contribution_type": "compulsory_state"
            }],
            "adjustment": {"coefficient_year": 2026}
        })
