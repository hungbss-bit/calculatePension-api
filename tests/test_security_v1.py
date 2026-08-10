import os
from fastapi.testclient import TestClient

os.environ.setdefault('REQUIRE_API_KEY', 'false')

from app.main import app

client = TestClient(app)


def test_health_security_headers_and_version():
    r = client.get('/health')
    assert r.status_code == 200
    assert r.json()['version'] == '1.0.6'
    assert r.headers['X-Content-Type-Options'] == 'nosniff'
    assert r.headers['X-Frame-Options'] == 'DENY'
    assert r.headers['Cache-Control'] == 'no-store'


def test_oversized_body_is_rejected(monkeypatch):
    monkeypatch.setenv('MAX_REQUEST_BODY_BYTES', '16')
    from app import main
    main.MAX_REQUEST_BODY_BYTES = 16
    r = client.post('/v1/calculatePension', content=b'{' + b'x' * 100 + b'}', headers={'content-type':'application/json'})
    assert r.status_code == 413
    assert r.json()['error_code'] == 'REQUEST_BODY_TOO_LARGE'
    main.MAX_REQUEST_BODY_BYTES = 2097152


def test_api_key_required_when_enabled(monkeypatch):
    monkeypatch.setenv('REQUIRE_API_KEY', 'true')
    monkeypatch.setenv('API_KEY', 'test-secret')
    r = client.post('/v1/calculatePension', json={})
    assert r.status_code == 401
    assert r.json()['error_code'] == 'X_API_KEY_MISSING'
    monkeypatch.setenv('REQUIRE_API_KEY', 'false')
