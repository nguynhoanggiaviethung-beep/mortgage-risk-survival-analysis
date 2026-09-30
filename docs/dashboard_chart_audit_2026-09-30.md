# Audit biểu đồ Dashboard — 30/09/2026

## Phạm vi và cách đọc kết luận

Đã lần theo các chart builder trong `app/pages/` và `app/components/charts.py`, các accessor ở `app/services/data_service.py`, pipeline tạo CIF/vintage ở `src/competing_risks/`, cùng release `20260929T235303Z_ca7d0c1`. Release có 4 mốc portfolio (12/24/36/60), 60 dòng CIF nhóm FICO/LTV/DTI, 44 dòng vintage-horizon; validation report ghi 62/62 PASS. Điều đó xác nhận hợp đồng dữ liệu và một số invariant, **không chứng minh mọi giả định thống kê hoặc lựa chọn trực quan đều phù hợp**.

Trong báo cáo này, “sự kiện” là kết cục được ghi nhận trong panel; “CIF” là xác suất tích lũy theo Aalen–Johansen (AJ) khi có competing event; “HR/SHR” là liên hệ trong mô hình, không phải tác động nhân quả. Mẫu số của CIF là cohort lúc bắt đầu risk set, còn `n_at_risk` là số còn có nguy cơ ngay trước mốc đó; hai số không được dùng thay cho nhau.

## PHẦN 1 — Bảng audit toàn bộ dashboard

| Page | Chart | Mục đích | Vấn đề | Mức độ | Đề xuất |
|---|---|---|---|---|---|
| Sidebar | Quy mô khoản vay theo vintage | So quy mô cohort mỗi năm | Thanh dùng max năm làm 100%, có min-width 3%; không phải chart rủi ro, không ghi trục | Thấp | Giữ như mini-bar; ghi rõ “số khoản”, dùng 0 làm gốc và tránh thanh tối thiểu gây sai tỷ lệ |
| 1 Tổng quan | Default/Prepayment CIF theo horizon (bar nhóm) | Xác suất tích lũy hai kết cục ở các mốc | Bar không nhấn mạnh tính tích lũy; legend dùng “trả nợ trước hạn” dù ZBC 01 gộp prepaid/matured; horizon là điểm ước lượng rời rạc | Vừa | Đổi line/step hoặc điểm có CI, title ghi CIF và 12/24/36/60 tháng; đổi nhãn thành “ZBC 01: tất toán trước hạn/đáo hạn” cho tới khi phân biệt được |
| 1 Tổng quan | Dots infographic “trong 1.000 khoản” | Minh họa Default CIF tại mốc chọn | Là mã hóa cùng một CIF lần nữa; chấm là quy đổi `round(CIF×1000)`, không phải 1.000 hồ sơ lấy mẫu | Thấp | Bỏ hoặc đổi thành số lớn + CI; nếu giữ, ghi “minh họa, mỗi chấm = 1/1.000 xác suất” |
| 1 Tổng quan | Kaplan–Meier survival | Xác suất sống sót khỏi default khi trả trước bị censor | KM không phải `1 − Default CIF`; trước đây thiếu CI, còn KM estimator vốn không tính prepayment là competing event; x-axis “giải ngân” là proxy | Cao | Giữ như đối chứng phương pháp, đổi title/axis ghi rõ; thêm CI và n-at-risk; không gọi là PD thực tế |
| 1 Tổng quan | CIF theo vintage (nếu có vintage trong nguồn) | So sánh cohort cùng horizon | Trang hiện đọc `pd_raw`, không `vintage_results`; production accessor gắn `vintage=All` cho PD portfolio nên filter/compare vintage không lấy được dữ liệu vintage thực | Cao | Nối `ds.get_vintage_results()`; mỗi line/horizon chỉ hiện vintage đủ seasoning, kèm N và CI |
| 2 Rủi ro danh mục | Bar Default/Prepayment CIF theo band + portfolio line | So sánh rủi ro mô tả giữa các band tại horizon chọn | Hợp loại chart; không có CI; baseline line là danh mục bao gồm chính các band; không điều chỉnh confounders; risk color cutoffs 0.8/1.25 là quy ước UI | Vừa | Giữ nhưng ghi “mô tả, chưa điều chỉnh”; thêm at-risk/CI; gọi baseline “toàn danh mục” chứ không “trung bình các nhóm” |
| 2 Rủi ro danh mục | Heatmap band × horizon | Xem pattern rủi ro qua thời gian và band | Không cố định `zmin/zmax`; màu tự co theo vùng dữ liệu hiện tại nên có thể phóng đại khác biệt nhỏ và không so được sau đổi filter; một số ô thiếu do eligibility | Cao | Dùng thang màu sequential, domain cố định được công bố (hoặc ghi min/max động); để NA thành ô xám; giữ con số trong ô và thêm CI/N |
| 2 Rủi ro danh mục | “Đặc điểm nào phân biệt rủi ro mạnh nhất?” max/min ratio | Xếp dimension theo khoảng cách giữa band cao nhất/thấp nhất | Tỷ số max/min rất nhạy khi min CIF gần 0; dimension có số band khác nhau; bỏ CI/độ lớn mẫu và không phải adjusted effect | Cao | Bỏ tỷ số khỏi thứ hạng chính; thay bằng range tuyệt đối (max−min, điểm %) kèm CI hoặc mô hình đa biến; nếu giữ chỉ làm mô tả và cảnh báo unstable |
| 2 Rủi ro danh mục | Vintage: nhiều line theo horizon | So sánh Default CIF của vintage tại cùng số tháng | Hợp mục tiêu; mỗi line có tập vintage đủ follow-up khác nhau; không CI/N trên đồ thị; nối các năm bằng đường tạo cảm giác trend liên tục | Vừa | Giữ dạng line/point theo vintage; không nối qua vintage bị loại; thêm band CI/N; mô tả association theo cohort, không quy nguyên nhân cho năm |
| 3 Yếu tố rủi ro | Forest plot HR/SHR + 95% CI | Xem biến nào liên hệ với hazard cao/thấp | Forest plot đúng; trục x tuyến tính trong khi HR/SHR nên đọc đối xứng quanh 1 trên log scale; UPB theo USD gây hệ số phụ thuộc đơn vị; Cox PH bị vi phạm trong release | Cao | Log-scale x, zero/reference=1; scale UPB (ví dụ mỗi $10k); hiện PH warning sát chart, không mặc định diễn giải Cox PH như effect bất biến |
| 4 Tra cứu khoản vay | Timeline của một loan | Xem thời gian quan sát và tháng event/censor | Y=0 ẩn; các monthly observation là dấu chấm trên thanh, không thể hiện delinquency/UPB; đường nối tháng thiếu có thể tạo cảm giác panel liên tục | Vừa | Đổi thành timeline event rõ ràng hoặc hai panel: DPD status theo tháng + UPB; đánh dấu missing-month gap và event terminal; ghi time origin proxy |
| 5 Kết quả mô hình | Default CIF + Prepayment CIF theo horizon | Xem cumulative incidence hai kết cục | Chỉ có 4 horizon; line nối điểm rời rạc trông như đường ước lượng liên tục; không CI/at-risk; trang 1 cũng có chart gần như trùng | Cao | Đổi thành point-range ở horizon cố định hoặc step curve từ full AJ (có CI); bỏ trùng với Overview hoặc biến Page 5 thành chẩn đoán/phương pháp |
| 5 Kết quả mô hình | 1−KM vs Default CIF | Minh họa censoring prepayment làm khác CIF | So cùng estimand? 1−KM là net-risk/hypothetical khi censor competing event, CIF là actual-world probability; so sánh có ý nghĩa như minh họa phương pháp nhưng line KM dày theo tháng còn CIF chỉ 4 điểm, thiếu CI | Cao | Giữ chỉ như chart giáo dục; hiển thị CIF step + KM monthly cùng thời điểm, CI, at-risk; title nói đây là hai estimand khác nhau |
| 5 Kết quả mô hình | Forest plot HR/SHR | Định lượng liên hệ các biến với default/prepayment | Đúng loại chart; PH diagnostic bị ẩn trong expander, mặc định chọn Cox PH; plot không log scale; dùng một trục cho effects có thể khác đơn vị/tầm giá trị | Cao | Chỉ show model có endpoint được nêu; log x; thêm cảnh báo Cox PH; hiệu ứng standardized/đơn vị diễn giải rõ; ưu tiên Fine–Gray hoặc time-varying theo câu hỏi phù hợp |

