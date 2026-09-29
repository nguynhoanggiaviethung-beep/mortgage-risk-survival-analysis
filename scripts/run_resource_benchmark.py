"""Run one explicitly requested, non-production model resource benchmark."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import polars as pl


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.production.benchmarks import (
    PLANNED_BENCHMARK_SIZES,
    run_fine_gray_benchmark,
    run_tv_cox_benchmark,
)


def print_console_safe_path(path: Path, *, stream=None) -> None:
    """Print a path without failing on a legacy Windows console encoding."""
    target = sys.stdout if stream is None else stream
    encoding = getattr(target, "encoding", None) or "utf-8"
    safe_path = str(path).encode(encoding, errors="backslashreplace").decode(encoding)
    print(safe_path, file=target)

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", choices=("fine-gray", "tv-cox"))
    parser.add_argument("--loans", required=True, type=int, choices=PLANNED_BENCHMARK_SIZES)
    parser.add_argument("--rscript", type=Path)
    parser.add_argument("--confirm-benchmark", action="store_true")
    args = parser.parse_args()
    if not args.confirm_benchmark:
        parser.error("benchmark execution requires --confirm-benchmark")
    complete = pl.scan_parquet(
        PROJECT_ROOT / "data/model/baseline_complete_cases_2016_2026.parquet"
    )
    output = (
        PROJECT_ROOT
        / "reports/benchmarks"
        / f"{args.model}_{args.loans}_loans.json"
    )
    if args.model == "fine-gray":
        if args.rscript is None:
            parser.error("fine-gray requires --rscript")
        run_fine_gray_benchmark(
            complete,
            requested_loans=args.loans,
            rscript=args.rscript,
            output_path=output,
        )
    else:
        performance = pl.scan_parquet(
            PROJECT_ROOT / "data/processed/performance.parquet"
        )
        run_tv_cox_benchmark(
            complete,
            performance,
            requested_loans=args.loans,
            output_path=output,
        )
    print_console_safe_path(output)


if __name__ == "__main__":
    main()
