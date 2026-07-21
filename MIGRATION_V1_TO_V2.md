# Nâng cấp từ v1.x lên v2.0

## Tương thích

Các trường cũ vẫn dùng được:

- `person`
- `pension_start_month`
- `retirement_case`
- `contributions[].from_month`
- `contributions[].to_month`
- `contributions[].monthly_basis_vnd`
- `contributions[].contribution_type`
- `coefficient_override`
- các trường nghề/địa bàn và suy giảm khả năng lao động
- `adjustment`

## Trường mới nên truyền khi dữ liệu đến từ Mẫu 07/SBH

```json
{
  "source_document_type": "mau_07_sbh",
  "history_confirmed": true,
  "gaps_confirmed_as_non_contribution": true,
  "contributions": [{
    "basis_input_type": "total_vnd",
    "confirmation_status": "confirmed",
    "source_row_id": "07-SBH-01",
    "source_text": "Nội dung dòng gốc"
  }]
}
```

## Thay đổi hành vi

1. Khoảng trống chưa xác nhận trả `needs_more_data`.
2. Tháng trùng trả `needs_more_data`, không ném lỗi tính toán chung.
3. `monthly_basis_vnd` phải là VND; hệ số thô bị từ chối nghiệp vụ.
4. `coefficient_year` phải trùng năm của `pension_start_month`.
5. Điều kiện quá trình hỗn hợp căn cứ số tháng BHXH bắt buộc; tổng thời gian bắt buộc + tự nguyện dùng tính tỷ lệ.
6. Nghỉ do suy giảm khả năng lao động dùng tuổi tham chiếu của năm nghỉ để tính giảm.
7. Mức sàn không còn tự động áp dụng nếu chưa có xác nhận `transitional_minimum_floor_eligible=true`.
8. Trợ cấp một lần có thể trả `null` nếu chưa xác định được tháng đồng thời đủ mọi điều kiện.

## Cập nhật GPT Action

Xóa schema Action cũ và nhập lại `openapi-gpt-action.yaml` hoặc `openapi-gpt-action.json`. Giữ nguyên header `X-API-Key`.
