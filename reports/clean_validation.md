# Freddie Mac Clean Data Validation

This report validates the cleaned Origination and Monthly Performance Parquet files used by the modelling pipeline.

| Year | Orig row match | Perf row match | Schema | Invalid first payment | Invalid maturity | Maturity < first payment | Negative loan age | Cleaning violations | Status |
|---:|:---:|:---:|:---:|---:|---:|---:|---:|---:|:---:|
| 2016 | PASS | PASS | PASS | 0 | 0 | 0 | 0 | 0 | PASS |
| 2017 | PASS | PASS | PASS | 0 | 0 | 0 | 0 | 0 | PASS_WITH_WARNING |
| 2018 | PASS | PASS | PASS | 0 | 0 | 0 | 0 | 0 | PASS |
| 2019 | PASS | PASS | PASS | 0 | 0 | 0 | 0 | 0 | PASS |
| 2020 | PASS | PASS | PASS | 0 | 0 | 0 | 0 | 0 | PASS |
| 2021 | PASS | PASS | PASS | 0 | 0 | 0 | 0 | 0 | PASS |
| 2022 | PASS | PASS | PASS | 0 | 0 | 0 | 0 | 0 | PASS |
| 2023 | PASS | PASS | PASS | 0 | 0 | 0 | 0 | 0 | PASS |
| 2024 | PASS | PASS | PASS | 0 | 0 | 0 | 0 | 0 | PASS |
| 2025 | PASS | PASS | PASS | 0 | 0 | 0 | 0 | 0 | PASS_WITH_WARNING |
| 2026 | PASS | PASS | PASS | 0 | 0 | 0 | 0 | 0 | PASS_WITH_WARNING |

## Cleaning principles

- Processed ingestion files remain unchanged.
- Raw special values are preserved in `*_raw` columns.
- Freddie Mac Not Available codes are converted to null in analytical columns and retained using flags.
- `XX` and `RA` remain available in the raw delinquency field and are not forced into numeric delinquency categories.
- No default/prepayment event definition is applied during cleaning.