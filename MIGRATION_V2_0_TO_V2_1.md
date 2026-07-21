# Chuyển calculatePension v2.0 lên v2.1

## Thay đổi không tương thích cần lưu ý

Dòng `credited_duration_only` phải bổ sung:

```json
"duration_only_reason": "pre1995_no_salary_or_living_allowance"
```

Không gán trạng thái này cho mọi giai đoạn trước năm 1995.

Dòng ghi rõ không tham gia:

```json
{
  "from_month": "2005-01",
  "to_month": "2005-12",
  "participation_status": "not_participating",
  "source_text": "Không tham gia BHXH"
}
```

không cần `monthly_basis_vnd`, `contribution_type` hoặc xác nhận lại.

## Kết quả mới cần trình bày

- `average_basis.average_monthly_basis_vnd`
- `average_basis.basis_months_used`
- `contribution_summary.credited_duration_only_months`
- `contribution_summary.excluded_non_participation_months`
- `pension_calculation_formula`

## Cập nhật

1. Thay các file trong repository bằng gói vá v2.1.
2. Commit lên GitHub để Render triển khai lại.
3. Thay OpenAPI schema trong GPT.
4. Thay Instructions và Knowledge bằng phiên bản mới.
5. Mở cuộc trò chuyện Preview mới để kiểm thử.
