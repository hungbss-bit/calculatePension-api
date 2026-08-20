from __future__ import annotations
from datetime import date
from decimal import Decimal
from pathlib import Path
import re
import yaml
from jsonschema import Draft202012Validator
from dateutil.relativedelta import relativedelta

from .models import (
    BenefitCalculationScope, Contribution, ContributionType, DurationOnlyReason,
    Identity, PensionCalculationRequest, Person, RetirementCase, RetirementPolicy,
    ParticipationStatus, AverageInclusion, AverageExclusionReason, BasisInputType,
    SBHComponents, SbhComponentUnit, Sex
)
from .rules import LEGAL_RULE_VERSION, base_salary_for_month, retirement_age_for_year

ROOT = Path(__file__).resolve().parent.parent
CONTRACT_PATH = ROOT / "contracts" / "02_API_V2.4.0.yaml"

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


def _business_issue(code: str, message_vi: str, row: dict | None = None) -> dict:
    return {
        "code": code,
        "severity": "error",
        "message_vi": message_vi,
        "source_row_id": row.get("source_row_id") if row else None,
        "from_month": row.get("from_month") if row else None,
        "to_month": row.get("to_month") if row else None,
    }


def payload_evidence_issues(payload: dict) -> list[dict]:
    """Khóa các xác nhận hồ sơ mà JSON Schema không thể diễn đạt đầy đủ."""
    issues: list[dict] = []
    if payload.get("history_confirmed") is not True:
        issues.append(_business_issue(
            "HISTORY_NOT_CONFIRMED",
            "Quá trình BHXH chưa được cán bộ xác nhận; chưa được dùng để tính.",
        ))

    for row in payload.get("contributions", []):
        if row.get("confirmation_status", "confirmed") != "confirmed":
            issues.append(_business_issue(
                "CONTRIBUTION_ROW_NOT_CONFIRMED",
                "Dòng quá trình chưa được xác nhận; cần đối chiếu hồ sơ trước khi tính.",
                row,
            ))
        sbh = row.get("sbh_components") or {}
        percent = dec(sbh.get("professional_seniority_percent"))
        amount = dec(sbh.get("professional_seniority_allowance"))
        if percent > 0 and amount > 0:
            issues.append(_business_issue(
                "PROFESSIONAL_SENIORITY_DUPLICATE_INPUT",
                "Chỉ nhập một trong hai: phụ cấp thâm niên nghề đã quy đổi hoặc tỷ lệ phần trăm.",
                row,
            ))
        if sbh.get("base_salary_vnd_override") is not None and sbh.get("unit") != "coefficient":
            issues.append(_business_issue(
                "BASE_SALARY_OVERRIDE_ONLY_FOR_COEFFICIENT",
                "base_salary_vnd_override chỉ dùng khi đơn vị thành phần là coefficient.",
                row,
            ))
        if row.get("basis_components") is not None:
            issues.append(_business_issue(
                "BASIS_COMPONENTS_NOT_AUTOMATED",
                "basis_components chưa thuộc luồng tự động; dùng monthly_basis_vnd hoặc sbh_components.",
                row,
            ))

    policy = payload.get("early_retirement_policy")
    if policy:
        if payload.get("retirement_case", "normal") != "normal":
            issues.append(_business_issue(
                "RETIREMENT_CASE_POLICY_CONFLICT",
                "NĐ 154/2025/NĐ-CP trong phiên bản này chỉ đi cùng retirement_case=normal.",
            ))
        document = re.sub(r"\s+", "", str(policy.get("legal_document_number", ""))).upper()
        if "154/2025/NĐ-CP" not in document and "154/2025/ND-CP" not in document:
            issues.append(_business_issue(
                "DECREE_154_DOCUMENT_MISMATCH",
                "Số văn bản phải xác định đúng Nghị định 154/2025/NĐ-CP.",
            ))
        if policy.get("approved_by_competent_authority") is not True:
            issues.append(_business_issue(
                "DECREE_154_AUTHORITY_APPROVAL_REQUIRED",
                "Chưa xác nhận hồ sơ nghỉ theo NĐ 154 được cấp có thẩm quyền phê duyệt.",
            ))
        if policy.get("no_reduction_confirmed") is not True:
            issues.append(_business_issue(
                "DECREE_154_NO_REDUCTION_CONFIRMATION_REQUIRED",
                "Chưa xác nhận căn cứ không trừ tỷ lệ lương hưu theo NĐ 154.",
            ))
        if policy.get("confirmation_status") != "confirmed":
            issues.append(_business_issue(
                "DECREE_154_EVIDENCE_NOT_CONFIRMED",
                "Căn cứ NĐ 154 phải có confirmation_status=confirmed trước khi tính.",
            ))

    adjustment = payload.get("adjustment") or {}
    if adjustment.get("coefficient_year", 2026) != 2026:
        issues.append(_business_issue(
            "COEFFICIENT_YEAR_UNAVAILABLE",
            "Bộ dữ liệu phát hành này chỉ có hệ số điều chỉnh năm hưởng 2026.",
        ))
    if adjustment.get("salary_coefficients") or adjustment.get("voluntary_income_coefficients"):
        issues.append(_business_issue(
            "CUSTOM_COEFFICIENTS_NOT_ALLOWED",
            "Không nhận hệ số điều chỉnh tự khai; phải dùng DataPack 2026 đã kiểm soát.",
        ))
    return issues


