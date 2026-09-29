# Hướng dẫn chạy và sử dụng Kết quả Chương 4 trong PyCharm

Tài liệu này hướng dẫn cách chạy và sử dụng toàn bộ mã nguồn vừa được tích hợp vào dự án để tính toán, xuất bảng và vẽ đồ thị cho **Chương 4: Kết quả nghiên cứu thực nghiệm** trên mẫu thật **499.393 khoản vay** (Complete Cases) từ tổng thể **504.405 khoản vay**.

---

## 1. Cấu trúc mã nguồn đã được tích hợp

Tất cả các thành phần đã được tích hợp trực tiếp vào kiến trúc canonical của dự án:

1. **Module cốt lõi**: [`src/results/chapter4_tables.py`](file:///e:/Python/mortgage-risk-survival-analysis/src/results/chapter4_tables.py)
   - Chứa toàn bộ logic tính toán 20 bảng thực nghiệm (Bảng 4.1 đến Bảng 4.20).
   - Hàm `build_all_chapter4_tables()`: Tính toán và trả về Dictionary chứa 20 bảng dưới dạng Pandas DataFrame.
   - Hàm `export_chapter4_tables()`: Xuất kết quả ra 3 định dạng đồng thời:
     - **20 file CSV riêng biệt** (phục vụ xử lý dữ liệu và chèn vào báo cáo).
     - **1 file Excel hoàn chỉnh** `outputs/tables/chapter4/Chapter4_All_Tables.xlsx` gồm 20 Sheet riêng biệt.
     - **1 file Markdown tổng hợp** `outputs/tables/chapter4/Chapter4_Results_Report.md`.
   - Hàm `generate_chapter4_figures()`: Xuất các biểu đồ học thuật độ phân giải cao (300 DPI) vào `outputs/figures/chapter4/`.

2. **Giao diện dòng lệnh & Script chạy PyCharm**: [`scripts/build_chapter4_tables.py`](file:///e:/Python/mortgage-risk-survival-analysis/scripts/build_chapter4_tables.py)
   - Điểm kích hoạt trực tiếp từ PyCharm hoặc Terminal.

3. **Cấu hình chạy PyCharm (Run Configurations)**:
   - Đã tạo sẵn cấu hình trong `.idea/runConfigurations/`:
     - **`Build Chapter 4 Tables`**: Chạy script tạo 20 bảng và đồ thị.
     - **`Test Chapter 4 Tables`**: Chạy test kiểm thử tính toàn vẹn toán học và số liệu.

4. **Bộ kiểm thử tự động (Unit Tests)**: [`tests/test_chapter4_tables.py`](file:///e:/Python/mortgage-risk-survival-analysis/tests/test_chapter4_tables.py)
   - Kiểm tra 20 bảng không bị rỗng.
   - Kiểm tra khớp số liệu mẫu 499.393 khoản vay (181 default, 209.404 prepayment, 289.808 censored).
   - Kiểm tra tính nhất quán toán học: $CIF_{\text{default}} + CIF_{\text{prepayment}} + S(t) = 1$.
   - Kiểm tra giả thuyết H3: $1 - KM > CIF$ tại mọi mốc thời gian.

---

## 2. Cách chạy trực tiếp trong PyCharm

### Cách 1: Sử dụng Run Configuration có sẵn
1. Nhìn lên thanh công cụ trên cùng của PyCharm, cạnh nút **Play** (màu xanh lá cây).
2. Chọn cấu hình **`Build Chapter 4 Tables`** từ menu thả xuống.
3. Nhấn **Run** (hoặc tổ hợp phím `Shift + F10`).
4. Toàn bộ 20 bảng, file Excel và đồ thị sẽ được tạo tự động trong vòng khoảng 60–90 giây.

### Cách 2: Chuột phải vào file script
1. Trong cây thư mục dự án (Project Explorer) bên trái PyCharm, mở thư mục `scripts/`.
2. Chuột phải vào file `build_chapter4_tables.py`.
3. Chọn **Run 'build_chapter4_tables'**.

### Cách 3: Chạy từ Terminal trong PyCharm
Mở tab **Terminal** ở góc dưới PyCharm và gõ:
```powershell
.\venv\Scripts\python.exe scripts/build_chapter4_tables.py
```

Để chạy bộ kiểm tra tự động:
```powershell
.\venv\Scripts\python.exe -m pytest tests/test_chapter4_tables.py -v
```

---

## 3. Danh mục các file kết quả xuất ra

Tất cả kết quả được lưu tại thư mục [`outputs/tables/chapter4/`](file:///e:/Python/mortgage-risk-survival-analysis/outputs/tables/chapter4/):

| Tên file | Nội dung bảng trong luận văn |
| :--- | :--- |
| `Chapter4_All_Tables.xlsx` | **File Excel tổng hợp toàn bộ 20 bảng** (gồm 20 Tab riêng biệt) |
| `Chapter4_Results_Report.md` | Báo cáo Markdown chi tiết có phân tích và diễn giải học thuật |
| `table_4_01_sample_selection.csv` | Bảng 4.1. Quá trình hình thành mẫu nghiên cứu |
| `table_4_02_event_distribution.csv` | Bảng 4.2. Phân bố trạng thái cuối cùng của khoản vay |
| `table_4_03_descriptive_statistics.csv` | Bảng 4.3. Thống kê mô tả các biến nghiên cứu |
| `table_4_04_vintage_distribution.csv` | Bảng 4.4. Phân bố mẫu theo Mortgage Vintage (2016–2026) |
| `table_4_05_prepayment_timing.csv` | Bảng 4.5. Phân bố thời điểm xảy ra trả nợ trước hạn theo năm |
| `table_4_06_kaplan_meier.csv` | Bảng 4.6. Ước lượng Kaplan–Meier tại các mốc thời gian (12, 24, 36, 60 tháng) |
| `table_4_07_km_by_fico.csv` | Bảng 4.7. So sánh Kaplan–Meier giữa các nhóm FICO Score |
| `table_4_08_univariate_cox.csv` | Bảng 4.8. Kết quả hồi quy Cox đơn biến |
| `table_4_09_multivariate_cox.csv` | Bảng 4.9. Kết quả ước lượng mô hình Cox đa biến |
| `table_4_10_ph_diagnostics.csv` | Bảng 4.10. Kiểm định giả định rủi ro tỷ lệ (Schoenfeld residuals) |
| `table_4_11_time_varying_cox.csv` | Bảng 4.11. Mô hình Cox với biến thay đổi theo thời gian |
| `table_4_12_cause_specific_default.csv` | Bảng 4.12. Mô hình Cause-Specific Cox cho Default |
| `table_4_13_cause_specific_prepayment.csv` | Bảng 4.13. Mô hình Cause-Specific Cox cho Voluntary Prepayment |
| `table_4_14_aalen_johansen_cif.csv` | Bảng 4.14. Hàm tỷ lệ sự cố tích lũy (CIF) Aalen–Johansen |
| `table_4_15_fine_gray.csv` | Bảng 4.15. Mô hình Fine–Gray Subdistribution Hazards cho Default |
| `table_4_16_vintage_cif.csv` | Bảng 4.16. So sánh CIF giữa các Mortgage Vintages |
| `table_4_17_vintage_cox.csv` | Bảng 4.17. Mô hình Cox với biến giả Vintage (ghi nhận phân tách hoàn toàn) |
| `table_4_18_horizon_comparison.csv` | Bảng 4.18. So sánh xác suất vỡ nợ KM vs. CIF (Đo lường sai lệch H3) |
| `table_4_19_subgroup_analysis.csv` | Bảng 4.19. Phân tích độ nhạy theo phân nhóm rủi ro (Subprime vs. Prime) |
| `table_4_20_hypothesis_summary.csv` | Bảng 4.20. Tổng hợp kết quả kiểm định các giả thuyết nghiên cứu (H1–H4) |

Thư mục đồ thị [`outputs/figures/chapter4/`](file:///e:/Python/mortgage-risk-survival-analysis/outputs/figures/chapter4/):
- `figure_4_01_km_vs_cif_bias.png`: Đồ thị so sánh đường cong KM và CIF (minh họa sai lệch thổi phồng rủi ro của KM tăng từ 6,4% lên 53,9%).
- `figure_4_02_forest_plot_hr_vs_shr.png`: Forest plot so sánh Hazard Ratio (Cox) và Subdistribution Hazard Ratio (Fine-Gray).
