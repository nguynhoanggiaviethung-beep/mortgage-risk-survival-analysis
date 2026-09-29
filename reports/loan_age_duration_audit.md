# Freddie Mac Loan Age / Survival Duration Audit

Primary survival clock uses an operational origination-month proxy (First Payment Month minus one calendar month) as a fixed origin.

`duration_months = event_month - operational_origination_month_proxy` on a calendar-month scale; the first payment month is month 1.

The Freddie Mac Loan Age field is retained for audit but is not used as the primary survival clock because its calculation can reset after loan modification.

| Year | Loans | Duration <0 | Duration =0 | Duration =1 | Min | Median | Max | Event before FP | Unmodified age mismatch | Modified loans | Event after last report |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2016 | 50,000 | 0 | 18 | 42 | 0 | 55.0 | 122 | 18 | 478 | 500 | 24 |
| 2017 | 50,000 | 1 | 27 | 70 | -1 | 42.0 | 110 | 28 | 567 | 629 | 28 |
| 2018 | 50,000 | 1 | 44 | 80 | -1 | 28.0 | 98 | 45 | 363 | 544 | 22 |
| 2019 | 50,000 | 0 | 30 | 81 | 0 | 22.0 | 86 | 30 | 484 | 405 | 35 |
| 2020 | 50,000 | 0 | 18 | 69 | 0 | 63.0 | 74 | 18 | 722 | 179 | 52 |
| 2021 | 50,000 | 2 | 20 | 79 | -1 | 54.0 | 62 | 22 | 909 | 249 | 65 |
| 2022 | 50,000 | 5 | 53 | 100 | -1 | 42.0 | 50 | 58 | 1,680 | 560 | 92 |
| 2023 | 50,000 | 2 | 72 | 153 | -1 | 30.0 | 38 | 74 | 3,988 | 283 | 214 |
| 2024 | 50,000 | 3 | 80 | 171 | -1 | 18.0 | 26 | 83 | 4,548 | 87 | 221 |
| 2025 | 49,994 | 3 | 66 | 226 | -1 | 7.0 | 14 | 69 | 3,053 | 0 | 178 |
| 2026 | 12,495 | 0 | 6,351 | 6,094 | 0 | 0.0 | 2 | 6,351 | 10 | 0 | 0 |