### Chi tiết các biểu đồ ngoài Page 5

#### Sidebar — số khoản vay theo vintage (mini-bars)

**1. Biểu đồ này đang thể hiện gì?** Số hồ sơ vay trong mỗi vintage để mô tả cơ cấu mẫu. **2. Dữ liệu:** `vintage_results.loan_count` (nếu có), fallback `portfolio_summary.loan_count` rồi `loan_profile`; group theo vintage, `max` để tránh cộng lặp horizon; mỗi bar width=`count/max_count×100%`, min 3%; unit=khoản vay. **3. Cách đọc:** số tuyệt đối bên phải là chính xác; chiều dài chỉ so với vintage lớn nhất. **4. Insight:** vintage nào có nhiều hồ sơ hơn trong extract. Fact đếm, không phải mức rủi ro/đại diện thị trường. **5. Vấn đề:** bar nhỏ bị ép tối thiểu 3%, không trục/zero baseline; có thể hiểu sai scale. **6. Đánh giá:** giữ nhưng chỉnh. **7. Chỉnh:** mini-bar vẫn được; X ngầm là loan count, Y=vintage; bỏ min-width giả tỷ lệ hoặc chuyển thanh ngang có trục; title “Số khoản vay trong mẫu theo vintage”; tooltip n và tỷ trọng trong mẫu.

#### Page 1 — Default CIF và Prepayment CIF theo horizon

