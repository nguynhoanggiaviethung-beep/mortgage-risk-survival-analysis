"""Regenerate the two checked-in Step 4 mock PH diagnostic CSVs."""

from pathlib import Path
import sys

import polars as pl


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.survival.cox_model import fit_cox_model
from src.survival.ph_test import run_ph_assumption_test, write_ph_diagnostics


SOURCE = PROJECT_ROOT / "tests" / "fixtures" / "mock_cox_input.parquet"
VARIABLE_OUTPUT = PROJECT_ROOT / "results" / "mock" / "ph_diagnostics.csv"
GLOBAL_OUTPUT = PROJECT_ROOT / "results" / "mock" / "ph_global_diagnostics.csv"


def main() -> None:
    cox_input = pl.read_parquet(SOURCE)
    cox_result = fit_cox_model(cox_input)
    result = run_ph_assumption_test(cox_result, cox_input)
    outputs = write_ph_diagnostics(result, VARIABLE_OUTPUT, GLOBAL_OUTPUT)

    print(f"R: {result.r_version}")
    print(f"survival: {result.survival_version}")
    print("Raw cross-engine differences (R - lifelines):")
    for row in result.engine_comparison.to_dicts():
        print(
            f"  {row['variable']}: "
            f"coefficient={row['coefficient_difference']!r}, "
            f"hazard_ratio={row['hazard_ratio_difference']!r}"
        )
    print(
        f"Wrote {result.variable_diagnostics.height} variable rows to "
        f"{outputs[0].relative_to(PROJECT_ROOT)}"
    )
    print(
        f"Wrote {result.global_diagnostics.height} GLOBAL rows to "
        f"{outputs[1].relative_to(PROJECT_ROOT)}"
    )


if __name__ == "__main__":
    main()
