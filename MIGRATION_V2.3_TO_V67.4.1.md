# MIGRATION V2.3 → V67.4.1

## Endpoint giữ nguyên

- `POST /v1/validateContributionHistory`
- `POST /v1/calculatePension`

## Thay đổi bắt buộc phía client

### Request

Bỏ các trường V2.3 không có trong schema V67.4, ví dụ:

- `source_document_type`
- `history_confirmed`
- `gaps_confirmed_as_non_contribution`
- `early_retirement_policy`
- `hazardous_match_status`
- `hazardous_catalog_code`
- `adjustment`
- `state_salary_values_are_converted`

Dùng đúng:

- `retirement_policy`
- `retirement_age_eligible_month`
- `benefit_calculation_scope`
- `average_inclusion`
- `average_exclusion_reason`
- `after_retirement_age_period`

### Kiểu mức đóng

V67.4 chỉ cho một trong hai:

```json
{
  "basis_input_type": "monthly_basis_vnd",
  "monthly_basis_vnd": 10000000
}
```

hoặc:

```json
{
  "basis_input_type": "mau_07_sbh_components",
  "sbh_components": {
    "unit": "coefficient",
    "base_value": 6.1,
    "position_allowance": 0.3
  }
}
```

### Response validate

Từ mô hình chi tiết V2.3 sang:

```json
{
  "validation": true,
  "normalized_summary": {
    "total_contribution_months": 360,
    "excluded_bhtn_months": 0,
    "contribution_count": 1
  },
  "warnings": []
}
```

### Response calculate

Dùng trực tiếp các trường V67.4:

- `total_months`
- `average_salary`
- `replacement_rate`
- `rate_before_early_reduction`
- `contribution_month_remainder_rate`
- `early_retirement_months`
- `early_retirement_reduction`
- `rate_after_reduction`
- `estimated_pension`
- `one_time_retirement_allowance`

## Action

Xóa schema Action cũ và nhập lại `SCHEMA_V67.4.1_Deploy.json`.

Authentication giữ:

```text
X-API-Key
```
