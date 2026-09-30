# Cẩm nang hiểu dự án phân tích rủi ro khoản vay thế chấp

> Dành cho thành viên nhóm chưa quen với thống kê sống còn, Python hay cấu trúc kho mã. Hãy đọc từ đầu; thuật ngữ chuyên môn được giải thích theo ngữ cảnh. Nội dung này được đối chiếu với code, đặc tả và release đang có trong repository tại ngày 30/09/2026.

## 1. Dự án trong vài phút

Dự án dùng dữ liệu khoản vay Freddie Mac để nghiên cứu hai khả năng khiến một khoản vay thế chấp chấm dứt: **vỡ nợ (default)** và **tất toán trước hạn (voluntary prepayment)**. Câu hỏi chính là: *các khoản vay gặp các sự kiện này vào lúc nào, xác suất tích lũy thay đổi ra sao theo thời gian, và những đặc điểm tín dụng/khoản vay nào có liên quan?*

Đây là **phân tích sống còn (survival analysis)**. “Sống còn” nghĩa là khoản vay vẫn chưa gặp sự kiện đang phân tích và còn trong thời gian theo dõi. Trả trước là **rủi ro cạnh tranh (competing risk)**: khoản vay đã trả trước thì không thể tiếp tục gặp default sau đó. Vì vậy, nghiên cứu dùng **Default CIF** làm PD theo thời gian, thay vì đơn giản coi mọi khoản trả trước là khoản chưa vỡ nợ.

Phạm vi: Freddie Mac Single-Family Loan-Level **Sample Dataset**, vintage 2016–2026; monthly performance đến 31/03/2026. Vintage 2026 là năm chưa đầy đủ. Kết quả mô tả liên hệ thống kê, không tự chứng minh quan hệ nhân quả. Hệ thống không tính đầy đủ ECL theo IFRS 9.

### Năm điều cần nhớ

1. Origination có một dòng mỗi khoản vay; performance có nhiều dòng mỗi khoản theo tháng.
2. Đồng hồ nghiên cứu bắt đầu tại một **proxy tháng origination** được khóa rõ ràng; tháng thanh toán đầu tiên là tháng 1.
3. Ba kết cục là default, prepayment và censor (kết thúc quan sát khi chưa thấy sự kiện quan tâm).
4. **1 − Kaplan–Meier không phải PD competing-risk chính thức**. PD(t) của dự án là Default CIF từ Aalen–Johansen.
5. Kết quả phụ thuộc mẫu, ngày cắt, event rule, thời gian theo dõi và phiên bản production run.

## 2. Câu hỏi nghiên cứu

| Câu hỏi | Diễn giải thông thường | Phân tích liên quan |
|---|---|---|
| Điểm tín dụng, LTV, DTI, lãi suất, kỳ hạn liên quan thế nào đến default? | Khoản vay có đặc điểm khác nhau có tốc độ gặp sự kiện khác nhau không? | Cox PH, Time-varying Cox, cause-specific Cox, Fine–Gray |
| Rủi ro tích lũy thay đổi theo tuổi khoản vay thế nào? | Đến tháng 12/24/36/60 đã tích lũy bao nhiêu xác suất default/prepayment? | Aalen–Johansen CIF và PD horizon |
| Trả trước ảnh hưởng ước lượng ra sao? | Kết quả khác thế nào khi tính prepayment như một kết cục cạnh tranh? | KM so với CIF |
| Các vintage có khác nhau không? | Khoản vay khởi tạo vào các năm khác nhau có CIF khác nhau tại cùng horizon không? | Vintage CIF/PD |

Đặc tả đầy đủ ở [docs/research_specification.md](docs/research_specification.md). “Vintage” là **năm khoản vay được khởi tạo**, không phải năm xảy ra default.

## 3. Dữ liệu, quy mô và các bảng

### Nguồn dữ liệu

Freddie Mac cung cấp hai phần liên kết bằng Loan Sequence Number:

