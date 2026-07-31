# SOURCE AUDIT

## Nguồn hợp đồng

- `SCHEMA_V67.4_Complete_OneTimeAllowance.json`
  - request bắt buộc: `person`, `pension_start_month`, `retirement_case`, `contributions`;
  - 4 `retirement_case`;
  - `retirement_policy`;
  - `retirement_age_eligible_month`;
  - `benefit_calculation_scope`;
  - response lương hưu và đối tượng `one_time_retirement_allowance`.

- `calculatePension_Instructions_V67.3.txt`
  - workflow bắt buộc validate trước calculate;
  - không tự tạo dữ liệu;
  - xử lý trước 01/1995;
  - quy tắc Mẫu 07/SBH;
  - ngưỡng trợ cấp một lần nữ >360 tháng, nam >420 tháng;
  - tách phần 0,5 và 2 lần;
  - không làm tròn thời gian vượt.

## Nguồn dữ liệu nghiệp vụ đã chuẩn hóa vào runtime

- `DM_01_Dien_bien_luong_co_so.xlsx`
  → `data/base_salary_timeline.json`
- `DM_02_He_so_dieu_chinh_2026.xlsx`
  → `data/adjustment_coefficients_2026.json`
- `DM_03_Tra_cuu_tuoi_nghi_huu.xlsx`
  → `data/retirement_age_schedule.json`
- `DM_04_So_nam_binh_quan_luong_Nha_nuoc.xlsx`
  → `data/state_average_windows.json`

Các bảng còn lại được dùng để đối chiếu công thức, cấu trúc Mẫu 07/SBH và chính sách; không được dùng làm dữ liệu mặc định cho hồ sơ người dùng.

## Quyết định thiết kế an toàn

1. Chỉ tính cho năm hưởng 2026 vì bộ hệ số tích hợp chỉ có năm 2026.
2. `calculatePension` luôn chạy lại validation để tránh bỏ qua luồng bắt buộc.
3. `other_special_policy` trả validation=false vì schema không có đủ căn cứ/quyết định để tự động hóa.
4. Khi có trợ cấp một lần, `retirement_age_eligible_month` được đối chiếu với tháng tuổi API tra theo lộ trình.
5. Thời gian vượt được giữ theo tháng:
   - trước/sát tuổi: `months / 12 × 0,5 × average`;
   - sau tuổi và đủ điều kiện: `months / 12 × 2 × average`.
6. Không áp dụng mức 2 lần cho toàn bộ thời gian vượt.
7. Không trả số lương hưu khi hồ sơ hoặc điều kiện không hợp lệ.
