# Khắc phục lỗi xác thực GPT Action - calculatePension v2.2.1

Phiên bản này chấp nhận hai cách xác thực bằng cùng một biến môi trường `API_KEY`:

1. `X-API-Key: <API_KEY>` — tương thích ngược.
2. `Authorization: Bearer <API_KEY>` — khuyến nghị cho GPT Actions.

API tự loại khoảng trắng đầu/cuối và dấu nháy bao quanh bị nhập nhầm trong biến môi trường Render.

## Cấu hình GPT Action khuyến nghị

- Authentication: API Key
- Auth type: Bearer
- Secret: chỉ nhập giá trị API_KEY, không nhập chữ `Bearer`
- Schema: `openapi-gpt-action.yaml`

## Cập nhật Render

Đưa toàn bộ mã nguồn v2.2.1 lên GitHub/Render. Chờ `/health` trả `version: 2.2.1` rồi mới thay Authentication của GPT sang Bearer.

## Kiểm tra thủ công

Chạy `test-calculatePension-auth.ps1`. Nếu cả X-API-Key và Bearer đều thành công, API và Render đúng; chỉ cần sửa Authentication trong GPT.
