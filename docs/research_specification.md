# Research Specification

## 1. Research Topic

Các đặc điểm tín dụng và đặc điểm khoản vay ảnh hưởng như thế nào đến
thời điểm xảy ra default và xác suất default tích lũy theo thời gian
của khoản vay thế chấp, trong bối cảnh voluntary prepayment là một
competing event?

---

## 2. Research Objectives

### Objective 1 — Determinants of Default Hazard
Phân tích mối liên hệ giữa các đặc điểm tín dụng và đặc điểm khoản vay
với default hazard theo thời gian.

Các đặc điểm chính:
- Credit Score
- LTV
- DTI
- Interest Rate
- Loan Term

Phương pháp chính:
- Cox Proportional Hazards
- Time-varying Cox khi phù hợp với dữ liệu và thiết kế nghiên cứu

### Objective 2 — Default Risk over Loan Life
Ước lượng cumulative probability of default theo thời gian kể từ
origination.

Các horizon chính:
- 12 months
- 24 months
- 36 months
- 60 months nếu đủ follow-up

### Objective 3 — Competing Risks
Đánh giá sự khác biệt trong ước lượng cumulative default incidence
khi voluntary prepayment được xử lý như một competing event.

Phương pháp:
- Kaplan–Meier
- Aalen–Johansen / Cumulative Incidence Function
- Cause-specific hazard
- Fine–Gray model

### Objective 4 — Mortgage Vintages
Phân tích sự khác biệt về default risk giữa các origination vintages
trong phạm vi dữ liệu nghiên cứu.

---

## 3. Research Questions

### Main RQ

Các đặc điểm tín dụng và đặc điểm khoản vay ảnh hưởng như thế nào
đến rủi ro vỡ nợ theo thời gian của các khoản vay thế chấp, và rủi ro
này thay đổi như thế nào trong suốt vòng đời khoản vay?

### RQ1 — Determinants of Default

Các đặc điểm Credit Score, LTV, DTI, Interest Rate và Loan Term có
liên quan như thế nào đến default hazard?

### RQ2 — Default Risk over Loan Life

Cumulative probability of default thay đổi như thế nào theo thời gian
kể từ origination?

### RQ3 — Competing Risks

Việc xem voluntary prepayment là một competing event ảnh hưởng như thế
nào đến cumulative default incidence so với Kaplan–Meier?

### RQ4 — Mortgage Vintages

Default risk có khác biệt giữa các origination vintages hay không?

---

## 4. Hypotheses

### H1a
Credit Score cao hơn có liên quan đến default hazard thấp hơn.

### H1b
LTV cao hơn có liên quan đến default hazard cao hơn.

### H1c
DTI cao hơn có liên quan đến default hazard cao hơn.

### H1d
Interest Rate cao hơn có liên quan đến default hazard cao hơn.

### H1e
Loan Term có liên quan đến default hazard.

### H2
Default hazard và cumulative probability of default thay đổi theo
loan age.

### H3
Việc xử lý voluntary prepayment như một competing event làm thay đổi
cumulative default incidence so với Kaplan–Meier.

### H4
Default hazard khác nhau giữa các mortgage origination vintages.

---

## 5. Data Scope

### Dataset

Freddie Mac 2016–2026 Sample Dataset.

### Performance Cutoff

31/03/2026.

### Time Origin

Origination Month. The Freddie Mac extract used by this project provides First
Payment Date but no direct origination date. We therefore define
`operational_origination_date` as the explicit proxy `First Payment Date - 1
calendar month`. Analysis time is the calendar-month difference from this proxy;
the first payment month is analysis month 1. Under this proxy, the calculation
is numerically equivalent to `performance_month - first_payment_month + 1`.
`freddie_loan_age` remains a separate source variable and is not substituted for
the study clock.

### Unit of Analysis

Loan-month.

### Time-Varying Cox Covariates

The time-varying default model uses the prior observed month's actual UPB,
interest rate, and mutually exclusive indicators for 1-month and 2-month
delinquency. The outcome is first 90+ DPD. The 90+ status in the terminal
event month is excluded from the predictors to prevent target leakage; as a
result, a 3+-month delinquency indicator has no variation in eligible
pre-event intervals and is not included in the model.

### Event Definition

Ba trạng thái phân tích chính:

1. Default
2. Voluntary Prepayment
3. Censored

### Horizon

12M, 24M, 36M.

60M chỉ được báo cáo khi khoản vay/cohort có đủ follow-up.

### PD(t)

PD(t) được định nghĩa trong nghiên cứu là:

> Cumulative default incidence at time t.

PD(t) được sử dụng như một thước đo cumulative default risk phục vụ
phân tích tín dụng.

Nghiên cứu không tuyên bố hệ thống tính đầy đủ IFRS 9 ECL.

---

## 6. Interpretation Scope

Các kết quả thực nghiệm được diễn giải theo hướng association.

Nghiên cứu không đưa ra kết luận causal effect nếu thiết kế và phương
pháp không hỗ trợ kết luận nhân quả.

PD(t) là cumulative default-risk measure trong phạm vi nghiên cứu,
không phải một hệ thống ECL hoàn chỉnh.
