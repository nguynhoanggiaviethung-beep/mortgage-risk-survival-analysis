"""Deterministic resource-benchmark tooling; outputs are never model results."""

from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import polars as pl
from lifelines import CoxTimeVaryingFitter

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
    STEP5A_PREDICTORS,
    TV_COX_TIME_VARYING_PREDICTORS,
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


def deterministic_tv_cox_loan_sample(
    frame: pl.DataFrame | pl.LazyFrame,
    requested_loans: int,
) -> pl.DataFrame:
    """Select all defaults plus a nested proportional non-default prefix."""
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

    event_counts = {
        row["event_type"]: row["len"]
        for row in source.group_by("event_type").len().to_dicts()
    }
    default_count = event_counts["DEFAULT"]
    minimum_size = default_count + 2
    if requested_loans < minimum_size or requested_loans > source.height:
        raise BenchmarkError(
            f"requested_loans must be between {minimum_size} and {source.height} "
            "so all defaults and both non-default strata are retained."
        )

    ranked = (
        source.with_columns(
            pl.col("loan_id")
            .map_elements(_stable_hash, return_dtype=pl.UInt64)
            .alias("_sample_hash")
        )
        .sort(["event_type", "_sample_hash", "loan_id"])
        .with_columns(
            pl.int_range(pl.len()).over("event_type").alias("_stratum_rank")
        )
    )
    default_ids = ranked.filter(pl.col("event_type") == "DEFAULT").select(
        "loan_id"
    )

    remaining = requested_loans - default_count
    censor_count = event_counts["CENSOR"]
    nondefault_count = censor_count + event_counts["PREPAYMENT"]
    allocation_rows = []
    prior_censors = 0
    stratum_ranks = {"CENSOR": 0, "PREPAYMENT": 0}
    for position in range(1, remaining + 1):
        # Integer half-up rounding creates monotone cumulative quotas. Each
        # position adds exactly one member, so every stage is a strict prefix.
        cumulative_censors = (
            2 * position * censor_count + nondefault_count
        ) // (2 * nondefault_count)
        event_type = (
            "CENSOR"
            if cumulative_censors > prior_censors
            else "PREPAYMENT"
        )
        allocation_rows.append({
            "event_type": event_type,
            "_stratum_rank": stratum_ranks[event_type],
        })
        stratum_ranks[event_type] += 1
        prior_censors = cumulative_censors

    allocation = pl.DataFrame(
        allocation_rows,
        schema={"event_type": pl.String, "_stratum_rank": pl.Int64},
    ).with_row_index("_nondefault_order")
    nondefault_ids = (
        allocation.join(
            ranked.filter(pl.col("event_type") != "DEFAULT").select(
                "loan_id", "event_type", "_stratum_rank"
            ),
            on=["event_type", "_stratum_rank"],
            how="left",
            validate="1:1",
        )
        .sort("_nondefault_order")
        .select("loan_id")
    )
    ordered_ids = pl.concat([default_ids, nondefault_ids]).with_row_index(
        "_sample_order"
    )
    sampled = (
        ordered_ids.join(source, on="loan_id", how="left", validate="1:1")
        .sort("_sample_order")
        .drop("_sample_order")
    )
    sampled_counts = sampled.group_by("event_type").len()
    sampled_event_counts = dict(
        zip(
            sampled_counts["event_type"],
            sampled_counts["len"],
            strict=True,
        )
    )
    if (
        sampled.height != requested_loans
        or sampled_event_counts.get("DEFAULT") != default_count
        or sampled_event_counts.get("CENSOR", 0) == 0
        or sampled_event_counts.get("PREPAYMENT", 0) == 0
    ):
        raise BenchmarkError(
            "TV-Cox event-enriched sampling violated its size or event contract."
        )
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


def _benchmark_metrics_template(kind: str, requested: int) -> dict[str, object]:
    """Return explicit nullable fields shared by successful and failed runs."""
    return {
        "status": None,
        "benchmark_kind": kind,
        "is_production_result": False,
        "created_at_utc": datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "requested_loans": requested,
        "actual_loans": None,
        "default_count": None,
        "prepayment_count": None,
        "censor_count": None,
        "delayed_entry_count": None,
        "peak_rss_bytes": None,
        "peak_rss_status": "UNAVAILABLE_WITH_INSTALLED_TOOLING",
        "total_runtime_seconds": None,
        "failure_stage": None,
        "exception_type": None,
        "exception_message": None,
    }


