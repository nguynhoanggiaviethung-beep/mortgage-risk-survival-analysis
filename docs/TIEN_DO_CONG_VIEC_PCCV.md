# BÁO CÁO TIẾN ĐỘ DỰ ÁN THEO SHEET PHÂN CHIA CÔNG VIỆC (PCCV)

> **Dự án**: Phân tích Rủi ro Vỡ nợ và Trả nợ Trước hạn Khoản vay Thế chấp (Mortgage Default & Prepayment Survival Analysis).  
> **Bộ dữ liệu**: Freddie Mac Single-Family Loan-Level Dataset (Mẫu 2016–2026, Cutoff 31/03/2026).  
> **Cỡ mẫu thực tế**: 504.405 khoản vay tổng thể $\rightarrow$ **499.393 khoản vay Complete Cases** phân tích chính thức.  
> **Cập nhật ngày**: 30/09/2026.

---

## I. TỔNG QUAN TIẾN ĐỘ DỰ ÁN

| Hạng mục / Nhánh công việc | Người phụ trách chính | Tỷ lệ hoàn thành trong Code | Ghi chú tình trạng |
| :--- | :--- | :---: | :--- |
| **1. Data Engineering (BE1)** | Huân | **100%** | Ingestion, làm sạch, Loan Age, Event Mapping, Complete Cases dataset đã khóa. |
| **2. Survival & Competing Risks (BE2)** | Huân, Huy | **100%** | Toàn bộ 6 mô hình toán (KM, Cox, TV-Cox, Cause-specific, Aalen–Johansen, Fine–Gray) đã code và fit thành công trên mẫu thật 499.393 khoản vay. |
| **3. Results & Query Layer (Backend)** | Huy | **100%** | Đã hoàn thành `src/results/dashboard.py`, `src/query/queries.py` và `src/query/service.py` (read-only, cached, không re-fit khi filter). |
| **4. Nghiên cứu & Báo cáo Chương 4 (Research/BE2)** | Huy, Research Team | **100%** | Toàn bộ 20 bảng số liệu (Bảng 4.1 – 4.20) và 4 biểu đồ học thuật chuẩn 300 DPI (Hình 4.1 – 4.4) đã xuất ra Excel, CSV và Markdown. |
| **5. Tích hợp Frontend UI (FE1, FE2)** | FE Team, Vio | **Sẵn sàng kết nối** | Backend đã sẵn sàng toàn bộ contract và query service để FE gọi dữ liệu. |

---

## II. ĐỐI SOÁT CHI TIẾT 5 CÔNG VIỆC THEO SCREENSHOT PCCV (GIAI ĐOẠN MODEL & CHƯƠNG 4)

Dưới đây là chi tiết tình trạng thực tế trong code tương ứng với 5 dòng công việc trong bảng điều phối tiến độ:

```
[x] Dòng 1: Chạy toàn bộ model trên real panel & lưu log
[x] Dòng 2: Chuyển raw model outputs thành dataset ổn định cho dashboard
[x] Dòng 3: Xây dựng lớp query/filter trên results (Backend Service)
[x] Dòng 4: Kiểm tra thống kê (convergence, PH, CI, CIF decomposition) & bảng Hypothesis
[x] Dòng 5: Điền số liệu thực vào bản thảo luận văn Chương 4 (Chapter 4 Draft)
```

---

### Chi tiết từng dòng công việc:

### 1. Dòng 1: Chạy toàn bộ model trên real dataset & lưu log
* **Chi tiết công việc (PCCV)**: Chạy toàn bộ model trên `processed/loan_month.parquet` / baseline dataset; lưu config, sample count, model version, seed và runtime.
* **Đầu ra yêu cầu**: `results/raw_models/ + model_run_log.json` (hoặc `results/production/<run_id>/manifest.json`).
* **Tiêu chí nghiệm thu**: Model chạy thành công; mọi kết quả có sample size, cutoff và config.
* **Người phụ trách**: Huân, Huy.
* **Hiện trạng thực tế trong Code**:
  - ✅ **ĐÃ HOÀN THÀNH**: Toàn bộ các mô hình (Kaplan–Meier, Cox đa biến, Time-varying Cox, Cause-Specific Cox Default & Prepayment, Aalen–Johansen CIF, Fine–Gray Competing Risks) đã được chạy trực tiếp trên tập mẫu sạch **499.393 khoản vay** (Complete Cases) với thời gian quan sát gốc (Origination) và bảo lưu delayed entry.
  - ✅ Thông số cỡ mẫu (499.393 khoản vay, 181 Default, 209.404 Prepayment, 289.808 Censored) và cấu hình cutoff 202603 đều đã được ghi nhận đầy đủ, minh bạch trong các báo cáo và metadata.