- **Origination**: thông tin khoản vay lúc khởi tạo/mua lại như FICO, DTI, LTV, lãi suất, UPB ban đầu, kỳ hạn và First Payment Date.
- **Monthly Performance**: trạng thái từng tháng như UPB hiện tại, delinquency, lãi suất hiện tại, Zero Balance Code và effective date.

Đây là bộ sample phục vụ nghiên cứu, không nên gọi là toàn bộ thị trường thế chấp Hoa Kỳ. ZIP Freddie Mac và dữ liệu trung gian lớn là file cục bộ, không nằm trong Git. Việc tải/sử dụng cần tuân thủ điều khoản nguồn dữ liệu.

### Quy mô đã ghi nhận trong repository

Đây là số liệu của bộ dữ liệu/release hiện đang được repository tham chiếu; bộ tải khác có thể đổi:

| Tầng | Số dòng/khoản | Ý nghĩa |
|---|---:|---|
| Origination nguồn | 512.500 | 50.000 mỗi năm 2016–2025 và 12.500 năm 2026 |
| Monthly Performance | 20.097.384 | Nhiều lần quan sát theo tháng cho mỗi khoản |
| Khoản có event map | 512.489 | Sau bước xác định sự kiện |
| Khoản đủ điều kiện phân tích sống còn | 504.405 | Có entry/exit hợp lệ |
| Complete-case cho 5 biến lõi | 499.393 | Mẫu mô hình tĩnh; không điền missing |
| Default trong cohort eligible | 16.556 | Theo định nghĩa hiện tại |
| Prepayment trong cohort eligible | 206.175 | Theo định nghĩa hiện tại |
| Censor trong cohort eligible | 281.674 | Theo dõi kết thúc khi chưa thấy default/prepayment |

Năm 2026 có theo dõi ngắn: trạng thái được ghi nhận là 5.123 khoản eligible, 6 prepayment, 5.117 censor và chưa có default. Không được diễn giải thành “vintage 2026 không có rủi ro default”; chỉ là chưa thấy sự kiện trong thời gian theo dõi hiện có.

### Các cấp dữ liệu

| Bảng | Mỗi dòng là | Ví dụ |
|---|---|---|
| Origination / loan master | Một khoản vay | FICO, LTV, DTI, lãi suất/kỳ hạn ban đầu |
| Performance / loan month | Một khoản vay trong một tháng | DPD, UPB, lãi suất hiện hành |
| Event map | Một khoản vay | Event type, event month, bằng chứng/mã nguồn |
| Survival duration | Một khoản vay | Tháng vào risk set, tháng ra, loại event, lý do loại |
| Time-varying input | Một khoảng của một khoản | Biến tháng trước được dùng dự báo khoảng kế tiếp |
| Dashboard projection | Một kết quả/nhóm/horizon | CIF, PD, HR/SHR, diagnostics, at-risk count |

Loan ID là khóa nối; trong Performance, khóa quan sát tháng gồm loan ID và performance month. Tra cứu biến cụ thể trong [docs/data_dictionary.md](docs/data_dictionary.md).

## 4. Mốc thời gian của nghiên cứu

### Vì sao time origin quan trọng?

Phân tích sống còn đo thời gian từ mốc bắt đầu tới khi xảy ra sự kiện hoặc theo dõi dừng lại. Mốc lệch sẽ làm mọi “tháng tuổi khoản vay” sai lệch.

Freddie Mac extract đang sử dụng có **First Payment Date**, nhưng không có ngày origination trực tiếp phù hợp. Nghiên cứu khóa quy ước:

~~~
operational_origination_date = First Payment Date trừ 1 tháng lịch
analysis_time_month = chênh lệch tháng lịch giữa performance_month và operational_origination_date
~~~

Vì vậy tháng thanh toán đầu tiên là **analysis month 1**. Tính theo số tháng thì tương đương performance_month - first_payment_month + 1, nhưng khi giải thích phải gọi đây là thời gian kể từ **origination proxy**.

