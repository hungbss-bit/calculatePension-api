# AR80 — Bổ sung xử lý NGHỈ HƯỞNG CHẾ ĐỘ THAI SẢN

## Mục tiêu

Chỉ bổ sung nghiệp vụ cho dòng Mẫu 07/SBH thể hiện **NGHỈ HƯỞNG CHẾ ĐỘ THAI SẢN**; giữ nguyên các quy tắc đang có của V1.0.9-rc.

## Quy tắc được bổ sung

- Input sử dụng:
  - `participation_status = credited_duration_only`
  - `duration_only_reason = maternity_leave`
  - `contribution_type` phải giữ đúng nhóm đóng của thời gian liền kề trước kỳ nghỉ.
- Các tháng thai sản được cộng vào tổng thời gian BHXH.
- Dòng thai sản không nhập `monthly_basis_vnd`, `sbh_components` hoặc `basis_input_type`.
- Engine tự kế thừa mức đóng/hệ số của **tháng liền kề ngay trước kỳ nghỉ**.
- Các tháng thai sản liên tiếp tiếp tục dùng mức đã kế thừa.
- Kiểu căn cứ và đơn vị được giữ nguyên:
  - lương doanh nghiệp VND → kế thừa VND;
  - lương Nhà nước bằng hệ số → kế thừa căn cứ đã quy đổi từ cùng hệ số và vẫn giữ `component_unit=coefficient`;
  - lương Nhà nước nhập VND → kế thừa VND.
- Từ 01/1995 trở đi, tháng thai sản được đưa vào mức bình quân với mức đóng kế thừa.
- Nếu không xác định được mức đóng của tháng liền kề trước kỳ nghỉ, validation trả `MATERNITY_PREVIOUS_BASIS_MISSING`.
- Nếu `contribution_type` của dòng thai sản không khớp với tháng trước, validation trả `MATERNITY_CONTRIBUTION_TYPE_MISMATCH`.
- Nếu người gọi tự nhập mức đóng/hệ số vào dòng thai sản, validation trả `MATERNITY_BASIS_MUST_BE_INHERITED`.

## Phạm vi thay đổi mã nguồn

- `app/models.py`: thêm enum `maternity_leave`.
- `app/engine.py`: validation, cộng thời gian và kế thừa mức đóng.
- `tests/test_maternity_leave.py`: 5 kiểm thử mới.
- OpenAPI/Schema V1.0: cập nhật enum để GPT Action có thể gửi `maternity_leave`.

## Kiểm thử

Các kiểm thử mới xác nhận:
1. 6 tháng thai sản được cộng đủ vào tổng thời gian.
2. 6 tháng thai sản kế thừa đúng mức lương doanh nghiệp của tháng trước.
3. Kết quả mức bình quân/lương hưu giống hệt trường hợp nhập thủ công 6 tháng với cùng mức đóng.
4. Hệ số lương Nhà nước được kế thừa đúng kiểu căn cứ.
5. Thiếu tháng liền kề trước kỳ nghỉ hoặc tự nhập mức đóng vào dòng thai sản bị từ chối.

Lưu ý: bộ mã nguồn đầu vào đã có 4 test cũ đang fail tại `tests/test_api_v674.py`; AR80 không sửa các lỗi cũ đó vì yêu cầu là chỉ bổ sung thai sản.