def _normalise_sbh(sbh: dict) -> dict:
    result = dict(sbh)
    percent = dec(result.get("professional_seniority_percent"))
    if percent > 0:
        base = dec(result.get("base_value"))
        position = dec(result.get("position_allowance"))
        beyond = dec(result.get("seniority_beyond_frame_allowance"))
        result["professional_seniority_allowance"] = (
            (base + position + beyond) * percent / Decimal("100")
        )
    return result


def to_internal(payload: dict, *, enforce_evidence: bool = True) -> PensionCalculationRequest:
    if enforce_evidence:
        evidence_issues = payload_evidence_issues(payload)
        if evidence_issues:
            raise ValueError(evidence_issues[0]["message_vi"])
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
            sbh = _normalise_sbh(sbh)
            components = SBHComponents(
                unit=SbhComponentUnit(sbh["unit"]),
                base_value=dec(sbh["base_value"]),
                position_allowance=dec(sbh.get("position_allowance")),
                seniority_beyond_frame_allowance=dec(sbh.get("seniority_beyond_frame_allowance")),
                professional_seniority_allowance=dec(sbh.get("professional_seniority_allowance")),
                regional_allowance=dec(sbh.get("regional_allowance")),
                other_allowance=dec(sbh.get("other_allowance")),
                reelection_allowance=dec(sbh.get("reelection_allowance")),
                base_salary_vnd_override=(
                    dec(sbh.get("base_salary_vnd_override"))
                    if sbh.get("base_salary_vnd_override") is not None else None
                ),
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
            after_retirement_age_period=row.get("after_retirement_age_period", False),
        ))

    return PensionCalculationRequest(
        identity=Identity(so_bhxh=None),
        person=Person(date_of_birth=date.fromisoformat(p["date_of_birth"]), sex=Sex(p["sex"])),
        pension_start_month=payload["pension_start_month"],
        retirement_case=RetirementCase(rc),
        retirement_policy=internal_policy,
        impairment_percent=(
            dec(payload.get("impairment_percent"))
            if payload.get("impairment_percent") is not None else None
        ),
        impairment_assessment_month=payload.get("impairment_assessment_month"),
        contributions=contributions,
        retirement_age_eligible_month=payload.get("eligibility_achieved_month"),
        benefit_calculation_scope=BenefitCalculationScope(
            payload.get("benefit_calculation_scope", "pension_and_one_time_allowance")
        ),
        transitional_minimum_floor_eligible=payload.get("transitional_minimum_floor_eligible", False),
        reference_level_vnd=(
            dec(payload.get("reference_level_vnd"))
            if payload.get("reference_level_vnd") is not None else None
        ),
    )


def _duration(months: int) -> str:
    return f"{months // 12} năm {months % 12} tháng"


def _regime(req):
    types = {c.contribution_type for c in req.contributions if c.participation_status != ParticipationStatus.not_participating and c.contribution_type}
    if types == {ContributionType.voluntary}: return "voluntary"
    if types and ContributionType.voluntary in types: return "mixed_voluntary_policy"
    if types: return "compulsory"
    return "undetermined"


