# TEST REPORT — calculatePension API V67.4.1

Ngày chạy: 2026-07-31

Kết quả:

```text
18 passed
```

Phạm vi kiểm thử:
- validation hợp lệ;
- trùng/chồng;
- khoảng trống;
- dòng `not_participating`;
- trước 01/1995;
- hai phương thức mức đóng;
- hợp đồng response;
- trợ cấp một lần không đủ điều kiện;
- trợ cấp một lần 1 tháng vượt;
- tách phần vượt trước/sau tuổi;
- Nghị định 154 không giảm tỷ lệ;
- reduced_capacity có giảm tỷ lệ;
- lỗi request 400;
- calculate tự validate lại;
- operationId OpenAPI;
- BHXH tự nguyện trước 2008;
- lỗi xác thực chuẩn hóa;
- `pension_only` không trả trường trợ cấp null;
- đối chiếu tháng đủ tuổi nghỉ hưu cho trợ cấp một lần.

Các ví dụ request/response đã được kiểm tra bằng JSON Schema V67.4.1.