**1. Thể hiện:** xác suất tích lũy hai kết cục tại các horizon. **2. Dữ liệu:** `overall_pd_horizons` cho Default CIF và `survival_results` Aalen–Johansen/PREPAYMENT tại `analysis_time≤horizon`; portfolio, eligible horizons; không có averaging trong production release (4 hàng). Formula là AJ CIF, unit probability. **3. Cách đọc:** X=12/24/36/60 tháng; Y=CIF %. **4. Insight:** estimate CIF có tính competing event, là calculation chứ không phải raw fact. **5. Vấn đề:** `add_bar` tạo cột cho cumulative values, trong khi mục tiêu là diễn tiến theo thời gian; thiếu uncertainty; ZBC01 label sai hẹp nếu gọi voluntary prepay; Page 5 lặp. **6. Đánh giá:** giữ nhưng đổi kiểu. **7. Chỉnh:** line-step/point-range; X=horizon; Y=CIF (%); giữ competing outcomes, CI và at-risk N; title “Xác suất tích lũy theo thời gian”; không hiển thị mốc không eligible.

#### Page 1 — dots infographic 1.000 khoản

**1. Thể hiện:** quy đổi CIF đang chọn ra số dots đỏ trong 1.000. **2. Dữ liệu:** cùng `pd_by_horizon`; `bad=round(CIF×1000)`, ép tối thiểu 1 nếu >0; unit là minh họa trên 1.000 xác suất. **3. Cách đọc:** mỗi dot đỏ biểu trưng khoảng 0,1 điểm phần trăm, không đại diện loan cụ thể. **4. Insight:** chỉ giúp quy mô dễ hình dung, không thêm thông tin. **5. Vấn đề:** dư thừa với KPI/chart; văn bản lại nói “khoản vay” như thể 1.000 case quan sát; nếu CIF nhỏ, làm tròn min1 phóng đại. **6. Đánh giá:** nên bỏ hoặc đổi. **7. Chỉnh:** bỏ; hoặc ghi rõ “minh họa xác suất, không phải mẫu hồ sơ” và dùng 100 dots/1000 dots nhất quán không ép min1.

#### Page 1 — Kaplan–Meier survival

**1. Thể hiện:** xác suất chưa gặp default theo KM, prepayment được coi censored. **2. Dữ liệu:** `km_results`: `analysis_time`, `survival`, CI, n-risk; production chọn endpoint DEFAULT/portfolio; chart hiện không lấy CI. **3. Cách đọc:** X=analysis month /12 đổi thành năm; Y=KM survival. **4. Insight:** net-risk survival estimate theo censoring convention, không actual-world PD; estimate. **5. Vấn đề:** title/copy cũ nói “chưa xảy ra default” dễ hiểu là probability thực tế; thiếu CI/n-risk; cut trục Y từ `min(survival)-.02` lên 1 khiến biến động cuối curve nhìn lớn hơn nếu không để ý. **6. Đánh giá:** giữ nhưng đổi chú giải/uncertainty. **7. Chỉnh:** step line; CI; at-risk table; X=tháng kể từ proxy; Y=KM S(t) với range [0,1] hoặc cảnh báo zoom; title “KM survival (prepayment censored)”.

#### Page 1 — vintage CIF bar

**1. Thể hiện:** Default CIF so sánh giữa vintage tại horizon chọn. **2. Dữ liệu:** code hiện tìm `vintage` trong `pd_raw`, `group=portfolio`, chọn horizon, groupby vintage lấy mean; unit probability. Production `get_pd_results()` chỉ gắn vintage All; dữ liệu đúng nằm ở `get_vintage_results()`. **3. Cách đọc:** X=vintage, Y=CIF tại cùng horizon. **4. Insight:** bản thân chart có thể hỗ trợ cohort comparison nếu được nối đúng nguồn; hiện dashboard current release không có hai vintage trở lên từ nguồn này. **5. Vấn đề:** chart không hiện hoặc vintage filter không hoạt động; `mean` không phải pooled CIF nếu duplicate curves. **6. Đánh giá:** giữ nhưng phải thay nguồn. **7. Chỉnh:** `ds.get_vintage_results()`, filter `follow_up_eligible`, X=vintage categorical, Y=default_cif; không mean các vintages/replicates; CI/N tooltip và ghi rõ năm gần cutoff bị loại.

#### Page 2 — CIF bar theo FICO/LTV/DTI + portfolio reference

**1. Thể hiện:** so sánh CIF giữa các band tại một horizon/endpoint. **2. Dữ liệu:** `grouped_pd_horizons` (grouped CIF; features FICO/LTV/DTI); band/horizon/metric; chỉ `follow_up_flag=True`; baseline `overall_pd_horizons`. **3. Cách đọc:** X=band thứ tự theo ngưỡng; Y=CIF; đường gạch là portfolio CIF. **4. Insight:** khác biệt mô tả giữa band; không causal/adjusted. **5. Vấn đề:** không có CI; baseline portfolio gồm chính các subgroups; risk traffic-light threshold ±20/25% là presentation rule, không validation threshold; hover không đưa N. **6. Đánh giá:** giữ nhưng bổ sung uncertainty. **7. Chỉnh:** horizontal bar/point-range (band labels dài); X=CIF %, Y=band; annotate portfolio estimate; show CI/N/at-risk; filter endpoint/horizon/dimension; title “CIF theo nhóm FICO/LTV/DTI tại H tháng”.

#### Page 2 — Heatmap band × horizon

