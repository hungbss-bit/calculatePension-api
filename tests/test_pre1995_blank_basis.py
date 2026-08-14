from app.v2_adapter import to_internal, validate_v2_payload
from app.engine import validate_request


def test_pre1995_zeroed_sbh_components_are_duration_only():
    payload = {
        "person": {"date_of_birth": "1971-12-07", "sex": "female"},
        "pension_start_month": "2026-06",
        "retirement_case": "normal",
        "contributions": [{
            "from_month": "1993-06",
            "to_month": "1994-12",
            "participation_status": "contributed",
            "contribution_type": "compulsory_state",
            "basis_input_type": "mau_07_sbh_components",
            "sbh_components": {
                "unit": "coefficient",
                "base_value": "0",
                "position_allowance": "0",
                "seniority_beyond_frame_allowance": "0",
                "professional_seniority_allowance": "0",
                "regional_allowance": "0",
                "other_allowance": "0",
                "reelection_allowance": "0"
            }
        }]
    }
    validate_v2_payload(payload)
    req = to_internal(payload)
    row = req.contributions[0]
    assert row.participation_status.value == "credited_duration_only"
    assert row.duration_only_reason.value == "pre1995_no_salary_or_living_allowance"
    assert row.basis_input_type is None
    assert row.sbh_components is None
    diag = validate_request(req)
    assert diag.response.validation is True, diag.issues


def test_pre1995_blank_basis_validation_is_calculable_and_not_need_data():
    # This guards the BAU_154 failure mode: a confirmed pre-1995 period with
    # blank salary must not be surfaced to GPT as missing critical data.
    from app.v2_adapter import to_internal
    from app.engine import validate_request
    payload = {
        "person": {"date_of_birth": "1970-10-21", "sex": "female"},
        "pension_start_month": "2026-07",
        "retirement_case": "normal",
        "benefit_calculation_scope": "pension_and_one_time_allowance",
        "contributions": [
            {"from_month":"1990-08","to_month":"1993-03","participation_status":"contributed",
             "contribution_type":"compulsory_state", "basis_input_type":"total_vnd",
             "monthly_basis_vnd":None},
            {"from_month":"1993-04","to_month":"1994-12","participation_status":"contributed",
             "contribution_type":"compulsory_state", "basis_input_type":"total_vnd",
             "monthly_basis_vnd":None},
            {"from_month":"1995-01","to_month":"1995-12","participation_status":"contributed",
             "contribution_type":"compulsory_state", "basis_input_type":"monthly_basis_vnd",
             "monthly_basis_vnd":"1000000"},
        ],
        "early_retirement_policy": {"policy_code":"nd154_2025_streamlining"}
    }
    req = to_internal(payload)
    diag = validate_request(req)
    assert diag.response.validation is True
    assert sum(1 for c in req.contributions if c.participation_status.value == "credited_duration_only") == 2