Freddie Loan Age là trường nguồn khác; không thay thế study clock. Code ở [src/data/survival_duration.py](src/data/survival_duration.py), đặc tả ở [docs/research_specification.md](docs/research_specification.md).

### Entry, exit, duration và delayed entry

- **Entry time**: mốc khoản vay bắt đầu có performance được quan sát, trên đồng hồ nghiên cứu.
- **Exit time**: thời điểm default/prepayment đầu tiên hoặc tháng cuối được quan sát.
- **Delayed entry (left truncation)**: nếu khoản chỉ bắt đầu được ghi nhận sau lúc đồng hồ nghiên cứu đã chạy, khoản đó chỉ tham gia risk set từ entry time; không giả sử đã quan sát nó trước đó.
- **Duration**: số tháng thực sự nằm trong phần quan sát thường là exit trừ entry. Tuổi tại exit là con số khác.
- Sự kiện trước tháng performance đầu tiên được giữ lại để audit nhưng loại khỏi risk set. Code không ép tuổi âm về 0.
- Censor ở cutoff 31/03/2026 nghĩa là theo dõi kết thúc ở mốc này mà chưa quan sát event; không có nghĩa khoản vay sẽ không bao giờ vỡ nợ.

## 5. Cách gán default, prepayment và censor

Event rule nằm trong [src/data/event_definition.py](src/data/event_definition.py). Nhãn số dùng trong mô hình:

| Event | Mã | Quy tắc khái quát |
|---|---:|---|
| Censor | 0 | Không thấy default/prepayment trước kết thúc quan sát |
| Default | 1 | Bằng chứng 90+ days past due (DPD) là nguồn chính; RA và Zero Balance Code 02/03/09 là bằng chứng/fallback theo mapping |
| Prepayment | 2 | Zero Balance Code 01, theo effective date |

Zero Balance Code 15 (whole loan sale), 16 (reperforming securitization), 96 (defect) thuộc nhóm kết thúc/censor theo mapping hiện tại; maturity cũng kết thúc theo dõi. Không phải mã nào cũng là default.

Các nguyên tắc chọn event:

1. Chọn sự kiện sớm nhất theo tháng hiệu lực.
2. Nếu có nhiều loại trong cùng tháng, ưu tiên **Default > Prepayment > Censor**.
3. Xung đột cùng tháng được giữ cờ audit.
4. Mã không mapping hoặc mã kết thúc thiếu effective date phải được kiểm tra; không âm thầm gán thành censor.
5. Một khoản năm 2025 có termination code nhưng ngày hiệu lực thiếu/sai đã bị loại khỏi event map và ghi trong reports/event_missing_date_2025.csv.

DPD là mức trễ hạn; 90+ DPD là bằng chứng default quan trọng. ZBC là Zero Balance Code. Ý nghĩa code phải đọc theo từng mã, không gộp tất cả mã zero balance thành một loại sự kiện.

### Missing values

Các mã đặc biệt như 999/9999/blank được hiểu theo từng cột rồi chuyển thành missing khi thích hợp. Baseline không thay missing bằng 0, mean, median hoặc mode.

- Cohort sống còn có thể giữ khoản vay dù FICO hay một biến giải thích bị thiếu.
- Mô hình tĩnh yêu cầu complete cases cho năm biến lõi, vì vậy mẫu nhỏ hơn.
- Bảng CIF theo nhóm có thể giữ “Missing” như một band để không giấu số liệu thiếu; band này không phải một mức FICO/LTV/DTI thực.

Xem mapping từng biến trong [docs/data_dictionary.md](docs/data_dictionary.md), chất lượng dữ liệu trong [docs/data_quality_check.md](docs/data_quality_check.md).

## 6. Mô hình và cách diễn giải

### 6.1 Kaplan–Meier (KM)

KM ước lượng S(t): xác suất chưa gặp endpoint tới thời điểm t. Trong KM single-event cho default, prepayment thường được censor tại lúc khoản vay được trả trước.

