from decimal import Decimal

from app.engine import calculate
from app.models import PensionCalculationRequest


def state_coeff(start, end, coeff, *, pre1995=False):
    row = {
        "from_month": start,
        "to_month": end,
        "participation_status": "contributed",
        "contribution_type": "compulsory_state",
        "basis_input_type": "mau_07_sbh_components",
        "sbh_components": {"unit": "coefficient", "base_value": coeff},
    }
    if pre1995:
        row["average_inclusion"] = "excluded"
        row["average_exclusion_reason"] = "pre1995_policy"
    return row


def state_last_60(start, end, base, position, seniority, overframe=0):
    # For the official ND154 profile, the professional-seniority allowance is
    # calculated on base salary + position allowance + seniority-beyond-frame.
    subtotal = Decimal(str(base)) + Decimal(str(position))
    overframe_amount = Decimal(str(base)) * Decimal(str(overframe))
    professional = (subtotal + overframe_amount) * Decimal(str(seniority))
    return {
        "from_month": start,
        "to_month": end,
        "participation_status": "contributed",
        "contribution_type": "compulsory_state",
        "basis_input_type": "mau_07_sbh_components",
        "sbh_components": {
            "unit": "coefficient",
            "base_value": base,
            "position_allowance": position,
            "seniority_beyond_frame_allowance": str(overframe_amount),
            "professional_seniority_allowance": str(professional),
        },
    }


def test_nd154_official_ground_truth_nguyen_thi_bau():
    rows = [
        state_coeff("1990-08", "1994-12", 1.0, pre1995=True),
        state_coeff("1995-01", "2021-06", 4.0),
        state_last_60("2021-07", "2021-08", 4.98, .4, .29),
        state_last_60("2021-09", "2022-01", 4.98, .4, .29, .05),
        state_last_60("2022-02", "2022-08", 4.98, .4, .30, .05),
        state_last_60("2022-09", "2023-01", 4.98, .4, .30, .06),
        state_last_60("2023-02", "2023-05", 4.98, .4, .31, .06),
        state_last_60("2023-06", "2023-06", 5.36, .4, .31, 0),
        state_last_60("2023-07", "2024-01", 5.36, .4, .31, 0),
        state_last_60("2024-02", "2024-06", 5.36, .4, .32, 0),
        state_last_60("2024-07", "2024-12", 5.36, .4, .32, 0),
        state_last_60("2025-01", "2025-01", 5.36, .4, .32, 0),
        state_last_60("2025-02", "2025-11", 5.36, .4, .33, 0),
        state_last_60("2025-12", "2026-01", 5.7, .4, .33, 0),
        state_last_60("2026-02", "2026-06", 5.7, .4, .34, 0),
    ]
    req = PensionCalculationRequest.model_validate({
        "identity": {"so_bhxh": "2196043661"},
        "person": {"date_of_birth": "1970-10-21", "sex": "female"},
        "pension_start_month": "2026-07",
        "retirement_case": "normal",
        "retirement_policy": "decree_154_streamlining",
        "retirement_age_eligible_month": "2028-06",
        "benefit_calculation_scope": "pension_and_one_time_allowance",
        "contributions": rows,
    })
    result = calculate(req)
    assert result.total_months == 431
    assert result.average_salary == 19117846
    assert result.replacement_rate == 75
    assert result.rate_before_early_reduction == 75
    assert result.early_retirement_reduction == 0
    assert result.estimated_pension == 14338385
    allowance = result.one_time_retirement_allowance
    assert allowance.total_excess_months == 71
    assert allowance.standard_allowance_amount == 57353538
    assert allowance.total_allowance_amount == 57353538
