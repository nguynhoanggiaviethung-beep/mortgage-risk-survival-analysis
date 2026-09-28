"""Build deterministic DEFAULT Fine-Gray mock artifacts."""

from __future__ import annotations

from pathlib import Path
import sys

import polars as pl


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.build_mock_cox_results import build_fixture
from src.competing_risks.fine_gray import (
    FINE_GRAY_INPUT_COLUMNS,
    fit_fine_gray_default,
    validate_fine_gray_input,
    write_fine_gray_results,
)


RESULTS = PROJECT_ROOT / "results/mock/fine_gray_default_results.parquet"
DIAGNOSTICS = (
    PROJECT_ROOT / "results/mock/fine_gray_default_diagnostics.parquet"
)


def build_fine_gray_fixture() -> pl.DataFrame:
    """Adapt the full-rank Step-3 fixture to canonical competing-risk codes."""
    fixture = build_fixture().with_columns(
        pl.when(pl.col("event_type") == "DEFAULT")
        .then(pl.lit(1, dtype=pl.Int8))
        .when(pl.col("event_type") == "PREPAYMENT")
        .then(pl.lit(2, dtype=pl.Int8))
        .otherwise(pl.lit(0, dtype=pl.Int8))
        .alias("cr_event_code")
    )
    return validate_fine_gray_input(fixture.select(FINE_GRAY_INPUT_COLUMNS))


def build_mock_fine_gray_results(
    results_path: Path = RESULTS,
    diagnostics_path: Path = DIAGNOSTICS,
) -> tuple[Path, Path]:
    """Fit only the deterministic fixture and write validated MOCK outputs."""
    result = fit_fine_gray_default(build_fine_gray_fixture())
    return write_fine_gray_results(result, results_path, diagnostics_path)


def main() -> None:
    outputs = build_mock_fine_gray_results()
    for output in outputs:
        print(f"Wrote {output.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
