from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import polars as pl

from src.config import (
    orig_parquet_path,
    perf_parquet_path,
)


year = 2026

orig_file = orig_parquet_path(year)
perf_file = perf_parquet_path(year)


orig = pl.scan_parquet(orig_file)
perf = pl.scan_parquet(perf_file)


# =========================================================
# Các Loan ID có trong Orig nhưng không có trong Perf
# =========================================================

perf_ids = (
    perf
    .select("loan_id")
    .unique()
)


missing_loans = (
    orig
    .join(
        perf_ids,
        on="loan_id",
        how="anti",
    )
    .select(
        "loan_id",
        "first_payment_date",
        "maturity_date",
        "fico",
        "original_ltv",
        "original_dti",
        "original_upb",
        "original_interest_rate",
        "original_loan_term",
        "vintage_year",
    )
    .collect()
)


print("\n" + "=" * 70)
print("LOANS CÓ TRONG ORIGINATION NHƯNG CHƯA CÓ PERFORMANCE")
print("=" * 70)

print(missing_loans)

print(
    "\nSố loan:",
    missing_loans.height
)


# =========================================================
# Tháng Performance mới nhất
# =========================================================

last_period = (
    perf
    .select(
        pl.col(
            "monthly_reporting_period"
        )
        .max()
        .alias("last_period")
    )
    .collect()
)


print("\nPERFORMANCE CUTOFF:")
print(last_period)