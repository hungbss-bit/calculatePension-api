from decimal import Decimal

from app.engine import calculate, calculate_average_salary, expand_records
from app.v2_adapter import to_internal, validate_v2_payload


def _row(start, end, pct):
    return {
        "from_month": start,
        "to_month": end,
        "participation_status": "contributed",
        "contribution_type": "compulsory_state",
        "basis_input_type": "mau_07_sbh_components",
        "sbh_components": {
            "unit": "coefficient",
            "base_value": "4.06",
            "position_allowance": "0",
            "seniority_beyond_frame_allowance": "0",
            "professional_seniority_allowance": str(pct),
            "regional_allowance": "0",
            "other_allowance": "0",
            "reelection_allowance": "0",
        },
    }


def test_raw_5_to_12_percent_run_is_normalized_to_component_coefficients():
    rows = [
        _row("2018-07", "2019-06", "0.05"),
        _row("2019-07", "2020-06", "0.06"),
        _row("2020-07", "2021-06", "0.07"),
        _row("2021-07", "2022-06", "0.08"),
        _row("2022-07", "2023-06", "0.09"),
        _row("2023-07", "2024-06", "0.10"),
        _row("2024-07", "2025-06", "0.11"),
        _row("2025-07", "2026-05", "0.12"),
    ]
    history = [{
        "from_month": "1993-06", "to_month": "1994-12",
        "participation_status": "credited_duration_only",
        "duration_only_reason": "pre1995_no_salary_or_living_allowance",
        "contribution_type": "compulsory_state"
    }, {
        "from_month": "1995-01", "to_month": "2018-06",
        "participation_status": "contributed",
        "contribution_type": "compulsory_state",
        "basis_input_type": "mau_07_sbh_components",
        "sbh_components": {"unit": "coefficient", "base_value": "4.06"}
    }] + rows
    payload = {
        "person": {"date_of_birth": "1971-12-07", "sex": "female"},
        "pension_start_month": "2026-06",
        "retirement_case": "normal",
        "contributions": history,
    }
    validate_v2_payload(payload)
    req = to_internal(payload)
    comp = req.contributions[2].sbh_components
    assert comp.professional_seniority_allowance == Decimal("0.2030")
    average, _, _, _ = calculate_average_salary(req, expand_records(req))
    # Average of the 60 monthly coefficients, converted at 2,340,000 VND.
    assert average == 10442523


def test_explicit_percent_source_unit_is_supported_for_single_row():
    payload = {
        "person": {"date_of_birth": "1971-12-07", "sex": "female"},
        "pension_start_month": "2026-06",
        "retirement_case": "normal",
        "contributions": [{
            "from_month": "2025-07", "to_month": "2026-05",
            "participation_status": "contributed",
            "contribution_type": "compulsory_state",
            "basis_input_type": "mau_07_sbh_components",
            "source_unit": "percent",
            "sbh_components": {
                "unit": "coefficient", "base_value": "4.06",
                "position_allowance": "0", "seniority_beyond_frame_allowance": "0",
                "professional_seniority_allowance": "0.12",
                "regional_allowance": "0", "other_allowance": "0", "reelection_allowance": "0"
            }
        }]
    }
    validate_v2_payload(payload)
    req = to_internal(payload)
    comp = req.contributions[0].sbh_components
    assert comp.professional_seniority_allowance == Decimal("0.4872")


def test_already_normalized_03248_is_not_double_converted():
    payload = {
        "person": {"date_of_birth": "1971-12-07", "sex": "female"},
        "pension_start_month": "2026-06",
        "retirement_case": "normal",
        "contributions": [{
            "from_month": "2025-07", "to_month": "2026-05",
            "participation_status": "contributed",
            "contribution_type": "compulsory_state",
            "basis_input_type": "mau_07_sbh_components",
            "sbh_components": {
                "unit": "coefficient", "base_value": "4.06",
                "position_allowance": "0", "seniority_beyond_frame_allowance": "0.3248",
                "professional_seniority_allowance": "0",
                "regional_allowance": "0", "other_allowance": "0", "reelection_allowance": "0"
            }
        }]
    }
    validate_v2_payload(payload)
    req = to_internal(payload)
    comp = req.contributions[0].sbh_components
    assert comp.seniority_beyond_frame_allowance == Decimal("0.3248")


def test_tnvk_and_tnnghe_percent_formula_uses_correct_bases():
    payload = {
        "person": {"date_of_birth": "1970-01-01", "sex": "female"},
        "pension_start_month": "2026-06",
        "retirement_case": "normal",
        "contributions": [{
            "from_month": "2025-07", "to_month": "2026-05",
            "participation_status": "contributed",
            "contribution_type": "compulsory_state",
            "basis_input_type": "mau_07_sbh_components",
            "source_unit": "percent",
            "sbh_components": {
                "unit": "coefficient", "base_value": "4.06",
                "position_allowance": "0.20",
                "seniority_beyond_frame_allowance": "0.05",
                "professional_seniority_allowance": "0.10",
                "regional_allowance": "0", "other_allowance": "0", "reelection_allowance": "0"
            }
        }]
    }
    validate_v2_payload(payload)
    req = to_internal(payload)
    comp = req.contributions[0].sbh_components
    # TN VK = 5% x 4.06 = 0.2030
    assert comp.seniority_beyond_frame_allowance == Decimal("0.2030")
    # TN Nghề = 10% x (4.06 + 0.20 + 0.2030) = 0.4463
    assert comp.professional_seniority_allowance == Decimal("0.4463")


def test_m7_uyen_golden_core_values_with_raw_percentage_input():
    rows = [
        {"from_month":"1993-06","to_month":"1994-12","participation_status":"credited_duration_only","duration_only_reason":"pre1995_no_salary_or_living_allowance","contribution_type":"compulsory_state"},
        {"from_month":"1995-01","to_month":"2018-06","participation_status":"contributed","contribution_type":"compulsory_state","basis_input_type":"mau_07_sbh_components","sbh_components":{"unit":"coefficient","base_value":"4.06"}},
    ]
    for start, end, pct in [
        ("2018-07","2019-06","0.05"),("2019-07","2020-06","0.06"),
        ("2020-07","2021-06","0.07"),("2021-07","2022-06","0.08"),
        ("2022-07","2023-06","0.09"),("2023-07","2024-06","0.10"),
        ("2024-07","2025-06","0.11"),("2025-07","2026-05","0.12")]:
        rows.append({"from_month":start,"to_month":end,"participation_status":"contributed","contribution_type":"compulsory_state","basis_input_type":"mau_07_sbh_components","sbh_components":{"unit":"coefficient","base_value":"4.06","professional_seniority_allowance":pct}})
    payload = {
        "person": {"date_of_birth": "1971-12-07", "sex": "female"},
        "pension_start_month": "2026-06",
        "retirement_case": "normal",
        "early_retirement_policy": {
            "policy_code": "nd154_2025_streamlining",
            "legal_document_number": "154/2025/NĐ-CP",
            "age_reference": "normal_schedule",
            "approved_by_competent_authority": True,
            "no_reduction_confirmed": True,
            "confirmation_status": "confirmed"
        },
        "contributions": rows,
    }
    validate_v2_payload(payload)
    req = to_internal(payload)
    result = calculate(req)
    assert result.total_months == 396
    assert result.average_salary == 10442523
    assert result.replacement_rate == 75
    assert result.early_retirement_reduction == 0
    assert result.estimated_pension == 7831892
    assert result.one_time_retirement_allowance.total_allowance_amount == 15663785
