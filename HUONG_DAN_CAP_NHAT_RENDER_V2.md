# Cập nhật dịch vụ Render từ v1.2 lên v2.0

1. Sao lưu repository GitHub hiện tại.
2. Giữ nguyên biến môi trường `API_KEY` trên Render.
3. Chép các tệp v2.0 vào repository và ghi đè tệp cũ.
4. Không tải `.venv`, `__pycache__` hoặc `.pytest_cache` lên GitHub.
5. Commit và push; Render sẽ tự triển khai lại.
6. Kiểm tra:

```text
https://TEN-DICH-VU.onrender.com/health
https://TEN-DICH-VU.onrender.com/v1/capabilities
https://TEN-DICH-VU.onrender.com/docs
```

`/health` phải trả `version: 2.0.0`.

7. Trong GPT Editor, xóa schema Action cũ và nhập lại `openapi-gpt-action.yaml` hoặc `.json` sau khi thay URL server.
8. Giữ Authentication: API Key, header `X-API-Key`.
9. Kiểm tra ba operation: `getPensionCapabilities`, `validateContributionHistory`, `calculatePension`.
10. Mở cuộc trò chuyện Preview mới để kiểm thử.

Nếu Render trả lỗi build, chọn **Manual Deploy → Clear build cache & deploy**.
