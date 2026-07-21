from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_and_capabilities():
    assert client.get('/health').json()['version'] == '2.1.0'
    response = client.get('/v1/capabilities')
    assert response.status_code == 200
    assert response.json()['built_in_coefficient_years'] == [2026]


def test_validation_endpoint_returns_structured_result():
    payload = {
        "person": {"date_of_birth": "1969-09-01", "sex": "female"},
        "pension_start_month": "2026-10",
        "retirement_case": "normal",
        "contributions": [{
            "from_month": "2006-10", "to_month": "2026-09",
            "monthly_basis_vnd": 10000000,
            "contribution_type": "compulsory_employer"
        }]
    }
    response = client.post('/v1/validateContributionHistory', json=payload)
    assert response.status_code == 200
    assert response.json()['valid_for_calculation'] is True


def test_calculation_endpoint_returns_business_status():
    payload = {
        "person": {"date_of_birth": "1969-09-01", "sex": "female"},
        "pension_start_month": "2026-10",
        "retirement_case": "normal",
        "contributions": [
            {"from_month": "2010-01", "to_month": "2020-12", "monthly_basis_vnd": 8000000, "contribution_type": "compulsory_employer"},
            {"from_month": "2020-12", "to_month": "2026-09", "monthly_basis_vnd": 9000000, "contribution_type": "compulsory_employer"}
        ]
    }
    response = client.post('/v1/calculatePension', json=payload)
    assert response.status_code == 200
    assert response.json()['status'] == 'needs_more_data'
