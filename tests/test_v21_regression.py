import os
from copy import deepcopy
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

os.environ["REQUIRE_API_KEY"] = "false"

from app.engine import calculate_rate, first_pension_month_after_threshold
from app.main import app
from app.models import Sex
from app.rules import retirement_age_for_year
from app.v2_adapter import payload_evidence_issues, to_internal


CLIENT = TestClient(app)


def period(start="2011-07", end="2026-06", amount=1_000_000):
    return {
        "from_month": start,
        "to_month": end,
        "participation_status": "contributed",
        "contribution_type": "compulsory_employer",
        "basis_input_type": "total_vnd",
        "monthly_basis_vnd": amount,
        "confirmation_status": "confirmed",
        "source_row_id": "R1",
    }


def base_payload():
    return {
        "person": {"date_of_birth": "1969-01-01", "sex": "female"},
        "pension_start_month": "2026-07",
        "retirement_case": "normal",
        "contributions": [period()],
        "source_document_type": "mau_07_sbh",
        "history_confirmed": True,
        "adjustment": {"coefficient_year": 2026},
    }


@pytest.mark.parametrize(
    "threshold,expected",
    [
        (date(2026, 1, 1), date(2026, 2, 1)),
        (date(2026, 1, 31), date(2026, 2, 1)),
        (date(2026, 2, 28), date(2026, 3, 1)),
        (date(2026, 6, 21), date(2026, 7, 1)),
        (date(2026, 12, 1), date(2027, 1, 1)),
        (date(2027, 12, 31), date(2028, 1, 1)),
    ],
)
def test_first_pension_month_is_month_after_threshold(threshold, expected):
    assert first_pension_month_after_threshold(threshold) == expected


@pytest.mark.parametrize(
    "sex,year,expected",
    [
        ("male", 2021, (60, 3)),
        ("male", 2022, (60, 6)),
        ("male", 2023, (60, 9)),
        ("male", 2024, (61, 0)),
        ("male", 2025, (61, 3)),
        ("male", 2026, (61, 6)),
        ("male", 2027, (61, 9)),
        ("male", 2028, (62, 0)),
        ("female", 2021, (55, 4)),
        ("female", 2023, (56, 0)),
        ("female", 2026, (57, 0)),
        ("female", 2028, (57, 8)),
        ("female", 2030, (58, 4)),
        ("female", 2032, (59, 0)),
        ("female", 2035, (60, 0)),
    ],
)
def test_retirement_age_schedule(sex, year, expected):
    assert retirement_age_for_year(sex, year) == expected


@pytest.mark.parametrize(
    "sex,months,before,remainder",
    [
        (Sex.female, 180, Decimal("45"), Decimal("0")),
        (Sex.female, 181, Decimal("46"), Decimal("1")),
        (Sex.female, 186, Decimal("46"), Decimal("1")),
        (Sex.female, 187, Decimal("47"), Decimal("2")),
        (Sex.female, 360, Decimal("75"), Decimal("0")),
        (Sex.male, 180, Decimal("40"), Decimal("0")),
        (Sex.male, 181, Decimal("40.5"), Decimal("0.5")),
        (Sex.male, 186, Decimal("40.5"), Decimal("0.5")),
        (Sex.male, 187, Decimal("41"), Decimal("1")),
        (Sex.male, 239, Decimal("45"), Decimal("1")),
        (Sex.male, 240, Decimal("45"), Decimal("0")),
        (Sex.male, 246, Decimal("46"), Decimal("1")),
        (Sex.male, 247, Decimal("47"), Decimal("2")),
        (Sex.male, 420, Decimal("75"), Decimal("0")),
    ],
)
def test_rate_rounding_month_remainder(sex, months, before, remainder):
    actual_before, actual_remainder, actual_after = calculate_rate(sex, months, Decimal("0"))
    assert actual_before == before
    assert actual_remainder == remainder
    assert actual_after == before


