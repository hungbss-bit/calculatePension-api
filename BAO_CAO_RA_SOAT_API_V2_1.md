# Báo cáo rà soát calculatePension v2.1

## Kết luận pháp lý quan trọng

Không được loại toàn bộ thời gian trước 01/01/1995 khỏi mức bình quân.

API phân biệt:

- `contributed`: có tiền lương/thu nhập làm căn cứ; dùng tính thời gian và bình quân.
- `credited_duration_only`: thời gian trước 01/01/1995 được công nhận nhưng không hưởng tiền lương/sinh hoạt phí; chỉ cộng thời gian.
- `not_participating`: không tham gia BHXH; loại khỏi toàn bộ phép tính.

## Kết quả trả về

API luôn tách rõ:

1. Tổng thời gian được tính.
2. Số tháng chỉ cộng thời gian.
3. Số tháng không tham gia đã loại.
4. Số tháng có mức đóng dùng bình quân.
5. Mức bình quân trước khi nhân tỷ lệ.
6. Tỷ lệ hưởng.
7. Công thức và lương hưu dự tính.

## Kiểm soát

- Không cho dùng `credited_duration_only` sau năm 1994.
- Không cho dùng trạng thái này nếu thiếu `duration_only_reason`.
- Không yêu cầu mức đóng cho `not_participating`.
- Không dùng hệ số sai năm hưởng.
