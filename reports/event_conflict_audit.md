# Freddie Mac Event Conflict Audit

This report is an audit only. No final Default, Prepayment, or Censoring definition has been applied yet.

## Event candidates by vintage

| Year | 90+ DPD | RA | ZB 02/03/09 | Any default evidence | Prepay candidate | Maturity | Ambiguous 01 | Admin 15/16/96 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2016 | 2,366 | 30 | 76 | 2,367 | 35,734 | 0 | 0 | 152 |
| 2017 | 2,916 | 38 | 76 | 2,916 | 37,311 | 0 | 0 | 243 |
| 2018 | 2,708 | 20 | 53 | 2,708 | 39,830 | 0 | 0 | 194 |
| 2019 | 2,786 | 16 | 36 | 2,786 | 35,551 | 0 | 0 | 167 |
| 2020 | 1,128 | 14 | 20 | 1,128 | 19,385 | 0 | 0 | 158 |
| 2021 | 1,004 | 9 | 17 | 1,004 | 9,583 | 0 | 0 | 130 |
| 2022 | 1,747 | 42 | 50 | 1,747 | 9,657 | 0 | 0 | 273 |
| 2023 | 1,213 | 56 | 48 | 1,214 | 12,990 | 0 | 0 | 213 |
| 2024 | 615 | 12 | 10 | 615 | 9,177 | 0 | 0 | 194 |
| 2025 | 71 | 2 | 0 | 71 | 3,701 | 0 | 0 | 67 |
| 2026 | 0 | 0 | 0 | 0 | 13 | 0 | 0 | 0 |

## Default / Prepayment conflicts

| Year | Both exist | Default before prepay | Same month | Prepay before default |
|---:|---:|---:|---:|---:|
| 2016 | 1,100 | 1,079 | 21 | 0 |
| 2017 | 1,393 | 1,383 | 10 | 0 |
| 2018 | 1,330 | 1,327 | 3 | 0 |
| 2019 | 1,337 | 1,337 | 0 | 0 |
| 2020 | 385 | 385 | 0 | 0 |
| 2021 | 151 | 151 | 0 | 0 |
| 2022 | 225 | 225 | 0 | 0 |
| 2023 | 125 | 125 | 0 | 0 |
| 2024 | 49 | 49 | 0 | 0 |
| 2025 | 1 | 1 | 0 | 0 |
| 2026 | 0 | 0 | 0 | 0 |

## Zero Balance Code 01 classification

| Year | Classification | Rows | Loans |
|---:|:---|---:|---:|
| 2016 | PREPAY_REMAINING_MATURITY | 35,734 | 35,734 |
| 2017 | PREPAY_REMAINING_MATURITY | 37,311 | 37,311 |
| 2018 | PREPAY_REMAINING_MATURITY | 39,830 | 39,830 |
| 2019 | PREPAY_REMAINING_MATURITY | 35,551 | 35,551 |
| 2020 | PREPAY_REMAINING_MATURITY | 19,385 | 19,385 |
| 2021 | PREPAY_REMAINING_MATURITY | 9,583 | 9,583 |
| 2022 | PREPAY_REMAINING_MATURITY | 9,657 | 9,657 |
| 2023 | PREPAY_REMAINING_MATURITY | 12,990 | 12,990 |
| 2024 | PREPAY_REMAINING_MATURITY | 9,177 | 9,177 |
| 2025 | PREPAY_FALLBACK_MATURITY_DATE | 35 | 35 |
| 2025 | PREPAY_REMAINING_MATURITY | 3,666 | 3,666 |
| 2026 | PREPAY_FALLBACK_MATURITY_DATE | 6 | 6 |
| 2026 | PREPAY_REMAINING_MATURITY | 7 | 7 |

## Interpretation rule

- 90+ DPD, RA, and Zero Balance 02/03/09 are audited as potential default evidence.
- Zero Balance 01 is separated into prepayment, maturity, or ambiguous cases.
- Zero Balance 15/16/96 are audited separately and are not automatically treated as borrower default.
- Same-month Default/Prepayment conflicts must be reviewed before final event precedence is locked.