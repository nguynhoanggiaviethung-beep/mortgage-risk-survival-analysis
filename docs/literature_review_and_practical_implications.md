# Tổng quan nghiên cứu và hàm ý thực tiễn

## 1. Phạm vi

Tài liệu này bổ sung phần nền tảng để thuyết minh nghiên cứu về thời điểm
vỡ nợ thế chấp, CIF và rủi ro cạnh tranh. Các bài báo dưới đây không phải
bằng chứng rằng kết quả của mẫu Freddie Mac 2016–2026 sẽ lặp lại ở một ngân
hàng, thị trường hoặc giai đoạn khác. Chúng giúp đặt câu hỏi và phương pháp
vào bối cảnh học thuật; kết luận thực nghiệm vẫn chỉ dựa trên dữ liệu của dự án.

## 2. Năm dòng nghiên cứu liên quan

| Nghiên cứu | Câu hỏi và phương pháp | Kết quả / đóng góp liên quan | Liên hệ và giới hạn khi áp dụng vào dự án |
|---|---|---|---|
| Deng, Quigley & Van Order (1996), *Mortgage Default and Low Downpayment Loans: The Costs of Public Subsidy*, *Regional Science and Urban Economics*, 26(3–4), 263–285. [DOI](https://doi.org/10.1016/0166-0462(95)02116-7) | Mô hình hazard cho default và prepayment như hai nguy cơ kết thúc cạnh tranh, có xét lựa chọn của chủ nhà. | LTV ban đầu, biến động vốn chủ sở hữu và một số biến cố kinh tế liên quan đến default/prepayment trong mẫu nghiên cứu. | Củng cố việc mô hình hóa hai kết cục theo thời gian. Dự án hiện không có chuỗi equity/property value và không suy ra quan hệ nhân quả từ Cox/Fine–Gray. |
| Haughwout, Peach & Tracy (2008), *Juvenile Delinquent Mortgages: Bad Credit or Bad Economy?*, *Journal of Urban Economics*, 64(2), 246–257. [DOI](https://doi.org/10.1016/j.jue.2008.07.008) | Phân tích nợ quá hạn sớm của mortgage nonprime theo vintage 2001–2007; đối chiếu tiêu chuẩn cấp tín dụng và điều kiện kinh tế. | Bài báo cho thấy điều kiện kinh tế, đặc biệt đảo chiều tăng giá nhà sau 2004, có vai trò quan trọng trong mức tăng default được nghiên cứu; kết quả phụ thuộc bối cảnh và nhóm khoản vay. | Gợi ý không diễn giải vintage như nguyên nhân tự thân. Dashboard Freddie Mac 2016–2026 không chứa vintage 2008 và không có đầy đủ giá nhà/thất nghiệp; không thể tái kiểm định kết luận về khủng hoảng từ dữ liệu này. |
| An & Qi (2012), *Competing Risks Models Using Mortgage Duration Data under the Proportional Hazards Assumption*, *Journal of Real Estate Research*, 34(1), 1–26. [DOI](https://doi.org/10.1080/10835547.2012.12091323) | Xem xét mô hình proportional hazards với dữ liệu thời lượng mortgage được nhóm theo kỳ. | Chỉ ra rằng baseline phi tham số có thể không nhận dạng được với dữ liệu duration grouped nếu thiếu giả định bổ sung; lựa chọn dạng baseline ảnh hưởng suy luận. | Nhắc nhóm cần nêu rõ thang thời gian tháng, baseline, giả định và chẩn đoán PH; không chỉ trình bày HR như kết luận ổn định theo thời gian. |
| Bhattacharya, Wilson & Soyer (2019), *A Bayesian Approach to Modeling Mortgage Default and Prepayment*, *European Journal of Operational Research*, 274(3), 1112–1124. [DOI](https://doi.org/10.1016/j.ejor.2018.10.047) | Mô hình competing-risk proportional hazards theo Bayesian cho default/prepayment trên dữ liệu loan-level. | Nhấn mạnh tác động biến có thể khác giữa default và prepayment; bàn về mất cân bằng sự kiện và bất định tham số. | Hỗ trợ trình bày CIF hai kết cục tách biệt và kèm độ bất định. Dự án không dùng Bayesian model; không tuyên bố tái tạo các kết quả paper. |
| Fine & Gray (1999), *A Proportional Hazards Model for the Subdistribution of a Competing Risk*, *Journal of the American Statistical Association*, 94(446), 496–509. [DOI](https://doi.org/10.1080/01621459.1999.10474144) | Đề xuất regression cho subdistribution hazard trong competing risks. | Cho phép gắn covariates với cumulative incidence; SHR là thước đo subdistribution hazard, không phải xác suất trực tiếp hay cause-specific HR. | Là căn cứ cho Fine–Gray trong trang yếu tố rủi ro. Diễn giải vẫn là association có điều kiện, phải nêu endpoint và giả định proportional subdistribution hazards. |
| Aalen & Johansen (1978), *Nonparametric Estimation of Partial Transition Probabilities in Multiple Decrement Models*, *Annals of Statistics*, 6(3), 534–545. [DOI](https://doi.org/10.1214/aos/1176344198) | Ước lượng xác suất chuyển trạng thái/biến cố trong mô hình nhiều nguyên nhân. | Nền tảng phi tham số cho cumulative incidence khi có nhiều loại event. | Hỗ trợ dùng Aalen–Johansen thay cho việc diễn giải 1−KM như xác suất default thực tế khi có competing event. |

## 3. Tổng hợp và khoảng trống của dự án

Các nghiên cứu mortgage duration nhất quán ở ba điểm có ích cho thiết kế:

1. **Thời điểm quan trọng:** hai khoản vay có thể cùng trạng thái cuối nhưng
   khác thời gian đến event; phân tích time-to-event tận dụng được thời gian
   kiểm duyệt thay vì gộp mọi quan sát thành “default / không default”.
2. **Kết cục cạnh tranh quan trọng:** kết thúc do default và kết thúc bằng
   ZBC 01 loại khoản vay khỏi risk set theo những cơ chế khác nhau. CIF trả lời
   xác suất tích lũy quan sát được trong môi trường có competing events; KM khi
   kiểm duyệt event cạnh tranh trả lời một đại lượng khác.
3. **Mối liên hệ không đồng nghĩa nguyên nhân:** FICO, LTV, DTI, lãi suất,
   kỳ hạn và vintage có thể liên hệ với kết cục, nhưng quan hệ quan sát có thể
   chịu ảnh hưởng của lựa chọn cấp tín dụng, biến kinh tế và đặc điểm thiếu
   trong dữ liệu.

**Khoảng trống mà dự án xử lý:** minh họa phân tích loan-level Freddie Mac
2016–2026 theo tháng, với định nghĩa event rõ, Aalen–Johansen, so sánh vintage
ở cùng tuổi theo dõi và mô hình association. Đây là nghiên cứu ứng dụng/giáo
dục; không phải mô hình được kiểm định ngoài mẫu thị trường, mô hình ra quyết
định cấp tín dụng hay ước lượng tổn thất IFRS 9.

## 4. Hàm ý cho ngân hàng và nhà đầu tư

### Ngân hàng / bên quản lý khoản vay

- Dùng FICO, LTV, DTI, lãi suất và kỳ hạn như **chỉ báo cần theo dõi** cùng
   lịch sử trả nợ; không dùng một hệ số đơn lẻ làm quy tắc từ chối/phê duyệt.
- Theo dõi vintage ở cùng horizon và hiển thị số khoản còn at-risk, event count
  cùng CI; một khác biệt CIF mô tả không tự xác lập nguyên nhân.
- Tách monitoring portfolio khỏi mô hình ở cấp hồ sơ: CIF toàn danh mục không
  phải PD cá nhân. Mọi triển khai cần hiệu chỉnh xác suất, kiểm định theo thời
  gian, giám sát drift và phê duyệt quản trị mô hình.
- Không suy ra expected loss từ CIF một mình. Cần tối thiểu EAD, LGD/recovery,
  dòng tiền/chiết khấu và khung kịch bản phù hợp; các đầu vào này không tạo
  thành một mô hình ECL hoàn chỉnh trong dự án.

### Nhà đầu tư / người quản lý danh mục

- Xem default và tất toán ZBC 01 như các lối ra khác nhau vì chúng làm thay
  đổi thời gian nắm giữ và dòng tiền; ZBC 01 ở nguồn này gộp prepaid/matured.
- So sánh các cohort tại cùng tuổi khoản vay và đọc cả bất định, cỡ nhóm, tỷ
  lệ còn theo dõi. Không xếp hạng portfolio chỉ bằng count thô hoặc một
  horizon không đồng đều.
- Dùng kết quả như một lớp sàng lọc/phân tích, không thay cho đánh giá cấu
  trúc MBS, thanh khoản, lãi suất, giá nhà hoặc tổn thất thực tế.

## 5. Bài học từ khủng hoảng 2008 và giới hạn so sánh

Financial Crisis Inquiry Commission kết luận khủng hoảng có thể tránh được và
nêu các thất bại rộng hơn về giám sát, quản trị doanh nghiệp, vay nợ/risk-taking
quá mức và mức độ chuẩn bị của nhà hoạch định chính sách. [Kết luận FCIC](https://fcic.law.stanford.edu/report/conclusions).
Tài liệu của Federal Reserve về bất ổn tài chính 2008 cũng ghi nhận thiếu sót
trong thực hành quản trị rủi ro, due diligence của nhà đầu tư và các mắt xích
underwriting/ratings trong mô hình originate-to-distribute. [Federal Reserve](https://www.federalreserve.gov/newsevents/speech/bernanke20080410a.htm).

Các bài học có thể đưa vào phần thảo luận:

1. Không dựa vào một điểm tín dụng hoặc một tỷ lệ cấp vốn; xem xét kết hợp
   đặc điểm khoản vay và bối cảnh kinh tế.
2. Theo dõi chất lượng cấp tín dụng và performance theo vintage, kể cả khi
   chỉ số danh mục hiện thời còn có vẻ tốt.
3. Kiểm tra giả định mô hình, tính đầy đủ của dữ liệu, concentration và các
   kịch bản bất lợi; điểm số/ratings không thay thế due diligence.
4. Giữ trách nhiệm giải trình dọc theo chuỗi cấp tín dụng, phân phối và nắm
   giữ khoản vay.

**Giới hạn quan trọng:** mẫu dự án bắt đầu từ vintage 2016 và không bao gồm
khủng hoảng 2008. Do đó, 2008 là bối cảnh lịch sử và nguồn bài học quản trị,
không phải giai đoạn mà kết quả dự án đã kiểm định. Các đặc điểm Freddie Mac
trong mẫu này cũng không đại diện cho toàn bộ thị trường subprime/non-agency
đã góp phần vào khủng hoảng.

## 6. Quy ước dữ liệu cần nói khi bảo vệ

- Freddie Mac ghi ZBC 01 là **“Prepaid or Matured (Voluntary Payoff)”**; trường
  nguồn gộp hai kết cục này. Dùng nhãn dashboard “ZBC 01 (trả trước/đáo hạn,
  gộp)”, không khẳng định quan sát được voluntary prepayment thuần túy.
- Freddie Mac monthly performance bắt đầu từ lúc khoản vay được Freddie Mac
  mua/nhận, không bao phủ đầy đủ giai đoạn từ ngày origination đến acquisition.
  Dự án dùng First Payment Date trừ một tháng làm proxy origin; cần nêu đây là
  quy ước vận hành, không phải origination date quan sát trực tiếp.
- Các kết quả CIF/HR/SHR là ước lượng trong mẫu. Chúng không chứng minh nhân
  quả, không phải individual PD đã hiệu chuẩn và không phải ECL.
- Data cutoff là 31/03/2026; các vintage mới có follow-up ngắn hơn.

## 7. Tài liệu tham khảo bổ sung

- Qi, M. & Yang, X. (2009). *Loss Given Default of High Loan-to-Value Residential Mortgages*. *Journal of Banking & Finance*, 33(5), 788–799. [DOI](https://doi.org/10.1016/j.jbankfin.2008.09.010). Dùng để giải thích vì sao PD không đủ để kết luận tổn thất; LGD chịu ảnh hưởng của tài sản và quy trình xử lý.
- Financial Crisis Inquiry Commission (2011). *The Financial Crisis Inquiry Report*. [Trang báo cáo và các chương](https://fcic.law.stanford.edu/report).
- Freddie Mac. *Single-Family Loan-Level Dataset General User Guide*. [Hướng dẫn dữ liệu](https://www.freddiemac.com/fmac-resources/research/pdf/user_guide.pdf).
