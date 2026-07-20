from __future__ import annotations

from fastapi.responses import HTMLResponse


# Swagger UI hiện chưa có tham số cấu hình chính thức để đổi toàn bộ ngôn ngữ.
# Trang này giữ nguyên Swagger UI và dùng MutationObserver để dịch các nhãn
# giao diện được tạo động sang tiếng Việt.
SWAGGER_UI_VI_HTML = r'''<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>API tính lương hưu BHXH - Tài liệu tương tác</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css" />
  <style>
    html { box-sizing: border-box; overflow-y: scroll; }
    *, *::before, *::after { box-sizing: inherit; }
    body { margin: 0; background: #fafafa; }
    .swagger-ui .topbar { display: none; }
    .swagger-ui .info { margin: 34px 0 24px; }
    .swagger-ui .info .title { color: #17365d; }
    .swagger-ui .scheme-container {
      background: #fff;
      box-shadow: 0 1px 4px rgba(0, 0, 0, .12);
    }
    .swagger-ui .opblock-tag { font-size: 22px; }
    .swagger-ui .model-title { font-weight: 700; }
    .vi-banner {
      position: sticky;
      top: 0;
      z-index: 10;
      padding: 10px 20px;
      background: #17365d;
      color: #fff;
      font-family: Arial, sans-serif;
      font-size: 14px;
      box-shadow: 0 1px 4px rgba(0, 0, 0, .2);
    }
    .vi-banner strong { margin-right: 8px; }
  </style>
</head>
<body>
  <div class="vi-banner">
    <strong>calculatePension</strong>
    Tài liệu API tương tác bằng tiếng Việt. Tên trường JSON được giữ nguyên để bảo đảm tương thích với ChatGPT Actions.
  </div>
  <div id="swagger-ui"></div>

  <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
  <script>
    window.onload = function () {
      window.ui = SwaggerUIBundle({
        url: '/openapi.json',
        dom_id: '#swagger-ui',
        deepLinking: true,
        displayRequestDuration: true,
        filter: true,
        persistAuthorization: true,
        docExpansion: 'list',
        defaultModelsExpandDepth: 1,
        defaultModelExpandDepth: 2,
        showExtensions: true,
        showCommonExtensions: true,
        syntaxHighlight: { activate: true },
        presets: [SwaggerUIBundle.presets.apis],
        layout: 'BaseLayout'
      });

      const translations = new Map([
        ['Authorize', 'Xác thực'],
        ['Available authorizations', 'Các phương thức xác thực'],
        ['Name:', 'Tên:'],
        ['In:', 'Vị trí:'],
        ['Value:', 'Giá trị:'],
        ['Close', 'Đóng'],
        ['Logout', 'Đăng xuất'],
        ['Try it out', 'Thử nhập dữ liệu'],
        ['Cancel', 'Hủy'],
        ['Execute', 'Thực hiện'],
        ['Clear', 'Xóa dữ liệu'],
        ['Parameters', 'Tham số'],
        ['No parameters', 'Không có tham số'],
        ['Request body', 'Nội dung yêu cầu'],
        ['Request URL', 'Địa chỉ yêu cầu'],
        ['Request duration', 'Thời gian xử lý'],
        ['Responses', 'Kết quả trả về'],
        ['Response body', 'Nội dung trả về'],
        ['Response headers', 'Header trả về'],
        ['Server response', 'Phản hồi từ máy chủ'],
        ['Code', 'Mã trạng thái'],
        ['Details', 'Chi tiết'],
        ['Description', 'Mô tả'],
        ['Links', 'Liên kết'],
        ['Headers', 'Header'],
        ['Media type', 'Kiểu dữ liệu'],
        ['Controls Accept header.', 'Điều khiển header Accept.'],
        ['Example Value', 'Giá trị ví dụ'],
        ['Example', 'Ví dụ'],
        ['Model', 'Cấu trúc dữ liệu'],
        ['Schema', 'Lược đồ'],
        ['Schemas', 'Các cấu trúc dữ liệu'],
        ['Models', 'Các cấu trúc dữ liệu'],
        ['Download', 'Tải xuống'],
        ['Curl', 'Lệnh cURL'],
        ['Servers', 'Máy chủ'],
        ['Server', 'Máy chủ'],
        ['Select a definition', 'Chọn cấu trúc dữ liệu'],
        ['Loading', 'Đang tải'],
        ['Fetch error', 'Lỗi tải dữ liệu'],
        ['Failed to fetch.', 'Không thể kết nối tới API.'],
        ['Network Error', 'Lỗi mạng'],
        ['required', 'bắt buộc'],
        ['Deprecated', 'Không còn khuyến nghị'],
        ['Validations', 'Điều kiện kiểm tra'],
        ['Extensions', 'Thuộc tính mở rộng'],
        ['Authorize your requests', 'Xác thực các yêu cầu'],
        ['Select all', 'Chọn tất cả'],
        ['Deselect all', 'Bỏ chọn tất cả']
      ]);

      function shouldSkip(node) {
        const parent = node.parentElement;
        return !parent || Boolean(parent.closest(
          'pre, code, textarea, input, select, option, .microlight, .highlight-code'
        ));
      }

      function translateTextNode(node) {
        if (shouldSkip(node)) return;
        const original = node.nodeValue;
        if (!original) return;
        const trimmed = original.trim();
        const translated = translations.get(trimmed);
        if (!translated) return;
        node.nodeValue = original.replace(trimmed, translated);
      }

      function translateAttribute(element, attribute) {
        const value = element.getAttribute(attribute);
        if (!value) return;
        const translated = translations.get(value.trim());
        if (translated) element.setAttribute(attribute, translated);
      }

      function translateTree(root) {
        if (!root) return;
        if (root.nodeType === Node.TEXT_NODE) {
          translateTextNode(root);
          return;
        }
        if (root.nodeType !== Node.ELEMENT_NODE && root.nodeType !== Node.DOCUMENT_NODE) return;

        const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
        let current;
        while ((current = walker.nextNode())) translateTextNode(current);

        if (root.querySelectorAll) {
          root.querySelectorAll('[title], [aria-label], [placeholder]').forEach((element) => {
            translateAttribute(element, 'title');
            translateAttribute(element, 'aria-label');
            translateAttribute(element, 'placeholder');
          });
        }
      }

      let scheduled = false;
      function scheduleTranslation() {
        if (scheduled) return;
        scheduled = true;
        window.requestAnimationFrame(() => {
          translateTree(document.getElementById('swagger-ui'));
          scheduled = false;
        });
      }

      const observer = new MutationObserver(scheduleTranslation);
      observer.observe(document.getElementById('swagger-ui'), {
        childList: true,
        subtree: true,
        characterData: true,
        attributes: true,
        attributeFilter: ['title', 'aria-label', 'placeholder']
      });

      scheduleTranslation();
    };
  </script>
</body>
</html>
'''


def get_swagger_ui_vi_html() -> HTMLResponse:
    return HTMLResponse(content=SWAGGER_UI_VI_HTML)
