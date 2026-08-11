## 1.0.9-rc — Early retirement Case 1 + Case 2

- **Preserved:** all V1.0/AR77 mixed-salary logic, B_HUONG1 and O_Quy2 official regression behavior, plus AR78 Render keep-warm workflow.
- **Case 1:** `retirement_case=reduced_capacity`, `retirement_policy=none`; requires at least 240 months compulsory BHXH and `impairment_percent >= 61`; V1.x supports early retirement up to 5 years. Reduction follows current Article 66 rule: 2% per full year, no reduction for a remainder under 6 months, 1% for 6–<12 months.
- **Case 2:** `retirement_case=normal`, `retirement_policy=decree_154_streamlining`; supports normal working conditions, sufficient compulsory contribution duration for pension, early retirement up to 5 years, and **no pension-rate reduction for early retirement**.
- Hazardous/special-region, underground-coal and other special policies remain out of scope.
- Added official ND154 ground-truth regression and early-retirement unit tests.

## 1.0.7-rc — Mixed State + Employer salary correction

- **Preserved:** all V1.0.6/AR75 behavior and the B_HUONG1 official regression result.
- **Fixed:** mixed salary profiles containing State salary coefficients plus employer VND salary.
- For mixed profiles, the State component uses the prescribed State averaging window (for this O_Quy case: 60 months), then the resulting State average is weighted by the **full State contribution duration**, including pre-01/1995 months that count toward contribution duration but are excluded from the average-basis window.
- The employer component continues to use each VND salary multiplied by the 2026 salary adjustment coefficient.
- Added official O_Quy2 regression test: 403 months, average 8,655,801 VND, 73%, pension 6,318,735 VND, one-time retirement allowance 0.
- Render deployment remains FastAPI/Uvicorn: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.

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

## V1.0.8 / AR78 — Render Free Keep-Warm

- Giữ nguyên Calculation Engine V1.0.7 / AR77.
- Giữ nguyên logic B_HUONG1 và mixed salary O_Quy2.
- Bổ sung GitHub Actions workflow ping `GET /health` khoảng 14 phút/lần.
- Không sử dụng API key cho health check.
- Không thay đổi GPT Actions/OpenAPI contract.
