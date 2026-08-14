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


def _parse_percent_token(value):
    """Return percentage fraction for raw % representations, else None.

    Accepted raw forms are deliberately narrow:
      5       -> 0.05
      0.05    -> 0.05
      "5%"    -> 0.05 (for tolerant internal clients; public schema may omit %)
      "0.05%" -> 0.0005

    A normalized coefficient such as 0.2030, 0.2490, 0.3248 or 1.632410
    is NOT a percent token.
    """
    if value in (None, ""):
        return None
    text = str(value).strip().replace(",", ".")
    if not text:
        return None
    has_pct = text.endswith("%")
    if has_pct:
        text = text[:-1].strip()
    try:
        d = Decimal(text)
    except Exception:
        return None
    if d < 0:
        return None
    if has_pct:
        return d / Decimal("100")
    # 0.05 = 5%; 0.29 = 29%; etc. Only exact integer hundredths are
    # recognized. This intentionally excludes normalized coefficients such
    # as 0.2030, 0.2490, 0.3248 and 1.632410.
    if Decimal("0.01") <= d <= Decimal("1") and (d * 100) == (d * 100).to_integral_value():
        return d
    # Whole-percent representation 5, 29, 34. Values > 1 are never treated
    # as normalized coefficient components in this model.
    if Decimal("1") < d <= Decimal("100") and d == d.to_integral_value():
        return d / Decimal("100")
    return None


def _is_percent_token(value) -> bool:
    return _parse_percent_token(value) is not None


