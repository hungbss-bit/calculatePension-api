from __future__ import annotations
from datetime import date
from decimal import Decimal
from pathlib import Path
import json
import yaml
from jsonschema import Draft202012Validator

from .models import (
    BenefitCalculationScope, Contribution, ContributionType, DurationOnlyReason,
    Identity, PensionCalculationRequest, Person, RetirementCase, RetirementPolicy,
    ParticipationStatus, AverageInclusion, AverageExclusionReason, BasisInputType,
    SBHComponents, SbhComponentUnit, Sex
)

ROOT = Path(__file__).resolve().parent.parent
CONTRACT_PATH = ROOT / "contracts" / "02_API_V2.3.0.yaml"

with CONTRACT_PATH.open("r", encoding="utf-8") as f:
    CONTRACT = yaml.safe_load(f)

# Resolve local component references before validation.
def _resolve_refs(obj):
    if isinstance(obj, dict):
        if "$ref" in obj and obj["$ref"].startswith("#/components/schemas/"):
            name = obj["$ref"].split("/")[-1]
            return _resolve_refs(CONTRACT["components"]["schemas"][name])
        return {k: _resolve_refs(v) for k,v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_refs(v) for v in obj]
    return obj

REQUEST_SCHEMA = _resolve_refs(CONTRACT["components"]["schemas"]["PensionRequest"])
VALIDATOR = Draft202012Validator(REQUEST_SCHEMA)


def validate_v2_payload(payload: dict) -> None:
    errors = sorted(VALIDATOR.iter_errors(payload), key=lambda e: list(e.path))
    if errors:
        e = errors[0]
        path = ".".join(str(x) for x in e.path) or "request"
        raise ValueError(f"{path}: {e.message}")


def dec(v, default="0"):
    if v is None:
        return Decimal(default)
    return Decimal(str(v))


def to_internal(payload: dict) -> PensionCalculationRequest:
    p = payload["person"]
    policy = payload.get("early_retirement_policy") or {}
    policy_code = policy.get("policy_code") if policy else None
    if policy_code == "nd154_2025_streamlining":
        internal_policy = RetirementPolicy.decree_154_streamlining
    else:
        internal_policy = RetirementPolicy.none

    rc = payload.get("retirement_case", "normal")
    if rc not in {"normal", "reduced_capacity"}:
        # V2 exposes broader cases, but current engine must fail explicitly rather than reinterpret.
        raise ValueError(f"retirement_case={rc} chưa được Engine hiện tại tự động hóa; không tự chuyển sang case khác.")

    contributions = []
    for row in payload["contributions"]:
        status = row.get("participation_status", "contributed")
        ctype = row.get("contribution_type")
        basis_type = row.get("basis_input_type", "total_vnd")
        monthly = row.get("monthly_basis_vnd")
        sbh = row.get("sbh_components")

        if basis_type == "mau_07_sbh_components":
            internal_basis_type = BasisInputType.mau_07_sbh_components
            if sbh is None:
                raise ValueError("basis_input_type=mau_07_sbh_components nhưng thiếu sbh_components")
            components = SBHComponents(
                unit=SbhComponentUnit(sbh["unit"]),
                base_value=dec(sbh["base_value"]),
                position_allowance=dec(sbh.get("position_allowance")),
                seniority_beyond_frame_allowance=dec(sbh.get("seniority_beyond_frame_allowance")),
                professional_seniority_allowance=dec(sbh.get("professional_seniority_allowance")),
                regional_allowance=dec(sbh.get("regional_allowance")),
                other_allowance=dec(sbh.get("other_allowance")),
                reelection_allowance=dec(sbh.get("reelection_allowance")),
            )
        else:
            internal_basis_type = BasisInputType.monthly_basis_vnd
            components = None
            if monthly is None and status == "contributed":
                # salary_coefficient can be carried through as monthly basis only when explicitly converted.
                if basis_type == "salary_coefficient" and row.get("coefficient_override") is not None:
                    components = SBHComponents(unit=SbhComponentUnit.coefficient, base_value=dec(row["coefficient_override"]))
                    internal_basis_type = BasisInputType.mau_07_sbh_components
                else:
                    raise ValueError(f"{row['from_month']}: contributed phải có monthly_basis_vnd hoặc sbh_components")

        avg_inc = None
        avg_reason = None
        if status == "credited_duration_only" or row["to_month"] < "1995-01":
            avg_inc = AverageInclusion.excluded
            if status == "credited_duration_only" or row["to_month"] < "1995-01":
                avg_reason = AverageExclusionReason.pre1995_policy

        contributions.append(Contribution(
            from_month=row["from_month"], to_month=row["to_month"],
            participation_status=ParticipationStatus(status),
            duration_only_reason=(DurationOnlyReason(row["duration_only_reason"]) if row.get("duration_only_reason") else None),
            contribution_type=(ContributionType(ctype) if ctype else None),
            # PRE-1995 credited-duration-only rows carry time only; they must not
            # carry a basis_input_type into the internal model because the Engine
            # correctly rejects any salary basis on duration-only rows.
            basis_input_type=(
                None
                if status == "credited_duration_only"
                else internal_basis_type if status != "not_participating" else None
            ),
            monthly_basis_vnd=(dec(monthly) if monthly is not None else None), sbh_components=components,
            average_inclusion=avg_inc,
            average_exclusion_reason=avg_reason,
            after_retirement_age_period=False,
        ))

    return PensionCalculationRequest(
        identity=Identity(so_bhxh=None),
        person=Person(date_of_birth=date.fromisoformat(p["date_of_birth"]), sex=Sex(p["sex"])),
        pension_start_month=payload["pension_start_month"],
        retirement_case=RetirementCase(rc),
        retirement_policy=internal_policy,
        impairment_percent=dec(payload.get("impairment_percent")),
        contributions=contributions,
        retirement_age_eligible_month=payload.get("eligibility_achieved_month"),
        benefit_calculation_scope=BenefitCalculationScope.pension_and_one_time_allowance,
    )


