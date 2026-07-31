from __future__ import annotations

import os
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.engine import BusinessError, calculate, validate_request
from app.main import app
from app.models import PensionCalculationRequest


@pytest.fixture(autouse=True)
def disable_auth(monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("CALCULATEPENSION_API_KEY", raising=False)
    monkeypatch.delenv("X_API_KEY", raising=False)
    monkeypatch.setenv("REQUIRE_API_KEY", "false")


def monthly_period(start: str, end: str, amount: int = 10_000_000, **extra):
    row = {
        "from_month": start,
        "to_month": end,
        "participation_status": "contributed",
        "contribution_type": "compulsory_employer",
        "basis_input_type": "monthly_basis_vnd",
        "monthly_basis_vnd": amount,
    }
    row.update(extra)
    return row


def make_request(contributions, **overrides):
    payload = {
        "person": {"date_of_birth": "1969-01-01", "sex": "female"},
        "pension_start_month": "2026-02",
        "retirement_case": "normal",
        "retirement_policy": "none",
        "contributions": contributions,
        "retirement_age_eligible_month": "2026-01",
        "benefit_calculation_scope": "pension_and_one_time_allowance",
    }
    payload.update(overrides)
    return PensionCalculationRequest.model_validate(payload)


def test_validate_accepts_continuous_history():
    request = make_request([monthly_period("2011-01", "2026-01")])
    result = validate_request(request).response
    assert result.validation is True
    assert result.normalized_summary.total_contribution_months == 181
    assert result.normalized_summary.excluded_bhtn_months == 0


def test_overlap_is_rejected():
    request = make_request(
        [
            monthly_period("2011-01", "2020-12"),
            monthly_period("2020-12", "2026-01"),
        ]
    )
    result = validate_request(request).response
    assert result.validation is False
    assert any("OVERLAPPING_MONTH" in warning for warning in result.warnings)


def test_undeclared_gap_is_rejected():
    request = make_request(
        [
            monthly_period("2011-01", "2015-12"),
            monthly_period("2016-02", "2026-01"),
        ]
    )
    result = validate_request(request).response
    assert result.validation is False
    assert any("UNDECLARED_GAP" in warning for warning in result.warnings)


def test_explicit_not_participating_gap_is_valid_and_excluded():
    request = make_request(
        [
            monthly_period("2011-01", "2015-12"),
            {
                "from_month": "2016-01",
                "to_month": "2016-01",
                "participation_status": "not_participating",
            },
            monthly_period("2016-02", "2026-01"),
        ]
    )
    result = validate_request(request).response
    assert result.validation is True
    assert result.normalized_summary.excluded_bhtn_months == 1


def test_pre1995_contributed_excluded_without_basis_is_valid():
    request = make_request(
        [
            {
                "from_month": "1994-01",
                "to_month": "1994-12",
                "participation_status": "contributed",
                "contribution_type": "compulsory_state",
                "average_inclusion": "excluded",
                "average_exclusion_reason": "pre1995_policy",
            },
            monthly_period("1995-01", "2026-01"),
        ]
    )
    result = validate_request(request).response
    assert result.validation is True
    assert result.normalized_summary.total_contribution_months == 385
    assert any("trước 01/1995" in warning for warning in result.warnings)


def test_mixed_basis_is_rejected():
    row = monthly_period("2011-01", "2026-01")
    row["sbh_components"] = {"unit": "vnd", "base_value": 1_000_000}
    request = make_request([row])
    result = validate_request(request).response
    assert result.validation is False
    assert any("EXACTLY_ONE_BASIS_REQUIRED" in warning for warning in result.warnings)


def test_calculation_returns_schema_fields():
    request = make_request([monthly_period("2011-01", "2026-01")])
    result = calculate(request)
    assert result.total_months == 181
    assert result.average_salary > 0
    assert result.estimated_pension > 0
    assert result.replacement_rate == result.rate_after_reduction
    assert result.one_time_retirement_allowance.eligible is False


def test_one_time_allowance_one_excess_month_before_age():
    request = make_request(
        [monthly_period("1995-01", "2025-01")],
        retirement_age_eligible_month="2025-09",
    )
    result = calculate(request)
    allowance = result.one_time_retirement_allowance
    assert result.total_months == 361
    assert allowance.eligible is True
    assert allowance.total_excess_months == 1
    assert allowance.excess_before_retirement_age_months == 1
    assert allowance.excess_after_retirement_age_months == 0
    expected = round(result.average_salary * 0.5 / 12)
    assert allowance.standard_allowance_amount == pytest.approx(expected, abs=1)


def test_one_time_allowance_splits_before_and_after_age():
    request = make_request(
        [
            monthly_period("1995-01", "2025-05"),
            monthly_period(
                "2025-06",
                "2025-12",
                after_retirement_age_period=True,
            ),
        ],
        person={"date_of_birth": "1968-09-01", "sex": "female"},
        pension_start_month="2026-02",
        retirement_age_eligible_month="2025-05",
    )
    result = calculate(request)
    allowance = result.one_time_retirement_allowance
    assert result.total_months == 372
    assert allowance.total_excess_months == 12
    assert allowance.excess_before_retirement_age_months == 5
    assert allowance.excess_after_retirement_age_months == 7
    expected_standard = round(result.average_salary * 0.5 * 5 / 12)
    expected_post = round(result.average_salary * 2 * 7 / 12)
    assert allowance.standard_allowance_amount == pytest.approx(expected_standard, abs=1)
    assert allowance.post_retirement_allowance_amount == pytest.approx(expected_post, abs=1)


def test_decree_154_has_no_early_reduction():
    request = make_request(
        [monthly_period("2011-01", "2025-12")],
        person={"date_of_birth": "1973-01-01", "sex": "female"},
        pension_start_month="2026-02",
        retirement_policy="decree_154_streamlining",
        retirement_age_eligible_month="2026-01",
    )
    result = calculate(request)
    assert result.early_retirement_months > 0
    assert result.early_retirement_reduction == 0
    assert result.rate_before_early_reduction == result.rate_after_reduction


def test_reduced_capacity_reduces_rate():
    request = make_request(
        [monthly_period("2006-01", "2025-12")],
        person={"date_of_birth": "1970-01-01", "sex": "male"},
        pension_start_month="2026-02",
        retirement_case="reduced_capacity",
        impairment_percent=81,
        retirement_age_eligible_month="2021-07",
    )
    result = calculate(request)
    assert result.total_months == 240
    assert result.early_retirement_months > 0
    assert result.early_retirement_reduction > 0
    assert result.rate_after_reduction < result.rate_before_early_reduction


def test_api_returns_400_error_response_for_invalid_payload():
    client = TestClient(app)
    response = client.post(
        "/v1/validateContributionHistory",
        json={
            "person": {"date_of_birth": "1969-01-01"},
            "pension_start_month": "2026-02",
            "retirement_case": "normal",
            "contributions": [monthly_period("2011-01", "2026-01")],
        },
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "REQUEST_VALIDATION_ERROR"
    assert "person.sex" in body["fields"]


def test_api_calculate_revalidates_and_returns_business_error():
    client = TestClient(app)
    payload = make_request(
        [
            monthly_period("2011-01", "2020-12"),
            monthly_period("2020-12", "2026-01"),
        ]
    ).model_dump(mode="json")
    response = client.post("/v1/calculatePension", json=payload)
    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "CONTRIBUTION_HISTORY_INVALID"


def test_openapi_operation_ids_match_action_schema():
    client = TestClient(app)
    schema = client.get("/openapi.json").json()
    assert schema["paths"]["/v1/validateContributionHistory"]["post"]["operationId"] == "validateContributionHistory"
    assert schema["paths"]["/v1/calculatePension"]["post"]["operationId"] == "calculatePension"


def test_voluntary_period_before_2008_is_rejected():
    request = make_request(
        [
            {
                "from_month": "2007-01",
                "to_month": "2026-01",
                "participation_status": "contributed",
                "contribution_type": "voluntary",
                "basis_input_type": "monthly_basis_vnd",
                "monthly_basis_vnd": 5_000_000,
            }
        ]
    )
    result = validate_request(request).response
    assert result.validation is False
    assert any("VOLUNTARY_PERIOD_BEFORE_2008" in warning for warning in result.warnings)


def test_auth_errors_use_error_response(monkeypatch):
    monkeypatch.setenv("REQUIRE_API_KEY", "true")
    monkeypatch.delenv("API_KEY", raising=False)
    client = TestClient(app)
    response = client.post(
        "/v1/validateContributionHistory",
        json=make_request([monthly_period("2011-01", "2026-01")]).model_dump(mode="json"),
    )
    assert response.status_code == 503
    body = response.json()
    assert body["error_code"] == "API_KEY_NOT_CONFIGURED"
    assert "detail" in body
    assert "fields" in body


def test_pension_only_omits_allowance_in_api_response():
    client = TestClient(app)
    payload = make_request(
        [monthly_period("2011-01", "2026-01")],
        benefit_calculation_scope="pension_only",
    ).model_dump(mode="json")
    response = client.post("/v1/calculatePension", json=payload)
    assert response.status_code == 200
    assert "one_time_retirement_allowance" not in response.json()


def test_retirement_age_month_mismatch_is_rejected_for_allowance():
    request = make_request(
        [monthly_period("1995-01", "2025-01")],
        retirement_age_eligible_month="2026-01",
    )
    with pytest.raises(BusinessError) as exc_info:
        calculate(request)
    assert exc_info.value.error_code == "RETIREMENT_AGE_MONTH_MISMATCH"