KM hữu ích để mô tả survival. Nhưng khi prepayment cạnh tranh với default, 1 − S(t) không phải xác suất CIF default phù hợp. Dự án dùng KM để mô tả và đối chiếu, **không lấy làm PD competing-risk chính**.

### 6.2 Aalen–Johansen và Cumulative Incidence Function

**CIF** là xác suất tích lũy xảy ra một loại sự kiện tới thời gian t, có tính tới việc các sự kiện khác cũng có thể kết thúc khoản vay.

- **Default CIF(t) = PD(t)** theo định nghĩa nghiên cứu.
- **Prepayment CIF(t)** là xác suất tích lũy trả trước.
- Hai kết cục cạnh tranh: trả trước làm khoản vay rời risk set của default.
- Mốc chính 12, 24, 36 tháng; 60 tháng là horizon bổ sung và chỉ được báo cáo khi đủ follow-up/observed support.
- Đầu vào hỗ trợ delayed entry; estimator production dùng R survival::survfit.

PD(t) ở đây không tự bao gồm EAD, LGD, chiết khấu, kịch bản kinh tế hay các yêu cầu khác để tạo Expected Credit Loss theo IFRS 9.

### 6.3 Cox Proportional Hazards (Cox PH)

Cox PH liên hệ biến giải thích với **hazard**: tốc độ tức thời gặp event trong các khoản còn trong risk set. Baseline default Cox dùng năm biến gốc:

- FICO/credit score
- Original LTV
- Original DTI
- Original interest rate
- Original loan term

Biến được giữ đơn vị gốc; không tự chuẩn hóa/điền missing trong estimator. Kết quả HR = exp(coefficient):

- HR > 1: hazard cao hơn theo mỗi đơn vị tăng của biến, theo mô hình.
- HR < 1: hazard thấp hơn.
- HR = 1: hazard tương đối không thay đổi.

HR **không phải** phần trăm PD hay điểm phần trăm. Diễn giải phải tính tới đơn vị lưu: một điểm FICO, một điểm phần trăm LTV/DTI/lãi suất (theo cách mã hóa) hoặc một tháng kỳ hạn. Xem CI 95%, p-value, complete-case sample và diagnostics. Giả định proportional hazards yêu cầu HR tương đối ổn định theo thời gian; diagnostics kiểm tra giả định này.

### 6.4 Cause-specific Cox

Chạy mô hình Cox riêng cho Default và Prepayment. Khi một loại là endpoint, event cạnh tranh còn lại được censor tại thời điểm xảy ra. Mô hình mô tả cause-specific hazard; nó không trực tiếp cho CIF/PD tuyệt đối.

### 6.5 Fine–Gray

Fine–Gray mô hình subdistribution hazard cho CIF khi có competing event. Kết quả là **SHR**, không phải HR Cox:

- SHR > 1 thường gắn với CIF của endpoint cao hơn theo hướng mô hình.
- SHR < 1 thường gắn với CIF thấp hơn.
- SHR cũng không phải PD tuyệt đối.

Implementation dùng R package survival, bảo toàn delayed entry và loan-clustered robust variance (theo đặc tả/code hiện hành).

### 6.6 Time-varying Cox

UPB hiện tại, lãi suất và delinquency có thể đổi theo tháng. Mô hình sử dụng giá trị tháng trước để dự báo khoảng kế tiếp; tránh nhìn giá trị event-month để dự báo chính event trong tháng đó. Các predictor time-varying đang khớp gồm:

- lagged actual UPB
- lagged current interest rate
- delinquency indicator 1 tháng và 2 tháng (mutually exclusive)

Các đặc điểm origination lõi cũng được đưa vào. Trạng thái 90+ DPD tháng xảy ra default không được đưa vào để dự báo chính default đó (tránh target leakage). Mô hình dùng L2 penalizer cố định 0.1 để ổn định predictor delinquency 2 tháng gần separation; diagnostics lưu thông số và variance. Nêu rõ lựa chọn này khi trình bày.

