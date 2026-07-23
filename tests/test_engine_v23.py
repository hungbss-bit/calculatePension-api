from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.engine import calculate_pension, validate_contribution_history
from app.models import PensionRequest


def req(payload):
    return PensionRequest.model_validate(payload)


def base_payload(dob="1972-09-01", sex="female"):
    return {
        "person": {"date_of_birth": dob, "sex": sex},
        "pension_start_month": "2026-10",
        "source_document_type": "mau_07_sbh",
        "history_confirmed": True,
        "gaps_confirmed_as_non_contribution": True,
        "adjustment": {"coefficient_year": 2026},
    }


def confirmed_hazardous_period(from_month="2006-10", to_month="2021-09"):
    return {
        "from_month": from_month,
        "to_month": to_month,
        "participation_status": "contributed",
        "monthly_basis_vnd": 10_000_000,
        "contribution_type": "compulsory_employer",
        "coefficient_override": 1,
        "hazardous_match_status": "confirmed",
        "hazardous_catalog_code": "DM-0008",
        "hazardous_catalog_title": "Khoan khai thác đá bằng búa máy cầm tay",
        "hazardous_class": "V",
        "hazardous_legal_document": "11/2020/TT-BLĐTBXH",
        "hazardous_user_confirmed": True,
        "qualifying_hazardous": True,
        "qualifying_especially_hazardous": True,
        "confirmation_status": "confirmed",
    }


def policy(code, age_reference="normal_schedule", max_custom=None):
    data = {
        "policy_code": code,
        "legal_document_number": {
            "nd154_2025_streamlining": "154/2025/NĐ-CP",
            "nd178_2024_nd67_2025_restructuring": "178/2024/NĐ-CP; 67/2025/NĐ-CP",
            "nd177_2024_non_reappointment": "177/2024/NĐ-CP",
            "other_no_reduction": "QD-OTHER",
        }[code],
        "age_reference": age_reference,
        "competent_authority_decision_number": "123/QĐ-UBND",
        "competent_authority_decision_date": "2026-09-01",
        "approved_by_competent_authority": True,
        "no_reduction_confirmed": True,
        "confirmation_status": "confirmed",
    }
    if max_custom:
        data["custom_maximum_early_months"] = max_custom
    return data


def test_hazardous_flag_requires_user_confirmation_and_catalog_reference():
    with pytest.raises(ValidationError):
        req({
            **base_payload(),
            "retirement_case": "hazardous_or_special_region",
            "contributions": [{
                "from_month": "2006-10", "to_month": "2021-09",
                "monthly_basis_vnd": 10_000_000,
                "contribution_type": "compulsory_employer",
                "qualifying_hazardous": True,
            }],
        })


def test_candidate_hazardous_period_blocks_hazardous_calculation():
    payload = {
        **base_payload(),
        "retirement_case": "hazardous_or_special_region",
        "contributions": [{
            "from_month": "2006-10", "to_month": "2026-09",
            "monthly_basis_vnd": 10_000_000,
            "contribution_type": "compulsory_employer",
            "hazardous_match_status": "candidate",
            "hazardous_catalog_code": "DM-0008",
            "hazardous_catalog_title": "Khoan khai thác đá bằng búa máy cầm tay",
        }],
    }
    result = calculate_pension(req(payload))
    assert result.status == "needs_more_data"
    assert any(i.code == "HAZARDOUS_PERIOD_NOT_CONFIRMED" for i in result.history_validation.issues)


def test_confirmed_hazardous_periods_are_counted_and_audited():
    payload = {
        **base_payload(dob="1975-09-01"),
        "retirement_case": "hazardous_or_special_region",
        "contributions": [
            confirmed_hazardous_period(),
            {
                "from_month": "2021-10", "to_month": "2026-09",
                "monthly_basis_vnd": 10_000_000,
                "contribution_type": "compulsory_employer",
                "coefficient_override": 1,
            },
        ],
    }
    result = calculate_pension(req(payload))
    assert result.hazardous_summary.confirmed_hazardous_months == 180
    assert result.hazardous_summary.confirmed_especially_hazardous_months == 180
    assert result.hazardous_summary.exact_hazardous_duration == "15 năm 0 tháng"
    assert result.hazardous_summary.confirmed_periods[0].catalog_code == "DM-0008"


