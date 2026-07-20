# Cập nhật giao diện Swagger sang tiếng Việt

## Cách nhanh nhất

1. Dừng API đang chạy bằng tổ hợp `Ctrl+C` trong PowerShell.
2. Sao lưu thư mục dự án hiện tại.
3. Chép đè ba tệp sau từ gói cập nhật:
   - `app/main.py`
   - `app/models.py`
   - `app/swagger_vi.py`
4. Tại thư mục dự án, chạy lại:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

5. Mở:

```text
http://127.0.0.1:8000/docs
```

6. Nhấn `Ctrl+F5` nếu trình duyệt còn hiển thị giao diện cũ.

## Hai địa chỉ tài liệu

- `/docs`: giao diện tiếng Việt.
- `/docs-en`: giao diện Swagger UI tiếng Anh để đối chiếu kỹ thuật.

## Vì sao tên trường JSON vẫn bằng tiếng Anh?

Các tên như `date_of_birth`, `pension_start_month` và `contributions` là tên
trường trong hợp đồng API. Đổi trực tiếp chúng sang tiếng Việt sẽ làm các yêu cầu
cũ và cấu hình ChatGPT Actions có nguy cơ không còn hoạt động. Vì vậy giao diện
hiển thị tiêu đề và mô tả tiếng Việt, còn khóa JSON được giữ ổn định.

## Nếu giao diện trắng hoặc không tải được

Swagger UI đang tải tệp CSS và JavaScript từ CDN. Hãy kiểm tra kết nối Internet,
sau đó tải lại trang. API tính toán vẫn chạy độc lập với giao diện tài liệu.
