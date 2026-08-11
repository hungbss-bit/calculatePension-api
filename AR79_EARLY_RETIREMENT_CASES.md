# AR79 — Early Retirement Case 1 + Case 2

## Mục tiêu

Bổ sung đúng hai nhánh nghỉ hưu trước tuổi đã được thống nhất, không thay đổi các logic tính toán đã đúng của V1.0/AR77 và cơ chế keep-warm AR78.

## Case 1 — Suy giảm khả năng lao động

Request:
- `retirement_case`: `reduced_capacity`
- `retirement_policy`: `none`
- `impairment_percent`: từ 61% trở lên

Phạm vi V1.x:
- BHXH bắt buộc tối thiểu 20 năm.
- Nghỉ trước tuổi không quá 5 năm.
- Giảm tỷ lệ theo Điều 66 Luật BHXH 2024: 2% cho mỗi năm nghỉ trước; phần lẻ dưới 6 tháng không giảm; từ đủ 6 đến dưới 12 tháng giảm 1%.

## Case 2 — Tinh giản biên chế theo NĐ 154/2025/NĐ-CP

Request:
- `retirement_case`: `normal`
- `retirement_policy`: `decree_154_streamlining`

Phạm vi V1.x:
- Chỉ tự động hóa điều kiện lao động bình thường.
- Có đủ thời gian BHXH bắt buộc để hưởng lương hưu.
- Nghỉ trước tuổi không quá 5 năm.
- Không trừ tỷ lệ lương hưu do nghỉ trước tuổi.
- Hồ sơ Ground Truth `ND154.pdf` của bà Nguyễn Thị Báu đạt: 35 năm 11 tháng, bình quân 19.117.846 đồng, tỷ lệ 75%, lương hưu 14.338.385 đồng/tháng, trợ cấp một lần khi nghỉ hưu 57.353.538 đồng.

## GPT workflow

Khi phát hiện thời điểm hưởng trước tuổi bình thường, GPTs phải hỏi:

> Bạn nghỉ hưu trước tuổi theo chính sách nào?
> 1. Suy giảm khả năng lao động
> 2. Tinh giản biên chế theo Nghị định 154/2025/NĐ-CP

Chỉ sau khi người dùng xác nhận lựa chọn, GPTs mới gọi API. Không tự suy đoán chính sách.

## Ngoài phạm vi

- Nghề/công việc nặng nhọc, độc hại, đặc biệt nặng nhọc, độc hại.
- Hầm lò.
- Vùng đặc biệt khó khăn và các nhánh chính sách đặc thù khác chưa được thống nhất cho V1.x.

## Ground Truth

- `158_TRUOCTUOI.pdf`: hồ sơ tham chiếu cho Case 1.
- `ND154.pdf`: hồ sơ giải quyết chính thức của bà Nguyễn Thị Báu theo NĐ 154/2025/NĐ-CP, dùng làm regression ground truth cho Case 2.
