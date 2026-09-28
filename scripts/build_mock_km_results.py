"""Regenerate the checked-in Step 2 Kaplan-Meier mock result."""

from pathlib import Path
import sys

import polars as pl


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.survival.kaplan_meier import fit_kaplan_meier, write_km_results
from src.survival.model_input import build_loan_level_input, to_survival_input


SOURCE = PROJECT_ROOT / "tests" / "fixtures" / "mock_loan_month.parquet"
OUTPUT = PROJECT_ROOT / "results" / "mock" / "km_results.parquet"


def main() -> None:
    monthly = pl.read_parquet(SOURCE)
    loan_level = build_loan_level_input(monthly)
    survival_input = to_survival_input(loan_level)
    results = fit_kaplan_meier(survival_input)
    output = write_km_results(results, OUTPUT)
    print(f"Wrote {results.height} rows to {output}")


if __name__ == "__main__":
    main()
