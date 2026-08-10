# AR-67 — Golden Profiles V1.0

## Mục đích

Bộ Golden Profiles kiểm định độc lập chuỗi:

`Input → Duration → Average Basis → Pension Rate → Estimated Pension → One-time Retirement Allowance`

Các Expected Values được xác lập bằng một reference calculation độc lập với `app.engine.calculate`, sử dụng cùng các bảng dữ liệu Policy V1.0 đã đóng gói trong repository.

> Đây là bộ kiểm thử kỹ thuật/nghiệp vụ của API, không phải quyết định giải quyết chế độ cho một cá nhân.

## 10 hồ sơ

| ID | Kịch bản | Tháng | Bình quân (đồng) | Tỷ lệ | Lương hưu dự tính (đồng/tháng) |
|---|---|---:|---:|---:|---:|
| G01 | Doanh nghiệp – nữ | 187 | 12,464,171 | 47% | 5,858,160 |
| G02 | Nhà nước theo mức tiền – nữ | 187 | 11,353,333 | 47% | 5,336,067 |
| G03 | Nhà nước theo hệ số – nữ | 187 | 4,587,058 | 47% | 2,155,917 |
| G04 | Nhà nước → doanh nghiệp – nữ | 187 | 8,155,080 | 47% | 3,832,888 |
| G05 | Doanh nghiệp → Nhà nước – nữ | 187 | 12,100,107 | 47% | 5,687,050 |
| G06 | Bắt buộc → tự nguyện – nữ | 223 | 12,105,471 | 53% | 6,415,900 |
| G07 | Nhà nước → doanh nghiệp → tự nguyện – nữ | 187 | 8,052,406 | 47% | 3,784,631 |
| G08 | PRE-1995 có 262 đồng → doanh nghiệp – nữ | 439 | 24,267,018 | 75% | 18,200,264 |
| G09 | PRE-1995 không có lương/hệ số → doanh nghiệp – nữ | 439 | 29,120,422 | 75% | 21,840,317 |
| G10 | PRE-1995 lịch sử quân đội/dân sự + doanh nghiệp + trợ cấp – nam | 499 | 24,267,018 | 75% | 18,200,264 |

## G10 — trợ cấp một lần khi nghỉ hưu

- Ngưỡng nam: 420 tháng.
- Tổng thời gian: 499 tháng.
- Thời gian vượt: 79 tháng.
- Trước/sát tuổi nghỉ hưu: 65 tháng.
- Sau tuổi nghỉ hưu: 14 tháng.
- Trợ cấp phần trước/sát tuổi: 65,723,175 đồng.
- Trợ cấp phần sau tuổi: 56,623,043 đồng.
- Tổng trợ cấp: **122,346,218 đồng**.

## Kết quả

`27 passed`

Bao gồm 25 test hồi quy trước đó và 2 test Golden mới.

## Lưu ý thiết kế

G10 dùng nhãn mô tả "lịch sử quân đội/dân sự" để kiểm thử nguyên tắc PRE-1995; V1.0 hiện **không suy diễn chế độ hưu trí đặc thù quân đội** từ nhãn này và schema chưa dùng một trường `military_service` để quyết định eligibility.

V1.0 tiếp tục loại khỏi phạm vi tự động hóa:

- nghề nặng nhọc, độc hại;
- hầm lò;
- suy giảm khả năng lao động;
- các chính sách nghỉ hưu đặc thù;
- BHXH một lần;
- điều chỉnh tăng lương hưu sau khi nghỉ.
