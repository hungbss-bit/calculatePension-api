# calculatePension API v2.1

API FastAPI kiểm tra dữ liệu Mẫu 07/SBH và dự tính lương hưu BHXH Việt Nam.

## Ba thay đổi chính của v2.1

1. **Trạng thái từng giai đoạn**
   - `contributed`: tính vào tổng thời gian và mức bình quân.
   - `credited_duration_only`: chỉ cộng thời gian; chỉ dùng trước 01/01/1995 khi hồ sơ xác định thời gian được công nhận nhưng không hưởng tiền lương/sinh hoạt phí. Bắt buộc gửi `duration_only_reason=pre1995_no_salary_or_living_allowance`.
   - `not_participating`: dòng ghi rõ “Không tham gia BHXH”; tự loại khỏi tổng thời gian và mức bình quân, không yêu cầu mức đóng hoặc xác nhận lại.

2. **Không loại toàn bộ thời gian trước năm 1995**
   - Tháng trước năm 1995 có đóng và có tiền lương làm căn cứ vẫn là `contributed`.
   - Hệ số “Trước năm 1995” vẫn được dùng khi tháng lương đó thuộc diện điều chỉnh.
   - Chỉ giai đoạn đặc biệt không hưởng lương/sinh hoạt phí mới là `credited_duration_only`.

3. **Trả mức bình quân trước tỷ lệ**
   - `average_basis.average_monthly_basis_vnd`
   - `average_basis.basis_months_used`
   - `pension_rate.final_rate_percent`
   - `pension_calculation_formula`
   - `estimated_monthly_pension_vnd`

## Endpoint

- `GET /health`
- `GET /v1/capabilities`
- `POST /v1/validateContributionHistory`
- `POST /v1/calculatePension`

## Quy trình Mẫu 07/SBH

1. GPT đọc từng giai đoạn.
2. Gán `participation_status`.
3. Dòng `not_participating` được loại tự động.
4. Dòng `credited_duration_only` phải có căn cứ pháp lý cụ thể.
5. GPT hiển thị dữ liệu để xác nhận đối với các dòng được tính.
6. Gọi `validateContributionHistory`.
7. Khi hợp lệ, gọi `calculatePension`.

Khoảng trống không có dòng trạng thái vẫn phải được xác nhận; chỉ dòng ghi rõ “Không tham gia BHXH” mới được tự động loại.

## Cài đặt Windows

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Mở `http://127.0.0.1:8000/docs`.

## Kiểm thử

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## Render

Giữ biến môi trường `API_KEY`. Render dùng:

```text
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

## Custom GPT

1. Dán `gpt-instructions.txt` vào Instructions.
2. Tải bộ Knowledge v1.1.
3. Nhập `openapi-gpt-action.yaml` hoặc JSON.
4. Authentication: API Key, custom header `X-API-Key`.
5. Thay `https://YOUR_PUBLIC_HTTPS_DOMAIN` bằng URL Render thật.

Kết quả là ước tính; hồ sơ do cơ quan BHXH xác nhận và quy định có hiệu lực tại thời điểm giải quyết là căn cứ cuối cùng.
