"""Regenerate the two deterministic Step 5A mock result artifacts."""

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.survival.time_varying_cox_model import (
    fit_time_varying_cox_model,
    validate_time_varying_cox_diagnostics,
    validate_time_varying_cox_results,
    write_time_varying_cox_artifacts,
)
from src.survival.time_varying_input import validate_time_varying_cox_input
from tests.time_varying_fixtures import build_fitter_fixture


COEFFICIENTS = (
    PROJECT_ROOT / "results" / "mock" / "time_varying_cox_results.parquet"
)
DIAGNOSTICS = (
    PROJECT_ROOT
    / "results"
    / "mock"
    / "time_varying_cox_diagnostics.parquet"
)


def build_mock_time_varying_cox_results(
    coefficients_path: Path = COEFFICIENTS,
    diagnostics_path: Path = DIAGNOSTICS,
) -> tuple[Path, Path]:
    """Fit the deterministic test fixture and write validated mock artifacts."""
    fixture = validate_time_varying_cox_input(build_fitter_fixture())
    result = fit_time_varying_cox_model(fixture)
    status = result.diagnostics["convergence_status"].item()
    if status != "PASS":
        warning = result.diagnostics["convergence_warning"].item()
        raise RuntimeError(
            "The deterministic Step 5A fixture did not produce a clean fit: "
            f"{warning}"
        )

    validate_time_varying_cox_results(result.coefficients)
    validate_time_varying_cox_diagnostics(result.diagnostics)
    return write_time_varying_cox_artifacts(
        result,
        coefficients_path,
        diagnostics_path,
    )


def main() -> None:
    fixture = build_fitter_fixture()
    outputs = build_mock_time_varying_cox_results()
    print(
        f"Fitted {fixture['loan_id'].n_unique()} loans, "
        f"{fixture.height} intervals, and "
        f"{int(fixture['default_event'].sum())} default events."
    )
    print(f"Wrote coefficients to {outputs[0].relative_to(PROJECT_ROOT)}")
    print(f"Wrote diagnostics to {outputs[1].relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