@pytest.mark.parametrize(
    "mutation,code",
    [
        (lambda p: p.update(history_confirmed=False), "HISTORY_NOT_CONFIRMED"),
        (lambda p: p["contributions"][0].update(confirmation_status="unconfirmed"), "CONTRIBUTION_ROW_NOT_CONFIRMED"),
        (lambda p: p["adjustment"].update(coefficient_year=2025), "COEFFICIENT_YEAR_UNAVAILABLE"),
        (lambda p: p["adjustment"].update(salary_coefficients={"2025": 1}), "CUSTOM_COEFFICIENTS_NOT_ALLOWED"),
        (lambda p: p["contributions"][0].update(basis_components={"main_salary_vnd": 1}), "BASIS_COMPONENTS_NOT_AUTOMATED"),
    ],
)
def test_evidence_gate_rejects_uncontrolled_input(mutation, code):
    payload = base_payload()
    mutation(payload)
    assert code in {item["code"] for item in payload_evidence_issues(payload)}


def nd154_payload():
    payload = base_payload()
    payload["early_retirement_policy"] = {
        "policy_code": "nd154_2025_streamlining",
        "legal_document_number": "154/2025/NĐ-CP",
        "approved_by_competent_authority": True,
        "no_reduction_confirmed": True,
        "confirmation_status": "confirmed",
    }
    return payload


@pytest.mark.parametrize(
    "field,code",
    [
        ("approved_by_competent_authority", "DECREE_154_AUTHORITY_APPROVAL_REQUIRED"),
        ("no_reduction_confirmed", "DECREE_154_NO_REDUCTION_CONFIRMATION_REQUIRED"),
        ("confirmation_status", "DECREE_154_EVIDENCE_NOT_CONFIRMED"),
    ],
)
def test_nd154_requires_confirmed_evidence(field, code):
    payload = nd154_payload()
    payload["early_retirement_policy"][field] = False if field != "confirmation_status" else "unconfirmed"
    assert code in {item["code"] for item in payload_evidence_issues(payload)}


def test_nd154_calculate_is_blocked_when_evidence_is_false():
    payload = nd154_payload()
    payload["early_retirement_policy"]["approved_by_competent_authority"] = False
    response = CLIENT.post("/v1/calculatePension", json=payload)
    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == "DECREE_154_AUTHORITY_APPROVAL_REQUIRED"


