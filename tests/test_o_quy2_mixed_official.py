from app.engine import calculate
from app.models import PensionCalculationRequest


def state(start, end, coeff, pre1995=False):
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


def employer(start, end, vnd):
    return {
        "from_month": start,
        "to_month": end,
        "participation_status": "contributed",
        "contribution_type": "compulsory_employer",
        "basis_input_type": "monthly_basis_vnd",
        "monthly_basis_vnd": vnd,
    }


def test_o_quy2_official_mixed_state_employer_profile():
    rows = [
        state("1992-11", "1992-12", 262, True),
        state("1993-01", "1993-11", 1.35, True),
        state("1993-12", "1994-12", 1.47, True),
        state("1995-01", "1996-06", 1.62),
        state("1996-07", "1999-11", 1.62),
        state("1999-12", "1999-12", 1.78),
        state("2000-01", "2002-12", 1.78),
        state("2003-01", "2004-09", 1.78),
        state("2004-10", "2004-11", 2.55),
        state("2004-12", "2007-12", 3.01),
        state("2008-01", "2008-11", 3.01),
        state("2008-12", "2009-11", 3.01),
        {"from_month":"2009-12","to_month":"2009-12","participation_status":"not_participating"},
        state("2010-01", "2010-11", 3.01),
        state("2010-12", "2015-12", 3.56),
        employer("2016-01", "2016-03", 4094000),
        employer("2016-04", "2016-11", 4131000),
        employer("2016-12", "2017-03", 4428000),
        employer("2017-04", "2017-12", 4644000),
        employer("2018-01", "2019-08", 5110000),
        employer("2019-09", "2021-12", 6960000),
        employer("2022-01", "2022-11", 8397000),
        employer("2022-12", "2023-10", 9072000),
        employer("2023-11", "2026-06", 9156000),
    ]
    req = PensionCalculationRequest.model_validate({
        "identity": {"so_bhxh": "2196008859"},
        "person": {"date_of_birth":"1965-01-12", "sex":"male"},
        "pension_start_month":"2026-08",
        "retirement_case":"normal",
        "retirement_policy":"none",
        "benefit_calculation_scope":"pension_and_one_time_allowance",
        "contributions": rows,
    })
    result = calculate(req)
    assert result.total_months == 403
    assert result.average_salary == 8655801
    assert result.replacement_rate == 73
    assert result.estimated_pension == 6318735
    assert result.one_time_retirement_allowance.total_allowance_amount == 0
    assert result.calculation.trace.average_basis_months == 403
