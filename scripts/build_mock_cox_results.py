"""Regenerate the deterministic Step 3 Cox fixture and mock artifacts."""

from pathlib import Path
import sys

import numpy as np
import polars as pl


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.model_dataset import CORE_COLUMNS
from src.survival.cox_model import (
    fit_cox_model,
    validate_cox_input,
    write_cox_artifacts,
)


SEED = 20260928
N_LOANS = 240
FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "mock_cox_input.parquet"
COEFFICIENTS = PROJECT_ROOT / "results" / "mock" / "cox_results.parquet"
DIAGNOSTICS = PROJECT_ROOT / "results" / "mock" / "cox_diagnostics.parquet"


def build_fixture() -> pl.DataFrame:
    """Build and validate the locked-seed Cox fixture without seed fallback."""
    rng = np.random.default_rng(SEED)
    event_type = np.array(
        ["DEFAULT"] * 72 + ["PREPAYMENT"] * 84 + ["CENSOR"] * 84,
        dtype=object,
    )
    rng.shuffle(event_type)

    entry = np.zeros(N_LOANS, dtype=np.int32)
    delayed_indices = rng.choice(N_LOANS, size=48, replace=False)
    entry[delayed_indices] = rng.integers(1, 7, size=48, dtype=np.int32)
    exit_time = entry + rng.integers(6, 73, size=N_LOANS, dtype=np.int32)

    fixture = pl.DataFrame({
        "loan_id": [f"C{i:04d}" for i in range(1, N_LOANS + 1)],
        "vintage_year": rng.integers(2016, 2027, size=N_LOANS).astype(np.int16),
        "entry_time_month": entry,
        "exit_time_month": exit_time,
        "duration_months": exit_time,
        "default_event": (event_type == "DEFAULT").astype(np.int8),
        "event_type": event_type.tolist(),
        "fico": rng.integers(580, 821, size=N_LOANS).astype(np.int16),
        "original_ltv": np.round(rng.uniform(50.0, 105.0, size=N_LOANS), 2),
        "original_dti": np.round(rng.uniform(15.0, 55.0, size=N_LOANS), 2),
        "original_interest_rate": np.round(
            rng.uniform(2.5, 7.0, size=N_LOANS), 3
        ),
        "original_loan_term": rng.choice(
            np.array([180, 240, 360], dtype=np.int16),
            size=N_LOANS,
            p=[0.15, 0.15, 0.70],
        ),
    }).cast({
        "loan_id": pl.String,
        "vintage_year": pl.Int16,
        "entry_time_month": pl.Int32,
        "exit_time_month": pl.Int32,
        "duration_months": pl.Int32,
        "default_event": pl.Int8,
        "event_type": pl.String,
        "fico": pl.Int16,
        "original_ltv": pl.Float64,
        "original_dti": pl.Float64,
        "original_interest_rate": pl.Float64,
        "original_loan_term": pl.Int16,
    })
    fixture = validate_cox_input(fixture)

    counts = fixture.group_by("event_type").len()
    actual_counts = dict(zip(counts["event_type"], counts["len"], strict=True))
    expected_counts = {"DEFAULT": 72, "PREPAYMENT": 84, "CENSOR": 84}
    if actual_counts != expected_counts:
        raise RuntimeError(f"Seed {SEED} produced wrong event counts: {actual_counts}.")
    if any(fixture[name].n_unique() < 2 for name in CORE_COLUMNS):
        raise RuntimeError(f"Seed {SEED} produced a predictor without variation.")
    design = fixture.select(CORE_COLUMNS).to_numpy().astype(float)
    if np.linalg.matrix_rank(design) != len(CORE_COLUMNS):
        raise RuntimeError(f"Seed {SEED} produced a rank-deficient design matrix.")
    if not (fixture["entry_time_month"] > 0).any():
        raise RuntimeError(f"Seed {SEED} produced no delayed-entry loans.")
    if fixture["exit_time_month"].n_unique() == fixture.height:
        raise RuntimeError(f"Seed {SEED} produced no tied exit times.")

    # Both outcomes must overlap on every predictor. Combined with a clean,
    # unpenalized fit below, this guards against practical perfect separation.
    for name in CORE_COLUMNS:
        events = fixture.filter(pl.col("default_event") == 1)[name]
        censored = fixture.filter(pl.col("default_event") == 0)[name]
        if events.max() < censored.min() or censored.max() < events.min():
            raise RuntimeError(
                f"Seed {SEED} produced separated ranges for {name!r}."
            )
    return fixture


def _atomic_write(frame: pl.DataFrame, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".tmp.parquet")
    frame.write_parquet(temporary, compression="zstd")
    temporary.replace(output)


def main() -> None:
    fixture = build_fixture()
    result = fit_cox_model(fixture)
    status = result.diagnostics["convergence_status"].item()
    if status != "PASS":
        warning = result.diagnostics["convergence_warning"].item()
        raise RuntimeError(
            f"Seed {SEED} did not produce a clean Cox fit: {warning}"
        )

    _atomic_write(fixture, FIXTURE)
    write_cox_artifacts(result, COEFFICIENTS, DIAGNOSTICS)
    print(
        f"Wrote {fixture.height} fixture rows to "
        f"{FIXTURE.relative_to(PROJECT_ROOT)}\n"
        f"Wrote {result.coefficients.height} coefficient rows to "
        f"{COEFFICIENTS.relative_to(PROJECT_ROOT)}\n"
        f"Wrote {result.diagnostics.height} diagnostic row to "
        f"{DIAGNOSTICS.relative_to(PROJECT_ROOT)}"
    )


if __name__ == "__main__":
    main()
