from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def clear_auth_env(monkeypatch):
    for name in (
        "API_KEY",
        "CALCULATEPENSION_API_KEY",
        "X_API_KEY",
        "REQUIRE_API_KEY",
        "AUTH_DIAGNOSTICS_ENABLED",
    ):
        monkeypatch.delenv(name, raising=False)


def test_api_key_with_surrounding_quotes_and_whitespace_is_normalized(monkeypatch):
    clear_auth_env(monkeypatch)
    monkeypatch.setenv("API_KEY", '  "abc123"  ')
    monkeypatch.setenv("REQUIRE_API_KEY", "true")

    response = client.get(
        "/v1/capabilities",
        headers={"X-API-Key": "  abc123  "},
    )

    assert response.status_code == 200
    assert response.json()["version"] == "2.3.0"


def test_missing_header_returns_distinct_error(monkeypatch):
    clear_auth_env(monkeypatch)
    monkeypatch.setenv("API_KEY", "abc123")
    monkeypatch.setenv("REQUIRE_API_KEY", "true")

    response = client.get("/v1/capabilities")

    assert response.status_code == 401
    assert response.json()["detail"]["error_code"] == "X_API_KEY_MISSING"


def test_wrong_header_returns_distinct_error(monkeypatch):
    clear_auth_env(monkeypatch)
    monkeypatch.setenv("API_KEY", "abc123")
    monkeypatch.setenv("REQUIRE_API_KEY", "true")

    response = client.get(
        "/v1/capabilities",
        headers={"X-API-Key": "wrong"},
    )

    assert response.status_code == 401
    assert response.json()["detail"]["error_code"] == "X_API_KEY_MISMATCH"


def test_missing_runtime_key_is_503_when_required(monkeypatch):
    clear_auth_env(monkeypatch)
    monkeypatch.setenv("REQUIRE_API_KEY", "true")

    response = client.get(
        "/v1/capabilities",
        headers={"X-API-Key": "anything"},
    )

    assert response.status_code == 503
    assert response.json()["detail"]["error_code"] == "API_KEY_NOT_CONFIGURED"


def test_auth_diagnostics_compares_runtime_and_received_key(monkeypatch):
    clear_auth_env(monkeypatch)
    monkeypatch.setenv("API_KEY", ' "abc123" ')
    monkeypatch.setenv("REQUIRE_API_KEY", "true")
    monkeypatch.setenv("AUTH_DIAGNOSTICS_ENABLED", "true")

    response = client.get(
        "/v1/authDiagnostics",
        headers={"X-API-Key": "abc123"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["configured"] is True
    assert body["configured_env_name"] == "API_KEY"
    assert body["expected_length"] == 6
    assert body["received_present"] is True
    assert body["normalized_match"] is True
    assert body["expected_fingerprint_sha256_12"] == body[
        "received_fingerprint_sha256_12"
    ]


def test_auth_diagnostics_is_disabled_by_default(monkeypatch):
    clear_auth_env(monkeypatch)

    response = client.get("/v1/authDiagnostics")

    assert response.status_code == 404
    assert response.json()["detail"]["error_code"] == "AUTH_DIAGNOSTICS_DISABLED"
