# calculatePension API v2.2

API FastAPI kiểm tra dữ liệu Mẫu 07/SBH và dự tính lương hưu BHXH Việt Nam.

## Thay đổi chính của v2.2

### 1. Tính tổng hệ số/mức đóng từ Mẫu 07/SBH

Khi dữ liệu được đọc theo các cột của Mẫu 07/SBH, API áp dụng:

```text
Tổng hệ số/mức đóng
= Mức đóng
+ Chức vụ
+ TN VK
+ TN Nghề
+ Khu vực
+ Khác
+ Tái cử
```

Ô trống được tính bằng 0. Tất cả thành phần phải cùng đơn vị:

- `coefficient`: tổng hệ số được nhân với lương cơ sở để quy đổi sang VND/tháng;
- `vnd`: các thành phần được cộng trực tiếp thành VND/tháng.

Dữ liệu gửi bằng:

```json
{
  "basis_input_type": "mau_07_sbh_components",
  "sbh_components": {
    "unit": "coefficient",
    "base_value": 6.1,
    "position_allowance": 0.3,
    "seniority_beyond_frame_allowance": 0,
    "professional_seniority_allowance": 0,
    "regional_allowance": 0,
    "other_allowance": 0,
    "reelection_allowance": 0,
    "base_salary_vnd_override": 2530000
  }
}
```

Không gửi đồng thời `monthly_basis_vnd` và `sbh_components`, nhằm tránh cộng hai lần.

### 2. Bảng kiểm toán thành phần

Kết quả có `basis_component_audit`, thể hiện:

- Mức đóng gốc;
- từng loại phụ cấp;
- tổng phụ cấp;
- tổng hệ số/mức đóng;
- lương cơ sở dùng quy đổi;
- mức đóng VND/tháng;
- công thức tiếng Việt.

### 3. Giữ nguyên quy tắc v2.1

- `contributed`: tính thời gian và mức bình quân;
- `credited_duration_only`: chỉ cộng thời gian trước 01/01/1995 khi có căn cứ không hưởng lương/sinh hoạt phí;
- `not_participating`: loại khỏi thời gian và bình quân;
- trả mức bình quân trước khi nhân tỷ lệ hưởng.

## Endpoint

- `GET /health`
- `GET /v1/capabilities`
- `POST /v1/validateContributionHistory`
- `POST /v1/calculatePension`

## Cài đặt Windows

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Mở `http://127.0.0.1:8000/docs`.

## Custom GPT

1. Dán `gpt-instructions.txt` vào Instructions.
2. Tải Knowledge Pack v1.2.
3. Nhập `openapi-gpt-action.yaml`.
4. Authentication: API Key, custom header `X-API-Key`.
5. Thay `https://YOUR_PUBLIC_HTTPS_DOMAIN` bằng URL Render thật.

Kết quả là ước tính; hồ sơ do cơ quan BHXH xác nhận và quy định có hiệu lực tại thời điểm giải quyết là căn cứ cuối cùng.
