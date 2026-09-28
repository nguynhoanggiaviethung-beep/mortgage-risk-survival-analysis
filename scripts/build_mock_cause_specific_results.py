"""Build deterministic paired cause-specific Cox mock artifacts."""

from __future__ import annotations

from pathlib import Path
import sys

import polars as pl


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.build_mock_cox_results import build_fixture
from src.competing_risks.cause_specific import (
    fit_paired_cause_specific_models,
    validate_cause_specific_input,
    write_cause_specific_artifacts,
)


DEFAULT_RESULTS = PROJECT_ROOT / "results/mock/cause_specific_default_results.parquet"
DEFAULT_DIAGNOSTICS = (
    PROJECT_ROOT / "results/mock/cause_specific_default_diagnostics.parquet"
)
PREPAYMENT_RESULTS = (
    PROJECT_ROOT / "results/mock/cause_specific_prepayment_results.parquet"
)
PREPAYMENT_DIAGNOSTICS = (
    PROJECT_ROOT / "results/mock/cause_specific_prepayment_diagnostics.parquet"
)


def build_cause_specific_fixture() -> pl.DataFrame:
    """Adapt the locked Step-3 fixture without changing rows or predictors."""
    fixture = build_fixture().with_columns(
        (pl.col("event_type") == "PREPAYMENT")
        .cast(pl.Int8)
        .alias("prepayment_event")
    )
    return validate_cause_specific_input(
        fixture.select(
            "loan_id",
            "vintage_year",
            "entry_time_month",
            "exit_time_month",
            "duration_months",
            "default_event",
            "prepayment_event",
            "event_type",
            "fico",
            "original_ltv",
            "original_dti",
            "original_interest_rate",
            "original_loan_term",
        )
    )


def build_mock_cause_specific_results(
    default_results: Path = DEFAULT_RESULTS,
    default_diagnostics: Path = DEFAULT_DIAGNOSTICS,
    prepayment_results: Path = PREPAYMENT_RESULTS,
    prepayment_diagnostics: Path = PREPAYMENT_DIAGNOSTICS,
) -> tuple[Path, Path, Path, Path]:
    fixture = build_cause_specific_fixture()
    pair = fit_paired_cause_specific_models(fixture)
    default_outputs = write_cause_specific_artifacts(
        pair.default, default_results, default_diagnostics
    )
    prepayment_outputs = write_cause_specific_artifacts(
        pair.prepayment, prepayment_results, prepayment_diagnostics
    )
    return (*default_outputs, *prepayment_outputs)


def main() -> None:
    outputs = build_mock_cause_specific_results()
    for output in outputs:
        print(f"Wrote {output.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
