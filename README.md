# calculatePension API V1.0.5-rc — AI Agent Hưu trí

API phục vụ **dự tính lương hưu tại thời điểm nghỉ hưu**, không phải quyết định giải quyết chế độ. V1.0 được khóa phạm vi theo các nguyên tắc đã thống nhất trong thiết kế AI Agent Hưu trí.

## 1. Phạm vi V1.0

### Hỗ trợ
- Nghỉ hưu **bình thường**.
- Tổng thời gian đóng BHXH bắt buộc + tự nguyện theo dữ liệu đầu vào.
- Thời gian trước 01/1995: vẫn tính vào tổng thời gian nếu hồ sơ xác nhận là thời gian được tính; mức lương/hệ số có thể có hoặc không có.
- Tiền lương theo hệ số và theo mức tiền.
- Quá trình kết hợp Nhà nước + doanh nghiệp.
- Quá trình kết hợp BHXH bắt buộc + BHXH tự nguyện.
- Trợ cấp một lần khi nghỉ hưu.
- Một số sổ BHXH được hỏi nhiều lần: mỗi lần có `calculation_id` riêng.

### Không hỗ trợ trong V1.0
- Nghề/công việc nặng nhọc, độc hại, nguy hiểm hoặc đặc biệt nặng nhọc, độc hại, nguy hiểm.
- Hầm lò.
- Suy giảm khả năng lao động.
- Chính sách nghỉ hưu đặc thù/tinh giản.
- Điều chỉnh tăng lương hưu sau khi đã nghỉ hưu.
- BHXH một lần.

Các trường hợp ngoài phạm vi phải trả `validation=false` hoặc `OUT_OF_SCOPE_*`, không tự suy đoán.

## 2. Định danh

`identity.so_bhxh` là tùy chọn.

- Có số sổ thật: giữ nguyên số sổ làm định danh nghiệp vụ.
- Để trắng hoặc che số: API sinh `temporary_id` 12 chữ số theo `YYYYMMDDHHMM` theo múi giờ Việt Nam (`Asia/Ho_Chi_Minh`).
- `temporary_id` không thay thế `calculation_id`; mỗi lần tính vẫn có UUID riêng để phân biệt các lần hỏi.
- API V1.0 không cần tạo một `HoSoID` nhân tạo làm khóa nghiệp vụ chính.

## 3. Workflow

```text
validateContributionHistory
        ↓ validation=true
calculatePension
        ↓
Calculation + Identity + Result
```

`calculatePension` luôn chạy lại validation.

## 4. PRE-1995

Ví dụ một giai đoạn 1990–1994 có mức 262 VND hoặc không có mức lương/hệ số: **thời gian vẫn phải được tính vào tổng thời gian BHXH** nếu đủ căn cứ xác nhận. Thiếu dữ liệu tiền lương không được biến thời gian thành 0.

Trong V1.0, phần PRE-1995 được đánh dấu `pre1995_policy` và không đưa trực tiếp vào mức bình quân theo chính sách dữ liệu hiện hành của gói này.

## 5. Tỷ lệ lương hưu

V1.0 sử dụng nhóm quy tắc của Điều 66 trong Văn bản hợp nhất 58/VBHN-VPQH 2025:

- Nữ: 45% tại 15 năm, thêm 2%/năm, tối đa 75%.
- Nam: 45% tại 20 năm, thêm 2%/năm, tối đa 75%.
- Nam từ đủ 15 đến dưới 20 năm: 40% tại 15 năm, thêm 1%/năm.

Không áp dụng giảm tỷ lệ do nghỉ sớm trong V1.0 vì các trường hợp nghỉ sớm thuộc phạm vi đặc thù đã được loại khỏi V1.0.

## 6. Mức bình quân

Engine tách riêng các nguồn:

- `compulsory_state`;
- `compulsory_employer`;
- `voluntary`.

Đối với trường hợp vừa bắt buộc vừa tự nguyện, V1.0 giữ nguyên mô hình bình quân chung theo tổng thời gian và mức bình quân tiền lương bắt buộc + tổng thu nhập tự nguyện sau điều chỉnh.

## 7. Dữ liệu năm 2026

Bộ hệ số điều chỉnh tích hợp hiện chỉ dành cho năm hưởng 2026. Nếu `pension_start_month` không thuộc năm 2026, API từ chối để tránh áp dụng nhầm bảng hệ số.

## 8. API

- `POST /v1/validateContributionHistory`
- `POST /v1/calculatePension`
- `GET /health`
- `GET /docs`

OpenAPI V1.0: `openapi-calculatePension-V1.0.yaml`

Schema V1.0: `SCHEMA_V1.0_Deploy.json`

## 9. Authentication

```text
X-API-Key
```

Render environment:

```text
API_KEY=<secret>
REQUIRE_API_KEY=true
AUTH_DIAGNOSTICS_ENABLED=false
```

## 10. Kiểm thử

```bash
python -m pytest -q -p no:cacheprovider
```

Release gate tối thiểu:

```text
Policy → Golden Test → Engine → API Contract
```

## 11. Tuyên bố

Đây là kết quả **dự tính**, không thay thế quyết định giải quyết chế độ của cơ quan BHXH có thẩm quyền.

## 12. Quy tắc temporary_id

`temporary_id` 12 chữ số chỉ là mã tạm theo phút, không phải định danh duy nhất tuyệt đối. Nếu nhiều yêu cầu không cung cấp số sổ đến trong cùng một phút, chúng có thể có cùng `temporary_id`; `calculation_id` UUID mới là định danh duy nhất của từng lần tính.

## AR-71 release note

The repository is a V1.0 Release Candidate. Local certification tests must pass before merge/release. Production deployment requires `REQUIRE_API_KEY=true` (the application default is also secure-by-default), provide `API_KEY` via the platform secret store, enable HTTPS, and perform a real deployment smoke test. Local `pytest` success alone does not constitute production certification.
