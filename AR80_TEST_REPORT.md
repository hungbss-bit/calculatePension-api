# AR80 TEST REPORT — Maternity leave support

## Kết quả kiểm thử phần bổ sung

Lệnh:

```bash
python -m pytest -q -p no:cacheprovider tests/test_maternity_leave.py
```

Kết quả:

```text
5 passed
```

Các ca kiểm thử mới bao phủ:
- cộng đủ tháng nghỉ thai sản vào tổng thời gian BHXH;
- kế thừa mức đóng doanh nghiệp của tháng liền kề trước kỳ nghỉ;
- kết quả tương đương trường hợp nhập thủ công cùng mức đóng cho các tháng thai sản;
- kế thừa đúng căn cứ lương Nhà nước dạng hệ số;
- từ chối khi thiếu mức đóng tháng liền kề trước hoặc khi nhập mức đóng trực tiếp vào dòng thai sản.

## Regression toàn bộ source

Trước khi sửa (gói người dùng cung cấp):

```text
47 passed, 4 failed
```

Sau khi bổ sung AR80:

```text
52 passed, 4 failed
```

Bốn lỗi còn lại đều là các lỗi đã tồn tại sẵn trong `tests/test_api_v674.py` của gói đầu vào:
- `test_one_time_allowance_one_excess_month_before_age`
- `test_one_time_allowance_splits_before_and_after_age`
- `test_decree_154_has_no_early_reduction`
- `test_reduced_capacity_reduces_rate`

AR80 không sửa các lỗi cũ này vì yêu cầu của lần nâng cấp là **chỉ bổ sung xử lý nghỉ hưởng chế độ thai sản**.

## Kết luận AR80

Không phát sinh failure mới do phần thai sản; 5 test mới đều đạt.
