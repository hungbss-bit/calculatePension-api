# Báo cáo rà soát calculatePension API v2.0

## Mục tiêu

Đồng bộ API với Instructions v3 và bộ Knowledge, bảo đảm dữ liệu từ Mẫu 07/SBH được kiểm tra và chuẩn hóa trước khi tính.

## Các vấn đề của v1.x đã sửa

1. **Không có lớp kiểm tra Mẫu 07/SBH** → bổ sung nguồn hồ sơ, trạng thái xác nhận, dòng nguồn, đơn vị và kiểu mức đóng.
2. **Tháng trùng phát sinh lỗi 422 chung** → trả kết quả nghiệp vụ `needs_more_data` kèm dòng/tháng cụ thể.
3. **Không kiểm soát khoảng trống** → phát hiện khoảng trống và yêu cầu xác nhận là thời gian không đóng.
4. **Có thể gửi hệ số lương thô như tiền đồng** → chặn `salary_coefficient`/`unknown` cho đến khi quy đổi.
5. **Quá trình hỗn hợp dùng tổng tháng để xét mọi điều kiện** → tách số tháng bắt buộc và tự nguyện; điều kiện chính sách bắt buộc xét 15/20 năm bắt buộc, tổng thời gian dùng tính tỷ lệ.
6. **Giảm do nghỉ trước tuổi dùng ngưỡng tuổi của một năm khác** → dùng tuổi áp dụng trong chính năm nghỉ hưu.
7. **Có thể dùng hệ số 2026 cho năm hưởng khác** → bắt buộc `coefficient_year` trùng năm hưởng.
8. **Mức sàn chuyển tiếp áp dụng quá rộng** → chỉ áp dụng khi đầu vào xác nhận điều kiện.
9. **Trợ cấp một lần có thể tách sai thời gian đủ điều kiện** → dùng `eligibility_achieved_month` hoặc suy ra từ tuổi, thời gian đóng và tháng giám định; nếu không đủ dữ liệu thì trả `null` kèm cảnh báo.
10. **Thiếu kiểm toán** → bổ sung bảng điều chỉnh theo năm, căn cứ, giả định và các bước tính.

## Endpoint mới

- `GET /v1/capabilities`
- `POST /v1/validateContributionHistory`
- `POST /v1/calculatePension`

## Kết quả kiểm thử

- 15/15 bài kiểm thử thành công.
- Bao phủ: ví dụ nữ 30 năm, nghỉ do suy giảm, quá trình hỗn hợp, nghề đặc thù, tháng trống, tháng trùng, hệ số thô, sai năm hệ số, lương Nhà nước, trợ cấp một lần và thiếu tối đa 6 tháng.

## Giới hạn có chủ đích

- API không OCR trực tiếp PDF/ảnh.
- API không tự xác nhận nghề thuộc danh mục đặc thù.
- API không tự quy đổi hệ số lương Nhà nước nếu thiếu đầy đủ dữ liệu pháp lý và thành phần lương.
- Bộ hệ số tích hợp sẵn chỉ có năm 2026.
