# calculatePension API v2.3.0

Phiên bản này giữ nguyên xác thực `X-API-Key` và bổ sung:

- Ghi nhận ứng viên nghề nặng nhọc từ Mẫu 07/SBH.
- Chỉ tính thời gian nghề nặng nhọc sau khi người dùng xác nhận đúng mã/tên nghề, điều kiện và giai đoạn.
- Tổng hợp `hazardous_summary` và bảng kiểm toán các giai đoạn đã xác nhận.
- Trường hợp `policy_no_reduction` cho nghỉ hưu trước tuổi không giảm tỷ lệ.
- Hỗ trợ có điều kiện NĐ 154/2025, NĐ 178/2024 sửa bởi NĐ 67/2025, NĐ 177/2024 và văn bản khác do người dùng cung cấp.
- Bắt buộc số/ngày quyết định của cấp có thẩm quyền.
- Không hỗ trợ lực lượng vũ trang; `armed_forces` trả `manual_review`.

## Knowledge cần tải lên GPT

- `Danh_muc_nghe_nang_nhoc_doc_hai_hien_hanh_2026.xlsx`
- `DM_07_Chinh_sach_nghi_huu_truoc_tuoi_khong_giam_2026.xlsx`
- Các tệp Knowledge v1.2 hiện có.

## Kiểm thử

`37 passed`
