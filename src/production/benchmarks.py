"""Deterministic resource-benchmark tooling; outputs are never model results."""

from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path

import polars as pl

from src.competing_risks.fine_gray import (
    FINE_GRAY_INPUT_COLUMNS,
    fit_fine_gray_default,
    validate_fine_gray_diagnostics,
    validate_fine_gray_results,
)
from src.results.writers import atomic_write_json
from src.survival.time_varying_cox_model import (
    fit_time_varying_cox_model,
    validate_time_varying_cox_diagnostics,
    validate_time_varying_cox_results,
)
from src.survival.time_varying_input import (
    build_time_varying_cox_input,
    validate_time_varying_cox_input,
)


PLANNED_BENCHMARK_SIZES = (25_000, 100_000, 250_000)


class BenchmarkError(ValueError):
    """Raised when a benchmark would violate its sampling contract."""


def _stable_hash(value: str) -> int:
    return int.from_bytes(
        hashlib.sha256(value.encode("utf-8")).digest()[:8], "big"
    )


def deterministic_nested_loan_sample(
    frame: pl.DataFrame | pl.LazyFrame,
    requested_loans: int,
) -> pl.DataFrame:
    """Select a nested loan-level sample with every observed event represented."""
    if not isinstance(requested_loans, int) or isinstance(requested_loans, bool):
        raise BenchmarkError("requested_loans must be an integer.")
    source = frame.collect() if isinstance(frame, pl.LazyFrame) else frame
    required = {"loan_id", "event_type"}
    if not required.issubset(source.columns):
        raise BenchmarkError("Benchmark input requires loan_id and event_type.")
    if source["loan_id"].null_count() or source["loan_id"].n_unique() != source.height:
        raise BenchmarkError("Benchmark input must have one non-null row per loan.")
    events = sorted(source["event_type"].unique().to_list())
    if events != ["CENSOR", "DEFAULT", "PREPAYMENT"]:
        raise BenchmarkError("Benchmark input must contain all canonical events.")
    if requested_loans < len(events) or requested_loans > source.height:
        raise BenchmarkError(
            f"requested_loans must be between {len(events)} and {source.height}."
        )

    ranked = (
        source.with_columns(
            pl.col("loan_id")
            .map_elements(_stable_hash, return_dtype=pl.UInt64)
            .alias("_sample_hash")
        )
        .sort(["event_type", "_sample_hash", "loan_id"])
        .with_columns(
            pl.int_range(pl.len()).over("event_type").alias("_stratum_rank"),
            pl.len().over("event_type").alias("_stratum_size"),
        )
    )
    anchors = ranked.filter(pl.col("_stratum_rank") == 0).sort("event_type")
    remainder = (
        ranked.filter(pl.col("_stratum_rank") > 0)
        .with_columns(
            (pl.col("_stratum_rank") / pl.col("_stratum_size")).alias(
                "_stratum_fraction"
            )
        )
        .sort(["_stratum_fraction", "_sample_hash", "event_type", "loan_id"])
    )
    ordered_ids = pl.concat(
        [anchors.select("loan_id"), remainder.select("loan_id")]
    ).head(requested_loans).with_row_index("_sample_order")
    sampled = (
        ordered_ids.join(source, on="loan_id", how="left", validate="1:1")
        .sort("_sample_order")
        .drop("_sample_order")
    )
    if sampled.height != requested_loans or set(sampled["event_type"]) != set(events):
        raise BenchmarkError("Deterministic benchmark sampling lost an event stratum.")
    return sampled


def select_complete_performance_histories(
    performance: pl.DataFrame | pl.LazyFrame,
    sampled_loans: pl.DataFrame,
) -> pl.LazyFrame:
    """Retain every monthly row for selected loans; never sample months."""
    if "loan_id" not in sampled_loans.columns:
        raise BenchmarkError("sampled_loans requires loan_id.")
    if sampled_loans["loan_id"].n_unique() != sampled_loans.height:
        raise BenchmarkError("sampled_loans must contain unique loans.")
    monthly = performance.lazy() if isinstance(performance, pl.DataFrame) else performance
    return monthly.join(sampled_loans.select("loan_id").lazy(), on="loan_id", how="semi")


