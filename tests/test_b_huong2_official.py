from app.engine import calculate
from app.models import PensionCalculationRequest


def state_coeff(start, end, coeff):
    return {
        'from_month': start, 'to_month': end,
        'participation_status': 'contributed',
        'contribution_type': 'compulsory_state',
        'basis_input_type': 'mau_07_sbh_components',
        'sbh_components': {'unit': 'coefficient', 'base_value': coeff},
    }


def test_b_huong2_official_state_salary_profile():
    rows = [
        {
            'from_month':'1987-09','to_month':'1994-12',
            'participation_status':'contributed','contribution_type':'compulsory_state',
            'average_inclusion':'excluded','average_exclusion_reason':'pre1995_policy'
        },
        state_coeff('1995-01','1997-12',1.63),
        state_coeff('1998-01','1998-12',1.73),
        state_coeff('1999-01','2004-09',2.16),
        state_coeff('2004-10','2007-11',2.96),
        state_coeff('2007-12','2008-11',3.27),
        state_coeff('2008-12','2010-11',3.27),
        state_coeff('2010-12','2011-09',3.58),
        state_coeff('2011-10','2015-09',3.66),
        state_coeff('2015-10','2018-09',3.99),
        state_coeff('2018-10','2021-09',4.32),
        state_coeff('2021-10','2024-09',4.65),
        state_coeff('2024-10','2026-07',4.98),
    ]
    req = PensionCalculationRequest.model_validate({
        'person': {'date_of_birth':'1969-07-09','sex':'female'},
        'pension_start_month':'2026-08',
        'retirement_case':'normal','retirement_policy':'none',
        'retirement_age_eligible_month':'2026-07',
        'benefit_calculation_scope':'pension_and_one_time_allowance',
        'contributions': rows,
    })
    result = calculate(req)
    assert result.total_months == 467
    assert result.average_salary == 12042800
    assert result.replacement_rate == 75
    assert result.estimated_pension == 9032100
    assert result.one_time_retirement_allowance.total_excess_months == 107
    assert result.one_time_retirement_allowance.standard_allowance_amount == 54192600
    assert result.one_time_retirement_allowance.total_allowance_amount == 54192600
