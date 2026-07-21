from __future__ import annotations


def get_privacy_policy_html() -> str:
    return """<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Chính sách quyền riêng tư - calculatePension</title>
  <style>
    body {
      font-family: Arial, sans-serif;
      max-width: 900px;
      margin: 40px auto;
      padding: 0 20px;
      line-height: 1.65;
      color: #1f2937;
    }
    h1, h2 { color: #153e75; }
    .notice {
      padding: 14px 18px;
      background: #fff7ed;
      border-left: 5px solid #f97316;
      border-radius: 6px;
    }
    code { background: #f3f4f6; padding: 2px 5px; }
  </style>
</head>
<body>
  <h1>Chính sách quyền riêng tư của calculatePension</h1>
  <p><strong>Cập nhật:</strong> 20/07/2026</p>

  <div class="notice">
    Trước khi công bố GPT rộng rãi, đơn vị vận hành cần thay địa chỉ liên hệ
    mẫu ở cuối trang bằng thông tin liên hệ thật.
  </div>

  <h2>1. Dữ liệu được xử lý</h2>
  <p>
    Dịch vụ có thể tiếp nhận ngày sinh, giới tính, thời điểm dự kiến hưởng
    lương hưu và quá trình đóng bảo hiểm xã hội do người dùng chủ động cung cấp.
  </p>

  <h2>2. Mục đích xử lý</h2>
  <p>
    Dữ liệu chỉ được sử dụng để thực hiện phép tính dự kiến về điều kiện hưởng,
    tỷ lệ hưởng và mức lương hưu theo yêu cầu.
  </p>

  <h2>3. Lưu trữ dữ liệu</h2>
  <p>
    Phiên bản tham chiếu không chủ động lưu nội dung yêu cầu hoặc kết quả tính
    vào cơ sở dữ liệu. Nhà cung cấp hạ tầng có thể xử lý nhật ký kỹ thuật cần
    thiết để vận hành và bảo vệ dịch vụ.
  </p>

  <h2>4. Chia sẻ dữ liệu</h2>
  <p>
    Dữ liệu không được bán. Dữ liệu chỉ có thể được xử lý bởi nhà cung cấp hạ
    tầng trong phạm vi cần thiết để vận hành dịch vụ.
  </p>

  <h2>5. Bảo mật</h2>
  <p>
    Dịch vụ sử dụng HTTPS và khóa truy cập API. Người vận hành cần bảo vệ khóa,
    định kỳ thay khóa và không ghi toàn bộ hồ sơ cá nhân vào nhật ký ứng dụng.
  </p>

  <h2>6. Giới hạn trách nhiệm</h2>
  <p>
    Kết quả do calculatePension cung cấp chỉ là ước tính. Hồ sơ được cơ quan
    bảo hiểm xã hội xác nhận và quy định có hiệu lực tại thời điểm giải quyết
    chế độ là căn cứ quyết định.
  </p>

  <h2>7. Liên hệ</h2>
  <p>
    Email: <code>thay-email-that-cua-ban@example.com</code>
  </p>
</body>
</html>"""
