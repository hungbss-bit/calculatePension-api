# CHANGELOG

## 1.0.0 — V1.0 scope hardening

### Phạm vi nghiệp vụ
- Khóa V1.0 chỉ hỗ trợ nghỉ hưu bình thường.
- Đưa nghề nặng nhọc/độc hại, hầm lò, suy giảm khả năng lao động và chính sách đặc thù ra ngoài phạm vi tự động hóa.
- Không tính điều chỉnh tăng lương hưu sau thời điểm nghỉ.

### Định danh và truy vết
- Bổ sung `identity.so_bhxh` tùy chọn.
- Khi số sổ trống/che, sinh `temporary_id` 12 chữ số theo `YYYYMMDDHHMM`.
- Mỗi lần tính sinh `calculation_id` UUID riêng, cho phép một số sổ được hỏi nhiều lần mà không ghi đè lần tính.
- Bổ sung `engine_version` và `policy_version` vào response.

### PRE-1995
- Khóa nguyên tắc thời gian PRE-1995 vẫn được tính vào tổng thời gian.
- Mức lương/hệ số PRE-1995 có thể có hoặc không có; không vì thiếu mức lương mà loại thời gian.

## 1.0.1 — AR-64 Calculation Trace

- Bổ sung `calculation.trace` vào response.
- Trace ghi số tháng thời gian, số tháng làm căn cứ bình quân, phương pháp bình quân, tỷ lệ và công thức đầu ra.
- Regenerate OpenAPI/SCHEMA từ FastAPI runtime.
- Regression tests: 23 passed.


## 1.0.2
- Temporary ID dùng múi giờ `Asia/Ho_Chi_Minh`, không phụ thuộc múi giờ máy chủ Render.
- Làm rõ `temporary_id` chỉ là mã tạm theo phút; `calculation_id` là định danh duy nhất của từng lần tính.
- Cập nhật API version/diagnostics version.


## 1.0.5-rc — AR-70 Production readiness
- Added request body size guard (2 MiB default).
- Added security response headers.
- Added GitHub Actions certification workflow with least-privilege permissions.
- Added Dependabot configuration and dependency review workflow.
- Added SECURITY.md and production-readiness documentation.
- Synchronized runtime/API/engine version to 1.0.5-rc.
- Kept V1.0 business scope unchanged.

## 1.0.5-rc — AR-72
- Secure-by-default API key requirement.
- Fixed GitHub source-hygiene private-key grep invocation.
- Final release audit documentation.
- Removed generated runtime cache artifacts from release contents.

## 1.0.5-rc — AR-73 Final local release audit
- Synchronized runtime/API/engine/auth diagnostics version to 1.0.5-rc.
- Enforced request-body size limit for both Content-Length and streamed/chunked requests.
- Sanitized unhandled exception responses so internal exception types are not exposed.
- Added V1.0 security regression tests.
- Added AR-73 final release audit documentation.


## 1.0.6-rc — Average salary and retirement allowance correction
- Fixed State-salary coefficient conversion: use the pension-month base salary/reference for coefficient records, not the historical monthly base salary.
- Prevented double application of annual salary adjustment coefficients for State-salary coefficient records.
- Fixed one-time retirement allowance month-to-year conversion: 1–6 months = 0.5 year; 7–11 months = 1 year.
- Added regression coverage for the official B_HUONG2 calculation profile.
