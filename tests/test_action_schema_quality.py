from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
ACTION_PATH = ROOT / "GPT_ACTION_SCHEMA_V2.1_FINAL.yaml"


def action_schema():
    return yaml.safe_load(ACTION_PATH.read_text(encoding="utf-8"))


def test_action_schema_has_exactly_two_business_operations():
    schema = action_schema()
    assert set(schema["paths"]) == {
        "/v1/validateContributionHistory",
        "/v1/calculatePension",
    }


def test_action_operation_ids_are_unique_and_expected():
    schema = action_schema()
    operation_ids = [item["post"]["operationId"] for item in schema["paths"].values()]
    assert operation_ids == ["validateContributionHistory", "calculatePension"]
    assert len(operation_ids) == len(set(operation_ids))


def test_action_server_is_https_production_url():
    assert action_schema()["servers"] == [{
        "url": "https://calculatepension-api.onrender.com",
        "description": "API production trên Render",
    }]


def test_action_uses_custom_api_key_header():
    scheme = action_schema()["components"]["securitySchemes"]["CalculatePensionApiKey"]
    assert scheme["type"] == "apiKey"
    assert scheme["in"] == "header"
    assert scheme["name"] == "X-API-Key"


def test_action_version_is_2_1():
    schema = action_schema()
    assert schema["info"]["version"] == "2.1.0"
    assert schema["x-source-api-version"] == "2.4.0"


def test_action_request_requires_history_confirmation():
    request = action_schema()["components"]["schemas"]["PensionRequest"]
    assert "history_confirmed" in request["required"]
    assert request["properties"]["history_confirmed"]["default"] is False


def test_action_only_exposes_automated_retirement_cases():
    values = action_schema()["components"]["schemas"]["RetirementCase"]["enum"]
    assert values == ["normal", "reduced_capacity"]


def test_action_only_exposes_confirmed_special_policy():
    schemas = action_schema()["components"]["schemas"]
    assert schemas["EarlyRetirementPolicyCode"]["enum"] == ["nd154_2025_streamlining"]
    required = schemas["EarlyRetirementPolicyEvidence"]["required"]
    assert {"approved_by_competent_authority", "no_reduction_confirmed", "confirmation_status"} <= set(required)


def test_action_schema_has_no_dangling_local_references():
    schema = action_schema()
    components = schema["components"]["schemas"]
    missing = []

    def visit(value):
        if isinstance(value, dict):
            ref = value.get("$ref")
            if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
                name = ref.rsplit("/", 1)[-1]
                if name not in components:
                    missing.append(name)
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(schema)
    assert missing == []


def test_action_schema_includes_auditable_outputs():
    properties = action_schema()["components"]["schemas"]["PensionResponse"]["properties"]
    assert "source_trace" in properties
    assert "basis_component_audit" in properties
    assert "one_time_retirement_allowance" in properties
    assert "legal_references" in properties

