# CHANGELOG

## 67.4.1 — 2026-07-31

### Đồng bộ schema
- Thay mô hình request/response V2.3 cũ bằng hợp đồng V67.4.
- Loại các enum ngoài schema như `policy_no_reduction`, `occupational_hiv`, `armed_forces`.
- Bổ sung `retirement_policy`, `retirement_age_eligible_month`, `benefit_calculation_scope`.
- Chuẩn hóa `ValidationResponse`, `PensionCalculationResponse`, `ErrorResponse`.

### Nghiệp vụ
- Xử lý `pre1995_policy` đúng nguyên tắc: tính thời gian, loại khỏi bình quân.
- Không cho gửi đồng thời `monthly_basis_vnd` và `sbh_components`.
- Quy đổi hệ số Mẫu 07/SBH theo mức lương cơ sở/mức tham chiếu.
- Tính bình quân theo nhóm Nhà nước, doanh nghiệp, tự nguyện, hỗn hợp.
- Tính tỷ lệ tháng lẻ và giảm nghỉ trước tuổi.
- Bổ sung trợ cấp một lần chi tiết:
  - ngưỡng nữ 360 tháng, nam 420 tháng;
  - tách tháng vượt trước/sau tuổi nghỉ hưu;
  - mức 0,5 và 2 lần;
  - không làm tròn thời gian.

### Vận hành
- Chuẩn hóa xác thực `X-API-Key`.
- Thêm schema Action có security scheme.
- Thêm Render, Docker, ví dụ request/response.
- 18 kiểm thử tích hợp.
