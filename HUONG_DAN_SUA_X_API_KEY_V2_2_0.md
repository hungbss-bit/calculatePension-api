# Xử lý X-API-Key cho calculatePension API v2.2.0

Bản này giữ nguyên phiên bản công khai **2.2.0** và chỉ sử dụng header:

```http
X-API-Key: <secret>
```

Không sử dụng Bearer.

## Thay đổi kỹ thuật

- Chuẩn hóa khoảng trắng và dấu nháy bao quanh API key.
- Đọc lần lượt `API_KEY`, `CALCULATEPENSION_API_KEY`, `X_API_KEY`.
- Trả mã lỗi riêng:
  - `X_API_KEY_MISSING`
  - `X_API_KEY_MISMATCH`
  - `API_KEY_NOT_CONFIGURED`
- Có endpoint chẩn đoán tạm thời `/v1/authDiagnostics`.
- Endpoint chẩn đoán không trả khóa bí mật, chỉ trả độ dài và fingerprint SHA-256 12 ký tự.

## Biến Render

```text
API_KEY=<khóa thật>
REQUIRE_API_KEY=true
AUTH_DIAGNOSTICS_ENABLED=true
```

Chọn **Save and deploy**. Sau khi sửa xong, đặt:

```text
AUTH_DIAGNOSTICS_ENABLED=false
```

và deploy lại.

## Chẩn đoán

Chạy:

```powershell
powershell -ExecutionPolicy Bypass -File .\test-auth-v220-xapikey.ps1
```

Kết quả quan trọng:

- `configured=false`: runtime không đọc được API_KEY.
- `received_present=false`: client không gửi X-API-Key.
- `normalized_match=false`: khóa client và khóa runtime khác nhau.
- `normalized_match=true`: khóa khớp; lỗi còn lại nằm ở cấu hình GPT Action.

## GPT Action

Nên xóa Action cũ và tạo **Action mới hoàn toàn** để tránh giữ cấu hình secret cũ.

Authentication:

```text
API Key
Custom header
X-API-Key
```

Không nhập tên header vào ô secret; chỉ nhập giá trị khóa.