def _normalize_percentage_components(payload: dict) -> None:
    """Normalize raw TN VK/TN Nghề percentages before internal calculation.

    R1.7 makes the rule deterministic per row. It no longer requires two or
    more rows to contain percentage-like values. This fixes the BAU_154 failure
    mode where a GPT payload can mix raw percentages and already-normalized
    coefficient components.

    Priority:
      1) source_unit=percent/%/percentage/pct -> always interpret allowance
         fields as percentages.
      2) source_unit=coefficient -> preserve already-normalized components.
      3) source_unit absent/unknown -> recognize only narrow percentage tokens
         (0.05, 0.29, 5, 29, etc.); values such as 0.2030/0.2490/1.632410 are
         preserved.

    TN VK is calculated first:
        % TN VK × Mức đóng
    TN Nghề is then calculated from:
        % TN Nghề × (Mức đóng + Chức vụ + TN VK)
    """
    audit = []
    rows = payload.get("contributions") or []

    for idx, row in enumerate(rows):
        # PRE-1995 values are audit-only in R1.9 and must not be reinterpreted
        # as allowance percentages or normalized salary components.
        if row.get("to_month") and row["to_month"] < "1995-01":
            continue
        sbh = row.get("sbh_components")
        if not isinstance(sbh, dict) or sbh.get("unit") != "coefficient":
            continue

        base = _as_decimal(sbh.get("base_value"))
        position = _as_decimal(sbh.get("position_allowance"))
        raw_tnvk = _as_decimal(sbh.get("seniority_beyond_frame_allowance"))
        raw_tnnghe = _as_decimal(sbh.get("professional_seniority_allowance"))

        source_unit = str(row.get("source_unit") or sbh.get("source_unit") or "").strip().lower()
        explicit_percent = source_unit in {"%", "percent", "percentage", "pct"}
        explicit_coefficient = source_unit in {"coefficient", "coef", "he_so", "hệ số"}
        source_text = str(row.get("source_text") or "")

        tnvk_pct = None if explicit_coefficient else _parse_percent_token(sbh.get("seniority_beyond_frame_allowance"))
        tnnghe_pct = None if explicit_coefficient else _parse_percent_token(sbh.get("professional_seniority_allowance"))

        # If the source explicitly says percent, a non-percent numeric value is
        # invalid rather than silently guessed. This prevents a hidden basis error.
        if explicit_percent:
            if raw_tnvk != 0 and tnvk_pct is None:
                raise ValueError(f"contributions[{idx}].sbh_components.seniority_beyond_frame_allowance: source_unit=percent nhưng giá trị không phải % hợp lệ")
            if raw_tnnghe != 0 and tnnghe_pct is None:
                raise ValueError(f"contributions[{idx}].sbh_components.professional_seniority_allowance: source_unit=percent nhưng giá trị không phải % hợp lệ")

        # Optional source text is useful when OCR preserved the '%' marker.
        if not explicit_coefficient and not explicit_percent and "%" in source_text:
            if raw_tnvk != 0 and tnvk_pct is None:
                tnvk_pct = _parse_percent_token(f"{sbh.get('seniority_beyond_frame_allowance')}%")
            if raw_tnnghe != 0 and tnnghe_pct is None:
                tnnghe_pct = _parse_percent_token(f"{sbh.get('professional_seniority_allowance')}%")

        applied = []
        normalized_tnvk = raw_tnvk
        normalized_tnnghe = raw_tnnghe

        # TN VK first.
        if tnvk_pct is not None and raw_tnvk != 0:
            normalized_tnvk = base * tnvk_pct
            sbh["seniority_beyond_frame_allowance"] = str(normalized_tnvk)
            applied.append("TN VK = % × Mức đóng")

        # TN Nghề second, using the normalized TN VK.
        if tnnghe_pct is not None and raw_tnnghe != 0:
            subtotal = base + position + normalized_tnvk
            normalized_tnnghe = subtotal * tnnghe_pct
            sbh["professional_seniority_allowance"] = str(normalized_tnnghe)
            applied.append("TN Nghề = % × (Mức đóng + Chức vụ + TN VK)")

        audit.append({
            "source_row_id": row.get("source_row_id") or str(idx + 1),
            "from_month": row.get("from_month"),
            "to_month": row.get("to_month"),
            "source_unit": source_unit or None,
            "source_text": source_text or None,
            "raw_tnvk": str(raw_tnvk),
            "raw_tnnghe": str(raw_tnnghe),
            "tnvk_percent": str(tnvk_pct * 100) if tnvk_pct is not None and raw_tnvk != 0 else None,
            "tnnghe_percent": str(tnnghe_pct * 100) if tnnghe_pct is not None and raw_tnnghe != 0 else None,
            "normalized_tnvk": str(normalized_tnvk),
            "normalized_tnnghe": str(normalized_tnnghe),
            "normalization_applied": bool(applied),
            "normalization_rule": "; ".join(applied) if applied else "Giữ nguyên component đã chuẩn hóa"
        })

    payload["_r17_normalization_audit"] = audit

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

        # R1.9 PRE-1995 canonical rule:
        # Every confirmed BHXH participation period ending before 01/1995 is
        # duration-only for pension-rate duration and is excluded from the
        # average basis. This is true whether the source salary cell is blank,
        # coefficient-like (e.g. 1.72) or VND-like (e.g. 262). Source values may
        # remain in source_value/source_text for audit, but no salary basis is
        # carried into the internal calculation model.
        is_pre1995 = row["to_month"] < "1995-01"
        if is_pre1995 and status != "not_participating":
            row = dict(row)
            if status == "contributed":
                status = "credited_duration_only"
            if status == "credited_duration_only" and row.get("duration_only_reason") not in {
                "pre1995_no_salary_or_living_allowance",
                "pre1995_duration_excluded_from_average_basis",
            }:
                row["duration_only_reason"] = "pre1995_duration_excluded_from_average_basis"
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
        if is_pre1995:
            avg_inc = AverageInclusion.excluded
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
            monthly_basis_vnd=(
                None
                if status == "credited_duration_only"
                else dec(monthly) if monthly is not None else None
            ),
            sbh_components=components,
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
    normalization_audit = {x.get("source_row_id"): x for x in (payload.get("_r17_normalization_audit") or [])}
    for i,c in enumerate(payload["contributions"]):
        if c.get("participation_status", "contributed") == "not_participating": continue
        sbh = c.get("sbh_components") or {}
        if c.get("basis_input_type", "total_vnd") == "mau_07_sbh_components":
            vals = {k: str(sbh.get(k, "0")) for k in ["base_value","position_allowance","seniority_beyond_frame_allowance","professional_seniority_allowance","regional_allowance","other_allowance","reelection_allowance"]}
            total = sum(Decimal(v) for v in vals.values())
            row_id = c.get("source_row_id") or str(i+1)
            audit_item = {"source_row_id":row_id,"from_month":c["from_month"],"to_month":c["to_month"],"component_unit":sbh.get("unit","vnd"),"base_value":vals["base_value"],"position_allowance":vals["position_allowance"],"seniority_beyond_frame_allowance":vals["seniority_beyond_frame_allowance"],"professional_seniority_allowance":vals["professional_seniority_allowance"],"regional_allowance":vals["regional_allowance"],"other_allowance":vals["other_allowance"],"reelection_allowance":vals["reelection_allowance"],"allowance_total":str(total-dec(vals["base_value"])),"total_component_value":str(total),"formula_vi":"Mức đóng + Chức vụ + TN VK + TN Nghề + Khu vực + Khác + Tái cử"}
            norm = normalization_audit.get(row_id)
            if norm:
                audit_item.update({
                    "source_unit": norm.get("source_unit"),
                    "source_text": norm.get("source_text"),
                    "raw_tnvk": norm.get("raw_tnvk"),
                    "raw_tnnghe": norm.get("raw_tnnghe"),
                    "tnvk_percent": norm.get("tnvk_percent"),
                    "tnnghe_percent": norm.get("tnnghe_percent"),
                    "normalized_tnvk": norm.get("normalized_tnvk"),
                    "normalized_tnnghe": norm.get("normalized_tnnghe"),
                    "normalization_applied": norm.get("normalization_applied"),
                    "normalization_rule": norm.get("normalization_rule"),
                })
            basis_audit.append(audit_item)

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
