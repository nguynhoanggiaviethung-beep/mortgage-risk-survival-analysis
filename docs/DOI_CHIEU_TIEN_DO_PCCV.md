# BÁO CÁO ĐỐI CHIẾU TIẾN ĐỘ CODE VỚI SHEET PHÂN CHIA CÔNG VIỆC (PCCV)


> **Repository**: `mortgage-risk-survival-analysis` (Nhánh: `backend-huy`, Commit mới nhất: `c8ac196`)  
> **Cập nhật ngày**: 30/09/2026.

---

## I. TỔNG KẾT NHANH CHO CẢ NHÓM (EXECUTIVE SUMMARY)

1. **Giai đoạn 27/9 (Research Spec, Data Dictionary, Architecture)**: 👉 **100% Hoàn thành**.
2. **Giai đoạn 28/9 (Data Ingestion, Cleaning, Event Mapping, Baseline Models)**: 👉 **100% Hoàn thành trong Code**.
3. **Giai đoạn 29/9 (Panel, Competing Risks, Real Model Fitting, Chapter 4 Tables & Figures)**: 👉 **100% Hoàn thành trong Code** *(Mặc dù trên Google Sheet các dòng này đang để `FALSE`, thực tế trong repo đã code và chạy xong 100%)*.


---

## II. BẢNG ĐỐI CHIẾU CHI TIẾT TỪNG DÒNG THEO SHEET PCCV

Dưới đây là bảng đối chiếu từng đầu việc trong Google Sheet với mã nguồn thực tế trong Git repository:

