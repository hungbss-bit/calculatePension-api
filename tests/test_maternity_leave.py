from __future__ import annotations

import os
from decimal import Decimal

import pytest

from app.engine import calculate, expand_records, validate_request
from app.models import PensionCalculationRequest


@pytest.fixture(autouse=True)
def disable_auth(monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("CALCULATEPENSION_API_KEY", raising=False)
    monkeypatch.delenv("X_API_KEY", raising=False)
    monkeypatch.setenv("REQUIRE_API_KEY", "false")


def make_request(contributions):
    return PensionCalculationRequest.model_validate(
        {
            "person": {"date_of_birth": "1969-01-01", "sex": "female"},
            "pension_start_month": "2026-02",
            "retirement_case": "normal",
            "retirement_policy": "none",
            "contributions": contributions,
            "retirement_age_eligible_month": "2026-01",
            "benefit_calculation_scope": "pension_only",
        }
    )


def employer_period(start: str, end: str, amount: int):
    return {
        "from_month": start,
        "to_month": end,
        "participation_status": "contributed",
        "contribution_type": "compulsory_employer",
        "basis_input_type": "monthly_basis_vnd",
        "monthly_basis_vnd": amount,
    }


def maternity_period(start: str, end: str, contribution_type: str = "compulsory_employer"):
    return {
        "from_month": start,
        "to_month": end,
        "participation_status": "credited_duration_only",
        "duration_only_reason": "maternity_leave",
        "contribution_type": contribution_type,
    }


def test_maternity_months_are_counted_and_inherit_previous_employer_basis():
    request = make_request(
        [
            employer_period("2011-01", "2020-06", 8_000_000),
            maternity_period("2020-07", "2020-12"),
            employer_period("2021-01", "2026-01", 9_000_000),
        ]
    )

    diagnostics = validate_request(request)
    assert diagnostics.response.validation is True
    assert diagnostics.response.normalized_summary.total_contribution_months == 181
    assert any("6 tháng nghỉ hưởng chế độ thai sản" in warning for warning in diagnostics.response.warnings)

    records = expand_records(request)
    maternity_rows = [
        row for row in records
        if row.duration_only_reason is not None
        and row.duration_only_reason.value == "maternity_leave"
    ]
    assert len(maternity_rows) == 6
    assert all(row.basis_vnd == Decimal("8000000") for row in maternity_rows)
    assert all(row.average_included is True for row in maternity_rows)


def test_maternity_result_matches_manual_contributed_basis_equivalent():
    maternity_request = make_request(
        [
            employer_period("2011-01", "2020-06", 8_000_000),
            maternity_period("2020-07", "2020-12"),
            employer_period("2021-01", "2026-01", 9_000_000),
        ]
    )
    manual_request = make_request(
        [
            employer_period("2011-01", "2020-06", 8_000_000),
            employer_period("2020-07", "2020-12", 8_000_000),
            employer_period("2021-01", "2026-01", 9_000_000),
        ]
    )

    maternity_result = calculate(maternity_request)
    manual_result = calculate(manual_request)

    assert maternity_result.total_months == manual_result.total_months == 181
    assert maternity_result.average_salary == manual_result.average_salary
    assert maternity_result.replacement_rate == manual_result.replacement_rate
    assert maternity_result.estimated_pension == manual_result.estimated_pension


def test_maternity_inherits_state_coefficient_basis_and_unit():
    request = make_request(
        [
            {
                "from_month": "2011-01",
                "to_month": "2020-06",
                "participation_status": "contributed",
                "contribution_type": "compulsory_state",
                "basis_input_type": "mau_07_sbh_components",
                "sbh_components": {
                    "unit": "coefficient",
                    "base_value": 3.0,
                },
            },
            maternity_period("2020-07", "2020-12", "compulsory_state"),
            {
                "from_month": "2021-01",
                "to_month": "2026-01",
                "participation_status": "contributed",
                "contribution_type": "compulsory_state",
                "basis_input_type": "mau_07_sbh_components",
                "sbh_components": {
                    "unit": "coefficient",
                    "base_value": 3.2,
                },
            },
        ]
    )

    diagnostics = validate_request(request)
    assert diagnostics.response.validation is True

    records = expand_records(request)
    june = next(row for row in records if row.month.isoformat() == "2020-06-01")
    july = next(row for row in records if row.month.isoformat() == "2020-07-01")
    december = next(row for row in records if row.month.isoformat() == "2020-12-01")

    assert july.basis_vnd == june.basis_vnd
    assert december.basis_vnd == june.basis_vnd
    assert july.component_unit == june.component_unit
    assert december.component_unit == june.component_unit


def test_maternity_without_immediately_previous_basis_is_rejected():
    request = make_request(
        [
            maternity_period("2011-01", "2011-06"),
            employer_period("2011-07", "2026-01", 9_000_000),
        ]
    )

    diagnostics = validate_request(request)
    assert diagnostics.response.validation is False
    assert any("MATERNITY_PREVIOUS_BASIS_MISSING" in warning for warning in diagnostics.response.warnings)


def test_maternity_must_not_carry_explicit_basis():
    row = maternity_period("2020-07", "2020-12")
    row["basis_input_type"] = "monthly_basis_vnd"
    row["monthly_basis_vnd"] = 8_000_000
    request = make_request(
        [
            employer_period("2011-01", "2020-06", 8_000_000),
            row,
            employer_period("2021-01", "2026-01", 9_000_000),
        ]
    )

    diagnostics = validate_request(request)
    assert diagnostics.response.validation is False
    assert any("MATERNITY_BASIS_MUST_BE_INHERITED" in warning for warning in diagnostics.response.warnings)