**1. Thể hiện:** một CIF cho mỗi band-horizon. **2. Dữ liệu:** cùng grouped table; chỉ eligibility; groupby band/horizon mean; unit probability. Với production data mỗi feature-band-horizon là một row, mean hiện tại không đổi giá trị. **3. Cách đọc:** X=horizon, Y=band, fill/text=CIF. **4. Insight:** pattern theo band và horizon, descriptive estimate. **5. Vấn đề:** `zmin/zmax` không cố định; custom colorscale 0…1 vẫn map current data min/max nếu Plotly auto-range, nên màu tương đối theo từng filter; missing cells dễ tưởng 0; không uncertainty/N. **6. Đánh giá:** giữ nhưng sửa scale và NA. **7. Chỉnh:** sequential single-hue, explicit colorbar bounds thống nhất giữa filter (chọn max được giải thích); X=horizon; Y=band; cell=CI/N tooltip, gray NA; title nêu metric/horizon.

#### Page 2 — tỷ số max/min theo dimension

**1. Thể hiện:** dimension có spread tương đối lớn nhất giữa các band. **2. Dữ liệu:** grouped CIF tại selected horizon; loại band missing và n-risk<100; groupby band mean; `max(CIF)/min(CIF)`, unit “lần”. **3. Cách đọc:** thanh dài hơn=tỷ lệ extreme lớn hơn. **4. Insight:** extreme ratio mô tả các band hiện có, không effect dimension. **5. Vấn đề:** min CIF→0 tạo ratio rất lớn; dimensions có band count/range khác nhau; bỏ uncertainty; chỉ có thể so dimensions nếu definition/populations/missingness tương thích. **6. Đánh giá:** nên bỏ chart ranking hiện tại. **7. Chỉnh:** thay bằng range tuyệt đối `max−min` percentage points kèm bootstrap CI hoặc model adjusted contrasts; filter cùng horizon và metric; title “Khoảng chênh CIF giữa band cực trị (mô tả)”; không tô dimension selected như thể có ý nghĩa thống kê.

#### Page 2 — vintage multi-line

**1. Thể hiện:** Default CIF theo vintage cho các horizon đủ follow-up. **2. Dữ liệu:** `vintage_horizon_results`: vintage, horizon, default_cif, eligibility, counts; lọc eligibility, mỗi horizon một line. **3. Cách đọc:** X=vintage, Y=CIF; mỗi line là horizon cố định. **4. Insight:** so sánh các thế hệ cùng age horizon; estimate. **5. Vấn đề:** từng horizon có số vintage khác nhau (release: 12m 7 eligible, 24m 6, 36m 6, 60m 2); line nối các năm có thể ám chỉ trend liên tục; no CI. **6. Đánh giá:** giữ nhưng đổi mã hóa. **7. Chỉnh:** point-range hoặc small multiples theo horizon; X=vintage, Y=CIF; không nối thiếu vintage; hover gồm loan_count/at-risk/event count/CI; title nói “vintage đủ seasoning”.

#### Page 3 — forest plot yếu tố rủi ro

**1. Thể hiện:** HR/SHR và CI của covariates cho model, endpoint/version đã chọn. **2. Dữ liệu:** `risk_driver_results` từ baseline Cox, TV Cox, cause-specific và Fine–Gray; Filter model/endpoint/version; không aggregate; effect=`exp(β)`. **3. Cách đọc:** X ratio, Y variable; CI cắt 1 nghĩa tương thích với no association ở mức danh nghĩa. **4. Insight:** conditional association; không causal. **5. Vấn đề:** linear scale, UPB unit scale, forest effect-size so sánh không cùng đơn vị; PH violation cần cảnh báo khi baseline Cox; multiple testing. **6. Đánh giá:** giữ nhưng sửa. **7. Chỉnh:** log x-axis; sort domain grouping; scale UPB (re-fit); show CI/p/model N/events and PH status; title nêu HR hoặc SHR + endpoint cụ thể.

#### Page 4 — single-loan timeline

**1. Thể hiện:** thời điểm proxy origination, first payment, monthly observations, terminal event/end follow-up cho loan tra cứu. **2. Dữ liệu:** `analysis_loans_2016_2026.parquet` + `performance.parquet`; loan id filter; `analysis_time_month = calendar month(performance) − proxy origin`; line có y=0; terminal code from event mapping. **3. Cách đọc:** X=analysis month, Y bị ẩn; marker cuối là observed termination/default/prepay/censor. **4. Insight:** thứ tự/thời lượng quan sát của cá nhân; raw display. Không phải xác suất/risk trajectory. **5. Vấn đề:** mặc dù bảng lịch sử có DPD/UPB, chart chỉ vẽ một đường ngang và monthly dots nên không giải thích biến động; nối qua tháng thiếu; marker terminal duplicates conceptually with loan_age; proxy không phải actual origination. **6. Đánh giá:** nên thay chart type. **7. Chỉnh:** timeline event strip riêng (loan opening, first payment, delinquency transitions, terminal outcome) hoặc two-panel monthly chart; X=month, Y=DPD category và UPB USD separate scales; highlight missing intervals; unit/legend explicit.

## PHẦN 2 — Page 5 audit chi tiết

