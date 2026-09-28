"""Build the deterministic delayed-entry Aalen-Johansen mock artifact."""

from __future__ import annotations

from pathlib import Path
import sys

import polars as pl


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.competing_risks.aalen_johansen import (
    fit_aalen_johansen,
    validate_aalen_johansen_input,
    write_aalen_johansen_results,
)


OUTPUT = PROJECT_ROOT / "results/mock/aalen_johansen_results.parquet"


def build_aalen_johansen_fixture() -> pl.DataFrame:
    """Create a hand-verifiable fixture with delays, ties, and all outcomes."""
    return validate_aalen_johansen_input(
        pl.DataFrame({
            "loan_id": [f"AJ{i}" for i in range(1, 7)],
            "vintage_year": [2020, 2020, 2020, 2021, 2021, 2021],
            "entry_time_month": [0, 0, 0, 1, 1, 2],
            "exit_time_month": [2, 2, 3, 3, 4, 4],
            "duration_months": [2, 2, 3, 3, 4, 4],
            "cr_event_code": [1, 2, 0, 1, 2, 0],
            "event_type": [
                "DEFAULT",
                "PREPAYMENT",
                "CENSOR",
                "DEFAULT",
                "PREPAYMENT",
                "CENSOR",
            ],
        }).cast({
            "loan_id": pl.String,
            "vintage_year": pl.Int16,
            "entry_time_month": pl.Int32,
            "exit_time_month": pl.Int32,
            "duration_months": pl.Int32,
            "cr_event_code": pl.Int8,
            "event_type": pl.String,
        })
    )


def build_mock_aalen_johansen_results(output: Path = OUTPUT) -> Path:
    result = fit_aalen_johansen(build_aalen_johansen_fixture())
    return write_aalen_johansen_results(result, output)


def main() -> None:
    output = build_mock_aalen_johansen_results()
    print(f"Wrote {output.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
