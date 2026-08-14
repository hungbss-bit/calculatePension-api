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
