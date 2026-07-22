# HƯỚNG DẪN NÂNG CẤP TOÀN BỘ LÊN calculatePension v2.2

1. Dừng Uvicorn và sao lưu thư mục dự án hiện tại.
2. Giải nén toàn bộ `calculatePension_api_v2.2.zip`.
3. Đặt thư mục mới tại:
   `D:\DMHUNG\Chuong_trinh_KH_2026\AI_2026\Pension\calculatePension_api`
4. Khôi phục `.git` và `.env` từ bản sao lưu nếu có.
5. Tạo lại `.venv`, cài `requirements.txt` và chạy kiểm thử.
6. Kết quả kiểm thử yêu cầu: `23 passed`.
7. Cập nhật GitHub và chờ Render trả `/health` với `version=2.2.0`.
8. Thay Instructions bằng v5, Knowledge bằng v1.2 và OpenAPI bằng bản v2.2.

## Thay đổi dữ liệu quan trọng

Với mỗi dòng Mẫu 07/SBH có đóng BHXH, ưu tiên dùng:

```json
"basis_input_type": "mau_07_sbh_components"
```

và truyền `sbh_components`. Công thức tổng là Mức đóng cộng Chức vụ, TN VK, TN Nghề, Khu vực, Khác và Tái cử.

Chỉ dùng `monthly_basis_vnd` khi người dùng nhập trực tiếp và xác nhận đó đã là tổng căn cứ VND/tháng.
