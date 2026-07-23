# calculatePension API v2.3.0

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


## Xác thực GPT Action — bản hoàn thiện v2.2.0

API chỉ sử dụng:

```http
X-API-Key: <API_KEY>
```

Không sử dụng Bearer.

Biến Render bắt buộc:

```text
API_KEY=<khóa bí mật>
REQUIRE_API_KEY=true
AUTH_DIAGNOSTICS_ENABLED=false
```

Khi cần chẩn đoán, tạm đặt `AUTH_DIAGNOSTICS_ENABLED=true`, chọn **Save and deploy**, rồi dùng:

- `openapi-auth-diagnostic-xapikey.yaml` trong GPT Action; hoặc
- `test-auth-v220-xapikey.ps1` trên Windows.

Endpoint `/v1/authDiagnostics` chỉ trả độ dài, fingerprint rút gọn và kết quả so khớp; không trả khóa bí mật. Sau khi sửa xong, đặt lại `AUTH_DIAGNOSTICS_ENABLED=false`.

Để tránh GPT giữ cấu hình secret cũ, nên xóa Action cũ và tạo một Action mới hoàn toàn:

```text
Authentication: API Key
Type: Custom header
Header: X-API-Key
Secret: chỉ nhập giá trị API_KEY
```