def _duration(months: int) -> str:
    return f"{months // 12} năm {months % 12} tháng"


def _regime(req):
    types = {c.contribution_type for c in req.contributions if c.participation_status != ParticipationStatus.not_participating and c.contribution_type}
    if types == {ContributionType.voluntary}: return "voluntary"
    if types and ContributionType.voluntary in types: return "mixed_voluntary_policy"
    if types: return "compulsory"
    return "undetermined"


def build_v2_response(payload, result, diagnostics, req):
    from .engine import determine_eligibility, expand_records, calculate_average_salary
    records = expand_records(req)
    elig = determine_eligibility(req, records)
    average, avg_warn, avg_months, avg_method = calculate_average_salary(req, records)
    retirement_end = date.fromisoformat(payload["pension_start_month"] + "-01")
    from dateutil.relativedelta import relativedelta
    retirement_end = retirement_end - relativedelta(days=1)
    normal = elig.normal_threshold
    compulsory = sum(1 for r in records if r.contribution_type in {ContributionType.compulsory_state, ContributionType.compulsory_employer})
    voluntary = sum(1 for r in records if r.contribution_type == ContributionType.voluntary)
    rounded_years = result.calculation.trace.average_basis_months  # overwritten below
    full_years, rem = divmod(len(records), 12)
    rounded_years = full_years + (1 if rem >= 7 else 0)
    rate_years = full_years + (0.5 if 1 <= rem <= 6 else 1 if rem >= 7 else 0)
    policy = payload.get("early_retirement_policy")
    policy_result = None
    if policy:
        policy_result = {
            "policy_code": policy.get("policy_code"),
            "legal_document_number": policy.get("legal_document_number"),
            "age_reference": policy.get("age_reference"),
            "reference_threshold_date": normal.isoformat(),
            "early_retirement_months": elig.early_retirement_months,
            "maximum_early_months": policy.get("custom_maximum_early_months") or 60,
            "no_reduction_applied": elig.early_retirement_reduction == 0,
            "approved_by_competent_authority": policy.get("approved_by_competent_authority", False),
            "decision_number": policy.get("competent_authority_decision_number"),
            "reasons": list(elig.warnings),
            "warnings": [],
        }

    basis_audit = []
    for i,c in enumerate(payload["contributions"]):
        if c.get("participation_status", "contributed") == "not_participating": continue
        sbh = c.get("sbh_components") or {}
        if c.get("basis_input_type", "total_vnd") == "mau_07_sbh_components":
            vals = {k: str(sbh.get(k, "0")) for k in ["base_value","position_allowance","seniority_beyond_frame_allowance","professional_seniority_allowance","regional_allowance","other_allowance","reelection_allowance"]}
            total = sum(Decimal(v) for v in vals.values())
            basis_audit.append({"source_row_id":c.get("source_row_id") or str(i+1),"from_month":c["from_month"],"to_month":c["to_month"],"component_unit":sbh.get("unit","vnd"),"base_value":vals["base_value"],"position_allowance":vals["position_allowance"],"seniority_beyond_frame_allowance":vals["seniority_beyond_frame_allowance"],"professional_seniority_allowance":vals["professional_seniority_allowance"],"regional_allowance":vals["regional_allowance"],"other_allowance":vals["other_allowance"],"reelection_allowance":vals["reelection_allowance"],"allowance_total":str(total-dec(vals["base_value"])),"total_component_value":str(total),"formula_vi":"Mức đóng + Chức vụ + TN VK + TN Nghề + Khu vực + Khác + Tái cử"})

    response = {
        "calculation_id": result.calculation.calculation_id,
        "status": "success",
        "legal_rule_version": result.calculation.policy_version,
        "requested_pension_start_month": payload["pension_start_month"],
        "retirement_end_date": retirement_end.isoformat(),
        "normal_retirement_age_in_retirement_year": "tra theo DataPack",
        "normal_retirement_threshold_date": normal.isoformat(),
        "earliest_normal_pension_start_month": f"{normal.year:04d}-{normal.month:02d}",
        "history_validation": {
            "valid_for_calculation": True,
            "total_unique_months": len(records),
            "average_basis_months": avg_months,
            "credited_duration_only_months": sum(1 for r in records if r.participation_status == ParticipationStatus.credited_duration_only),
            "excluded_non_participation_months": diagnostics.response.normalized_summary.excluded_bhtn_months,
            "gaps": [], "overlaps": [], "issues": []
        },
        "contribution_summary": {
            "total_months": len(records), "compulsory_months": compulsory, "voluntary_months": voluntary,
            "average_basis_months": avg_months,
            "credited_duration_only_months": sum(1 for r in records if r.participation_status == ParticipationStatus.credited_duration_only),
            "excluded_non_participation_months": diagnostics.response.normalized_summary.excluded_bhtn_months,
            "exact_duration": _duration(len(records)), "rounded_years_for_rate": str(rounded_years)
        },
        "early_retirement_policy_result": policy_result,
        "eligibility": {"eligible": True,"case": payload.get("retirement_case","normal"),"regime":_regime(req),"reasons":list(elig.warnings),"missing_fields":[],"required_total_months":180,"required_compulsory_months":180 if payload.get("retirement_case","normal")=="normal" else 240,"months_short":0,"can_pay_missing_months_once":False},
        "average_basis": {"amount_vnd":str(result.average_salary),"average_monthly_basis_vnd":str(result.average_salary),"basis_months_used":avg_months,"method":avg_method,"coefficient_year":int(payload["pension_start_month"][:4]),"state_average_months_used":avg_months if compulsory else 0,"yearly_breakdown":[]},
        "basis_component_audit": basis_audit,
        "pension_rate": {"rounded_years":str(rounded_years),"base_rate_percent":str(result.rate_before_early_reduction),"early_retirement_months":result.early_retirement_months,"early_retirement_reduction_percent":str(result.early_retirement_reduction),"final_rate_percent":str(result.rate_after_reduction),"reduction_reference_age":None},
        "estimated_monthly_pension_vnd":str(result.estimated_pension),
        "pension_calculation_formula":"mức bình quân tiền lương/thu nhập làm căn cứ tính hưởng × tỷ lệ %",
        "one_time_retirement_allowance_vnd":str(result.one_time_retirement_allowance.total_allowance_amount) if result.one_time_retirement_allowance else "0",
        "minimum_floor_applied":False,
        "assumptions":[],
        "warnings":result.warnings,
        "audit_steps":["Đọc và chuẩn hóa lịch sử đóng BHXH","Kiểm tra điều kiện hưởng","Tính mức bình quân","Tính tỷ lệ hưởng","Tính lương hưu dự tính"],
        "legal_references":[]
    }
    return response
