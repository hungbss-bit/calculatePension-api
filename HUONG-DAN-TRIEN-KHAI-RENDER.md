# HƯỚNG DẪN ĐƯA calculatePension LÊN RENDER MIỄN PHÍ

## Kết quả sau khi triển khai

Render cấp một địa chỉ dạng:

https://calculatepension-api.onrender.com

Đây là địa chỉ HTTPS công khai. Bạn không cần mua tên miền riêng để thử GPT
Actions.

Các URL quan trọng:

- Tài liệu API: `/docs`
- Kiểm tra hoạt động: `/health`
- OpenAPI do FastAPI sinh: `/openapi.json`
- Chính sách quyền riêng tư: `/privacy-policy`
- Endpoint tính lương hưu: `/v1/calculatePension`

## 1. Đưa mã nguồn lên GitHub

Tạo repository mới, ví dụ `calculatePension-api`.

Khi tải mã nguồn lên, thư mục gốc của repository phải chứa trực tiếp:

- `app`
- `requirements.txt`
- `render.yaml`
- `.python-version`
- `openapi-gpt-action.yaml`

Không để toàn bộ các tệp nằm thêm một cấp thư mục không cần thiết.

Không tải thư mục `.venv` lên GitHub.

## 2. Triển khai bằng Render Blueprint

1. Đăng nhập Render bằng GitHub.
2. Chọn **New** → **Blueprint**.
3. Chọn repository `calculatePension-api`.
4. Render tự đọc file `render.yaml`.
5. Khi được hỏi biến `API_KEY`, nhập một khóa bí mật dài.
6. Chọn **Apply** hoặc **Deploy Blueprint**.
7. Chờ trạng thái chuyển thành **Live**.

Có thể tạo khóa bằng PowerShell:

```powershell
py -c "import secrets; print(secrets.token_urlsafe(48))"
```

Lưu khóa này ở nơi an toàn vì phải nhập cùng khóa trong GPT Action.

## 3. Kiểm tra API

Thay `TEN-DICH-VU` bằng tên Render thực tế:

```text
https://TEN-DICH-VU.onrender.com/health
https://TEN-DICH-VU.onrender.com/docs
https://TEN-DICH-VU.onrender.com/privacy-policy
```

`/health` phải trả về:

```json
{"status":"ok","service":"calculatePension"}
```

## 4. Cập nhật OpenAPI cho GPT Action

Mở `openapi-gpt-action.yaml` và thay:

```yaml
servers:
  - url: https://YOUR_PUBLIC_HTTPS_DOMAIN
```

bằng:

```yaml
servers:
  - url: https://TEN-DICH-VU.onrender.com
```

Chỉ dùng URL gốc, không thêm `/docs`.

## 5. Khai báo trong GPT Editor

Trong GPT Editor:

1. Vào **Configure** → **Actions** → **Create new action**.
2. Authentication: **API key**.
3. Kiểu: **Custom header**.
4. Header name: `X-API-Key`.
5. Secret: nhập đúng `API_KEY` đã khai báo trên Render.
6. Dán nội dung file `openapi-gpt-action.yaml`.
7. Nhập Privacy Policy URL:

```text
https://TEN-DICH-VU.onrender.com/privacy-policy
```

8. Bấm **Test** ở action `calculatePension`.
9. Kiểm thử trong cửa sổ Preview trước khi lưu hoặc chia sẻ GPT.

## 6. Lưu ý về gói miễn phí

Dịch vụ miễn phí có thể tạm ngủ khi không có truy cập. Lần gọi đầu sau một
khoảng không hoạt động có thể chậm. Gói này thích hợp để thử nghiệm và sử dụng
quy mô nhỏ; không phù hợp cho dịch vụ hành chính hoặc sản xuất đòi hỏi sẵn sàng
liên tục.

## 7. Không công khai khóa API

Không ghi API key vào:

- GitHub;
- `openapi-gpt-action.yaml`;
- README;
- mã Python;
- ảnh chụp màn hình.

Khóa chỉ được lưu trong Render Environment và phần Authentication của GPT
Action.