| Con số | Trả lời câu hỏi | Không phải |
|---|---|---|
| KM survival S(t) | Xác suất chưa gặp endpoint | PD competing-risk |
| 1 − KM | Bù xác suất survival theo KM | Default CIF |
| Default CIF | Xác suất tích lũy default có tính prepayment | HR, SHR hay ECL |
| Cox HR | Quan hệ biến với cause-specific hazard | Mức tăng PD tuyệt đối |
| Fine–Gray SHR | Quan hệ biến với subdistribution hazard/CIF | Cox HR |
| CIF nhóm/vintage | Mô tả rủi ro của cohort | Hiệu ứng nhân quả đã kiểm soát |

## 7. PD theo danh mục, vintage và nhóm

### PD toàn danh mục

PD(H) là Default CIF tại horizon H. Ví dụ PD(24) là xác suất tích lũy default đến tháng 24 trong cohort nghiên cứu, có tính prepayment competing risk.

### Vintage

Cohort được gom theo năm origination. So sánh vintage tại cùng horizon chỉ khi follow-up phù hợp. Code kiểm tra thời gian đầy đủ theo performance cutoff; thiếu follow-up hoặc observed support thì không ngoại suy và không thay bằng 0. Vintage 2025/2026 thường không đủ tuổi cho horizon dài. Khi báo cáo nêu vintage, horizon, at-risk count và follow-up eligibility.

### CIF theo FICO/LTV/DTI

Backend hỗ trợ CIF riêng cho các band đặc tính gốc:

| Chiều | Các band hiện tại |
|---|---|
| FICO | <650; 650–699; 700–749; 750+; Missing |
| Original LTV | ≤60%; >60–70%; >70–80%; >80%; Missing |
| Original DTI | ≤30%; >30–40%; >40–50%; >50%; Missing |

Đây là CIF **mô tả của từng nhóm**, không phải ảnh hưởng độc lập của đặc tính sau khi giữ mọi yếu tố khác không đổi. Để xem liên hệ có điều chỉnh đồng thời covariates, xem hệ số Cox/Fine–Gray. Code trang Rủi ro danh mục dùng at-risk tối thiểu 100 khi xếp hạng; nhóm nhỏ vẫn có thể hiển thị kèm cảnh báo. “Missing” phải đọc như trạng thái thiếu dữ liệu, không phải risk band thực.

## 8. Dashboard có những gì?

Dashboard Streamlit đọc production release đã publish; nó không fit lại mô hình mỗi khi mở trang.

### 1 — Tổng quan

Quy mô khoản vay, tỷ lệ event thô, PD/CIF ở các horizon và Kaplan–Meier. Tỷ lệ default thô trong toàn thời kỳ và CIF tại một horizon là hai đại lượng khác nhau; không thay thế nhau.

### 2 — Rủi ro danh mục

Xem PD toàn danh mục, vintage, và nếu kết quả grouped đã publish thì CIF theo FICO/LTV/DTI; lựa chọn horizon/metric, baseline, bảng/heatmap và at-risk support. Đây là mô tả so sánh cohort.

### 3 — Yếu tố rủi ro

Forest plot HR/SHR, CI 95%, p-value và hệ số theo model/endpoint/version. Luôn xác định loại hệ số và đơn vị predictor.

### 4 — Tra cứu khoản vay

Tìm Loan ID để xem dữ liệu origination, trạng thái, monthly timeline và nhóm so sánh. Lookup lịch sử đầy đủ cần Parquet cục bộ; code trên GitHub một mình có thể không đủ dữ liệu để tra cứu.

### 5 — Kết quả mô hình

Chọn KM, Cox PH, Time-varying Cox, Cause-specific Hazard, Aalen–Johansen/CIF hoặc Fine–Gray; xem đồ thị, diagnostics và đối chiếu KM với CIF. KM không có regression coefficient/convergence diagnostics là bình thường; nó phi tham số.