def test_nd154_normal_schedule_no_early_reduction():
    payload = {
        **base_payload(),
        "retirement_case": "policy_no_reduction",
        "early_retirement_policy": policy("nd154_2025_streamlining"),
        "contributions": [{
            "from_month": "2006-10", "to_month": "2026-09",
            "monthly_basis_vnd": 10_000_000,
            "contribution_type": "compulsory_employer",
            "coefficient_override": 1,
        }],
    }
    result = calculate_pension(req(payload))
    assert result.status == "eligible"
    assert result.early_retirement_policy_result.no_reduction_applied is True
    assert result.early_retirement_policy_result.early_retirement_months <= 60
    assert result.pension_rate.early_retirement_reduction_percent == Decimal("0")
    assert result.estimated_monthly_pension_vnd is not None


def test_nd154_hazardous_schedule_requires_180_confirmed_months():
    payload = {
        **base_payload(dob="1975-09-01"),
        "retirement_case": "policy_no_reduction",
        "early_retirement_policy": policy(
            "nd154_2025_streamlining", "hazardous_schedule"
        ),
        "contributions": [
            confirmed_hazardous_period(),
            {
                "from_month": "2021-10", "to_month": "2026-09",
                "monthly_basis_vnd": 10_000_000,
                "contribution_type": "compulsory_employer",
                "coefficient_override": 1,
            },
        ],
    }
    result = calculate_pension(req(payload))
    assert result.status == "eligible"
    assert result.hazardous_summary.confirmed_hazardous_months == 180
    assert result.early_retirement_policy_result.age_reference.value == "hazardous_schedule"
    assert result.pension_rate.early_retirement_reduction_percent == Decimal("0")


def test_nd178_normal_schedule_allows_over_five_to_ten_years_with_decision():
    payload = {
        **base_payload(dob="1973-01-01", sex="male"),
        "retirement_case": "policy_no_reduction",
        "early_retirement_policy": policy(
            "nd178_2024_nd67_2025_restructuring"
        ),
        "contributions": [{
            "from_month": "2006-10", "to_month": "2026-09",
            "monthly_basis_vnd": 10_000_000,
            "contribution_type": "compulsory_employer",
            "coefficient_override": 1,
        }],
    }
    result = calculate_pension(req(payload))
    assert result.status == "eligible"
    assert 60 < result.early_retirement_policy_result.early_retirement_months <= 120
    assert result.early_retirement_policy_result.maximum_early_months == 120
    assert result.pension_rate.early_retirement_reduction_percent == Decimal("0")


def test_nd177_requires_complete_approved_evidence():
    evidence = policy("nd177_2024_non_reappointment")
    evidence["approved_by_competent_authority"] = False
    evidence["competent_authority_decision_number"] = None
    payload = {
        **base_payload(),
        "retirement_case": "policy_no_reduction",
        "early_retirement_policy": evidence,
        "contributions": [{
            "from_month": "2006-10", "to_month": "2026-09",
            "monthly_basis_vnd": 10_000_000,
            "contribution_type": "compulsory_employer",
            "coefficient_override": 1,
        }],
    }
    result = calculate_pension(req(payload))
    assert result.status == "needs_more_data"
    assert "early_retirement_policy.approved_by_competent_authority" in result.eligibility.missing_fields
    assert "early_retirement_policy.competent_authority_decision_number" in result.eligibility.missing_fields


def test_armed_forces_remains_out_of_scope_manual_review():
    payload = {
        **base_payload(),
        "retirement_case": "armed_forces",
        "contributions": [{
            "from_month": "2006-10", "to_month": "2026-09",
            "monthly_basis_vnd": 10_000_000,
            "contribution_type": "compulsory_employer",
            "coefficient_override": 1,
        }],
    }
    result = calculate_pension(req(payload))
    assert result.status == "manual_review"
    assert result.estimated_monthly_pension_vnd is None
