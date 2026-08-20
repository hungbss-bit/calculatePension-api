import os
os.environ['REQUIRE_API_KEY']='false'
from fastapi.testclient import TestClient
from app.main import app

def test_health_security_headers_and_v2_version():
    r=TestClient(app).get('/health')
    assert r.status_code==200
    assert r.json()['version']=='2.4.0'
    assert r.json()['action_schema_version']=='2.1.0'
    assert r.headers['X-Content-Type-Options']=='nosniff'
    assert r.headers['X-Frame-Options']=='DENY'
    assert r.headers['Cache-Control']=='no-store'

def test_version_endpoint():
    r=TestClient(app).get('/version')
    assert r.status_code==200
    assert r.json()['api_version']=='2.4.0'
    assert r.json()['action_schema_version']=='2.1.0'

def test_v2_openapi_matches_contract_version():
    r=TestClient(app).get('/openapi.json')
    assert r.status_code==200
    assert r.json()['info']['version']=='2.4.0'
    assert r.json()['paths']['/v1/validateContributionHistory']['post']['operationId']=='validateContributionHistory'
    assert r.json()['paths']['/v1/calculatePension']['post']['operationId']=='calculatePension'

def test_api_key_missing_is_rejected(monkeypatch):
    monkeypatch.setenv('REQUIRE_API_KEY', 'true')
    monkeypatch.setenv('API_KEY', 'test-secret')
    r=TestClient(app).post('/v1/validateContributionHistory',json={})
    assert r.status_code==401
    assert r.json()['error_code']=='X_API_KEY_MISSING'

def test_api_key_mismatch_is_rejected(monkeypatch):
    monkeypatch.setenv('REQUIRE_API_KEY', 'true')
    monkeypatch.setenv('API_KEY', 'test-secret')
    r=TestClient(app).post('/v1/validateContributionHistory',json={},headers={'X-API-Key':'wrong'})
    assert r.status_code==401
    assert r.json()['error_code']=='X_API_KEY_MISMATCH'

def test_api_key_match_reaches_schema_validation(monkeypatch):
    monkeypatch.setenv('REQUIRE_API_KEY', 'true')
    monkeypatch.setenv('API_KEY', 'test-secret')
    r=TestClient(app).post('/v1/validateContributionHistory',json={},headers={'X-API-Key':'test-secret'})
    assert r.status_code==422