Nguồn code: [app/pages](app/pages), [app/services/data_service.py](app/services/data_service.py), [src/results/dashboard.py](src/results/dashboard.py). Tầng dữ liệu ưu tiên release trong results/current.json; query CSV/Parquet là fallback cho release cũ.

## 9. Luồng từ file ZIP tới trang web

~~~
flowchart TD
  A[Freddie Mac ZIP: Origination + Performance] --> B[Đọc layout, chia chunk, kiểm tra khóa]
  B --> C[Chuẩn hóa và xử lý missing]
  C --> D[Lập event map: default / prepay / censor]
  D --> E[Time origin, entry/exit, survival eligibility]
  E --> F[Loan-level và monthly model inputs]
  F --> G[KM, Cox, Aalen-Johansen, Fine-Gray, vintage và grouped CIF]
  G --> H[Validate, manifest, provenance, diagnostics]
  H --> I[Publish run và cập nhật current.json]
  I --> J[Dashboard đọc release đã publish]
~~~

1. **Ingestion**: đọc file theo layout cột ở config/data_config.yaml; chunking giảm áp lực bộ nhớ.
2. **Cleaning**: chuẩn hóa ID, ngày, kiểu số và mã missing theo từng biến.
3. **Audit**: kiểm tra duplicate, khóa, ngày, event conflict và duration.
4. **Event map**: nối Origination/Performance và xác định sự kiện đầu tiên.
5. **Survival duration**: tạo origin proxy, entry/exit và lý do loại.
6. **Model dataset**: tạo một dòng/loan cho static models và interval input cho time-varying Cox.
7. **Production**: preflight, fit, xuất artifacts/diagnostics/provenance, validate rồi publish.

Một production run nằm trong results/production/<run_id>/. Manifest liệt kê artifact/hash/status; provenance ghi dấu vết đầu vào; results/current.json trỏ tới run dashboard đang đọc. Không sửa CSV riêng để “chữa” một biểu đồ; hãy tạo và publish release hợp lệ.

## 10. Cấu trúc thư mục — tìm đúng phần

| Đường dẫn | Chức năng |
|---|---|
| app/app.py | Khởi tạo dashboard và điều hướng |
| app/pages/ | Năm trang người dùng |
| app/components/ | KPI, chart, filter, timeline, giao diện chung |
| app/services/data_service.py | Đọc/cached kết quả cho giao diện |
| src/data/ | Đọc, làm sạch, event rule, duration, model data |
| src/survival/ | KM, Cox, time-varying Cox, diagnostics |
| src/competing_risks/ | CIF, Aalen–Johansen, Fine–Gray, grouped/vintage |
| src/production/ | Preflight, contracts, build và validation |
| src/results/ | Manifest, integrity, reader/writer |
| config/data_config.yaml | Cấu hình layout nguồn và năm |
| docs/ | Đặc tả, từ điển biến, chất lượng dữ liệu |
| scripts/ | Các lệnh xử lý và kiểm định |
| reports/ | Audit reports và diagnostics dễ đọc |
| outputs/tables/ | Bảng CSV bằng chứng gọn |
| src/data/ | Raw ZIP được đặt tại đây theo cấu hình hiện tại |
| data/processed/ | Parquet Origination/Performance sau ingestion |
| data/model/ | Event map, duration, model input |
| results/production/ | Các run có version và artifacts |
| results/current.json | Con trỏ run đang publish |

Tài liệu tham chiếu: [README.md](README.md) (workflow kỹ thuật), [README_NGUOI_MOI.md](README_NGUOI_MOI.md) (cài đặt từng bước), [research specification](docs/research_specification.md), [data dictionary](docs/data_dictionary.md), [data quality report](docs/data_quality_check.md).

## 11. Cài đặt và chạy trên Windows

### Chỉ mở dashboard khi đã có kết quả

Mở PowerShell ở project root:

~~~
cd "D:\Gói 1\mortgage-risk-survival-analysis"
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m streamlit run app/app.py
~~~

Mở http://localhost:8501; giữ terminal mở khi dùng app; nhấn Ctrl+C để dừng. Nếu No module named streamlit, hãy cài dependencies trong đúng virtual environment rồi chạy lại. Entry point là app/app.py; yourscript.py chỉ là placeholder ví dụ, không phải tệp dự án.

### Tạo dữ liệu phân tích từ ZIP

Đặt đủ ZIP Freddie Mac theo năm vào src/data/. Từ root, chạy tuần tự:

~~~
python scripts\process_all.py
python scripts\check_data.py
python scripts\clean_all.py
python scripts\final_data_validation.py
python scripts\audit_event_conflicts.py
python scripts\build_event_maps_all.py
python scripts\audit_loan_age_duration.py
python scripts\build_survival_duration_all.py
python scripts\build_model_datasets_all.py
~~~

Nếu có lỗi validator, thiếu ZIP hay counts lệch, dừng lại để điều tra. Không sửa expected count hoặc bỏ kiểm tra chỉ để pipeline chạy qua.

### Production model release

Complete release cần R và package survival theo version được hướng dẫn trong README người mới. Quy trình có ba chặng rõ ràng:

~~~
python scripts\run_production.py preflight --group complete --rscript "C:\path\to\Rscript.exe"
python scripts\run_production.py build --rscript "C:\path\to\Rscript.exe" --confirm-full-production
python scripts\run_production.py validate --run-id <run-id-vừa-tạo>
python scripts\run_production.py publish --run-id <run-id-vừa-tạo> --confirm-publish
~~~

Thay đường dẫn và run ID placeholder bằng giá trị thật. Preflight kiểm tra đầu vào; build fit mô hình; validate kiểm tra artifacts; publish chỉ thực hiện khi run hợp lệ. Không cần chạy lại production chỉ để mở dashboard nếu đã có release cục bộ hợp lệ.

## 12. Đọc và trình bày kết quả

Khi nói về một con số, kèm tối thiểu:

1. Endpoint: Default hay Prepayment?
2. Estimator: KM, Aalen–Johansen, Cox hay Fine–Gray?
3. Population: toàn cohort, complete-case, vintage hay band nào?
4. Horizon và time origin?
5. Follow-up eligibility/at-risk count?
6. CI 95% và p-value nếu nói về hệ số?
7. Cutoff, data/model version và run ID?

Ví dụ diễn giải cẩn thận:

> Trong Freddie Mac sample vintage 2016–2026 đủ điều kiện, Default CIF tại 36 tháng là …%, tính từ origination proxy (First Payment Date trừ một tháng), với voluntary prepayment là competing event và performance cutoff 31/03/2026. Đây là ước lượng cho cohort quan sát, không phải kết luận nhân quả hay ECL IFRS 9.

Cần tránh:

- “HR 1,2 nghĩa là PD tăng 20 điểm phần trăm.” HR không phải xác suất tuyệt đối.
- “1 − KM là PD.” Không đúng với mục tiêu CIF khi có competing prepayment.
- “LTV cao gây default.” CIF nhóm là mô tả, chưa chứng minh nhân quả.
- “2026 không có rủi ro default.” Follow-up quá ngắn không cho kết luận đó.
- “Censor là khách hàng tốt.” Chỉ có nghĩa event chưa xuất hiện trong thời gian quan sát.
- Cộng PD(12)+PD(24)+PD(36) để ra lifetime PD. Các mốc là xác suất tích lũy tại các thời điểm khác nhau.

## 13. Giới hạn cần nói rõ