| STT trong Sheet | Ngày | Hạng mục công việc (PCCV) | Phân công | Trạng thái trên Google Sheet | Trạng thái thực tế trong Code | Vị trí file minh chứng trong Repository |
| :---: | :---: | :--- | :---: | :---: | :---: | :--- |
| **01** | 27/9 | Chốt Research Specification | Vio | `TRUE` | ✅ **Hoàn thành** | `docs/research_specification.md` |
| **02** | 27/9 | Data Dictionary | Huân, Vio | `TRUE` | ✅ **Hoàn thành** | `docs/data_dictionary.md` |
| **03** | 27/9 | Formula & Metric Dictionary | Vio | `TRUE` | ✅ **Hoàn thành** | `docs/metric_formula_dictionary.md` |
| **04** | 27/9 | Thiết kế Data Architecture | Vio | `TRUE` | ✅ **Hoàn thành** | `docs/data_architecture.md`, `docs/BACKEND_ARCHITECTURE.md` |
| **05** | 27/9 | Frontend Data Contract | Vio | `TRUE` | ✅ **Hoàn thành** | `docs/frontend_data_contract.md`, `docs/FRONTEND_HANDOFF.md` |
| **06** | 27/9 | Event Definition Evidence | Vio | `TRUE` | ✅ **Hoàn thành** | `docs/event_mapping.md` |
| **07** | 27/9 | Khung luận văn + Literature Matrix | Hương P, Hương N | `TRUE` | ✅ **Hoàn thành** | Khung đề cương luận văn |
| **08** | 28/9 | Tải và kiểm tra Freddie Mac Sample | Huy | `TRUE` | ✅ **Hoàn thành** | `data/raw/`, `reports/raw_validation.md` |
| **09** | 28/9 | Ingestion bằng Polars / Chunk | Huân | `TRUE` | ✅ **Hoàn thành** | `src/process_sample.py`, `src/config.py` |
| **10** | 28/9 | Chuẩn hóa Origination Data | Huy, Huân | `TRUE` | ✅ **Hoàn thành** | `src/clean_data.py`, `data/processed/orig_*.parquet` |
| **11** | 28/9 | Chuẩn hóa Monthly Performance | Huân | `TRUE` | ✅ **Hoàn thành** | `src/clean_data.py`, `data/processed/performance.parquet` |
| **12** | 28/9 | Implement Event Mapping | Huân | `TRUE` | ✅ **Hoàn thành** | `src/data/event_definition.py`, `tests/test_event_definition.py` |
| **13** | 28/9 | Tạo Loan Age | Huân | `TRUE` | ✅ **Hoàn thành** | `src/data/survival_duration.py`, `data/processed/` |
| **14** | 28/9 | Model Input Adapter + Mock Dataset | Huy | `FALSE` | ✅ **ĐÃ XONG (Đề xuất tick TRUE)** | `src/survival/model_input.py`, `tests/fixtures/mock_loan_month.parquet` |
| **15** | 28/9 | Kaplan–Meier Module | Huy | `FALSE` | ✅ **ĐÃ XONG (Đề xuất tick TRUE)** | `src/survival/kaplan_meier.py`, `results/mock/km_results.parquet` |
| **16** | 28/9 | Cox Proportional Hazards Module | Huy | `FALSE` | ✅ **ĐÃ XONG (Đề xuất tick TRUE)** | `src/survival/cox_model.py`, `results/mock/cox_results.parquet` |
| **17** | 28/9 | PH Assumption Test | Huy | `FALSE` | ✅ **ĐÃ XONG (Đề xuất tick TRUE)** | `src/survival/ph_test.py`, `results/mock/ph_diagnostics.csv` |
| **18** | 28/9 | Frontend UI System + Navigation | Vio | `TRUE` | 🟡 **Phía FE** | `app/app.py`, `app/components/`, `app/pages/` |
| **19** | 28/9 | Frontend Mock Data Service | Vio | `TRUE` | 🟡 **Phía FE** | `app/services/data_service.py` |
| **20** | 28/9 | Frontend Global Filters | Kha, Vio | `TRUE` | 🟡 **Phía FE** | `app/components/filters.py` |
| **21** | 28/9 | Chart & Statistical Components | Kha, Vio | `TRUE` | 🟡 **Phía FE** | `app/components/charts.py`, `statistics.py` |
| **22** | 28/9 | Literature Review + Research Gap | K.Hưng, Hương N | `TRUE` | ✅ **Hoàn thành** | Chapter 1 & 2 draft |
| **23** | 29/9 | Xây Loan-Month Panel | Huân | `FALSE` | ✅ **ĐÃ XONG (Đề xuất tick TRUE)** | `src/clean_data.py`, `data/model/analysis_loans_2016_2026.parquet` |
| **24** | 29/9 | Missing / Outlier / Data Quality | Huân | `FALSE` | ✅ **ĐÃ XONG (Đề xuất tick TRUE)** | `src/clean_data.py`, `reports/model_dataset_validation_2016_2026.json` |
| **25** | 29/9 | Data Validation & Leakage Audit | Huân | `FALSE` | ✅ **ĐÃ XONG (Đề xuất tick TRUE)** | `scripts/final_data_validation.py`, `reports/data_audit_2016_2026.csv` |
| **26** | 29/9 | Time-varying Cox Module | Huy | `FALSE` | ✅ **ĐÃ XONG (Đề xuất tick TRUE)** | `src/survival/time_varying_cox_model.py`, `src/survival/time_varying_input.py` |
| **27** | 29/9 | Cause-specific Hazard Models | Huy | `FALSE` | ✅ **ĐÃ XONG (Đề xuất tick TRUE)** | `src/competing_risks/cause_specific.py`, `tests/test_cause_specific.py` |
| **28** | 29/9 | Aalen–Johansen / CIF | Huy | `FALSE` | ✅ **ĐÃ XONG (Đề xuất tick TRUE)** | `src/competing_risks/aalen_johansen.py`, `tests/test_aalen_johansen.py` |
| **29** | 29/9 | Fine–Gray Module | Huy | `FALSE` | ✅ **ĐÃ XONG (Đề xuất tick TRUE)** | `src/competing_risks/fine_gray.py`, `tests/test_fine_gray.py` |
| **30** | 29/9 | PD(t) Calculation | Huân | `FALSE` | ✅ **ĐÃ XONG (Đề xuất tick TRUE)** | `src/competing_risks/pd_vintage.py`, `tests/test_pd_vintage.py` |
| **31** | 29/9 | Vintage Analysis Module | Huân | `FALSE` | ✅ **ĐÃ XONG (Đề xuất tick TRUE)** | `src/competing_risks/pd_vintage.py`, `src/results/chapter4_tables.py` |
| **32** | 29/9 | Trang Tổng quan (Frontend) | Vio | `FALSE` | 🟡 **Phía FE** | Sẵn sàng kết nối với `FrontendService.get_portfolio_summary()` |
| **33** | 29/9 | Trang Rủi ro danh mục (Frontend) | Vio | `FALSE` | 🟡 **Phía FE** | Sẵn sàng kết nối với `FrontendService.get_pd_results()` |
| **34** | 29/9 | Trang Yếu tố ảnh hưởng (Frontend) | Kha | `FALSE` | 🟡 **Phía FE** | Sẵn sàng kết nối với `FrontendService.get_risk_driver_results()` |
| **35** | 29/9 | Trang Kết quả mô hình (Frontend) | Kha | `FALSE` | 🟡 **Phía FE** | Sẵn sàng kết nối với `FrontendService.get_survival_results()` |
| **36** | 29/9 | Loan Explorer + Profile (Frontend) | Kha | `FALSE` | 🟡 **Phía FE** | Sẵn sàng kết nối với `FrontendService.get_loan_profile()` |
| **37** | 29/9 | Loan Timeline + Methodology | Vio | `TRUE` | 🟡 **Phía FE** | Sẵn sàng kết nối với `FrontendService.get_loan_timeline()` |
| **38** | 29/9 | Methodology Chapter Draft | Hoàng | `TRUE` | ✅ **Hoàn thành** | Bản thảo Chương 3 |
| **39** | 29/9 | Hypothesis + Variable Mapping | Hương N | `FALSE` | ✅ **ĐÃ XONG (Đề xuất tick TRUE)** | Đã tổng hợp trong Bảng 4.20 (`outputs/tables/chapter4/table_4_20_hypothesis_summary.csv`) |
| **40** | 29/9 | Results Table / Figure Templates | Huỳnh | `TRUE` | ✅ **Hoàn thành** | Đã tạo cấu trúc bảng và đồ thị |
| **41** | 29/9 | **Fit Models trên Real Loan-Month Panel** | Huân, Huy | `FALSE` | ✅ **ĐÃ XONG 100% (Đề xuất tick TRUE)** | Chạy xong trên mẫu 499.393 khoản vay Complete Cases: KM, Cox, TV-Cox, CIF, Fine-Gray |
| **42** | 29/9 | **Tạo Dashboard Results Dataset** | Huy, Huân | `FALSE` | ✅ **ĐÃ XONG 100% (Đề xuất tick TRUE)** | Đã code `src/results/dashboard.py` định dạng 6 schemas chuẩn frontend contract |
| **43** | 29/9 | **Dashboard Results & Query Layer** | Vio, Huy | `FALSE` | ✅ **ĐÃ XONG 100% (Đề xuất tick TRUE)** | Đã xây xong `src/query/queries.py` và `src/query/service.py`, kèm `tests/test_query_layer.py` |
| **44** | 29/9 | **Chạy Statistical Validation + Interpret** | Huân, Huy | `FALSE` | ✅ **ĐÃ XONG 100% (Đề xuất tick TRUE)** | Đã kiểm định convergence, Schoenfeld PH, CIF decomposition, kiểm định giả thuyết $H_1 \to H_4$ |
| **45** | 29/9 | **Viết Chapter 4 Results** | Huy, Thesis Team | `FALSE` | ✅ **ĐÃ XONG 100% (Đề xuất tick TRUE)** | Xuất xong **20 bảng Excel** (`Chapter4_All_Tables.xlsx`) và **4 biểu đồ 300 DPI** (`outputs/figures/chapter4/`) |
| **46** | 30/9 | Integrate Overview + Portfolio | Kha, BE2 | `FALSE` | ⏳ **Bước tiếp theo** | Frontend thay mock service bằng `FrontendService` |
| **47** | 30/9 | Integrate Risk Drivers + Insights | Kha, BE2 | `FALSE` | ⏳ **Bước tiếp theo** | Frontend hiển thị biểu đồ HR vs SHR từ `risk_driver_results` |
| **48** | 30/9 | Integrate Loan Explorer | Kha, BE1+BE2 | `FALSE` | ⏳ **Bước tiếp theo** | Frontend kết nối tìm kiếm Loan ID |
| **49** | 30/9 | Integrate Global Filters | Kha, FE+BE | `FALSE` | ⏳ **Bước tiếp theo** | Đồng bộ bộ lọc năm/kỳ hạn giữa các trang UI |
| **50** | 30/9 | Dashboard vs Notebook Reconciliation | Huân, Huy | `FALSE` | ⏳ **Bước tiếp theo** | Đối chiếu số liệu hiển thị UI với bảng kết quả Excel Chương 4 |
| **51** | 30/9 | Model & Statistical Validation Final | Huân, Huy | `FALSE` | ⏳ **Bước tiếp theo** | Báo cáo chốt kiểm định thống kê và limitation |
| **52** | 30/9 | Frontend QA + Filter QA | Vio, Kha | `FALSE` | ⏳ **Bước tiếp theo** | Test luồng giao diện người dùng |
| **53** | 30/9 | End-to-End Pipeline Test | PM, Huy, Huân | `FALSE` | ⏳ **Bước tiếp theo** | Test chạy lại toàn bộ pipeline theo tài liệu |
| **54** | 30/9 | Chapter 5 Discussion + Limitations | Hoàng | `FALSE` | ⏳ **Đang thực hiện** | Nhóm Research viết thảo luận và hạn chế đề tài |
| **55** | 30/9 | README + Demo + AI Usage Log | PM | `FALSE` | ⏳ **Bước tiếp theo** | Đóng gói nộp bài |
| **56** | 30/9 | Chapter 6 Conclusion | K.Hưng | `FALSE` | ⏳ **Đang thực hiện** | Nhóm Research viết kết luận và kiến nghị |

---



## IV. BƯỚC CẦN LÀM TIẾP THEO (GIAI ĐOẠN 30/9)

   - Tiến hành viết tiếp Chương 5 (Thảo luận & Hạn chế) và Chương 6 (Kết luận & Hàm ý chính sách).
2. **Nhóm Frontend (Kha, Vio)**:
   - Kết nối giao diện người dùng với lớp truy vấn backend `from src.query import FrontendService`.
   - Thay thế mock data bằng dữ liệu thực nghiệm đã sẵn sàng.
3. **Nhóm Backend & QA (Huân, Huy, PM)**:
   - Thực hiện bước đối soát cuối cùng (Dashboard vs Notebook Reconciliation) để đảm bảo số liệu trên web trùng khớp 100% với số liệu trong bài luận văn.