def _payload_months(payload: dict) -> tuple[set[date], set[date], set[date], list[str], list[dict]]:
    covered: dict[date, list[int]] = {}
    credited: set[date] = set()
    excluded: set[date] = set()
    rows = payload.get("contributions", [])
    for index, row in enumerate(rows):
        try:
            start = date.fromisoformat(row["from_month"] + "-01")
            end = date.fromisoformat(row["to_month"] + "-01")
        except (KeyError, ValueError):
            continue
        if start > end:
            continue
        current = start
        while current <= end:
            covered.setdefault(current, []).append(index)
            if row.get("participation_status", "contributed") == "credited_duration_only":
                credited.add(current)
            elif row.get("participation_status", "contributed") == "not_participating":
                excluded.add(current)
            current += relativedelta(months=1)

    overlaps = [
        f"{month.year:04d}-{month.month:02d} (dòng {', '.join(str(i + 1) for i in owners)})"
        for month, owners in sorted(covered.items()) if len(owners) > 1
    ]
    gaps: list[dict] = []
    if covered:
        current = min(covered)
        last = max(covered)
        gap_start = None
        while current <= last:
            if current not in covered and gap_start is None:
                gap_start = current
            if current in covered and gap_start is not None:
                gap_end = current - relativedelta(months=1)
                months = (gap_end.year - gap_start.year) * 12 + gap_end.month - gap_start.month + 1
                gaps.append({
                    "from_month": f"{gap_start.year:04d}-{gap_start.month:02d}",
                    "to_month": f"{gap_end.year:04d}-{gap_end.month:02d}",
                    "months": months,
                })
                gap_start = None
            current += relativedelta(months=1)
        if gap_start is not None:
            months = (last.year - gap_start.year) * 12 + last.month - gap_start.month + 1
            gaps.append({
                "from_month": f"{gap_start.year:04d}-{gap_start.month:02d}",
                "to_month": f"{last.year:04d}-{last.month:02d}",
                "months": months,
            })
    counted = set(covered) - excluded
    return counted, credited, excluded, overlaps, gaps


def build_history_validation(
    payload: dict,
    diagnostics,
    average_basis_months: int = 0,
    evidence_issues: list[dict] | None = None,
) -> dict:
    counted, credited, excluded, overlaps, gaps = _payload_months(payload)
    rows = payload.get("contributions", [])
    issues: list[dict] = list(evidence_issues or [])
    for issue in diagnostics.issues:
        row = None
        for field in issue.fields:
            match = re.match(r"contributions\[(\d+)\]", field)
            if match and int(match.group(1)) < len(rows):
                row = rows[int(match.group(1))]
                break
        issues.append(_business_issue(issue.code, issue.message, row))
    return {
        "valid_for_calculation": diagnostics.response.validation and not issues,
        "total_unique_months": len(counted),
        "average_basis_months": average_basis_months,
        "credited_duration_only_months": len(credited),
        "excluded_non_participation_months": len(excluded),
        "gaps": gaps,
        "overlaps": overlaps,
        "issues": issues,
    }


def _legal_references(payload: dict, req) -> list[dict]:
    references = [
        {
            "document": "Luật Bảo hiểm xã hội số 41/2024/QH15",
            "provisions": "Khoản 6 Điều 5; Điều 64–73; Điều 98–104 (theo chế độ áp dụng)",
            "purpose": "Điều kiện, tỷ lệ, giảm trừ, trợ cấp một lần, thời điểm hưởng và mức bình quân.",
        },
        {
            "document": "Nghị định 135/2020/NĐ-CP",
            "provisions": "Điều 4 và Phụ lục I",
            "purpose": "Lộ trình tuổi nghỉ hưu trong điều kiện lao động bình thường.",
        },
        {
            "document": "Nghị định 158/2025/NĐ-CP",
            "provisions": "Điều 12, Điều 13, Điều 15 và Điều 16",
            "purpose": "Điều kiện, mức lương hưu và mức bình quân đối với BHXH bắt buộc.",
        },
        {
            "document": "Thông tư 12/2025/TT-BNV",
            "provisions": "Điều 14, Điều 15 và Điều 16",
            "purpose": "Cách tính trợ cấp một lần, tháng bắt đầu hưởng và mức bình quân.",
        },
    ]
    if _regime(req) in {"voluntary", "mixed_voluntary_policy"}:
        references.append({
            "document": "Nghị định 159/2025/NĐ-CP",
            "provisions": "Quy định chi tiết chế độ hưu trí BHXH tự nguyện",
            "purpose": "Điều kiện và cách tính phần BHXH tự nguyện/hỗn hợp.",
        })
    if payload.get("early_retirement_policy"):
        references.append({
            "document": "Nghị định 154/2025/NĐ-CP",
            "provisions": "Khoản 2 và khoản 4 Điều 6",
            "purpose": "Nghỉ hưu trước tuổi theo diện tinh giản biên chế, không trừ tỷ lệ lương hưu.",
        })
    return references