### Câu chuyện và thứ tự hiện tại

Page 5 đang kể: **(1)** rủi ro tích lũy theo thời gian; **(2)** vì sao CIF competing-risk khác `1−KM`; **(3)** biến nào liên hệ với hazard/subdistribution hazard; **(4)** kiểm định mô hình; **(5)** quy ước dữ liệu. Chuỗi này có logic phương pháp: outcome → competing risk → covariate association → diagnostics.

Trong 10–15 giây, người xem nên hiểu “PD tại horizon là CIF; trả trước là kết cục cạnh tranh; HR/SHR là liên hệ có điều kiện chứ không phải nhân quả”. Hiện thông điệp này bị chia: chart CIF lặp Overview, chart 1−KM/CIF có mật độ điểm không cân xứng, còn cảnh báo quan trọng nhất (Cox PH bị vi phạm) nằm trong expander Diagnostics. Vì vậy Page 5 trông như ghép chart, dù nội dung nền có một mạch hợp lý.

Release cụ thể cho thấy dữ liệu khác nhau về mật độ: overall PD có 4 dòng (12, 24, 36, 60); KM có 123 điểm theo thời gian; AJ có dữ liệu theo thời điểm. Chart CIF hiện lấy `overall_pd_horizons` 4 điểm, không lấy full AJ curve. Đây là nguyên nhân trực quan chính khiến các line nhìn “kỳ”: hai đại lượng có số điểm và cách biểu diễn khác nhau.

### 1) KPI Default CIF · 12/24/36/60 tháng

**1. Biểu đồ này đang thể hiện gì?** Xác suất tích lũy khoản vay đã xảy ra default đến các horizon định trước; Prepayment CIF là xác suất tích lũy kết cục ZBC 01.

**2. Dữ liệu đang được sử dụng**
- Dataset: `derived/overall_pd_horizons.parquet` qua `ds.get_pd_results(group="portfolio")`; prepayment tại horizon được `data_service.get_pd_results` lấy từ Aalen–Johansen endpoint PREPAYMENT, tại điểm cuối có `analysis_time <= horizon`.
- Variables: `horizon_months`, `default_cif`, AJ `cumulative_incidence` cho endpoint PREPAYMENT.
- Filters: `follow_up_eligible`; portfolio, mọi vintage gộp; horizons 12/24/36/60.
- Aggregation: không cần gộp trung bình trong bảng portfolio; một CIF step estimate cho mỗi horizon.
- Formula: AJ `F_k(t)=Σ_{u≤t} S(u−) d_k(u)/Y(u)`; chart nối các giá trị tại bốn t.
- Unit: xác suất tích lũy (0–1, hiển thị %), trên cohort phân tích.

**3. Cách đọc biểu đồ** X=horizon tháng; Y=CIF tích lũy; mỗi marker là ước lượng tại horizon đó, không phải hazard tháng đó.

**4. Insight thực sự có thể rút ra** Có thể mô tả CIF 12/24/36/60 trong mẫu, với prepayment là kết cục cạnh tranh. Không suy ra nguyên nhân hay xác suất cá nhân.

**5. Vấn đề phát hiện** Calculation không thấy lỗi trong đường dữ liệu; visualization: đường thẳng giữa horizon hàm ý nội suy không được tính; không có CI/at-risk; label Prepayment chưa phản ánh ZBC 01 “prepaid or matured”; cùng nội dung xuất hiện ở Overview.

**6. Đánh giá** **Giữ nhưng chỉnh sửa**: giữ KPI horizon vì đó là deliverable PD; giảm lặp bằng cách để Overview tóm tắt một horizon còn Page 5 so sánh method.

**7. Nếu chỉnh sửa** Chart type: point-range; X=horizon 12/24/36/60; Y=Default CIF; thêm Prepayment CIF ở panel phụ hoặc đường thứ hai; lấy CI từ full AJ đúng horizon và `n_at_risk`; filter follow-up eligible; title “Xác suất tích lũy default theo horizon”; tooltip: CIF, 95% CI, at-risk, N cohort; highlight mức tăng CIF giữa horizon là kết quả tính toán chứ không dự báo cá nhân.

### 2) “Tại sao không dùng 1 − KM?”

**1. Biểu đồ này đang thể hiện gì?** So sánh `1−S_KM(t)` với Default CIF AJ. KM mã hóa competing prepayment như censoring; AJ giữ prepayment là một competing outcome.

**2. Dữ liệu đang được sử dụng**
- Dataset: `models/km_results.parquet` (123 tháng) và `models/aalen_johansen_results.parquet`; dashboard chỉ dùng `survival_results` KM DEFAULT và `pd_results` 4 horizon.
- Variables: `analysis_time`, `survival`, `cif_default`, `n_at_risk`; CI có trong raw curves nhưng builder hiện không vẽ.
- Filters: endpoint DEFAULT; portfolio; horizon eligible; KM bị cắt tại horizon lớn nhất hiện có.
- Aggregation: tại bảng cạnh chart, lấy KM row lớn nhất với `analysis_time <= horizon`; CIF lấy row cố định horizon.
- Formula: `1−KM survival` so với AJ `F_DEFAULT(t)`.
- Unit: probability (%).

