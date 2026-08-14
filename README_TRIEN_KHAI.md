# AI Agent Hưu trí V2.1

Bộ phát hành gồm GPT Instructions V2.1, GPT Action Schema V2.1 và calculatePension API 2.4.0. Phiên bản này dành cho cán bộ giải quyết chế độ và chỉ tự động kết luận trong phạm vi đã nêu tại `PHAM_VI_NGHIEP_VU_V2.1.md`.

## 1. Thứ tự triển khai bắt buộc

1. Triển khai lại backend từ toàn bộ thư mục này.
2. Chờ endpoint `/health` trả đúng `version=2.4.0`, `action_schema_version=2.1.0`, `engine_version=1.1.0`.
3. Sau đó mới thay Instructions và Action Schema trong GPT đang sử dụng.

Không ghép Action Schema V2.1 với backend 2.3.0 cũ vì hợp đồng dữ liệu và các khóa kiểm soát nghiệp vụ không tương thích hoàn toàn.

## 2. Triển khai backend trên Render

Có thể dùng `render.yaml` hoặc tạo Web Service với các lệnh:

```text
Build command: pip install -r requirements.txt
Start command: uvicorn app.main:app --host 0.0.0.0 --port $PORT
Health check: /health
```

Biến môi trường bắt buộc:

```text
API_KEY=<khóa bí mật mạnh, không đưa vào mã nguồn>
REQUIRE_API_KEY=true
AUTH_DIAGNOSTICS_ENABLED=false
MAX_REQUEST_BODY_BYTES=2097152
PYTHON_VERSION=3.13.5
```

Endpoint kiểm tra sau triển khai:

```text
https://calculatepension-api.onrender.com/health
https://calculatepension-api.onrender.com/version
https://calculatepension-api.onrender.com/privacy-policy
```

Gói Render miễn phí có thể ngủ khi không hoạt động. GPT Action có giới hạn thời gian phản hồi; môi trường vận hành thực tế nên dùng dịch vụ luôn hoạt động hoặc gói không cold-start.

## 3. Cấu hình GPT

1. Mở GPT Builder và thay toàn bộ phần Instructions bằng nội dung `INSTRUCTIONS_V2.1_FINAL.txt`.
2. Trong Actions, nhập `GPT_ACTION_SCHEMA_V2.1_FINAL.yaml`.
3. Chọn Authentication = API Key, kiểu Custom, header `X-API-Key`.
4. Giá trị khóa phải trùng tuyệt đối với `API_KEY` trên Render.
5. Privacy Policy URL: `https://calculatepension-api.onrender.com/privacy-policy`.
6. Giữ các văn bản pháp luật, quy trình nghiệp vụ và hồ sơ mẫu đã ẩn danh trong Knowledge; không đưa khóa API hoặc dữ liệu cá nhân thật vào Knowledge.

## 4. Kiểm tra nghiệm thu nhanh

Thực hiện theo thứ tự:

1. Gọi `validateContributionHistory` với một hồ sơ hợp lệ: phải trả `valid_for_calculation=true`.
2. Gọi lại cùng hồ sơ với `history_confirmed=false`: phải trả `valid_for_calculation=false` và mã `HISTORY_NOT_CONFIRMED`.
3. Hồ sơ NĐ 154 với một trong ba xác nhận bị thiếu phải bị chặn.
4. Hồ sơ có khoảng trống hoặc tháng trùng phải trả chi tiết tại `gaps`, `overlaps`, `issues`.
5. Chỉ khi validate hợp lệ mới gọi `calculatePension`.
6. Kết quả phải có `legal_references`, `source_trace`, `basis_component_audit` (nếu dùng Mẫu 07/SBH) và chi tiết trợ cấp một lần.

## 5. Vận hành an toàn

- Không tắt `REQUIRE_API_KEY` ở môi trường thật.
- Chỉ bật `AUTH_DIAGNOSTICS_ENABLED` tạm thời khi chẩn đoán, sau đó tắt ngay.
- Không ghi khóa API vào Schema, Instructions, log, ảnh chụp hoặc hồ sơ kiểm thử.
- Luôn giữ câu cảnh báo: “Đây là kết quả ước tính, không thay thế quyết định giải quyết chế độ của cơ quan BHXH.”
- Với trường hợp ngoài phạm vi tự động, GPT phải trả `MANUAL_REVIEW`; không đổi loại hồ sơ để ép API tính.

## 6. Kiểm thử nhà phát triển

```text
python -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest -q
```

Bộ phát hành hiện có 87 phép kiểm thử đạt.