def build_v2_response(payload, result, diagnostics, req):
    from .engine import (
        calculate_average_salary,
        determine_eligibility,
        expand_records,
        first_pension_month_after_threshold,
    )
    records = expand_records(req)
    elig = determine_eligibility(req, records)
    _, _, avg_months, avg_method = calculate_average_salary(req, records)
    retirement_end = date.fromisoformat(payload["pension_start_month"] + "-01")
    retirement_end = retirement_end - relativedelta(days=1)
    normal = elig.normal_threshold
    normal_start = first_pension_month_after_threshold(normal)
    age_years, age_months = retirement_age_for_year(payload["person"]["sex"], normal.year)
    compulsory = sum(1 for r in records if r.contribution_type in {ContributionType.compulsory_state, ContributionType.compulsory_employer})
    voluntary = sum(1 for r in records if r.contribution_type == ContributionType.voluntary)
    full_years, rem = divmod(len(records), 12)
    rounded_years = full_years + (1 if rem >= 7 else 0)
    policy = payload.get("early_retirement_policy")
    policy_result = None
    if policy:
        policy_result = {
            "policy_code": policy.get("policy_code"),
            "legal_document_number": policy.get("legal_document_number"),
            "age_reference": policy.get("age_reference", "normal_schedule"),
            "reference_threshold_date": normal.isoformat(),
            "early_retirement_months": elig.early_retirement_months,
            "maximum_early_months": policy.get("custom_maximum_early_months") or 60,
            "no_reduction_applied": True,
            "approved_by_competent_authority": policy.get("approved_by_competent_authority", False),
            "decision_number": policy.get("competent_authority_decision_number"),
            "reasons": list(elig.warnings),
            "warnings": [],
        }

    basis_audit: list[dict] = []
    source_trace: list[dict] = []
    for i,c in enumerate(payload["contributions"]):
        source_trace.append({
            "source_row_id": c.get("source_row_id") or str(i + 1),
            "from_month": c["from_month"],
            "to_month": c["to_month"],
            "source_value": str(c.get("source_value")) if c.get("source_value") is not None else None,
            "source_unit": c.get("source_unit"),
            "source_text": c.get("source_text"),
            "confirmation_status": c.get("confirmation_status", "confirmed"),
        })
        if c.get("participation_status", "contributed") == "not_participating":
            continue
        sbh = c.get("sbh_components") or {}
        if c.get("basis_input_type", "total_vnd") == "mau_07_sbh_components":
            sbh = _normalise_sbh(sbh)
            vals = {k: str(sbh.get(k, "0")) for k in ["base_value","position_allowance","seniority_beyond_frame_allowance","professional_seniority_allowance","regional_allowance","other_allowance","reelection_allowance"]}
            total = sum(Decimal(v) for v in vals.values())
            unit = sbh.get("unit", "vnd")
            reference_values: list[str] = []
            monthly_basis = total
            if unit == "coefficient":
                reference = (
                    dec(sbh.get("base_salary_vnd_override"))
                    if sbh.get("base_salary_vnd_override") is not None
                    else base_salary_for_month(date.fromisoformat(payload["pension_start_month"] + "-01"))
                )
                reference_values = [str(reference)]
                monthly_basis = total * reference
            basis_audit.append({
                "source_row_id": c.get("source_row_id") or str(i + 1),
                "from_month": c["from_month"], "to_month": c["to_month"],
                "component_unit": unit, "base_value": vals["base_value"],
                "position_allowance": vals["position_allowance"],
                "seniority_beyond_frame_allowance": vals["seniority_beyond_frame_allowance"],
                "professional_seniority_allowance": vals["professional_seniority_allowance"],
                "professional_seniority_percent": (
                    str(sbh.get("professional_seniority_percent"))
                    if sbh.get("professional_seniority_percent") is not None else None
                ),
                "regional_allowance": vals["regional_allowance"],
                "other_allowance": vals["other_allowance"],
                "reelection_allowance": vals["reelection_allowance"],
                "allowance_total": str(total - dec(vals["base_value"])),
                "total_component_value": str(total),
                "base_salary_values_used_vnd": reference_values,
                "monthly_basis_min_vnd": str(monthly_basis),
                "monthly_basis_max_vnd": str(monthly_basis),
                "formula_vi": "Mức đóng + Chức vụ + TN VK + TN Nghề + Khu vực + Khác + Tái cử",
            })

    history = build_history_validation(payload, diagnostics, avg_months)
    allowance = result.one_time_retirement_allowance
    allowance_result = None
    if allowance:
        allowance_result = {
            "eligible": allowance.eligible,
            "threshold_months": allowance.threshold_months,
            "total_excess_months": allowance.total_excess_months,
            "excess_before_retirement_age_months": allowance.excess_before_retirement_age_months,
            "excess_after_retirement_age_months": allowance.excess_after_retirement_age_months,
            "standard_allowance_vnd": str(allowance.standard_allowance_amount),
            "post_retirement_allowance_vnd": str(allowance.post_retirement_allowance_amount),
            "total_allowance_vnd": str(allowance.total_allowance_amount),
            "average_basis_vnd": str(allowance.average_basis),
            "warnings": allowance.warnings,
        }

    required_months = 240 if payload.get("retirement_case") == "reduced_capacity" else 180
    required_compulsory = 180 if policy else 240 if payload.get("retirement_case") == "reduced_capacity" else None

    response = {
        "calculation_id": result.calculation.calculation_id,
        "status": "success",
        "legal_rule_version": LEGAL_RULE_VERSION,
        "requested_pension_start_month": payload["pension_start_month"],
        "retirement_end_date": retirement_end.isoformat(),
        "normal_retirement_age_in_retirement_year": f"{age_years} năm {age_months} tháng",
        "normal_retirement_threshold_date": normal.isoformat(),
        "earliest_normal_pension_start_month": f"{normal_start.year:04d}-{normal_start.month:02d}",
        "history_validation": history,
        "contribution_summary": {
            "total_months": len(records), "compulsory_months": compulsory, "voluntary_months": voluntary,
            "average_basis_months": avg_months,
            "credited_duration_only_months": sum(1 for r in records if r.participation_status == ParticipationStatus.credited_duration_only),
            "excluded_non_participation_months": diagnostics.response.normalized_summary.excluded_bhtn_months,
            "exact_duration": _duration(len(records)), "rounded_years_for_rate": str(rounded_years)
        },
        "early_retirement_policy_result": policy_result,
        "eligibility": {"eligible": True,"case": payload.get("retirement_case","normal"),"regime":_regime(req),"reasons":list(elig.warnings),"missing_fields":[],"required_total_months":required_months,"required_compulsory_months":required_compulsory,"months_short":0,"can_pay_missing_months_once":False},
        "average_basis": {"amount_vnd":str(result.average_salary),"average_monthly_basis_vnd":str(result.average_salary),"basis_months_used":avg_months,"method":avg_method,"coefficient_year":int(payload["pension_start_month"][:4]),"state_average_months_used":avg_months if compulsory else 0,"yearly_breakdown":[]},
        "basis_component_audit": basis_audit,
        "source_trace": source_trace,
        "pension_rate": {"rounded_years":str(rounded_years),"base_rate_percent":str(result.rate_before_early_reduction),"early_retirement_months":result.early_retirement_months,"early_retirement_reduction_percent":str(result.early_retirement_reduction),"final_rate_percent":str(result.rate_after_reduction),"reduction_reference_age":None},
        "estimated_monthly_pension_vnd":str(result.estimated_pension),
        "pension_calculation_formula":"mức bình quân tiền lương/thu nhập làm căn cứ tính hưởng × tỷ lệ %",
        "one_time_retirement_allowance_vnd":str(allowance.total_allowance_amount) if allowance else "0",
        "one_time_retirement_allowance": allowance_result,
        "minimum_floor_applied": result.minimum_floor_applied,
        "assumptions":["Hệ số điều chỉnh và mức tham chiếu theo DataPack năm hưởng 2026."],
        "warnings":result.warnings,
        "audit_steps":["Đọc và chuẩn hóa lịch sử đóng BHXH","Kiểm tra điều kiện hưởng","Tính mức bình quân","Tính tỷ lệ hưởng","Tính lương hưu dự tính"],
        "legal_references":_legal_references(payload, req)
    }
    return response
