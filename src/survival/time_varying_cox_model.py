"""Step 5A time-varying Cox model for the locked default endpoint."""

from __future__ import annotations

from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import TypeAlias
import warnings

import numpy as np
import polars as pl
from lifelines import CoxTimeVaryingFitter
from lifelines.exceptions import ConvergenceError, ConvergenceWarning

from src.survival.time_varying_input import (
    STEP5A_PREDICTORS,
    validate_time_varying_cox_input,
)


FrameLike: TypeAlias = pl.DataFrame | pl.LazyFrame
PathSource: TypeAlias = str | PathLike[str]

TIME_VARYING_COX_RESULT_DTYPES: dict[str, pl.DataType] = {
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

TIME_VARYING_COX_DIAGNOSTIC_DTYPES: dict[str, pl.DataType] = {
    "model_type": pl.String,
    "endpoint": pl.String,
    "n_intervals": pl.UInt32,
    "n_loans": pl.UInt32,
    "n_events": pl.UInt32,
    "n_censored_loans": pl.UInt32,
    "n_predictors": pl.UInt32,
    "n_delayed_entry_loans": pl.UInt32,
    "n_gap_intervals": pl.UInt32,
    "max_interval_length_months": pl.Int32,
    "variance_type": pl.String,
    "log_likelihood": pl.Float64,
    "partial_aic": pl.Float64,
    "convergence_status": pl.String,
    "convergence_warning": pl.String,
}

TIME_VARYING_COX_RESULT_COLUMNS = list(TIME_VARYING_COX_RESULT_DTYPES)
TIME_VARYING_COX_DIAGNOSTIC_COLUMNS = list(
    TIME_VARYING_COX_DIAGNOSTIC_DTYPES
)


class TimeVaryingCoxModelError(ValueError):
    """Raised when Step 5A fitting or output violates its contract."""


@dataclass(frozen=True)
class TimeVaryingCoxFitResult:
    """Fitted lifelines model plus stable public result tables."""

    model: CoxTimeVaryingFitter
    coefficients: pl.DataFrame
    diagnostics: pl.DataFrame


def _as_lazy(frame: FrameLike) -> pl.LazyFrame:
    if isinstance(frame, pl.DataFrame):
        return frame.lazy()
    if isinstance(frame, pl.LazyFrame):
        return frame
    raise TypeError("Expected a Polars DataFrame or LazyFrame.")


def _warning_text(records: list[warnings.WarningMessage]) -> str:
    messages = [
        str(record.message)
        for record in records
        if issubclass(record.category, ConvergenceWarning)
    ]
    return " | ".join(dict.fromkeys(messages))


def fit_time_varying_cox_model(
    frame: FrameLike,
    confidence_level: float = 0.95,
) -> TimeVaryingCoxFitResult:
    """Fit the locked Step 5A model using model-based variance only."""
    if not isinstance(confidence_level, (int, float)) or isinstance(
        confidence_level, bool
    ):
        raise TimeVaryingCoxModelError("confidence_level must be numeric.")
    if not 0.0 < float(confidence_level) < 1.0:
        raise TimeVaryingCoxModelError(
            "confidence_level must be strictly between 0 and 1."
        )

    try:
        data = validate_time_varying_cox_input(frame)
    except (TypeError, ValueError) as exc:
        raise TimeVaryingCoxModelError(str(exc)) from exc

    n_events = int(data["default_event"].sum())
    n_loans = data["loan_id"].n_unique()
    if n_events == 0 or n_events == n_loans:
        raise TimeVaryingCoxModelError(
            "Time-varying Cox input must contain both default and censored loans."
        )

    fit_columns = [
        "loan_id",
        "start_time_month",
        "stop_time_month",
        "default_event",
        *STEP5A_PREDICTORS,
    ]
    pandas_input = data.select(fit_columns).to_pandas()
    estimator = CoxTimeVaryingFitter(
        alpha=1.0 - float(confidence_level),
        penalizer=0.0,
        l1_ratio=0.0,
    )

    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            estimator.fit(
                pandas_input,
                id_col="loan_id",
                start_col="start_time_month",
                stop_col="stop_time_month",
                event_col="default_event",
                robust=False,
                show_progress=False,
            )
    except (ConvergenceError, np.linalg.LinAlgError) as exc:
        raise TimeVaryingCoxModelError(
            f"Time-varying Cox fit failed to converge: {exc}"
        ) from exc
    except Exception as exc:
        raise TimeVaryingCoxModelError(
            f"Time-varying Cox fit failed: {exc}"
        ) from exc

    convergence_warning = _warning_text(caught)
    summary = estimator.summary.loc[STEP5A_PREDICTORS]
    coefficient_ci = estimator.confidence_intervals_.loc[STEP5A_PREDICTORS]
    lower_hr = np.exp(coefficient_ci.iloc[:, 0])
    upper_hr = np.exp(coefficient_ci.iloc[:, 1])

    coefficient_rows = []
    for variable in STEP5A_PREDICTORS:
        coefficient_rows.append({
            "model_type": "time_varying_cox",
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
        schema=TIME_VARYING_COX_RESULT_DTYPES,
    )

    first_starts = data.group_by("loan_id").agg(
        pl.col("start_time_month").min().alias("first_start")
    )
    diagnostic_row = {
        "model_type": "time_varying_cox",
        "endpoint": "default",
        "n_intervals": data.height,
        "n_loans": n_loans,
        "n_events": n_events,
        "n_censored_loans": n_loans - n_events,
        "n_predictors": len(STEP5A_PREDICTORS),
        "n_delayed_entry_loans": int(
            (first_starts["first_start"] > 0).sum()
        ),
        "n_gap_intervals": int(data["gap_interval_flag"].sum()),
        "max_interval_length_months": int(
            data["interval_length_months"].max()
        ),
        "variance_type": "model_based",
        "log_likelihood": float(estimator.log_likelihood_),
        "partial_aic": float(estimator.AIC_partial_),
        "convergence_status": "WARNING" if convergence_warning else "PASS",
        "convergence_warning": convergence_warning,
    }
    diagnostics = pl.DataFrame(
        [diagnostic_row],
        schema=TIME_VARYING_COX_DIAGNOSTIC_DTYPES,
    )

    numeric_coefficients = coefficients.select(
        pl.exclude("model_type", "endpoint", "variable")
    ).to_numpy()
    numeric_diagnostics = np.array([
        diagnostic_row["log_likelihood"],
        diagnostic_row["partial_aic"],
    ])
    if not np.isfinite(numeric_coefficients).all() or not np.isfinite(
        numeric_diagnostics
    ).all():
        raise TimeVaryingCoxModelError(
            "Time-varying Cox fit produced non-finite estimates."
        )

    return TimeVaryingCoxFitResult(estimator, coefficients, diagnostics)


def _validate_result_schema(
    frame: FrameLike,
    expected: dict[str, pl.DataType],
    label: str,
) -> pl.DataFrame:
    source = _as_lazy(frame)
    schema = source.collect_schema()
    if schema.names() != list(expected):
        raise TimeVaryingCoxModelError(
            f"{label} columns do not match the canonical order."
        )
    mismatches = {
        name: {"expected": str(dtype), "actual": str(schema[name])}
        for name, dtype in expected.items()
        if schema[name] != dtype
    }
    if mismatches:
        raise TimeVaryingCoxModelError(
            f"{label} has incompatible column types: {mismatches}."
        )
    return source.collect()


def validate_time_varying_cox_results(frame: FrameLike) -> pl.DataFrame:
    """Validate the public twelve-row Step 5A coefficient table."""
    data = _validate_result_schema(
        frame,
        TIME_VARYING_COX_RESULT_DTYPES,
        "Time-varying Cox results",
    )
    if (
        data.height != len(STEP5A_PREDICTORS)
        or data["variable"].to_list() != STEP5A_PREDICTORS
    ):
        raise TimeVaryingCoxModelError(
            "Time-varying Cox results must contain the locked predictors in order."
        )
    numeric = data.select(
        pl.exclude("model_type", "endpoint", "variable")
    ).to_numpy()
    valid_limits = data.select(
        (pl.col("hazard_ratio") > 0)
        & (pl.col("ci_lower") > 0)
        & (pl.col("ci_lower") <= pl.col("hazard_ratio"))
        & (pl.col("hazard_ratio") <= pl.col("ci_upper"))
    ).to_series()
    if not np.isfinite(numeric).all() or not valid_limits.all():
        raise TimeVaryingCoxModelError(
            "Time-varying Cox results contain invalid estimates."
        )
    return data


def validate_time_varying_cox_diagnostics(frame: FrameLike) -> pl.DataFrame:
    """Validate the one-row Step 5A diagnostic contract."""
    data = _validate_result_schema(
        frame,
        TIME_VARYING_COX_DIAGNOSTIC_DTYPES,
        "Time-varying Cox diagnostics",
    )
    if data.height != 1:
        raise TimeVaryingCoxModelError(
            "Time-varying Cox diagnostics must contain exactly one row."
        )
    row = data.row(0, named=True)
    if row["variance_type"] != "model_based":
        raise TimeVaryingCoxModelError(
            "Step 5A variance_type must be model_based."
        )
    if row["n_events"] + row["n_censored_loans"] != row["n_loans"]:
        raise TimeVaryingCoxModelError("Diagnostic loan counts are inconsistent.")
    if row["n_predictors"] != len(STEP5A_PREDICTORS):
        raise TimeVaryingCoxModelError("Diagnostic predictor count is inconsistent.")
    if row["n_intervals"] < row["n_loans"]:
        raise TimeVaryingCoxModelError("Diagnostic interval count is inconsistent.")
    if row["max_interval_length_months"] < 1:
        raise TimeVaryingCoxModelError("Diagnostic interval length is invalid.")
    if row["convergence_status"] not in {"PASS", "WARNING"}:
        raise TimeVaryingCoxModelError("Diagnostic convergence status is invalid.")
    if row["convergence_status"] == "PASS" and row["convergence_warning"]:
        raise TimeVaryingCoxModelError("PASS diagnostics cannot contain a warning.")
    if not np.isfinite([row["log_likelihood"], row["partial_aic"]]).all():
        raise TimeVaryingCoxModelError("Diagnostics contain non-finite estimates.")
    return data


def write_time_varying_cox_artifacts(
    result: TimeVaryingCoxFitResult,
    coefficients_path: PathSource,
    diagnostics_path: PathSource,
) -> tuple[Path, Path]:
    """Validate and atomically write Step 5A Parquet artifacts."""
    coefficients = validate_time_varying_cox_results(result.coefficients)
    diagnostics = validate_time_varying_cox_diagnostics(result.diagnostics)
    outputs = (Path(coefficients_path), Path(diagnostics_path))
    frames = (coefficients, diagnostics)
    temporary_paths: list[Path] = []
    try:
        for output_frame, output in zip(frames, outputs, strict=True):
            output.parent.mkdir(parents=True, exist_ok=True)
            temporary = output.with_suffix(".tmp.parquet")
            output_frame.write_parquet(temporary, compression="zstd")
            temporary_paths.append(temporary)
        for temporary, output in zip(temporary_paths, outputs, strict=True):
            temporary.replace(output)
    finally:
        for temporary in temporary_paths:
            temporary.unlink(missing_ok=True)
    return outputs
