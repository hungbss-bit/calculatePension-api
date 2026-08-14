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


def _as_decimal(value):
    return Decimal(str(value)) if value is not None else Decimal("0")


def _is_percent_token(value) -> bool:
    """Conservative detector for raw percentage values such as 0.05..0.12."""
    if value in (None, "", 0, "0", 0.0, "0.0"):
        return False
    try:
        d = Decimal(str(value))
    except Exception:
        return False
    # Supported raw percentage representations:
    #   0.05 / 0.29 / 0.34  (decimal fraction)
    #   5 / 29 / 34          (whole percent)
    # Do NOT convert normalized coefficient amounts such as 0.2030, 0.3248
    # or 0.4872. The decimal-fraction form is therefore restricted to
    # integer percentages, while whole-percent form is restricted to the
    # allowance fields where values above 1 are not valid normalized
    # coefficient allowances in the Mẫu 07/SBH model.
    if Decimal("0.01") <= d <= Decimal("1"):
        return (d * 100) == (d * 100).to_integral_value()
    return Decimal("1") < d <= Decimal("100") and d == d.to_integral_value()


def _normalize_percentage_components(payload: dict) -> None:
    """Normalize percentage-form allowance input before internal conversion.

    Public contract keeps sbh_components in coefficient units. GPT/clients may
    nevertheless supply raw percentage fractions (e.g. 0.05 for 5%). We support
    two safe paths:
      1) explicit source_unit=percent/%/percentage;
      2) conservative multi-row detection for percentage-like values in TN VK/TN Nghề
         fields, requiring at least two matching rows when source_unit is absent.
         This covers both 0.05/0.29 and 5/29 representations.

    Already normalized coefficient values such as 0.3248 are never converted by
    the heuristic.
    """
    rows = payload.get("contributions") or []
    candidate_counts = {"seniority_beyond_frame_allowance": 0,
                        "professional_seniority_allowance": 0}
    for row in rows:
        sbh = row.get("sbh_components")
        if not isinstance(sbh, dict) or sbh.get("unit") != "coefficient":
            continue
        for field in candidate_counts:
            if _is_percent_token(sbh.get(field)):
                candidate_counts[field] += 1

    for row in rows:
        sbh = row.get("sbh_components")
        if not isinstance(sbh, dict) or sbh.get("unit") != "coefficient":
            continue

        source_unit = str(row.get("source_unit") or sbh.get("source_unit") or "").strip().lower()
        explicit_percent = source_unit in {"%", "percent", "percentage", "pct"}

        base = _as_decimal(sbh.get("base_value"))
        position = _as_decimal(sbh.get("position_allowance"))
        raw_tnvk = _as_decimal(sbh.get("seniority_beyond_frame_allowance"))
        raw_tnnghe = _as_decimal(sbh.get("professional_seniority_allowance"))

        # If source_unit explicitly says percent, values may be written as 5 or
        # 0.05. Convert both supported representations to a coefficient amount.
        tnvk_is_pct = explicit_percent and raw_tnvk != 0
        tnnghe_is_pct = explicit_percent and raw_tnnghe != 0

        # Conservative compatibility path for the observed GPT failure mode:
        # repeated raw 5%..12% values sent as 0.05..0.12.
        if not explicit_percent:
            tnvk_is_pct = candidate_counts["seniority_beyond_frame_allowance"] >= 2 and _is_percent_token(sbh.get("seniority_beyond_frame_allowance"))
            tnnghe_is_pct = candidate_counts["professional_seniority_allowance"] >= 2 and _is_percent_token(sbh.get("professional_seniority_allowance"))

        if tnvk_is_pct:
            pct = raw_tnvk if raw_tnvk <= 1 else raw_tnvk / Decimal("100")
            sbh["seniority_beyond_frame_allowance"] = str(base * pct)
            row["source_unit"] = "percent"
            row["source_value"] = str(raw_tnvk * 100 if raw_tnvk <= 1 else raw_tnvk)
            raw_tnvk = base * pct

        if tnnghe_is_pct:
            pct = raw_tnnghe if raw_tnnghe <= 1 else raw_tnnghe / Decimal("100")
            # TN Nghề is calculated on Mức đóng + Chức vụ + TN VK.
            subtotal = base + position + raw_tnvk
            sbh["professional_seniority_allowance"] = str(subtotal * pct)
            row["source_unit"] = "percent"
            row["source_value"] = str(raw_tnnghe * 100 if raw_tnnghe <= 1 else raw_tnnghe)


def to_internal(payload: dict) -> PensionCalculationRequest:
    _normalize_percentage_components(payload)
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

        # PRE-1995: Mẫu 07/SBH có thể chỉ xác nhận thời gian đóng mà không có
        # căn cứ tiền lương/hệ số. Một số GPT/clients vẫn gửi một object
        # sbh_components toàn số 0 để thỏa schema. Object đó KHÔNG phải là
        # một căn cứ tiền lương thực tế và phải được coi như "không có basis".
        sbh_raw = row.get("sbh_components")
        sbh_has_basis = False
        if isinstance(sbh_raw, dict):
            numeric_keys = [
                "base_value", "position_allowance",
                "seniority_beyond_frame_allowance",
                "professional_seniority_allowance", "regional_allowance",
                "other_allowance", "reelection_allowance"
            ]
            sbh_has_basis = any(
                sbh_raw.get(k) not in (None, "", 0, "0", 0.0, "0.0")
                for k in numeric_keys
            )
        elif sbh_raw is not None:
            sbh_has_basis = True

        has_real_basis = (
            row.get("monthly_basis_vnd") is not None
            or sbh_has_basis
            or row.get("coefficient_override") is not None
        )

        # Treat PRE-1995 rows without a real salary basis as
        # credited-duration-only. This preserves the duration for pension
        # eligibility/rate while excluding the row from average salary.
        if (
            status == "contributed"
            and row["to_month"] < "1995-01"
            and not has_real_basis
        ):
            status = "credited_duration_only"
            if not row.get("duration_only_reason"):
                row = dict(row)
                row["duration_only_reason"] = "pre1995_no_salary_or_living_allowance"
        monthly = row.get("monthly_basis_vnd")
        sbh = row.get("sbh_components")

        if status == "credited_duration_only":
            internal_basis_type = None
            components = None
        elif basis_type == "mau_07_sbh_components":
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