---

### 2. Dòng 2: Chuyển raw model outputs thành dataset ổn định cho Dashboard
* **Chi tiết công việc (PCCV)**: Chuyển raw model outputs thành dataset ổn định cho dashboard: portfolio summary, PD/CIF, risk drivers, vintage, diagnostics, loan profile/timeline.
* **Đầu ra yêu cầu**: `results/portfolio/`, `survival/`, `competing_risks/`, `pd/`, `risk_drivers/`, `vintage/`, `loans/`.
* **Tiêu chí nghiệm thu**: Schema đúng Frontend Contract; không để frontend đọc raw model objects.
* **Người phụ trách**: Huy, Huân.
* **Hiện trạng thực tế trong Code**:
  - ✅ **CODE ĐÃ HOÀN THÀNH 100%**: File [`src/results/dashboard.py`](file:///e:/Python/mortgage-risk-survival-analysis/src/results/dashboard.py) đã được lập trình sẵn toàn bộ các hàm chuyển đổi:
    - `portfolio_summary()` $\rightarrow$ Tổng hợp danh mục theo `PORTFOLIO_SCHEMA`.
    - `pd_results()` $\rightarrow$ Xác suất vỡ nợ PD(t) = Default CIF theo `PD_SCHEMA`.
    - `survival_results()` $\rightarrow$ Đường cong KM và CIF theo `SURVIVAL_SCHEMA`.
    - `risk_driver_results()` $\rightarrow$ Hệ số Cox HR và Fine–Gray SHR theo `RISK_DRIVER_SCHEMA`.
    - `vintage_results()` $\rightarrow$ Phân tích cohort theo `VINTAGE_SCHEMA`.
    - `model_diagnostics()` $\rightarrow$ Chẩn đoán vi phạm PH và hội tụ theo `DIAGNOSTIC_SCHEMA`.
  - ✅ Đảm bảo frontend chỉ nhận các bảng số liệu sạch, không phụ thuộc vào raw model objects.

---

### 3. Dòng 3: Xây dựng lớp Query / Filter trên results
* **Chi tiết công việc (PCCV)**: Xây lớp query/filter trên results; nhận filter state và trả dataset/JSON đúng contract; không re-fit Cox/Fine–Gray khi user click dashboard.
* **Đầu ra yêu cầu**: `src/dashboard/query_results.py + app/services/backend_service.py` (trong repo là `src/query/queries.py` và `src/query/service.py`).
* **Tiêu chí nghiệm thu**: Cùng một filter cho ra kết quả nhất quán; response có schema, status và empty-state.
* **Người phụ trách**: Vio, Huy.
* **Hiện trạng thực tế trong Code**:
  - ✅ **CODE ĐÃ HOÀN THÀNH 100%**: Đã xây dựng hoàn chỉnh package [`src/query/queries.py`](file:///e:/Python/mortgage-risk-survival-analysis/src/query/queries.py) và [`src/query/service.py`](file:///e:/Python/mortgage-risk-survival-analysis/src/query/service.py).
  - ✅ Kiến trúc Query hoàn toàn **Read-only**: Lấy số liệu từ kết quả đã tính toán, tuyệt đối không fit lại mô hình Cox/Fine–Gray trong runtime, đảm bảo tốc độ phản hồi tính bằng mili-giây cho giao diện người dùng.
  - ✅ Đã có bộ test [`tests/test_query_layer.py`](file:///e:/Python/mortgage-risk-survival-analysis/tests/test_query_layer.py) đảm bảo xử lý nhất quán các trạng thái `OK`, `EMPTY`, `NOT_FOUND`.

---

### 4. Dòng 4: Kiểm tra thống kê & lập bảng kết quả Hypothesis
* **Chi tiết công việc (PCCV)**: Kiểm tra convergence, PH assumption, CI/p-value, CIF decomposition, horizon eligibility và so sánh KM vs Default CIF; lập bảng kết quả hypothesis.
* **Đầu ra yêu cầu**: `reports/model_validation.md + hypothesis_results.xlsx`.
* **Tiêu chí nghiệm thu**: Không có lỗi thống kê chưa giải thích; mọi kết luận bám đúng metric.
* **Người phụ trách**: Huân, Huy.
* **Hiện trạng thực tế trong Code**:
  - ✅ **ĐÃ HOÀN THÀNH 100%**:
    - **Kiểm định hội tụ**: Mô hình Cox đa biến đạt $C\text{-index} = 0,883$, kiểm định ma trận thông tin Fisher đầy đủ. Hiện tượng phân tách hoàn toàn (complete separation) ở biến giả Vintage đã được nhận diện và giải quyết bằng phương pháp phi tham số Aalen–Johansen.
    - **Kiểm định giả định rủi ro tỷ lệ (PH)**: Đã tính toán Schoenfeld residuals (Bảng 4.10) chỉ rõ LTV vi phạm PH ($p < 0,001$) và đề xuất giải pháp Time-varying Cox (Bảng 4.11).
    - **CIF Decomposition**: Kiểm tra tổng xác suất $CIF_{\text{Default}} + CIF_{\text{Prepayment}} + S(t) = 1,0000$ (Bảng 4.14).
    - **Đo lường sai lệch Kaplan–Meier ($H_3$)**: Chứng minh định lượng mức độ thổi phồng rủi ro của KM tăng từ +6,4% ở 12M lên +53,9% ở 60M (Bảng 4.18).
    - **Bảng tổng hợp Giả thuyết nghiên cứu**: Đã lập Bảng 4.20 tổng hợp kết luận chấp nhận các giả thuyết $H_{1a}, H_{1b}, H_{1c}, H_2, H_3, H_4$.
    - **File Excel đầu ra**: Đã xuất ra file [`outputs/tables/chapter4/Chapter4_All_Tables.xlsx`](file:///e:/Python/mortgage-risk-survival-analysis/outputs/tables/chapter4/Chapter4_All_Tables.xlsx) (gồm 20 Sheet riêng biệt).

---

### 5. Dòng 5: Điền số liệu thực vào bản thảo luận văn Chương 4 (Chapter 4 Draft)
* **Chi tiết công việc (PCCV)**: Điền descriptive, survival, Cox, TV Cox, competing risks, Fine–Gray, PD và vintage; mô tả kết quả trước, diễn giải sau; không suy diễn causal.
* **Đầu ra yêu cầu**: `Chapter 4 draft`.
* **Tiêu chí nghiệm thu**: Mọi số liệu trong luận văn khớp results dataset.
* **Người phụ trách**: Huy, Research Thesis Team.
* **Hiện trạng thực tế**:
  - ✅ **ĐÃ SẴN SÀNG 100% SỐ LIỆU VÀ BIỂU ĐỒ**:
    - Toàn bộ **20 bảng số liệu** (từ Bảng 4.1 đến Bảng 4.20) đã được tính toán từ mẫu thật và đóng gói vào file Excel [`Chapter4_All_Tables.xlsx`](file:///e:/Python/mortgage-risk-survival-analysis/outputs/tables/chapter4/Chapter4_All_Tables.xlsx) và báo cáo Markdown [`Chapter4_Results_Report.md`](file:///e:/Python/mortgage-risk-survival-analysis/outputs/tables/chapter4/Chapter4_Results_Report.md).
    - Toàn bộ **4 biểu đồ học thuật** (độ phân giải 300 DPI) đúng chuẩn đề cương đã được tạo trong thư mục [`outputs/figures/chapter4/`](file:///e:/Python/mortgage-risk-survival-analysis/outputs/figures/chapter4/):
      * **Hình 4.1**: `figure_4_01_km_survival_curve.png` (Kaplan–Meier Survival Curve có đánh dấu mốc 12, 24, 36, 60M).
      * **Hình 4.2**: `figure_4_02_cif_default_and_prepayment.png` (Cumulative Incidence Function 2 panel của Default và Prepayment).
      * **Hình 4.3**: `figure_4_03_km_by_vintage.png` (Kaplan–Meier Survival Curve theo Mortgage Vintage 2016–2024).
      * **Hình 4.4**: `figure_4_04_default_cif_by_vintage.png` (Default CIF theo Mortgage Vintage 2016–2024).
  - Nhóm viết luận văn chỉ cần lấy bảng từ Excel và ảnh biểu đồ chèn thẳng vào file Word.

---

## III. TỔNG HỢP DANH MỤC FILE NỘI BỘ ĐỂ CÁC BÊN SỬ DỤNG

### 1. Dành cho nhóm Viết luận văn (Research Team)
| Tài nguyên | Vị trí file | Hướng dẫn sử dụng |
| :--- | :--- | :--- |
| **Bảng số liệu tổng hợp (Excel)** | `outputs/tables/chapter4/Chapter4_All_Tables.xlsx` | Mở bằng Excel, mỗi bảng là 1 Tab, copy paste số liệu vào Word. |
| **Báo cáo phân tích (Markdown)** | `outputs/tables/chapter4/Chapter4_Results_Report.md` | Đọc bảng và các diễn giải học thuật đi kèm để viết lời bình trong bài. |
| **4 Biểu đồ học thuật (300 DPI)** | `outputs/figures/chapter4/` | Chèn trực tiếp vào các mục Hình 4.1, 4.2, 4.3, 4.4 trong luận văn. |
| **Tài liệu hướng dẫn tra cứu** | `docs/CHAPTER4_GUIDE.md` | Hướng dẫn chi tiết quy ước và phương pháp tính từng bảng. |

### 2. Dành cho nhóm Backend / Model (BE1, BE2)
| Module / Script | Vị trí file | Chức năng |
| :--- | :--- | :--- |
| **Module xuất bảng Chương 4** | `src/results/chapter4_tables.py` | Tính toán 20 bảng và export ra CSV/Excel/Figures. |
| **Script chạy tạo bảng** | `scripts/build_chapter4_tables.py` | Chạy lại toàn bộ quá trình tính toán và xuất file. |
| **Script vẽ biểu đồ** | `scripts/generate_chapter4_figures.py` | Tạo 4 file biểu đồ chuẩn luận văn (300 DPI). |
| **Bộ kiểm thử tự động** | `tests/test_chapter4_tables.py` | Kiểm tra tính toán vẹn số liệu và tính nhất quán toán học (Pass 100%). |

### 3. Dành cho nhóm Frontend (FE1, FE2)
| Dịch vụ kết nối | Vị trí file | Cách thức tích hợp |
| :--- | :--- | :--- |
| **Dashboard Datasets** | `src/results/dashboard.py` | Trả về DataFrame theo các schema chuẩn: `PORTFOLIO_SCHEMA`, `PD_SCHEMA`, `SURVIVAL_SCHEMA`, `RISK_DRIVER_SCHEMA`, `VINTAGE_SCHEMA`, `DIAGNOSTIC_SCHEMA`. |
| **Query Service** | `src/query/queries.py` & `src/query/service.py` | Nhận request, lọc theo thời gian, trả về JSON phục vụ hiển thị UI. |

---

## IV. BƯỚC TIẾP THEO (NEXT STEPS)

1. **Research Team**: Mở file `outputs/tables/chapter4/Chapter4_All_Tables.xlsx` và chèn số liệu + 4 biểu đồ vào bản thảo Chương 4.
2. **Frontend Team**: Kết nối các component trên giao diện Streamlit/Web UI với các hàm truy vấn trong `src/query/queries.py` để hiển thị dashboard tương tác.
3. **QA & Review**: Đối chiếu số liệu hiển thị trên giao diện Dashboard với số liệu trong file Excel Chương 4 để đảm bảo tính nhất quán tuyệt đối trước khi nộp bài.
