# calculatePension API V67.4.1 — Deploy ngay

Bản nâng cấp đồng bộ payload với `SCHEMA_V67.4_Complete_OneTimeAllowance.json` và workflow `validateContributionHistory` → `calculatePension`.

## Điểm đã hoàn thiện

- Request/response đúng hợp đồng V67.4.
- Chỉ chấp nhận 4 `retirement_case`: `normal`, `hazardous_or_special_region`, `underground_coal`, `reduced_capacity`.
- Kiểm tra tháng đảo, trùng/chồng, khoảng trống, dòng sau tháng hưởng, trạng thái tham gia và phương thức mức đóng.
- Tách đúng thời gian trước 01/1995: vẫn cộng thời gian nhưng loại khỏi mức bình quân khi dùng `pre1995_policy`.
- Loại `not_participating`/BHTN khỏi thời gian và mức bình quân.
- Quy đổi Mẫu 07/SBH theo 7 thành phần; hệ số lương Nhà nước được nhân mức lương cơ sở/mức tham chiếu theo dữ liệu tích hợp.
- Tính bình quân lương Nhà nước, doanh nghiệp, tự nguyện và quá trình hỗn hợp.
- Tính tỷ lệ trước/sau giảm nghỉ trước tuổi.
- Tính trợ cấp một lần theo số tháng vượt, tách:
  - đến tháng đủ tuổi: `tháng vượt / 12 × 0,5 × mức bình quân`;
  - sau tháng đủ tuổi và đủ điều kiện: `tháng vượt / 12 × 2 × mức bình quân`.
- Không làm tròn thời gian vượt thành năm.
- Chuẩn hóa lỗi HTTP thành `ErrorResponse`.
- Xác thực `X-API-Key`.
- Có 18 kiểm thử tích hợp.

## Giới hạn dữ liệu hiện tại

Bộ hệ số điều chỉnh tích hợp chỉ dành cho `pension_start_month` thuộc năm **2026**. API trả validation=false nếu dùng năm khác để tránh áp dụng sai bảng hệ số.

`retirement_policy=other_special_policy` chưa thể tự động hóa vì schema V67.4 không có trường quyết định/căn cứ chi tiết. `decree_154_streamlining` được xử lý theo lựa chọn đã xác nhận trong request và không giảm tỷ lệ.

Với `hazardous_or_special_region` hoặc `underground_coal`, lựa chọn `retirement_case` được coi là đã có hồ sơ xác nhận điều kiện tương ứng; API vẫn trả cảnh báo.

## Triển khai Render

1. Giải nén gói và đưa thư mục này lên GitHub.
2. Trên Render, tạo **Blueprint** từ repository; `render.yaml` đã cấu hình sẵn.
3. Thiết lập biến môi trường:
   - `API_KEY`: khóa bí mật dài, ngẫu nhiên;
   - `REQUIRE_API_KEY=true`;
   - `AUTH_DIAGNOSTICS_ENABLED=false`.
4. Deploy và kiểm tra:
   - `GET /health`
   - `GET /docs`

Build command:

```bash
pip install -r requirements.txt
```

Start command:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

## Triển khai Docker

```bash
docker build -t calculatepension:v67.4.1 .
docker run --rm -p 8000:8000 \
  -e API_KEY='replace-with-secret' \
  -e REQUIRE_API_KEY=true \
  calculatepension:v67.4.1
```

## Cấu hình GPT Action

Dùng file:

```text
SCHEMA_V67.4.1_Deploy.json
```

Authentication:

```text
Type: API Key
Auth type: Custom header
Header: X-API-Key
Secret: cùng giá trị API_KEY trên Render
```

Luồng gọi bắt buộc:

1. `validateContributionHistory`
2. Chỉ khi `validation=true`, gọi `calculatePension`

## Chạy kiểm thử

```bash
python -m pytest -q -p no:cacheprovider
```

## Ví dụ

- `examples/request_normal.json`
- `examples/request_normal_validation_response.json`
- `examples/request_normal_calculation_response.json`
- `examples/request_one_time_allowance_split.json`
- `examples/request_one_time_allowance_split_validation_response.json`
- `examples/request_one_time_allowance_split_calculation_response.json`

## Dữ liệu tích hợp

- `data/base_salary_timeline.json`
- `data/adjustment_coefficients_2026.json`
- `data/retirement_age_schedule.json`
- `data/state_average_windows.json`

Các tệp JSON này được chuẩn hóa từ bộ danh mục Excel đính kèm để runtime không phải cài thư viện xử lý Excel.

## Tuyên bố

Đây là kết quả ước tính, không thay thế quyết định giải quyết chế độ của cơ quan BHXH.
