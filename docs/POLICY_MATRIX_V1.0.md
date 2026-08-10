# POLICY MATRIX V1.0 — AI Agent Hưu trí

## 1. Phạm vi

| ID | Rule | V1.0 |
|---|---|---|
| SCOPE-001 | Nghỉ hưu bình thường | SUPPORTED |
| SCOPE-002 | Nghề nặng nhọc/độc hại/đặc thù | OUT_OF_SCOPE |
| SCOPE-003 | Hầm lò | OUT_OF_SCOPE |
| SCOPE-004 | Suy giảm khả năng lao động | OUT_OF_SCOPE |
| SCOPE-005 | Chính sách nghỉ hưu đặc thù/tinh giản | OUT_OF_SCOPE |
| SCOPE-006 | Điều chỉnh tăng lương hưu sau nghỉ | OUT_OF_SCOPE |
| SCOPE-007 | BHXH một lần | OUT_OF_SCOPE |
| SCOPE-008 | Trợ cấp một lần khi nghỉ hưu | SUPPORTED |

## 2. Identity

| ID | Rule | V1.0 |
|---|---|---|
| ID-001 | Số sổ BHXH thật | Dùng làm định danh nghiệp vụ |
| ID-002 | Số sổ trắng/che | Sinh `temporary_id=YYYYMMDDHHMM` theo múi giờ Việt Nam; mã này có thể trùng trong cùng một phút, `calculation_id` là khóa duy nhất của lần tính |
| ID-003 | Một số sổ được hỏi nhiều lần | Mỗi lần tính có `calculation_id` riêng |
| ID-004 | HoSoID nhân tạo | Không dùng làm khóa nghiệp vụ chính |

## 3. PRE-1995

| ID | Rule | V1.0 |
|---|---|---|
| PRE95-001 | Thời gian hợp lệ trước 01/1995 | Vẫn cộng vào tổng thời gian |
| PRE95-002 | Có mức lương, ví dụ 262 VND | Không làm mất thời gian |
| PRE95-003 | Không có mức lương/hệ số | Không làm mất thời gian |
| PRE95-004 | Quân đội/dân sự trước 1995 | Được xử lý theo dữ liệu thời gian được xác nhận; không tự đồng nhất với chế độ hưu đặc thù |
| PRE95-005 | Đưa PRE-1995 vào bình quân | V1.0 dùng `pre1995_policy` để loại khỏi bình quân trong gói dữ liệu này |

## 4. Tỷ lệ lương hưu

| ID | Rule |
|---|---|
| RATE-001 | Nữ: 45% tại 15 năm, +2%/năm, tối đa 75% |
| RATE-002 | Nam: 45% tại 20 năm, +2%/năm, tối đa 75% |
| RATE-003 | Nam 15–<20 năm: 40% tại 15 năm, +1%/năm |
| RATE-004 | Thời gian tháng lẻ khi tính mức hưởng: 01–06 tháng = 0,5 năm; 07–11 tháng = 1 năm |
| RATE-005 | Không giảm tỷ lệ do nghỉ sớm trong V1.0 |

## 5. Mức bình quân

| ID | Rule |
|---|---|
| AVG-001 | Lương Nhà nước: xác định cửa sổ bình quân theo thời điểm bắt đầu tham gia |
| AVG-002 | Lương doanh nghiệp: bình quân toàn bộ thời gian thuộc chế độ này |
| AVG-003 | Nhà nước + doanh nghiệp: bình quân chung theo tổng thời gian; phần Nhà nước được bình quân theo quy định riêng |
| AVG-004 | BHXH tự nguyện: thu nhập sau điều chỉnh |
| AVG-005 | Bắt buộc + tự nguyện: bình quân chung theo công thức tổng hợp |
| AVG-006 | Hệ số lương và mức tiền: tách rõ loại dữ liệu, không tự suy đoán |

## 6. Trợ cấp một lần khi nghỉ hưu

| ID | Rule |
|---|---|
| OA-001 | Nam >35 năm có thể phát sinh trợ cấp |
| OA-002 | Nữ >30 năm có thể phát sinh trợ cấp |
| OA-003 | Phần vượt đến tuổi nghỉ hưu: 0,5 lần mức bình quân/năm |
| OA-004 | Phần vượt sau khi đã đủ điều kiện tuổi: 2 lần mức bình quân/năm |
| OA-005 | Engine giữ thời gian theo tháng, không làm tròn sớm thành năm |

## 7. Versioning

Mỗi kết quả phải ghi:

- `calculation_id`
- `engine_version`
- `policy_version`

## 8. Release Gate

Không phát hành V1.0 nếu:

- Golden tests thất bại;
- API contract không khớp;
- OUT_OF_SCOPE bị tính tự động;
- PRE-1995 bị mất khỏi tổng thời gian;
- một số sổ được hỏi nhiều lần làm ghi đè/nhầm Calculation;
- thiếu dữ liệu quan trọng nhưng Engine vẫn tự đoán.
