# Thay đổi từ bản nháp V2.0 sang V2.1

- Giữ hai operation nghiệp vụ cũ; bổ sung server production và xác thực API key thống nhất.
- Sửa tháng hưởng bình thường sớm nhất thành tháng liền kề sau tháng đủ tuổi.
- Sửa số tháng nghỉ hưu trước tuổi bị thiếu một tháng do dùng sai mốc so sánh.
- Bổ sung nhánh suy giảm khả năng lao động từ 81% trở lên, giới hạn tối đa 10 năm; bắt buộc tháng kết luận giám định.
- Khóa NĐ 154: không tính nếu chưa xác nhận thẩm quyền, căn cứ không trừ tỷ lệ và trạng thái chứng cứ.
- Không còn để GPT gửi các loại nghỉ hưu mà Engine chưa tự động hóa.
- Trả chi tiết khoảng trống, tháng trùng và lỗi hồ sơ thay vì mảng rỗng.
- Bổ sung `maternity_leave` vào hợp đồng Action.
- Bổ sung `after_retirement_age_period` và tự suy ra mốc tuổi khi tính trợ cấp.
- Bổ sung nhập phụ cấp thâm niên nghề theo phần trăm và quy đổi quyết định tại backend.
- Bổ sung `base_salary_vnd_override` cho thành phần hệ số.
- Bổ sung mức sàn lương hưu chuyển tiếp khi hồ sơ xác nhận đủ điều kiện và cung cấp mức tham chiếu.
- Bổ sung chi tiết trợ cấp một lần trước/sau tuổi; sửa công thức giải thích để khớp cách quy đổi năm.
- Bổ sung căn cứ pháp lý, dấu vết dữ liệu nguồn và kiểm toán thành phần Mẫu 07/SBH trong response.
- Sửa Dockerfile để đóng gói contracts và chạy bằng người dùng không đặc quyền.
- Khóa phiên bản phụ thuộc để triển khai lặp lại ổn định.
- Mở rộng từ 16 lên 87 phép kiểm thử.
