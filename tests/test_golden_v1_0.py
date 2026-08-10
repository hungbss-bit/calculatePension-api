import json
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP

from app.engine import calculate
from app.models import PensionCalculationRequest

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / 'tests/golden_v1_0_manifest.json').read_text(encoding='utf-8'))


def _expected_allowance_g10():
    avg = Decimal('24267018.46965699208443271768')
    standard = (avg * Decimal(65) / Decimal(12) * Decimal('0.5')).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    post = (avg * Decimal(14) / Decimal(12) * Decimal('2')).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    return {
        'eligible': True,
        'threshold_months': 420,
        'total_excess_months': 79,
        'excess_before_retirement_age_months': 65,
        'excess_after_retirement_age_months': 14,
        'standard_allowance_amount': float(standard),
        'post_retirement_allowance_amount': float(post),
        'total_allowance_amount': float(standard + post),
        'average_basis': float(avg.quantize(Decimal('1'), rounding=ROUND_HALF_UP)),
    }


def test_all_golden_profiles_match_independent_expected_values():
    for item in MANIFEST:
        payload = json.loads((ROOT / item['request_file']).read_text(encoding='utf-8'))
        result = calculate(PensionCalculationRequest.model_validate(payload))
        expected = item['expected']
        assert result.total_months == expected['total_months'], item['id']
        assert result.average_salary == expected['average_salary'], item['id']
        assert result.replacement_rate == expected['replacement_rate'], item['id']
        assert result.estimated_pension == expected['estimated_pension'], item['id']


def test_g10_allowance_matches_independent_formula():
    payload = json.loads((ROOT / 'examples/golden_v1_0/G10.json').read_text(encoding='utf-8'))
    result = calculate(PensionCalculationRequest.model_validate(payload))
    actual = result.one_time_retirement_allowance.model_dump()
    expected = _expected_allowance_g10()
    for key, value in expected.items():
        assert actual[key] == value, key
