from decimal import Decimal

from app.engine import calculate
from app.v2_adapter import to_internal, validate_v2_payload


def test_blank_tn_nghe_is_zero_and_tnvk_is_kept_separate():
    # Mẫu 07/SBH giả lập: TN Nghề trống, TN VK = 8%.
    # 60 tháng: 06/2021-05/2026; hệ số được quy đổi theo mức tham chiếu tháng hưởng 06/2026.
    payload = {
        "person": {"date_of_birth": "1960-01-01", "sex": "female"},
        "pension_start_month": "2026-06",
        "retirement_case": "normal",
        "contributions": [{
            "from_month": "2011-06",
            "to_month": "2026-05",
            "participation_status": "contributed",
            "contribution_type": "compulsory_state",
            "basis_input_type": "mau_07_sbh_components",
            "sbh_components": {
                "unit": "coefficient",
                "base_value": "4.06",
                "position_allowance": "0",
                "seniority_beyond_frame_allowance": "0.3248",
                "professional_seniority_allowance": "0",
                "regional_allowance": "0",
                "other_allowance": "0",
                "reelection_allowance": "0"
            }
        }]
    }
    validate_v2_payload(payload)
    req = to_internal(payload)
    comp = req.contributions[0].sbh_components
    assert comp is not None
    assert comp.seniority_beyond_frame_allowance == Decimal("0.3248")
    assert comp.professional_seniority_allowance == Decimal("0")

    result = calculate(req)
    # (4.06 + 0.3248) * 2,340,000 = 10,260,432 VND/month.
    assert result.average_salary == 10260432