**3. Cách đọc biểu đồ** Đường xám là xác suất net-risk `1−KM` dưới quy ước censor prepayment; đường/điểm đỏ là xác suất CIF có competing event. Chênh lệch là khác estimand, không phải sai số giữa hai phép tính.

**4. Insight thực sự có thể rút ra** Nếu `1−KM > CIF`, việc bỏ competing-risk khỏi định nghĩa xác suất thực tế cho kết quả lớn hơn trong mẫu này. Không thể kết luận censoring độc lập/độc lập có điều kiện từ chart.

**5. Vấn đề phát hiện** 123 monthly points so với 4 horizon points làm nét vẽ không cân xứng; CIF line thẳng không phải step; CI không hiện; cần xác nhận hai đường dùng cùng eligibility/cohort và delayed-entry convention trước khi xem độ lệch là so sánh sạch. Code đang dùng KM & CIF cùng release, nhưng Page 5 không in cohort N/entry summary.

**6. Đánh giá** **Giữ nhưng chỉnh sửa** vì chart này dạy đúng khác biệt estimand; giữ thêm bảng horizon comparison.

**7. Nếu chỉnh sửa** Chart type: line-step cho `1−KM`, point-range/step AJ CIF cùng trục thời gian; X=analysis month; Y=probability; same portfolio eligible population; tooltip=CI, at-risk, event count; title “Hai cách ước lượng khác nhau khi có trả trước hạn”; note “đây không phải so sánh model accuracy”.

### 3) Forest plot hệ số mô hình

**1. Biểu đồ này đang thể hiện gì?** Ước lượng HR hoặc SHR và CI 95% cho mỗi covariate của model/end point đang chọn.

**2. Dữ liệu đang được sử dụng**
- Dataset: `cox_results`, `time_varying_cox_results`, `cause_specific_*_results`, `fine_gray_default_results` qua `risk_driver_results`.
- Variables: `variable/predictor`, HR hoặc SHR=`exp(coefficient)`, `ci_lower`, `ci_upper`, p-value.
- Filters: model dropdown; endpoint; hiện Page 5 tự lấy endpoint đầu tiên nếu có nhiều, sau đó mới cho radio; không có filter cohort bổ sung ngoài cohort complete-case của model.
- Aggregation: không aggregate; một điểm/hệ số mỗi predictor.
- Formula: hệ số β đổi thành HR/SHR=`exp(β)`; CI đổi từ hệ số bằng exponential ở pipeline.
- Unit: ratio; covariate unit khác nhau (FICO +1 điểm, LTV/DTI/rate +1 điểm phần trăm, term +1 tháng, UPB theo scale đầu vào; biến cờ 0→1).

**3. Cách đọc biểu đồ** Điểm bên phải 1 nghĩa liên hệ với hazard/subdistribution hazard cao hơn theo đơn vị biến; CI cắt 1 nghĩa chưa có bằng chứng khác 1 theo CI danh nghĩa.

**4. Insight thực sự có thể rút ra** Chỉ liên hệ có điều kiện theo model và scale. Không chứng minh tác động nhân quả, không trực tiếp là PD. Baseline Cox release có global PH p-values `7.0e−99` và `1.6e−88`, `ph_status=FLAGGED`; mặc định model Page5 là Cox PH. Do đó các HR không được mô tả như tỷ số không đổi theo thời gian.

**5. Vấn đề phát hiện** Trục không phải log-scale; HR lớn của delinquency 2-month trong TV Cox (khoảng 80 ở release đã rà) có thể ép các effect gần 1 sát vào nhau; đơn vị UPB khó đọc; PH warning bị giấu trong expander; kiểm định nhiều biến chưa điều chỉnh; chọn “Cause-specific Hazard” cần nêu endpoint để người dùng biết event nào.

**6. Đánh giá** **Giữ nhưng chỉnh sửa**: forest plot phù hợp coefficient+CI, nhưng encoding và model gate cần sửa.

**7. Nếu chỉnh sửa** Chart type: forest plot log-x; X=HR/SHR ratio trên thang log, reference line=1; Y=predictor, sort theo domain order hoặc magnitude; aggregation=none; filter=single model + explicit endpoint + model version; title chứa model/end point; tooltip ghi estimate, CI, p, unit, N/events, PH status; highlight CI/reference and PH warnings.

### 4) Diagnostics và methodology

Hiện không có chart trong Diagnostics/Methodology; có bảng text trong expander. Nên đưa trạng thái PH p-value thành banner cạnh Cox chart. Không cần vẽ p-value chart; một bảng diagnostic có status/threshold/method phù hợp hơn.

## PHẦN 3 — Page 5 đề xuất lại

Page 5 nên có **2 chart chính và 1 forest plot**, không cần bày cùng lúc cả curve CIF, curve comparison, rồi thêm bảng trùng lặp. Giữ câu chuyện: “rủi ro tích lũy → tác động của competing event → yếu tố liên quan và độ tin cậy mô hình”.

------------------------------------------------
### PAGE 5 — PD THEO THỜI GIAN & KIỂM ĐỊNH MÔ HÌNH

