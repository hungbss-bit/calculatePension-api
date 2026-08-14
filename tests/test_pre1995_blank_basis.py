from app.v2_adapter import to_internal, validate_v2_payload
from app.engine import validate_request, calculate_average_salary, expand_records


def _post1995_basis_row():
    return {
        "from_month": "1995-01",
        "to_month": "1995-12",
        "participation_status": "contributed",
        "contribution_type": "compulsory_state",
        "basis_input_type": "mau_07_sbh_components",
        "sbh_components": {"unit": "coefficient", "base_value": "1.91"},
    }


def test_pre1995_zeroed_sbh_components_are_duration_only():
    payload = {
        "person": {"date_of_birth": "1971-12-07", "sex": "female"},
        "pension_start_month": "2026-06",
        "retirement_case": "normal",
        "contributions": [{
            "from_month": "1993-06",
            "to_month": "1994-12",
            "participation_status": "contributed",
            "contribution_type": "compulsory_state",
            "basis_input_type": "mau_07_sbh_components",
            "sbh_components": {
                "unit": "coefficient",
                "base_value": "0",
                "position_allowance": "0",
                "seniority_beyond_frame_allowance": "0",
                "professional_seniority_allowance": "0",
                "regional_allowance": "0",
                "other_allowance": "0",
                "reelection_allowance": "0"
            }
        }]
    }
    validate_v2_payload(payload)
    req = to_internal(payload)
    row = req.contributions[0]
    assert row.participation_status.value == "credited_duration_only"
    assert row.duration_only_reason.value == "pre1995_duration_excluded_from_average_basis"
    assert row.basis_input_type is None
    assert row.monthly_basis_vnd is None
    assert row.sbh_components is None
    diag = validate_request(req)
    assert diag.response.validation is True, diag.issues


def test_pre1995_blank_basis_validation_is_calculable_and_not_need_data():
    # Guards the BAU_154 failure mode: confirmed PRE-1995 time is duration-only
    # even when salary cells are blank. It must not be surfaced as missing data.
    payload = {
        "person": {"date_of_birth": "1970-10-21", "sex": "female"},
        "pension_start_month": "2026-07",
        "retirement_case": "normal",
        "contributions": [
            {
                "from_month": "1990-08",
                "to_month": "1993-03",
                "participation_status": "credited_duration_only",
                "duration_only_reason": "pre1995_duration_excluded_from_average_basis",
                "contribution_type": "compulsory_state",
                "source_text": "Mức đóng/tiền lương trống trên hồ sơ"
            },
            {
                "from_month": "1993-04",
                "to_month": "1994-12",
                "participation_status": "credited_duration_only",
                "duration_only_reason": "pre1995_duration_excluded_from_average_basis",
                "contribution_type": "compulsory_state",
                "source_value": "1,74",
                "source_unit": "unknown",
                "source_text": "1,74"
            },
            _post1995_basis_row(),
        ],
    }
    validate_v2_payload(payload)
    req = to_internal(payload)
    diag = validate_request(req)
    assert diag.response.validation is True, diag.issues
    assert sum(
        1 for c in req.contributions
        if c.participation_status.value == "credited_duration_only"
    ) == 2
    assert all(c.sbh_components is None and c.monthly_basis_vnd is None
               for c in req.contributions[:2])


def test_pre1995_coefficient_like_basis_from_legacy_client_is_ignored_for_average():
    # Legacy clients may still send a PRE-1995 value as a coefficient component.
    # R1.9 must normalize the row to duration-only and strip the basis internally.
    payload = {
        "person": {"date_of_birth": "1970-10-21", "sex": "female"},
        "pension_start_month": "2026-07",
        "retirement_case": "normal",
        "contributions": [
            {
                "from_month": "1993-04",
                "to_month": "1994-12",
                "participation_status": "contributed",
                "contribution_type": "compulsory_state",
                "basis_input_type": "mau_07_sbh_components",
                "sbh_components": {"unit": "coefficient", "base_value": "1.74"},
                "source_value": "1,74",
                "source_unit": "unknown",
            },
            _post1995_basis_row(),
        ],
    }
    validate_v2_payload(payload)
    req = to_internal(payload)
    first = req.contributions[0]
    assert first.participation_status.value == "credited_duration_only"
    assert first.duration_only_reason.value == "pre1995_duration_excluded_from_average_basis"
    assert first.basis_input_type is None
    assert first.sbh_components is None
    assert first.monthly_basis_vnd is None
    diag = validate_request(req)
    assert diag.response.validation is True, diag.issues
    records = expand_records(req)
    assert all(r.basis_vnd is None for r in records if r.month.year < 1995)


def test_pre1995_vnd_like_basis_262_from_legacy_client_is_ignored_for_average():
    # The raw token 262 is not reinterpreted as 2.62. Even if a legacy client
    # labeled it monthly_basis_vnd, PRE-1995 calculation uses duration only.
    payload = {
        "person": {"date_of_birth": "1970-10-21", "sex": "female"},
        "pension_start_month": "2026-07",
        "retirement_case": "normal",
        "contributions": [
            {
                "from_month": "1993-04",
                "to_month": "1994-12",
                "participation_status": "contributed",
                "contribution_type": "compulsory_state",
                "basis_input_type": "total_vnd",
                "monthly_basis_vnd": "262",
                "source_value": "262",
                "source_unit": "unknown",
            },
            _post1995_basis_row(),
        ],
    }
    validate_v2_payload(payload)
    req = to_internal(payload)
    first = req.contributions[0]
    assert first.participation_status.value == "credited_duration_only"
    assert first.duration_only_reason.value == "pre1995_duration_excluded_from_average_basis"
    assert first.basis_input_type is None
    assert first.monthly_basis_vnd is None
    assert first.sbh_components is None
    diag = validate_request(req)
    assert diag.response.validation is True, diag.issues


def test_pre1995_raw_value_does_not_change_post1995_average():
    # Blank / coefficient-like / VND-like PRE-1995 variants must converge to
    # the same average because only POST-1995 basis rows are eligible.
    variants = [
        {
            "participation_status": "credited_duration_only",
            "duration_only_reason": "pre1995_duration_excluded_from_average_basis",
            "source_text": "blank",
        },
        {
            "participation_status": "credited_duration_only",
            "duration_only_reason": "pre1995_duration_excluded_from_average_basis",
            "source_value": "1,72",
            "source_unit": "unknown",
        },
        {
            "participation_status": "credited_duration_only",
            "duration_only_reason": "pre1995_duration_excluded_from_average_basis",
            "source_value": "262",
            "source_unit": "unknown",
        },
    ]
    averages = []
    for variant in variants:
        pre = {
            "from_month": "1993-01",
            "to_month": "1994-12",
            "contribution_type": "compulsory_state",
            **variant,
        }
        payload = {
            "person": {"date_of_birth": "1970-10-21", "sex": "female"},
            "pension_start_month": "2026-07",
            "retirement_case": "normal",
            "contributions": [pre, _post1995_basis_row()],
        }
        validate_v2_payload(payload)
        req = to_internal(payload)
        average, _, _, _ = calculate_average_salary(req, expand_records(req))
        averages.append(average)

    assert len(set(averages)) == 1
