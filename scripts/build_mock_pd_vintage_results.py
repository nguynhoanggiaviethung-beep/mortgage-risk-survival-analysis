"""Build deterministic MOCK portfolio-PD and vintage CIF artifacts."""

from __future__ import annotations

from datetime import date
from pathlib import Path
import sys

import polars as pl


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.competing_risks.pd_vintage import (
    fit_pd_vintage_analysis,
    validate_pd_vintage_input,
    write_pd_vintage_results,
)


OVERALL_PD = PROJECT_ROOT / "results/mock/overall_pd_horizons.parquet"
VINTAGE_CIF = PROJECT_ROOT / "results/mock/vintage_cif_results.parquet"
VINTAGE_HORIZONS = PROJECT_ROOT / "results/mock/vintage_horizon_results.parquet"


def build_pd_vintage_fixture() -> pl.DataFrame:
    """Create all vintages with events, delays, ties, and partial follow-up."""
    maximum_age = {
        2016: 72,
        2017: 72,
        2018: 72,
        2019: 72,
        2020: 72,
        2021: 60,
        2022: 48,
        2023: 36,
        2024: 24,
        2025: 10,
        2026: 2,
    }
    event_types = [
        "DEFAULT",
        "PREPAYMENT",
        "CENSOR",
        "DEFAULT",
        "PREPAYMENT",
        "CENSOR",
    ]
    rows: list[dict[str, object]] = []
    for vintage, max_age in maximum_age.items():
        exits = [
            min(max_age, 12),
            min(max_age, 18),
            min(max_age, 24),
            min(max_age, 36),
            min(max_age, 48),
            max_age,
        ]
        entries = [0, 0, 0, 0, 1 if max_age > 2 else 0, 0]
        latest = date(vintage, 3 if vintage == 2026 else 12, 1)
        for index, (event_type, entry, exit_time) in enumerate(
            zip(event_types, entries, exits, strict=True), start=1
        ):
            rows.append({
                "loan_id": f"V{vintage}_{index}",
                "vintage_year": vintage,
                "entry_time_month": entry,
                "exit_time_month": exit_time,
                "duration_months": exit_time,
                "cr_event_code": {
                    "CENSOR": 0,
                    "DEFAULT": 1,
                    "PREPAYMENT": 2,
                }[event_type],
                "event_type": event_type,
                "operational_origination_date": (
                    latest if index == 6 else date(vintage, 1, 1)
                ),
            })
    return validate_pd_vintage_input(
        pl.DataFrame(rows).cast({
            "loan_id": pl.String,
            "vintage_year": pl.Int16,
            "entry_time_month": pl.Int32,
            "exit_time_month": pl.Int32,
            "duration_months": pl.Int32,
            "cr_event_code": pl.Int8,
            "event_type": pl.String,
            "operational_origination_date": pl.Date,
        })
    )


def build_mock_pd_vintage_results(
    overall_path: Path = OVERALL_PD,
    vintage_cif_path: Path = VINTAGE_CIF,
    vintage_horizon_path: Path = VINTAGE_HORIZONS,
) -> tuple[Path, Path, Path]:
    """Fit only the deterministic fixture and write validated MOCK outputs."""
    result = fit_pd_vintage_analysis(build_pd_vintage_fixture())
    return write_pd_vintage_results(
        result, overall_path, vintage_cif_path, vintage_horizon_path
    )


def main() -> None:
    outputs = build_mock_pd_vintage_results()
    for output in outputs:
        print(f"Wrote {output.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
