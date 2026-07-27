# calculatePension — Bộ nâng cấp V66

## 1. Thành phần

1. `calculatePension_Instructions_V66.txt`
   - Dán toàn bộ vào **Instructions** của Custom GPT.
   - Chuẩn hóa luồng bắt buộc:
     `validateContributionHistory` -> `calculatePension`.
   - Không cho GPT tự tính thay API.
   - Không cho kết luận mức lương hưu trước khi có response `calculatePension`.

2. `calculatePension_OpenAPI_V66.yaml`
   - Dán vào **Actions > Schema**.
   - Giữ server đang dùng trong schema gần nhất:
     `https://calculatepension-api.onrender.com`
   - Giữ API version là `3.1.0`.
   - Gắn nhãn riêng `x-gpt-config-version: V66`, để không nhầm V66 với phiên bản backend.

3. `calculatePension_V66_README.md`
   - File hướng dẫn này.

## 2. Nguồn dùng để dựng V66

V66 được hợp nhất từ:
- `GPT_Instructions_v3.1_FINAL.txt`
- `openapi-gpt-action_v2.3.15.yaml`
- `Ban_de_tri_thuc_calculatePension.docx` (Bản đề tri thức v1.2)
- `DM_06_Mau_07_SBH.xlsx`

Các file danh mục còn lại tiếp tục là Knowledge/nguồn tra cứu theo vai trò đã quy định.

## 3. Điểm chuẩn hóa chính của V66

### A. Action
Bắt buộc:
1. Tạo `PensionCalculationRequest`.
2. Gọi `validateContributionHistory`.
3. Chỉ khi `validation = true` mới gọi `calculatePension`.
4. Chỉ sau response `calculatePension` mới được nêu mức lương hưu.

### B. Mẫu 07/SBH
Dùng:
`basis_input_type = mau_07_sbh_components`

Gửi `sbh_components`, gồm:
- `unit`
- `base_value`
- `position_allowance`
- `seniority_beyond_frame_allowance`
- `professional_seniority_allowance`
- `regional_allowance`
- `other_allowance`
- `reelection_allowance`

Không gửi đồng thời `monthly_basis_vnd`.

### C. Hệ số Nhà nước
Các giá trị như `1.581`, `3.990`, `5.360` không được tự hiểu là VND trong bối cảnh lương Nhà nước/07-SBH.

### D. Phụ cấp %
Không gửi `"14%"`.
Phải quy đổi thành số cùng đơn vị trước khi gọi Action.

Ví dụ:
`3.990 x 14% = 0.5586`

Gửi:
`professional_seniority_allowance: 0.5586`

### E. BHTN
Dòng được nhận diện theo quy tắc Instructions là BHTN:
- `participation_status = not_participating`
- không dùng tính tổng thời gian hưu
- không dùng tính bình quân
- không gửi vào `calculatePension`

### F. Thời gian chỉ cộng thời gian
Chỉ dùng:
`credited_duration_only`

khi:
- trước 01/01/1995
- có căn cứ công nhận
- không hưởng tiền lương/sinh hoạt phí

và gửi:
`duration_only_reason = pre1995_no_salary_or_living_allowance`

### G. Response bắt buộc đọc
Sau `calculatePension`:
- `total_months`
- `average_salary`
- `replacement_rate`
- `early_retirement_reduction`
- `estimated_pension`
- `warnings`

## 4. Cách nâng cấp trong GPT Builder

### Instructions
Xóa phần Instructions cũ và dán nội dung từ:
`calculatePension_Instructions_V66.txt`

### Knowledge
Giữ/đính kèm các file:
- `Ban_de_tri_thuc_calculatePension.docx`
- `DM_01_Dien_bien_luong_co_so.xlsx`
- `DM_02_He_so_dieu_chinh_2026.xlsx`
- `DM_03_Tra_cuu_tuoi_nghi_huu.xlsx`
- `DM_04_So_nam_binh_quan_luong_Nha_nuoc.xlsx`
- `DM_05_Vi_du_tinh_luong_huu.xlsx`
- `DM_06_Mau_07_SBH.xlsx`
- `Danh_muc_nghe_nang_nhoc_doc_hai_hien_hanh_2026.xlsx`

### Action
Thay Schema hiện tại bằng:
`calculatePension_OpenAPI_V66.yaml`

Giữ cấu hình Authentication hiện đang chạy của Action. File V66 không tự thay đổi cơ chế xác thực vì schema gần nhất được dùng làm căn cứ không mô tả security scheme.

## 5. Kiểm thử tối thiểu sau nâng cấp

### Test 1 — Mẫu 07/SBH lương Nhà nước
Đầu vào có:
- `base_value = 3.990`
- `TN Nghề = 14%`

Kỳ vọng request có:
- `basis_input_type = mau_07_sbh_components`
- `unit = coefficient`
- `professional_seniority_allowance = 0.5586`
- không có `monthly_basis_vnd`

### Test 2 — BHTN
Kỳ vọng:
- không đưa dòng BHTN vào `calculatePension`
- không tính vào bình quân

### Test 3 — Validation lỗi
Kỳ vọng GPT nêu:
- operation đã gọi
- mã lỗi/HTTP status nếu có
- `detail`
- `field`
- không tự tính tiếp

### Test 4 — Validation thành công
Kỳ vọng:
- `validation = true`
- GPT bắt buộc gọi `calculatePension`
- trả đủ 6 trường kết quả
- kết thúc bằng câu tuyên bố ước tính.

## 6. Lưu ý kỹ thuật

V66 là **phiên bản cấu hình GPT**, không phải tuyên bố rằng backend đã nâng lên API 6.6.
Metadata API vẫn là `3.1.0` vì đó là phiên bản được schema gần nhất của bạn khai báo.

Schema V66 giữ đúng hai endpoint gần nhất:
- `/validateContributionHistory`
- `/calculatePension`

Nếu backend thực tế đổi path hoặc response sau bản `openapi-gpt-action_v2.3.15.yaml`, cần cập nhật Schema tương ứng trước khi triển khai.