- Đây là sample Freddie Mac; không tự đại diện cho mọi ngân hàng/loan book.
- Vintage 2026 còn ngắn; thiếu event không có nghĩa PD bằng 0.
- Origination date dùng proxy First Payment Date − 1 tháng do dữ liệu nguồn.
- Kết quả phụ thuộc giả định censoring, event mapping và support quan sát.
- Static baseline Cox là complete-case; mẫu nhỏ hơn cohort survival.
- Nhóm CIF nhỏ có thể dao động mạnh; xem số at risk/follow-up.
- Association không đồng nghĩa causation.
- PD(t) không bao gồm đầy đủ EAD, LGD, discounting, kịch bản kinh tế để thành ECL.
- Dashboard là công cụ phân tích, không phải hệ thống ra quyết định phê duyệt khoản vay.

## 14. Bằng chứng kiểm định và trạng thái hiện hành

Repository có schema/event/time validators, audit reports và production release có manifest, input provenance, hashes, model diagnostics và validation report. Release hiện được trỏ ở results/current.json; run ID ghi nhận là 20260929T235303Z_ca7d0c1. Một máy mới clone code nhưng chưa có dữ liệu/release cục bộ có thể không mở được mọi chart/loan lookup.

Báo cáo chất lượng ghi nhận reporting gap ở 2017, 10 Origination không có Performance thuộc 2025–2026 và một khoản năm 2025 thiếu effective date bị loại khỏi event map. Không bỏ các caveat này khỏi báo cáo.

Test event rule:

~~~
python -m unittest tests.test_event_definition -v
~~~

Validation dữ liệu lớn cần các file local. Xem [README.md](README.md). generate_mock_data.py, nếu dùng, tạo mock cho phát triển; mock không phải kết quả nghiên cứu thực nghiệm.

## 15. Từ điển nhanh

| Từ | Nghĩa |
|---|---|
| Loan-level / loan-month | Một dòng mỗi khoản / một dòng mỗi khoản mỗi tháng |
| Vintage | Năm khoản vay được khởi tạo |
| FICO | Điểm tín dụng |
| LTV | Loan-to-Value, tỷ lệ khoản vay so với giá trị tài sản theo nguồn |
| DTI | Debt-to-Income, tỷ lệ nghĩa vụ nợ so với thu nhập theo nguồn |
| UPB | Unpaid Principal Balance, dư nợ gốc chưa trả |
| DPD | Days Past Due, trạng thái trễ hạn |
| Event | Kết cục được theo dõi |
| Censor | Kết thúc thời gian quan sát trước khi thấy event quan tâm |
| Risk set / at risk | Các khoản còn có thể gặp event tại thời điểm đó |
| Delayed entry | Bắt đầu quan sát sau mốc time origin |
| Hazard | Tốc độ tức thời gặp event trong nhóm at risk |
| CIF | Xác suất tích lũy của event khi có event cạnh tranh |
| HR / SHR | Hazard ratio Cox / subdistribution hazard ratio Fine–Gray |
| Horizon | Mốc 12, 24, 36 hoặc 60 tháng |
| Complete case | Quan sát có đủ các biến bắt buộc cho model |
| Provenance / manifest | Dấu vết đầu vào / danh mục và trạng thái artifacts của run |
| ECL | Expected Credit Loss; cần nhiều cấu phần ngoài PD(t) |

## 16. Lộ trình học tiếp

1. Đọc phần 1–5 để nắm mục tiêu, cohort, event và time origin.
2. Đọc phần 6–8 để hiểu model và dashboard.
3. Mở docs/research_specification.md để xem quyết định phương pháp đã khóa.
4. Mở docs/data_dictionary.md khi gặp tên trường cụ thể.
5. Đọc docs/data_quality_check.md và các file reports/ trước khi bảo vệ kết luận.
6. Nếu muốn lần theo code, đi theo thứ tự: src/data/ → src/survival/ và src/competing_risks/ → src/production/ → src/results/ → app/.

---

**Nguồn của cẩm nang:** tài liệu nghiên cứu, từ điển biến, báo cáo chất lượng, README, code pipeline/dashboard và manifest production hiện hành. Khi thay đổi code/spec, cập nhật tài liệu này để tránh hướng dẫn và hệ thống lệch nhau.
