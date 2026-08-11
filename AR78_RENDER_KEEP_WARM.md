# AR78 — Render Free Keep-Warm Configuration

## Mục đích

AR78 **không thay đổi Calculation Engine V1.0.7/AR77**. Bản này chỉ bổ sung cơ chế giữ Render Free Web Service hoạt động bằng một GitHub Actions workflow gọi endpoint `/health` khoảng 14 phút/lần.

Endpoint được gọi:

`https://calculatepension-api.onrender.com/health`

## Vì sao gọi `/health`?

- Request rất nhẹ.
- Không thực hiện phép tính lương hưu.
- Không gửi dữ liệu hồ sơ.
- Không cần `X-API-Key`.
- Không ảnh hưởng dữ liệu người dùng.

Trong API hiện tại, `/health` là endpoint công khai và các endpoint tính toán `/v1/*` vẫn bảo vệ bằng `X-API-Key`.

## Lịch GitHub Actions

Workflow:

`.github/workflows/keep-render-warm.yml`

Cron:

`*/14 * * * *`

Điều này tạo các lần chạy ở phút:

`00, 14, 28, 42, 56` mỗi giờ (UTC).

GitHub Actions scheduler không phải đồng hồ thời gian thực và có thể có độ trễ. Vì vậy đây là biện pháp giảm nguy cơ Render sleep do idle, **không phải cam kết uptime 100%**.

## Cách triển khai

1. Copy toàn bộ package AR78 lên repository GitHub đang chứa API.
2. Commit/push.
3. Render tiếp tục deploy service hiện tại.
4. Vào GitHub → Actions → `Keep Render Free Service Warm` để kiểm tra workflow.
5. Có thể bấm `Run workflow` để kiểm tra thủ công.

Không cần tạo API key mới.
Không cần đưa `API_KEY` vào GitHub.
Không cần sửa GPT Action.

## Kiểm tra

Workflow phải nhận HTTP thành công từ:

`https://calculatepension-api.onrender.com/health`

Nếu `/health` trả HTTP 200, step sẽ kết thúc thành công.

## Giới hạn quan trọng

Keep-warm chỉ xử lý trường hợp Render đưa Free Web Service vào trạng thái ngủ do không có traffic. Nó không ngăn được mọi trường hợp restart, lỗi nền tảng, bảo trì hoặc giới hạn tài nguyên của gói Free. Khi hệ thống phục vụ production quan trọng, nên dùng instance trả phí/giải pháp uptime phù hợp.


## AR79 calculation additions

This package retains the AR78 keep-warm workflow and adds the two controlled early-retirement branches described in the V1.0.9 release notes.