def test_validate_returns_gap_details_and_issue():
    payload = base_payload()
    payload["contributions"] = [
        period("2020-01", "2020-03"),
        {**period("2020-05", "2020-06"), "source_row_id": "R2"},
    ]
    response = CLIENT.post("/v1/validateContributionHistory", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["valid_for_calculation"] is False
    assert body["gaps"] == [{"from_month": "2020-04", "to_month": "2020-04", "months": 1}]
    assert "UNDECLARED_GAP" in {issue["code"] for issue in body["issues"]}


def test_validate_returns_overlap_details_and_issue():
    payload = base_payload()
    payload["contributions"] = [
        period("2020-01", "2020-03"),
        {**period("2020-03", "2020-04"), "source_row_id": "R2"},
    ]
    body = CLIENT.post("/v1/validateContributionHistory", json=payload).json()
    assert body["valid_for_calculation"] is False
    assert body["overlaps"] == ["2020-03 (dòng 1, 2)"]
    assert "OVERLAPPING_MONTH" in {issue["code"] for issue in body["issues"]}


def test_validate_returns_unconfirmed_history_as_business_issue():
    payload = base_payload()
    payload["history_confirmed"] = False
    body = CLIENT.post("/v1/validateContributionHistory", json=payload).json()
    assert body["valid_for_calculation"] is False
    assert body["issues"][0]["code"] == "HISTORY_NOT_CONFIRMED"


def test_professional_seniority_percent_is_converted_by_backend():
    payload = base_payload()
    payload["contributions"] = [{
        "from_month": "2011-07", "to_month": "2026-06",
        "participation_status": "contributed",
        "contribution_type": "compulsory_state",
        "basis_input_type": "mau_07_sbh_components",
        "confirmation_status": "confirmed",
        "source_row_id": "TN-01",
        "source_text": "TN nghề 10%",
        "sbh_components": {
            "unit": "coefficient", "base_value": 4,
            "position_allowance": 0.4,
            "seniority_beyond_frame_allowance": 0.2,
            "professional_seniority_percent": 10,
        },
    }]
    response = CLIENT.post("/v1/calculatePension", json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    audit = body["basis_component_audit"][0]
    assert Decimal(audit["professional_seniority_allowance"]) == Decimal("0.46")
    assert audit["professional_seniority_percent"] == "10"
    assert body["source_trace"][0]["source_text"] == "TN nghề 10%"


def test_professional_seniority_percent_and_amount_cannot_be_combined():
    payload = base_payload()
    payload["contributions"][0].update({
        "basis_input_type": "mau_07_sbh_components",
        "monthly_basis_vnd": None,
        "contribution_type": "compulsory_state",
        "sbh_components": {
            "unit": "coefficient", "base_value": 4,
            "professional_seniority_allowance": 0.4,
            "professional_seniority_percent": 10,
        },
    })
    codes = {item["code"] for item in payload_evidence_issues(payload)}
    assert "PROFESSIONAL_SENIORITY_DUPLICATE_INPUT" in codes


def test_minimum_floor_is_applied_only_when_explicitly_confirmed():
    payload = base_payload()
    payload["transitional_minimum_floor_eligible"] = True
    payload["reference_level_vnd"] = 2_340_000
    response = CLIENT.post("/v1/calculatePension", json=payload)
    assert response.status_code == 200, response.text
    assert response.json()["minimum_floor_applied"] is True
    assert response.json()["estimated_monthly_pension_vnd"] == "2340000.0"


def test_missing_reference_level_is_reported_by_validation():
    payload = base_payload()
    payload["transitional_minimum_floor_eligible"] = True
    body = CLIENT.post("/v1/validateContributionHistory", json=payload).json()
    assert body["valid_for_calculation"] is False
    assert "REFERENCE_LEVEL_REQUIRED" in {issue["code"] for issue in body["issues"]}


def reduced_payload(dob, impairment):
    payload = base_payload()
    payload["person"] = {"date_of_birth": dob, "sex": "male"}
    payload["retirement_case"] = "reduced_capacity"
    payload["impairment_percent"] = impairment
    payload["impairment_assessment_month"] = "2026-06"
    payload["contributions"] = [period("2006-07", "2026-06", 10_000_000)]
    return payload


def test_reduced_capacity_61_percent_allows_at_most_five_year_branch():
    payload = reduced_payload("1969-01-01", 61)
    response = CLIENT.post("/v1/calculatePension", json=payload)
    assert response.status_code == 200, response.text
    assert 0 < response.json()["pension_rate"]["early_retirement_months"] <= 60


def test_reduced_capacity_81_percent_allows_ten_year_branch():
    payload = reduced_payload("1974-01-01", 81)
    response = CLIENT.post("/v1/calculatePension", json=payload)
    assert response.status_code == 200, response.text
    assert 60 < response.json()["pension_rate"]["early_retirement_months"] <= 120


def test_reduced_capacity_requires_assessment_month():
    payload = reduced_payload("1969-01-01", 61)
    payload.pop("impairment_assessment_month")
    body = CLIENT.post("/v1/validateContributionHistory", json=payload).json()
    assert body["valid_for_calculation"] is False
    assert "IMPAIRMENT_ASSESSMENT_MONTH_REQUIRED" in {issue["code"] for issue in body["issues"]}


def test_reduced_capacity_cannot_start_before_month_after_assessment():
    payload = reduced_payload("1969-01-01", 61)
    payload["impairment_assessment_month"] = "2026-07"
    response = CLIENT.post("/v1/calculatePension", json=payload)
    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == "PENSION_START_BEFORE_IMPAIRMENT_ASSESSMENT"


def test_response_contains_legal_references_and_correct_normal_start_month():
    body = CLIENT.post("/v1/calculatePension", json=base_payload()).json()
    assert body["earliest_normal_pension_start_month"] == "2025-10"
    documents = {item["document"] for item in body["legal_references"]}
    assert "Luật Bảo hiểm xã hội số 41/2024/QH15" in documents
    assert "Thông tư 12/2025/TT-BNV" in documents


def test_one_time_allowance_has_before_after_breakdown():
    payload = base_payload()
    payload["contributions"] = [
        period("1990-01", "1994-12", 10_000_000),
        {**period("1995-01", "2026-06", 10_000_000), "source_row_id": "R2"},
    ]
    response = CLIENT.post("/v1/calculatePension", json=payload)
    assert response.status_code == 200, response.text
    allowance = response.json()["one_time_retirement_allowance"]
    assert allowance["eligible"] is True
    assert allowance["total_excess_months"] == 78
    assert Decimal(allowance["total_allowance_vnd"]) > 0


def test_adapter_does_not_turn_missing_impairment_into_zero():
    request = to_internal(base_payload())
    assert request.impairment_percent is None