**KPI 1 | Default CIF 36 tháng** — estimate, CI 95%, cohort N  
**KPI 2 | Prepayment/ZBC 01 CIF 36 tháng** — tạm ghi “ZBC 01 (prepaid/matured)”  
**KPI 3 | Số at-risk ở 36 tháng**  
**KPI 4 | Cox PH diagnostic** — “Vi phạm”/“Không bị bác bỏ”; không dùng chữ “đạt” khi chỉ là p-value

**[CHART 1] CIF competing-risk theo thời gian**  
Tên: Default và ZBC 01 CIF theo tháng  
Mục đích: xác suất của mỗi kết cục tích lũy đến thời điểm t  
X: analysis month kể từ origination proxy  
Y: Aalen–Johansen CIF (0–1)  
Chart type: step line + 95% CI; hai endpoint cùng risk set  
Formula: `Σ S(u−) d_k(u)/Y(u)`; không nối tuyến tính giữa 12/24/36/60.

**[CHART 2] CIF so với 1−KM**  
Tên: Cách xử lý trả trước hạn làm thay đổi đại lượng nào?  
Mục đích: minh họa estimand actual-world CIF khác net-risk 1−KM  
X: analysis month  
Y: probability  
Chart type: line-step `1−KM` và AJ Default CIF point/step với CI; ghi rõ KM censor prepayment  
Filter: cùng portfolio/cohort, cùng time origin, hiện n-at-risk tại các mốc.

**[CHART 3] Forest plot theo mô hình và endpoint**  
Tên: Covariates liên hệ với Default [HR/SHR]  
Mục đích: association có điều kiện, không phải causal effect  
X: HR/SHR, log scale, line=1  
Y: biến, sắp xếp nhóm baseline/varying  
Filter: model, endpoint, version; CI/p/unit/events đi kèm.

**[INSIGHT / KEY TAKEAWAY]**  
“CIF là xác suất tích lũy phù hợp câu hỏi competing-risk; 1−KM trả lời đại lượng khác. Chỉ diễn giải hệ số Cox PH sau khi kiểm tra giả định; nếu PH bị bác bỏ, dùng mô hình cho phép thay đổi theo thời gian hoặc báo cáo mô hình thay thế.”
------------------------------------------------

**Bỏ/thay:** bỏ line chart CIF 4 điểm riêng nếu Chart 1 dùng full AJ curve; bỏ bảng lặp chênh lệch `1−KM−CIF` nếu tooltip/chart đã có mốc horizon; không lấy HR lớn nhất làm KPI “yếu tố mạnh nhất” vì scale khác nhau.

**Benchmark/reference:** đường HR/SHR=1 là bắt buộc; không đặt benchmark PD thị trường nếu không có nguồn đối sánh cùng cohort/định nghĩa. Ở chart CIF, không dùng line trung bình không trọng số của groups làm benchmark.

**Slicer nên có:** endpoint; model type; model version; horizon chỉ khi dùng điểm horizon cố định; vintage chỉ nếu mô hình/CIF được fit riêng vintage. Không dùng filter vintage từ portfolio bảng All.

## PHẦN 4 — Danh sách thay đổi cần thực hiện

### CRITICAL

- `app/pages/overview.py`: nguồn vintage hiện là `pd_raw` với portfolio accessor gắn `vintage="All"`; chart vintage/selection không được cấp dữ liệu vintage thật. Nối `ds.get_vintage_results()` và dùng `default_cif`, `follow_up_eligible`; không giả lập lọc vintage từ overall CIF.
- `app/pages/portfolio_risk.py`: heatmap không đặt `zmin/zmax`; màu tự scale theo data range hiện hành. Chốt domain màu và biểu diễn NA rõ để không thổi phồng khác biệt.
- `app/pages/portfolio_risk.py`: bỏ/xem lại chart max/min ratio. Min CIF gần 0 làm ratio nổ; không nên xếp “đặc điểm phân biệt rủi ro” bằng ratio thuần. Dùng chênh lệch tuyệt đối và uncertainty hoặc adjusted model.
- `app/pages/model_insights.py`: hiển thị Cox PH FLAGGED ngay cạnh forest plot và cảnh báo không diễn giải HR bất biến theo thời gian; hiện diagnostic có thể chỉ thấy nếu người dùng mở expander.
- `app/pages/model_insights.py` + `app/components/charts.py`: không nối bốn CIF horizon bằng line thường như một continuous fitted curve; dùng full AJ step curve có CI hoặc point-range tại mốc báo cáo.
- Chuẩn hóa nhãn ZBC 01: code hiện coi mọi ZBC 01 là `PREPAYMENT`; Freddie Mac guide mô tả code này là “Prepaid or Matured”. Trước khi khẳng định voluntary prepayment, cần phân biệt matured bằng maturity date hoặc đổi label/định nghĩa outcome. Không có cột raw đủ chứng minh phân biệt chính xác sau khi gộp.

### IMPORTANT

