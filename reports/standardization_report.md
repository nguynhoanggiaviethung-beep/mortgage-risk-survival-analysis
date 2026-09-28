# Báo cáo chuẩn hóa Origination và Performance

Phạm vi: chuẩn hóa nguồn; chưa lọc cohort mô hình, chưa gán event và chưa ghép panel.

Origination: 512,500 dòng.
Performance: 20,097,384 dòng.
Loại sau cutoff: 0 dòng.

Kiểm tra khóa, thứ tự và coverage đã qua. Các cờ qc_ vẫn cần xem xét; không đồng nghĩa toàn bộ model-input QC đã hoàn tất.

Lãi suất/LTV/DTI giữ đơn vị phần trăm của nguồn; UPB là USD; kỳ hạn và tuổi báo cáo là tháng.
Ngày đầu tháng biểu diễn tháng dữ liệu. Không điền mean/median và không loại complete-case ở bước này.

## Origination

Cờ cần xem lại: `{'qc_credit_score_out_of_range': 0, 'qc_dti_out_of_range': 0, 'qc_proxy_year_differs_from_vintage': 39266, 'qc_original_upb_nonpositive': 0, 'qc_original_term_nonpositive': 0}`

| Biến | Kiểu dữ liệu | Số null |
|---|---|---:|
| loan_id | large_string | 0 |
| fico_raw | large_string | 0 |
| first_payment_date | date32[day] | 0 |
| maturity_date | date32[day] | 0 |
| original_cltv_raw | large_string | 0 |
| original_dti_raw | large_string | 0 |
| original_upb | double | 0 |
| original_ltv_raw | large_string | 0 |
| original_interest_rate | double | 0 |
| occupancy_status_raw | large_string | 0 |
| amortization_type | large_string | 0 |
| property_state | large_string | 0 |
| property_type_raw | large_string | 0 |
| loan_purpose_raw | large_string | 0 |
| original_loan_term | int16 | 0 |
| number_borrowers_raw | large_string | 0 |
| vantagescore_4_raw | large_string | 0 |
| vintage_year | int16 | 0 |
| fico_not_available_flag | bool | 0 |
| fico | int16 | 121 |
| dti_not_available_flag | bool | 0 |
| original_dti | double | 4,892 |
| ltv_not_available_flag | bool | 0 |
| original_ltv | double | 1 |
| cltv_not_available_flag | bool | 0 |
| original_cltv | double | 2 |
| vantagescore_not_available_flag | bool | 0 |
| vantagescore_4 | int16 | 512,499 |
| number_borrowers_not_available_flag | bool | 0 |
| origination_quarter | int8 | 0 |
| occupancy_status | large_string | 0 |
| property_type | large_string | 0 |
| loan_purpose | large_string | 0 |
| first_payment_month | date32[day] | 0 |
| maturity_month | date32[day] | 0 |
| ltv_above_100_flag | bool | 0 |
| cltv_above_100_flag | bool | 0 |
| legacy_number_borrowers_encoding_flag | bool | 0 |
| multiple_borrowers_flag | bool | 0 |
| number_borrowers | int16 | 54,162 |
| first_payment_date_raw | large_string | 0 |
| maturity_date_raw | large_string | 0 |
| qc_credit_score_out_of_range | bool | 0 |
| qc_dti_out_of_range | bool | 0 |
| credit_score | int16 | 121 |
| origination_vintage | int16 | 0 |
| operational_origination_date | date32[day] | 0 |
| operational_origination_year | int32 | 0 |
| qc_proxy_year_differs_from_vintage | bool | 0 |
| qc_original_upb_nonpositive | bool | 0 |
| qc_original_term_nonpositive | bool | 0 |

## Performance

Cờ cần xem lại: `{'qc_current_upb_negative': 0}`

| Biến | Kiểu dữ liệu | Số null |
|---|---|---:|
| loan_id | large_string | 0 |
| monthly_reporting_period | large_string | 0 |
| current_actual_upb | double | 0 |
| delinquency_status_raw | large_string | 0 |
| loan_age | int16 | 0 |
| remaining_months_maturity | int16 | 45 |
| modification_flag | large_string | 20,002,398 |
| zero_balance_code | large_string | 19,882,275 |
| zero_balance_effective_date | date32[day] | 19,882,276 |
| current_interest_rate | double | 0 |
| ddlpi | large_string | 19,897,540 |
| payment_deferral_flag | large_string | 19,814,879 |
| estimated_ltv_raw | large_string | 0 |
| delinquency_due_to_disaster | large_string | 19,969,234 |
| borrower_assistance_plan | large_string | 19,944,630 |
| current_interest_bearing_upb | double | 0 |
| vintage_year | int16 | 0 |
| reporting_period_num | int32 | 0 |
| reporting_month | date32[day] | 0 |
| delinquency_num | int16 | 26,992 |
| is_xx | bool | 0 |
| is_ra | bool | 0 |
| estimated_ltv_not_available_flag | bool | 0 |
| estimated_ltv | double | 2,305,476 |
| zero_balance_effective_month | date32[day] | 19,882,276 |
| ddlpi_month | date32[day] | 19,897,540 |
| is_loan_age_zero | bool | 0 |
| estimated_ltv_pre_201704_flag | bool | 0 |
| has_zero_balance_event | bool | 0 |
| zero_balance_effective_date_raw | large_string | 19,882,276 |
| performance_month | date32[day] | 0 |
| freddie_loan_age | int16 | 0 |
| current_delinquency_status | large_string | 0 |
| qc_current_upb_negative | bool | 0 |