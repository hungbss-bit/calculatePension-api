# Cập nhật Render lên calculatePension v2.1

1. Giải nén gói vá vào repository hiện tại và thay file cũ.
2. Không tải `.venv`, `__pycache__` hoặc `.env` lên GitHub.
3. Commit và push. Render tự triển khai lại.
4. Giữ nguyên biến môi trường `API_KEY`.
5. Kiểm tra:
   - `/health` trả `version: 2.1.0`
   - `/v1/capabilities`
   - `/docs`
6. Trong GPT Editor, thay schema Action bằng `openapi-gpt-action.yaml`.
7. Giữ header xác thực `X-API-Key`.
