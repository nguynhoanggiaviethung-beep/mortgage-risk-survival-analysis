# Freddie Mac Sample Raw / Processed Validation

Study vintages: 2016–2026
Performance cutoff used: 202603

Raw ZIP files are preserved unchanged. ZIP validation checks that each archive is readable, contains the expected Origination and Performance members, and that both members are non-empty. The ingestion pipeline has already successfully extracted and processed every vintage.

| Year | ZIP | Orig rows | Perf rows | Orig dup ID | Perf dup loan-month | Perf ID not Orig | Orig without Perf | Order violations | After cutoff | Reporting gaps | Status |
|---:|:---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|
| 2016 | PASS | 50,000 | 3,379,650 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | PASS |
| 2017 | PASS | 50,000 | 2,800,219 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | PASS_WITH_WARNING |
| 2018 | PASS | 50,000 | 2,059,564 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | PASS |
| 2019 | PASS | 50,000 | 1,934,614 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | PASS |
| 2020 | PASS | 50,000 | 2,517,857 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | PASS |
| 2021 | PASS | 50,000 | 2,537,054 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | PASS |
| 2022 | PASS | 50,000 | 2,034,798 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | PASS |
| 2023 | PASS | 50,000 | 1,458,169 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | PASS |
| 2024 | PASS | 50,000 | 952,865 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | PASS |
| 2025 | PASS | 50,000 | 404,946 | 0 | 0 | 0 | 5 | 0 | 0 | 0 | PASS_WITH_WARNING |
| 2026 | PASS | 12,500 | 17,648 | 0 | 0 | 0 | 5 | 0 | 0 | 0 | PASS_WITH_WARNING |

## Interpretation

- `Orig without Perf` is reported separately because a newly originated loan may legitimately have no available monthly performance record before the dataset cutoff.
- Reporting gaps are treated as warnings for review, not automatically as corrupted observations.
- Duplicate Loan ID, duplicate loan-month, unknown Performance Loan IDs, dates beyond cutoff, or temporal order violations are treated as critical validation failures.