- `app/components/charts.py:forest_plot`: dùng log x-axis cho HR/SHR; ghi rõ unit per predictor; cân nhắc rescale `lag_current_actual_upb` (ví dụ theo $10,000) từ trước khi fit và lưu scale vào metadata.
- `app/pages/portfolio_risk.py`: thêm CI/n-at-risk cho bar/horizon; legend màu rủi ro chỉ là quy ước relative-to-portfolio 0.8/1.25, không phải ngưỡng tín dụng đã hiệu chuẩn.
- `app/pages/portfolio_risk.py`: vintage lines chỉ nối các điểm đủ seasoning; thêm N/CI; không diễn giải năm vintage là nguyên nhân.
- `app/pages/overview.py`: nếu giữ KM, thêm CI và at-risk; chú thích `1−KM` không phải Default CIF khi prepayment competing.
- `app/pages/loan_explorer.py` + `app/components/charts.py`: nếu muốn timeline có analytical value, vẽ delinquency/status theo tháng và UPB ở panel riêng; đánh dấu khoảng thiếu tháng; chart thanh hiện chỉ thể hiện thời gian + kết cục, không thể hiện nội dung performance.
- Toàn dashboard: cùng gọi ZBC 01 “prepayment” trên page1/2/4/5 dù source includes maturity; chốt định nghĩa/nhãn đồng nhất.

### OPTIONAL

- Bỏ dots infographic ở Overview (trùng CIF); thay bằng metric + CI.
- Dùng fixed/common sequential color scale cho heatmap và thân thiện với mù màu.
- Rút gọn Page 5 còn 3 chart như layout trên; chuyển diagnostics đầy đủ vào bảng nhưng đưa cảnh báo trọng yếu ra ngoài expander.
- Thêm tooltip gồm numerator events, cohort N, at-risk N, follow-up eligibility, CI, data cutoff.
- Xem lại tỷ lệ chart lặp: Overview, Portfolio Risk và Page 5 đều có Default CIF; phân vai rõ: Overview = 36-month headline, Page 2 = subgroup/vintage, Page 5 = method comparison + model association.

## Tính nhất quán toàn dashboard

1. **Flow hiện tại:** Overview → Rủi ro danh mục → Yếu tố rủi ro → Tra cứu khoản vay → Kết quả mô hình. Đây là flow nghiên cứu hợp lý hơn “financial/operational performance”: project không có EAD/LGD/ECL đầy đủ và không phải dashboard vận hành ngân hàng. Tuy nhiên Page 5 “Kết quả mô hình” nên đặt trước loan explorer nếu muốn flow nghiên cứu → giải thích cá nhân; nếu Page 4 là tra cứu demo thì vị trí hiện tại chấp nhận được.
2. **Metric:** CIF là probability; HR/SHR là ratio; count là loans/events; UPB là USD. Một số labels “tỷ lệ” không nói rõ cumulative horizon, và các trang chưa nhất quán trong gọi Prepayment/ZBC 01.
3. **Thời gian:** cutoff 31/03/2026 và first-payment-minus-one-month proxy phải xuất hiện nhất quán. Không gọi như actual origination date. Theo Freddie Mac, performance bắt đầu từ loan acquisition, không luôn từ origination; khoảng trước acquisition không có monthly performance. Vì vậy survival trước thời điểm bắt đầu được quan sát không thể khôi phục chỉ bằng chart.
4. **Filters:** Overview vintage filter đang không khớp accessor production `All`; trang grouped risk lọc FICO/LTV/DTI và horizon thật. Page 5 model selector đổi model nhưng cohort/model sample N không nổi bật. Loan Explorer filter áp dụng catalog mẫu, không phải toàn bộ loans.
5. **Redundancy:** Overview bar CIF, Page 2 baseline/vintage, Page 5 CIF và comparison đều nhắc default risk. Nên định vai rõ như mục Optional.
6. **Insight vs fact:** số loan, event count là fact đếm trong file; CIF/HR/SHR là estimate; màu cao/thấp, “nhóm rủi ro nhất”, trend giữa vintages là diễn giải mô tả; nguyên nhân/causality không được chart chứng minh.

## Căn cứ nguồn

- Freddie Mac General User Guide — định nghĩa dataset, kỳ performance và Zero Balance Code 01 (`Prepaid or Matured`): [Freddie Mac User Guide](https://www.freddiemac.com/fmac-resources/research/pdf/user_guide.pdf).
- Aalen–Johansen cumulative incidence framework: [Aalen & Johansen (1978), Annals of Statistics](https://projecteuclid.org/journals/annals-of-statistics/volume-6/issue-3/Nonparametric-Estimation-of-Partial-Transition-Probabilities-in-Multiple/10.1214/aos/1176344247.full).
- Fine–Gray subdistribution hazards: [Fine & Gray (1999), JASA](https://www.tandfonline.com/doi/abs/10.1080/01621459.1999.10474144).

## Giới hạn audit

Code và production release đã kiểm tra trực tiếp. Không có raw population panel kèm mọi lần chạy mô hình/BI context để tính độc lập lại từng điểm trên từng chart; release validation PASS là kiểm tra chất lượng artifact, không phải benchmark external validation. Chưa đưa ra con số/insight ngoài các trường hiện có. Đặc biệt, không thể phân loại tất cả ZBC 01 thành voluntary prepayment chỉ từ cột code vì source definition gộp payoff và maturity.