def _base_metrics(kind: str, requested: int, data: pl.DataFrame) -> dict[str, object]:
    counts = data.group_by("event_type").len()
    event_counts = dict(zip(counts["event_type"], counts["len"], strict=True))
    return {
        "benchmark_kind": kind,
        "is_production_result": False,
        "created_at_utc": datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "requested_loans": requested,
        "actual_loans": data.height,
        "default_count": event_counts.get("DEFAULT", 0),
        "prepayment_count": event_counts.get("PREPAYMENT", 0),
        "censor_count": event_counts.get("CENSOR", 0),
        "delayed_entry_count": int((data["entry_time_month"] > 0).sum()),
        "peak_rss_bytes": None,
        "peak_rss_status": "UNAVAILABLE_WITH_INSTALLED_TOOLING",
    }


def run_fine_gray_benchmark(
    complete_cases: pl.DataFrame | pl.LazyFrame,
    *,
    requested_loans: int,
    rscript: Path,
    output_path: Path,
) -> dict[str, object]:
    """Run one explicitly requested Fine-Gray resource benchmark stage."""
    started = time.perf_counter()
    sample = deterministic_nested_loan_sample(complete_cases, requested_loans)
    model_input = sample.select(FINE_GRAY_INPUT_COLUMNS)
    serialized = model_input.write_csv().encode("utf-8")
    fit_started = time.perf_counter()
    result = fit_fine_gray_default(model_input, rscript=rscript)
    fit_seconds = time.perf_counter() - fit_started
    validate_fine_gray_results(result.coefficients)
    diagnostic = validate_fine_gray_diagnostics(result.diagnostics).row(
        0, named=True
    )
    metrics = {
        **_base_metrics("FINE_GRAY_RESOURCE", requested_loans, sample),
        "serialized_input_bytes": len(serialized),
        "expanded_rows": diagnostic["n_expanded_rows"],
        "expansion_ratio": diagnostic["n_expanded_rows"] / sample.height,
        "expansion_runtime_seconds": None,
        "expansion_runtime_status": "NOT_EXPOSED_BY_CURRENT_ESTIMATOR_API",
        "fit_runtime_seconds": fit_seconds,
        "total_runtime_seconds": time.perf_counter() - started,
        "convergence_status": diagnostic["convergence_status"],
        "convergence_warning": diagnostic["convergence_warning"],
        "robust_variance_present": True,
        "naive_variance_present": True,
        "result_validation_status": "PASS",
    }
    atomic_write_json(output_path, metrics)
    return metrics


def run_tv_cox_benchmark(
    complete_cases: pl.DataFrame | pl.LazyFrame,
    performance: pl.DataFrame | pl.LazyFrame,
    *,
    requested_loans: int,
    output_path: Path,
) -> dict[str, object]:
    """Run one loan-sampled TV-Cox resource benchmark with full histories."""
    started = time.perf_counter()
    sample = deterministic_nested_loan_sample(complete_cases, requested_loans)
    selected_monthly = select_complete_performance_histories(performance, sample)
    source_rows = selected_monthly.select(pl.len()).collect().item()
    build_started = time.perf_counter()
    intervals_lazy = build_time_varying_cox_input(selected_monthly, sample.lazy())
    intervals = intervals_lazy.collect()
    build_seconds = time.perf_counter() - build_started
    validation_started = time.perf_counter()
    validated = validate_time_varying_cox_input(intervals)
    validation_seconds = time.perf_counter() - validation_started
    fit_started = time.perf_counter()
    result = fit_time_varying_cox_model(validated)
    fit_seconds = time.perf_counter() - fit_started
    validate_time_varying_cox_results(result.coefficients)
    diagnostic = validate_time_varying_cox_diagnostics(result.diagnostics).row(
        0, named=True
    )
    metrics = {
        **_base_metrics("TV_COX_RESOURCE", requested_loans, sample),
        "source_monthly_rows": source_rows,
        "constructed_interval_rows": intervals.height,
        "interval_expansion_ratio": intervals.height / sample.height,
        "input_build_runtime_seconds": build_seconds,
        "validation_runtime_seconds": validation_seconds,
        "pandas_conversion_memory_bytes": None,
        "pandas_conversion_memory_status": "NOT_EXPOSED_BY_CURRENT_ESTIMATOR_API",
        "fit_runtime_seconds": fit_seconds,
        "total_runtime_seconds": time.perf_counter() - started,
        "convergence_status": diagnostic["convergence_status"],
        "convergence_warning": diagnostic["convergence_warning"],
        "output_validation_status": "PASS",
        "selected_histories_complete": True,
    }
    atomic_write_json(output_path, metrics)
    return metrics
