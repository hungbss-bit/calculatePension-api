import os
os.environ["REQUIRE_API_KEY"]="false"
from decimal import Decimal
from fastapi.testclient import TestClient
from app.main import app
from app.v2_adapter import validate_v2_payload, to_internal
from app.engine import calculate
import yaml
from jsonschema import Draft202012Validator
from pathlib import Path


def bau_rows():
    def coeff(start,end,c):
        return {"from_month":start,"to_month":end,"participation_status":"contributed","contribution_type":"compulsory_state","basis_input_type":"mau_07_sbh_components","sbh_components":{"unit":"coefficient","base_value":c}}
    def last(start,end,base,pos,sen,over=0):
        over_amt=Decimal(str(base))*Decimal(str(over))
        prof=(Decimal(str(base))+Decimal(str(pos))+over_amt)*Decimal(str(sen))
        return {"from_month":start,"to_month":end,"participation_status":"contributed","contribution_type":"compulsory_state","basis_input_type":"mau_07_sbh_components","sbh_components":{"unit":"coefficient","base_value":base,"position_allowance":pos,"seniority_beyond_frame_allowance":str(over_amt),"professional_seniority_allowance":str(prof)}}
    return [coeff('1990-08','1994-12',1.0),coeff('1995-01','2021-06',4.0),last('2021-07','2021-08',4.98,.4,.29),last('2021-09','2022-01',4.98,.4,.29,.05),last('2022-02','2022-08',4.98,.4,.30,.05),last('2022-09','2023-01',4.98,.4,.30,.06),last('2023-02','2023-05',4.98,.4,.31,.06),last('2023-06','2023-06',5.36,.4,.31),last('2023-07','2024-01',5.36,.4,.31),last('2024-02','2024-06',5.36,.4,.32),last('2024-07','2024-12',5.36,.4,.32),last('2025-01','2025-01',5.36,.4,.32),last('2025-02','2025-11',5.36,.4,.33),last('2025-12','2026-01',5.7,.4,.33),last('2026-02','2026-06',5.7,.4,.34)]


def v2_bau():
    return {"person":{"date_of_birth":"1970-10-21","sex":"female"},"pension_start_month":"2026-07","retirement_case":"normal","contributions":bau_rows(),"source_document_type":"mau_07_sbh","history_confirmed":True,"early_retirement_policy":{"policy_code":"nd154_2025_streamlining","legal_document_number":"154/2025/NĐ-CP","approved_by_competent_authority":True,"no_reduction_confirmed":True,"confirmation_status":"confirmed"}}


def test_v2_request_validates_and_maps_nd154():
    p=v2_bau(); validate_v2_payload(p); req=to_internal(p)
    assert req.retirement_policy.value == 'decree_154_streamlining'
    assert req.retirement_case.value == 'normal'


def test_v2_bau_engine_ground_truth():
    p=v2_bau(); req=to_internal(p); r=calculate(req)
    assert r.total_months == 431
    assert r.average_salary == 19117846
    assert r.replacement_rate == 75
    assert r.early_retirement_reduction == 0
    assert r.estimated_pension == 14338385


def test_v2_http_contract_returns_v2_response():
    c=TestClient(app)
    p=v2_bau(); r=c.post('/v1/calculatePension',json=p)
    assert r.status_code == 200, r.text
    body=r.json()
    assert body['status']=='success'
    assert body['contribution_summary']['exact_duration']=='35 năm 11 tháng'
    assert body['average_basis']['basis_months_used']==60
    assert body['average_basis']['average_monthly_basis_vnd']=='19117846.0'
    assert body['pension_rate']['final_rate_percent']=='75.0'
    assert body['estimated_monthly_pension_vnd']=='14338385.0'
    assert body['early_retirement_policy_result']['policy_code']=='nd154_2025_streamlining'
    assert body['early_retirement_policy_result']['no_reduction_applied'] is True


def test_v2_adapter_pre1995_duration_only_does_not_carry_salary_basis():
    p=v2_bau()
    p["contributions"] = [
        {
            "from_month": "1993-06", "to_month": "1994-12",
            "participation_status": "credited_duration_only",
            "duration_only_reason": "pre1995_no_salary_or_living_allowance",
            "contribution_type": "compulsory_state"
        },
        *p["contributions"][1:]
    ]
    req=to_internal(p)
    first=req.contributions[0]
    assert first.participation_status.value == "credited_duration_only"
    assert first.basis_input_type is None
    assert first.monthly_basis_vnd is None
    assert first.sbh_components is None


def test_v2_response_validates_against_public_response_schema():
    p=v2_bau(); req=to_internal(p); r=calculate(req)
    body=__import__("app.v2_adapter", fromlist=["build_v2_response"]).build_v2_response(
        p, r, __import__("app.engine", fromlist=["validate_request"]).validate_request(req), req
    )
    contract=yaml.safe_load((Path(__file__).resolve().parents[1] / "contracts" / "02_API_V2.3.0.yaml").read_text(encoding="utf-8"))
    schemas=contract["components"]["schemas"]
    def resolve(obj):
        if isinstance(obj, dict) and "$ref" in obj:
            return resolve(schemas[obj["$ref"].split("/")[-1]])
        if isinstance(obj, dict): return {k:resolve(v) for k,v in obj.items()}
        if isinstance(obj, list): return [resolve(v) for v in obj]
        return obj
    Draft202012Validator(resolve(schemas["PensionResponse"])).validate(body)
