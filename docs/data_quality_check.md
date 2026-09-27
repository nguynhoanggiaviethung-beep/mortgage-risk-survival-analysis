# Báo cáo kiểm tra dữ liệu Freddie Mac Sample

## 1. Nguồn và phạm vi kiểm tra

- Dataset: Freddie Mac Single-Family Loan-Level Sample Dataset.
- Phạm vi kiểm tra nguồn: các năm 2016–2026.
- Performance cutoff dùng trong báo cáo: tháng 03/2026.
- Nguồn kết quả: reports/raw_validation.md.
- Các file ZIP gốc được giữ nguyên.

Phạm vi kiểm tra nguồn không tự quyết định cohort đưa vào mô hình.

Báo cáo nguồn kiểm tra cả raw và processed. Vì vậy, những kết quả
trên bảng đã xử lý không được mặc nhiên hiểu là thống kê trước xử lý.

## 2. Kết quả kiểm tra tổng hợp

| Nội dung | Kết quả |
|---|---|
| Đủ Origination và Performance | Cả 11 ZIP đều chứa hai thành phần cần thiết và không rỗng |
| Khả năng đọc dữ liệu | 11 ZIP đều PASS; pipeline đã giải nén và xử lý thành công tất cả các năm |
| Tổng số dòng origination | 512.500 dòng |
| Tổng số dòng performance | 20.097.384 dòng |
| Trùng Loan ID trong origination | 0 ở tất cả các năm |
| Trùng khóa loan_id + performance_month | 0 ở tất cả các năm |
| Performance ID không có trong origination | 0 ở tất cả các năm |
| Origination không có performance | 10 khoản: 5 thuộc năm 2025 và 5 thuộc năm 2026 |
| Vi phạm thứ tự thời gian | 0 ở tất cả các năm |
| Quan sát sau cutoff trong bảng được kiểm tra | 0 ở tất cả các năm |
| Khoảng trống lịch sử báo cáo | 1 trường hợp được ghi nhận ở năm 2017 |
| Loan ID bị thiếu | Báo cáo nguồn chưa cung cấp số lượng riêng |
| Số cột khớp layout | Chưa có kết quả đếm cột trong báo cáo nguồn; kỳ vọng 31 cột origination và 35 cột performance theo layout July 2026 |
| Phân bố mã đặc biệt | Chưa có thống kê theo biến cho 999, 9999, blank, RA và các Zero Balance Code |

## 3. Quy mô dữ liệu từng năm

| Năm | Dòng origination | Dòng performance | Kết quả |
|---|---:|---:|---|
| 2016 | 50.000 | 3.379.650 | PASS |
| 2017 | 50.000 | 2.800.219 | PASS_WITH_WARNING |
| 2018 | 50.000 | 2.059.564 | PASS |
| 2019 | 50.000 | 1.934.614 | PASS |
| 2020 | 50.000 | 2.517.857 | PASS |
| 2021 | 50.000 | 2.537.054 | PASS |
| 2022 | 50.000 | 2.034.798 | PASS |
| 2023 | 50.000 | 1.458.169 | PASS |
| 2024 | 50.000 | 952.865 | PASS |
| 2025 | 50.000 | 404.946 | PASS_WITH_WARNING |
| 2026 | 12.500 | 17.648 | PASS_WITH_WARNING |
| Tổng | 512.500 | 20.097.384 | Có cảnh báo cần xem xét |

Số dòng performance lớn hơn số dòng origination là phù hợp với
cấu trúc theo dõi một khoản vay qua nhiều tháng. Khóa của bảng
performance là loan_id kết hợp performance_month.

## 4. Các cảnh báo cần xem xét

### Năm 2017

Báo cáo ghi nhận 1 reporting gap.

Cần xác định khoản vay và các tháng liên quan trước khi xây dựng
timeline. Không tự điền trạng thái cho tháng chưa được quan sát.

### Năm 2025 và 2026

Mỗi năm có 5 khoản trong origination chưa có performance.

Đây có thể là các khoản mới chưa có lịch sử tại cutoff.
Cần kiểm tra thời điểm liên quan trước khi quyết định xử lý.
Không tự gán các khoản này là default, khoản tốt hoặc PD bằng 0.

## 5. Kiểm tra còn cần bổ sung

- Đếm Loan ID bị thiếu trong cả hai bảng.
- Xác nhận số cột và vị trí cột theo File Layout July 2026.
- Thống kê mã đặc biệt riêng theo từng biến.
- Ghi rõ kiểm tra nào thực hiện trên raw và kiểm tra nào trên processed.
- Nếu bước xử lý có loại dòng, bổ sung số lượng trước và sau xử lý.

Không đếm chung mã 999 hoặc 9999 trên mọi cột rồi coi tất cả
là missing; ý nghĩa mã phụ thuộc từng biến.

## 6. Kết luận

Trong phạm vi các kiểm tra được báo cáo, không phát hiện trùng khóa,
Performance ID ngoài origination, vi phạm thứ tự thời gian
hoặc quan sát sau cutoff.

Có cảnh báo về reporting gap năm 2017 và 10 khoản chưa có
performance thuộc năm 2025–2026.

Chưa kết luận toàn bộ kiểm tra chất lượng đã hoàn tất.
Cần bổ sung kiểm tra ID thiếu, schema và mã đặc biệt trước
khi xác nhận hoàn thành đầy đủ yêu cầu kiểm tra dữ liệu.