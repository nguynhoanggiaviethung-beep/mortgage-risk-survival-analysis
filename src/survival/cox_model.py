"""Cause-specific Cox proportional-hazards model for mortgage default.

Default is the event of interest. Prepayment and ordinary censoring are both
treated as right-censoring. Delayed entry is retained through lifelines'
``entry_col`` contract. Predictors are passed in their original project units;
this module performs no scaling, normalization, imputation, or feature changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import TypeAlias
import warnings

import numpy as np
import polars as pl
from lifelines import CoxPHFitter
from lifelines.exceptions import ConvergenceError, ConvergenceWarning

from src.data.model_dataset import CORE_COLUMNS


FrameLike: TypeAlias = pl.DataFrame | pl.LazyFrame
PathSource: TypeAlias = str | PathLike[str]

COX_INPUT_DTYPES: dict[str, pl.DataType] = {
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
}

COX_RESULT_DTYPES: dict[str, pl.DataType] = {
    "model_type": pl.String,
    "endpoint": pl.String,
    "variable": pl.String,
    "coefficient": pl.Float64,
    "hazard_ratio": pl.Float64,
    "standard_error": pl.Float64,
    "ci_lower": pl.Float64,
    "ci_upper": pl.Float64,
    "p_value": pl.Float64,
    "z_statistic": pl.Float64,
}

COX_DIAGNOSTIC_DTYPES: dict[str, pl.DataType] = {
    "model_type": pl.String,
    "endpoint": pl.String,
    "n_observations": pl.UInt32,
    "n_events": pl.UInt32,
    "n_censored": pl.UInt32,
    "n_predictors": pl.UInt32,
    "delayed_entry_count": pl.UInt32,
    "log_likelihood": pl.Float64,
    "partial_aic": pl.Float64,
    "concordance_index": pl.Float64,
    "convergence_status": pl.String,
    "convergence_warning": pl.String,
}

COX_RESULT_COLUMNS = list(COX_RESULT_DTYPES)
COX_DIAGNOSTIC_COLUMNS = list(COX_DIAGNOSTIC_DTYPES)


class CoxModelError(ValueError):
    """Raised when Cox input, fitting, or output violates the contract."""


@dataclass(frozen=True)
class CoxFitResult:
    """Lightweight fitted-model container intended for downstream reuse."""

    model: CoxPHFitter
    coefficients: pl.DataFrame
    diagnostics: pl.DataFrame


def _as_lazy(frame: FrameLike) -> pl.LazyFrame:
    if isinstance(frame, pl.DataFrame):
        return frame.lazy()
    if isinstance(frame, pl.LazyFrame):
        return frame
    raise TypeError("Expected a Polars DataFrame or LazyFrame.")


def validate_cox_input(frame: FrameLike) -> pl.DataFrame:
    """Validate and collect a complete-case one-row-per-loan Cox input."""
    source = _as_lazy(frame)
    schema = source.collect_schema()
    missing = [name for name in COX_INPUT_DTYPES if name not in schema]
    if missing:
        raise CoxModelError(f"Cox input is missing required columns: {missing}.")

    mismatches = {
        name: {"expected": str(dtype), "actual": str(schema[name])}
        for name, dtype in COX_INPUT_DTYPES.items()
        if schema[name] != dtype
    }
    if mismatches:
        raise CoxModelError(f"Cox input has incompatible column types: {mismatches}.")

    expected_event = (pl.col("event_type") == "DEFAULT").cast(pl.Int8)
    valid_event = (
        pl.col("event_type").is_in(["DEFAULT", "PREPAYMENT", "CENSOR"])
        & pl.col("default_event").is_in([0, 1])
        & (pl.col("default_event") == expected_event)
    ).fill_null(False)
    valid_time = (
        pl.col("entry_time_month").is_not_null()
        & pl.col("exit_time_month").is_not_null()
        & pl.col("duration_months").is_not_null()
        & (pl.col("entry_time_month") >= 0)
        & (pl.col("exit_time_month") > pl.col("entry_time_month"))
        & (pl.col("duration_months") == pl.col("exit_time_month"))
    ).fill_null(False)
    complete_predictors = pl.all_horizontal([
        pl.col(name).is_not_null()
        & pl.col(name).cast(pl.Float64).is_finite().fill_null(False)
        for name in CORE_COLUMNS
    ])

    stats = source.select(
        pl.len().alias("rows"),
        pl.col("loan_id").n_unique().alias("unique_loans"),
        pl.col("loan_id").null_count().alias("missing_loan_id"),
        (~valid_event).sum().alias("invalid_event"),
        (~valid_time).sum().alias("invalid_time"),
        (~complete_predictors).sum().alias("incomplete_predictors"),
        pl.col("default_event").sum().alias("events"),
    ).collect().to_dicts()[0]

    if stats["rows"] == 0:
        raise CoxModelError("Cox input is empty.")
    if stats["missing_loan_id"]:
        raise CoxModelError("Cox input contains null loan_id values.")
    if stats["rows"] != stats["unique_loans"]:
        raise CoxModelError("Cox input contains duplicate loan_id values.")
    if stats["invalid_event"]:
        raise CoxModelError(
            f"Cox input has {stats['invalid_event']} invalid or inconsistent "
            "event row(s)."
        )
    if stats["invalid_time"]:
        raise CoxModelError(
            f"Cox input has {stats['invalid_time']} invalid "
            "entry/exit/duration row(s)."
        )
    if stats["incomplete_predictors"]:
        raise CoxModelError(
            f"Cox input has {stats['incomplete_predictors']} row(s) with "
            "missing or non-finite predictors."
        )
    if stats["events"] == 0 or stats["events"] == stats["rows"]:
        raise CoxModelError("Cox input must contain both events and censored rows.")

    return source.collect()


def _warning_text(records: list[warnings.WarningMessage]) -> str:
    messages = []
    for record in records:
        if issubclass(record.category, ConvergenceWarning):
            messages.append(str(record.message))
    return " | ".join(dict.fromkeys(messages))


def fit_cox_model(
    frame: FrameLike,
    confidence_level: float = 0.95,
) -> CoxFitResult:
    """Fit the locked five-predictor default Cox PH specification.

    The baseline is estimated with Breslow's method and tied event times use
    lifelines' Efron handling. No project-level penalization or preprocessing
    is applied. The returned confidence limits are for hazard ratios.
    """
    if not isinstance(confidence_level, (int, float)) or isinstance(
        confidence_level, bool
    ):
        raise CoxModelError("confidence_level must be numeric.")
    if not 0.0 < float(confidence_level) < 1.0:
        raise CoxModelError("confidence_level must be strictly between 0 and 1.")

    data = validate_cox_input(frame)
    fit_columns = [
        "entry_time_month",
        "exit_time_month",
        "default_event",
        *CORE_COLUMNS,
    ]
    pandas_input = data.select(fit_columns).to_pandas()
    estimator = CoxPHFitter(
        baseline_estimation_method="breslow",
        penalizer=0.0,
        l1_ratio=0.0,
        alpha=1.0 - float(confidence_level),
    )

    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            estimator.fit(
                pandas_input,
                duration_col="exit_time_month",
                event_col="default_event",
                entry_col="entry_time_month",
                robust=False,
                batch_mode=None,
                show_progress=False,
            )
    except (ConvergenceError, np.linalg.LinAlgError) as exc:
        raise CoxModelError(f"Cox fit failed to converge: {exc}") from exc
    except Exception as exc:
        raise CoxModelError(f"Cox fit failed: {exc}") from exc

    convergence_warning = _warning_text(caught)
    summary = estimator.summary.loc[CORE_COLUMNS]
    coefficient_ci = estimator.confidence_intervals_.loc[CORE_COLUMNS]
    lower_hr = np.exp(coefficient_ci.iloc[:, 0])
    upper_hr = np.exp(coefficient_ci.iloc[:, 1])

    coefficient_rows = []
    for variable in CORE_COLUMNS:
        coefficient_rows.append({
            "model_type": "cox_ph",
            "endpoint": "default",
            "variable": variable,
            "coefficient": float(summary.loc[variable, "coef"]),
            "hazard_ratio": float(summary.loc[variable, "exp(coef)"]),
            "standard_error": float(summary.loc[variable, "se(coef)"]),
            "ci_lower": float(lower_hr.loc[variable]),
            "ci_upper": float(upper_hr.loc[variable]),
            "p_value": float(summary.loc[variable, "p"]),
            "z_statistic": float(summary.loc[variable, "z"]),
        })
    coefficients = pl.DataFrame(
        coefficient_rows,
        schema=COX_RESULT_DTYPES,
    )

    n_observations = data.height
    n_events = int(data["default_event"].sum())
    diagnostic_row = {
        "model_type": "cox_ph",
        "endpoint": "default",
        "n_observations": n_observations,
        "n_events": n_events,
        "n_censored": n_observations - n_events,
        "n_predictors": len(CORE_COLUMNS),
        "delayed_entry_count": int((data["entry_time_month"] > 0).sum()),
        "log_likelihood": float(estimator.log_likelihood_),
        "partial_aic": float(estimator.AIC_partial_),
        "concordance_index": float(estimator.concordance_index_),
        "convergence_status": "WARNING" if convergence_warning else "PASS",
        "convergence_warning": convergence_warning,
    }
    diagnostics = pl.DataFrame(
        [diagnostic_row],
        schema=COX_DIAGNOSTIC_DTYPES,
    )

    numeric_coefficients = coefficients.select(
        pl.exclude("model_type", "endpoint", "variable")
    ).to_numpy()
    numeric_diagnostics = np.array([
        diagnostic_row["log_likelihood"],
        diagnostic_row["partial_aic"],
        diagnostic_row["concordance_index"],
    ])
    if not np.isfinite(numeric_coefficients).all() or not np.isfinite(
        numeric_diagnostics
    ).all():
        raise CoxModelError("Cox fit produced one or more non-finite estimates.")

    return CoxFitResult(estimator, coefficients, diagnostics)


def validate_cox_results(frame: FrameLike) -> pl.DataFrame:
    """Validate the public/persisted five-row Cox coefficient table."""
    source = _as_lazy(frame)
    schema = source.collect_schema()
    if schema.names() != COX_RESULT_COLUMNS:
        raise CoxModelError(
            "Cox result columns do not match the canonical order: "
            f"{COX_RESULT_COLUMNS}."
        )
    mismatches = {
        name: {"expected": str(dtype), "actual": str(schema[name])}
        for name, dtype in COX_RESULT_DTYPES.items()
        if schema[name] != dtype
    }
    if mismatches:
        raise CoxModelError(f"Cox result has incompatible types: {mismatches}.")

    data = source.collect()
    if data.height != len(CORE_COLUMNS) or data["variable"].to_list() != CORE_COLUMNS:
        raise CoxModelError("Cox result must contain the five predictors in canonical order.")
    valid = data.select(
        pl.all_horizontal([
            pl.col(name).is_not_null() & pl.col(name).is_finite()
            for name in COX_RESULT_COLUMNS[3:]
        ]),
        (pl.col("hazard_ratio") > 0)
        & (pl.col("ci_lower") > 0)
        & (pl.col("ci_lower") <= pl.col("hazard_ratio"))
        & (pl.col("hazard_ratio") <= pl.col("ci_upper")),
    ).to_numpy()
    if not valid.all():
        raise CoxModelError("Cox result contains invalid or non-finite estimates.")
    return data


def validate_cox_diagnostics(frame: FrameLike) -> pl.DataFrame:
    """Validate the public/persisted one-row Cox diagnostics table."""
    source = _as_lazy(frame)
    schema = source.collect_schema()
    if schema.names() != COX_DIAGNOSTIC_COLUMNS:
        raise CoxModelError(
            "Cox diagnostics columns do not match the canonical order: "
            f"{COX_DIAGNOSTIC_COLUMNS}."
        )
    mismatches = {
        name: {"expected": str(dtype), "actual": str(schema[name])}
        for name, dtype in COX_DIAGNOSTIC_DTYPES.items()
        if schema[name] != dtype
    }
    if mismatches:
        raise CoxModelError(f"Cox diagnostics have incompatible types: {mismatches}.")

    data = source.collect()
    if data.height != 1:
        raise CoxModelError("Cox diagnostics must contain exactly one model-level row.")
    row = data.row(0, named=True)
    if row["convergence_status"] not in {"PASS", "WARNING"}:
        raise CoxModelError("Cox diagnostics contain an invalid convergence status.")
    if row["convergence_status"] == "PASS" and row["convergence_warning"]:
        raise CoxModelError("PASS diagnostics cannot contain a convergence warning.")
    if row["n_events"] + row["n_censored"] != row["n_observations"]:
        raise CoxModelError("Cox diagnostic observation counts are inconsistent.")
    if row["n_predictors"] != len(CORE_COLUMNS):
        raise CoxModelError("Cox diagnostic predictor count is inconsistent.")
    for name in ("log_likelihood", "partial_aic", "concordance_index"):
        if not np.isfinite(row[name]):
            raise CoxModelError(f"Cox diagnostic {name!r} is non-finite.")
    return data


def write_cox_artifacts(
    result: CoxFitResult,
    coefficients_path: PathSource,
    diagnostics_path: PathSource,
) -> tuple[Path, Path]:
    """Validate and atomically write both Cox Parquet artifacts."""
    coefficients = validate_cox_results(result.coefficients)
    diagnostics = validate_cox_diagnostics(result.diagnostics)
    outputs = (Path(coefficients_path), Path(diagnostics_path))
    frames = (coefficients, diagnostics)
    temporary_paths: list[Path] = []
    try:
        for frame, output in zip(frames, outputs, strict=True):
            output.parent.mkdir(parents=True, exist_ok=True)
            temporary = output.with_suffix(".tmp.parquet")
            frame.write_parquet(temporary, compression="zstd")
            temporary_paths.append(temporary)
        for temporary, output in zip(temporary_paths, outputs, strict=True):
            temporary.replace(output)
    finally:
        for temporary in temporary_paths:
            temporary.unlink(missing_ok=True)
    return outputs