def _persist_failed_benchmark(
    output_path: Path,
    metrics: dict[str, object],
    *,
    stage: str,
    error: Exception,
    started: float,
) -> None:
    """Persist the facts known at failure without converting it into success."""
    metrics.update({
        "status": "FAILED",
        "total_runtime_seconds": time.perf_counter() - started,
        "failure_stage": stage,
        "exception_type": type(error).__name__,
        "exception_message": str(error),
    })
    if stage == "MODEL_FIT":
        metrics["convergence_status"] = "FAILED"
    atomic_write_json(output_path, metrics)


def build_tv_cox_benchmark_preflight(data: pl.DataFrame) -> dict[str, object]:
    """Summarize exact TV-Cox support and initial lifelines identifiability."""
    predictor_support = {}
    for predictor in STEP5A_PREDICTORS:
        values = pl.col(predictor).cast(pl.Float64)
        counts = data.select(
            pl.col(predictor).null_count().alias("null_count"),
            (~values.is_finite().fill_null(False)).sum().alias(
                "null_or_nonfinite_count"
            ),
        ).row(0, named=True)
        predictor_support[predictor] = {
            "all_finite": counts["null_or_nonfinite_count"] == 0,
            "null_count": counts["null_count"],
            "nonfinite_count": (
                counts["null_or_nonfinite_count"] - counts["null_count"]
            ),
        }

    binary_support = {}
    terminal_defaults = pl.col("terminal_interval_flag") & (
        pl.col("default_event") == 1
    )
    for predictor in TV_COX_TIME_VARYING_PREDICTORS[2:]:
        counts = data.select(
            pl.col(predictor).sum().alias("positive_count_overall"),
            pl.when(terminal_defaults)
            .then(pl.col(predictor))
            .otherwise(0)
            .sum()
            .alias("positive_count_default_terminal_intervals"),
        ).row(0, named=True)
        binary_support[predictor] = counts

    interval_counts = data.select(
        pl.len().alias("row_count"),
        (pl.col("start_time_month") < 0).sum().alias("negative_start_count"),
        (pl.col("stop_time_month") == pl.col("start_time_month"))
        .sum()
        .alias("zero_width_count"),
        (pl.col("stop_time_month") < pl.col("start_time_month"))
        .sum()
        .alias("negative_width_count"),
        pl.struct(["loan_id", "start_time_month", "stop_time_month"])
        .n_unique()
        .alias("unique_interval_key_count"),
        terminal_defaults.sum().alias("terminal_default_event_count"),
    ).row(0, named=True)
    interval_counts["duplicate_interval_key_count"] = (
        interval_counts["row_count"]
        - interval_counts["unique_interval_key_count"]
    )
    interval_counts["status"] = (
        "PASS"
        if all(
            interval_counts[name] == 0
            for name in (
                "negative_start_count",
                "zero_width_count",
                "negative_width_count",
                "duplicate_interval_key_count",
            )
        )
        else "FAILED"
    )

    pandas_input = data.select([
        *STEP5A_PREDICTORS,
        "default_event",
        "start_time_month",
        "stop_time_month",
    ]).to_pandas()
    covariates = pandas_input[STEP5A_PREDICTORS]
    normalized = (covariates - covariates.mean(axis=0)) / covariates.std(axis=0)
    initial_hessian, initial_gradient, _ = CoxTimeVaryingFitter._get_gradients(
        normalized.to_numpy(),
        pandas_input["default_event"].astype(bool).to_numpy(),
        pandas_input["start_time_month"].to_numpy(),
        pandas_input["stop_time_month"].to_numpy(),
        np.ones(len(pandas_input)),
        np.zeros(len(STEP5A_PREDICTORS)),
    )
    information_rank = int(np.linalg.matrix_rank(-initial_hessian))

    return {
        "status": "COMPLETED",
        "predictor_finite_support": predictor_support,
        "binary_delinquency_support": binary_support,
        "interval_integrity": interval_counts,
        "terminal_default_event_count": interval_counts[
            "terminal_default_event_count"
        ],
        "initial_information_matrix_rank": information_rank,
        "initial_information_matrix_dimension": len(STEP5A_PREDICTORS),
        "initial_information_matrix_all_finite": bool(
            np.isfinite(initial_hessian).all()
        ),
        "initial_gradient_all_finite": bool(np.isfinite(initial_gradient).all()),
        "rank_computation": "LIFELINES_INITIAL_NEWTON_RAPHSON_GRADIENT",
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
    metrics = {
        **_benchmark_metrics_template("FINE_GRAY_RESOURCE", requested_loans),
        "serialized_input_bytes": None,
        "expanded_rows": None,
        "expansion_ratio": None,
        "expansion_runtime_seconds": None,
        "expansion_runtime_status": "NOT_EXPOSED_BY_CURRENT_ESTIMATOR_API",
        "fit_runtime_seconds": None,
        "convergence_status": None,
        "convergence_warning": None,
        "robust_variance_present": None,
        "naive_variance_present": None,
        "result_validation_status": None,
    }
    stage = "SAMPLE_SELECTION"
    try:
        sample = deterministic_nested_loan_sample(complete_cases, requested_loans)
        metrics.update(_base_metrics("FINE_GRAY_RESOURCE", requested_loans, sample))
        stage = "INPUT_SERIALIZATION"
        model_input = sample.select(FINE_GRAY_INPUT_COLUMNS)
        serialized = model_input.write_csv().encode("utf-8")
        metrics["serialized_input_bytes"] = len(serialized)
        stage = "MODEL_FIT"
        fit_started = time.perf_counter()
        result = fit_fine_gray_default(model_input, rscript=rscript)
        metrics["fit_runtime_seconds"] = time.perf_counter() - fit_started
        stage = "RESULT_VALIDATION"
        validate_fine_gray_results(result.coefficients)
        diagnostic = validate_fine_gray_diagnostics(result.diagnostics).row(
            0, named=True
        )
        metrics.update({
            "status": "PASS",
            "expanded_rows": diagnostic["n_expanded_rows"],
            "expansion_ratio": diagnostic["n_expanded_rows"] / sample.height,
            "convergence_status": diagnostic["convergence_status"],
            "convergence_warning": diagnostic["convergence_warning"],
            "robust_variance_present": True,
            "naive_variance_present": True,
            "result_validation_status": "PASS",
            "total_runtime_seconds": time.perf_counter() - started,
        })
    except Exception as error:
        _persist_failed_benchmark(
            output_path, metrics, stage=stage, error=error, started=started
        )
        raise
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
    metrics = {
        **_benchmark_metrics_template("TV_COX_RESOURCE", requested_loans),
        "source_monthly_rows": None,
        "constructed_interval_rows": None,
        "interval_expansion_ratio": None,
        "input_build_runtime_seconds": None,
        "input_validation_status": None,
        "validation_runtime_seconds": None,
        "pandas_conversion_memory_bytes": None,
        "pandas_conversion_memory_status": "NOT_EXPOSED_BY_CURRENT_ESTIMATOR_API",
        "fit_runtime_seconds": None,
        "convergence_status": None,
        "convergence_warning": None,
        "output_validation_status": None,
        "selected_histories_complete": None,
        "identifiability_preflight": None,
        "identifiability_preflight_runtime_seconds": None,
    }
    stage = "SAMPLE_SELECTION"
    try:
        sample = deterministic_tv_cox_loan_sample(complete_cases, requested_loans)
        metrics.update(_base_metrics("TV_COX_RESOURCE", requested_loans, sample))
        stage = "HISTORY_SELECTION"
        selected_monthly = select_complete_performance_histories(performance, sample)
        metrics["source_monthly_rows"] = (
            selected_monthly.select(pl.len()).collect().item()
        )
        metrics["selected_histories_complete"] = True
        stage = "INPUT_BUILD"
        build_started = time.perf_counter()
        intervals_lazy = build_time_varying_cox_input(selected_monthly, sample.lazy())
        intervals = intervals_lazy.collect()
        metrics.update({
            "constructed_interval_rows": intervals.height,
            "interval_expansion_ratio": intervals.height / sample.height,
            "input_build_runtime_seconds": time.perf_counter() - build_started,
        })
        stage = "INPUT_VALIDATION"
        validation_started = time.perf_counter()
        validated = validate_time_varying_cox_input(intervals)
        metrics.update({
            "input_validation_status": "PASS",
            "validation_runtime_seconds": time.perf_counter() - validation_started,
        })
        stage = "IDENTIFIABILITY_PREFLIGHT"
        preflight_started = time.perf_counter()
        metrics["identifiability_preflight"] = build_tv_cox_benchmark_preflight(
            validated
        )
        metrics["identifiability_preflight_runtime_seconds"] = (
            time.perf_counter() - preflight_started
        )
        stage = "MODEL_FIT"
        fit_started = time.perf_counter()
        try:
            result = fit_time_varying_cox_model(validated)
        finally:
            metrics["fit_runtime_seconds"] = time.perf_counter() - fit_started
        stage = "RESULT_VALIDATION"
        validate_time_varying_cox_results(result.coefficients)
        diagnostic = validate_time_varying_cox_diagnostics(result.diagnostics).row(
            0, named=True
        )
        metrics.update({
            "status": "PASS",
            "convergence_status": diagnostic["convergence_status"],
            "convergence_warning": diagnostic["convergence_warning"],
            "output_validation_status": "PASS",
            "total_runtime_seconds": time.perf_counter() - started,
        })
    except Exception as error:
        _persist_failed_benchmark(
            output_path, metrics, stage=stage, error=error, started=started
        )
        raise
    atomic_write_json(output_path, metrics)
    return metrics
