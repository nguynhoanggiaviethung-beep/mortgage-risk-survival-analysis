"""Paired static-covariate cause-specific Cox models.

For each cause, the other research event is censored at its actual exit time.
The module preserves the canonical absolute entry/exit time scale and passes
``entry_time_month`` to lifelines; it does not use Fine-Gray risk sets.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import TypeAlias

import numpy as np
import polars as pl
from lifelines import CoxPHFitter
from lifelines.exceptions import ConvergenceError, ConvergenceWarning

from src.data.model_dataset import CORE_COLUMNS
from src.survival.cox_model import COX_DIAGNOSTIC_DTYPES, COX_RESULT_DTYPES


FrameLike: TypeAlias = pl.DataFrame | pl.LazyFrame
PathSource: TypeAlias = str | PathLike[str]

CAUSES = ("DEFAULT", "PREPAYMENT")
EVENT_COLUMNS = {"DEFAULT": "default_event", "PREPAYMENT": "prepayment_event"}

CAUSE_SPECIFIC_INPUT_DTYPES: dict[str, pl.DataType] = {
    "loan_id": pl.String,
    "vintage_year": pl.Int16,
    "entry_time_month": pl.Int32,
    "exit_time_month": pl.Int32,
    "duration_months": pl.Int32,
    "default_event": pl.Int8,
    "prepayment_event": pl.Int8,
    "event_type": pl.String,
    "fico": pl.Int16,
    "original_ltv": pl.Float64,
    "original_dti": pl.Float64,
    "original_interest_rate": pl.Float64,
    "original_loan_term": pl.Int16,
}
CAUSE_SPECIFIC_RESULT_DTYPES = dict(COX_RESULT_DTYPES)
CAUSE_SPECIFIC_DIAGNOSTIC_DTYPES = dict(COX_DIAGNOSTIC_DTYPES)
CAUSE_SPECIFIC_RESULT_COLUMNS = list(CAUSE_SPECIFIC_RESULT_DTYPES)
CAUSE_SPECIFIC_DIAGNOSTIC_COLUMNS = list(CAUSE_SPECIFIC_DIAGNOSTIC_DTYPES)


class CauseSpecificModelError(ValueError):
    """Raised when a cause-specific input, fit, or result is invalid."""


@dataclass(frozen=True)
class CauseSpecificFitResult:
    model: CoxPHFitter
    coefficients: pl.DataFrame
    diagnostics: pl.DataFrame


@dataclass(frozen=True)
class CauseSpecificPairResult:
    default: CauseSpecificFitResult
    prepayment: CauseSpecificFitResult


def _as_lazy(frame: FrameLike) -> pl.LazyFrame:
    if isinstance(frame, pl.DataFrame):
        return frame.lazy()
    if isinstance(frame, pl.LazyFrame):
        return frame
    raise TypeError("Expected a Polars DataFrame or LazyFrame.")


def _validate_cause(cause: str) -> str:
    if cause not in CAUSES:
        raise CauseSpecificModelError(
            f"Unknown cause {cause!r}; expected one of {CAUSES}."
        )
    return cause


def validate_cause_specific_input(frame: FrameLike) -> pl.DataFrame:
    """Validate a complete-case, one-row-per-loan paired Cox input."""
    source = _as_lazy(frame)
    schema = source.collect_schema()
    missing = [name for name in CAUSE_SPECIFIC_INPUT_DTYPES if name not in schema]
    if missing:
        raise CauseSpecificModelError(
            f"Cause-specific input is missing required columns: {missing}."
        )
    mismatches = {
        name: {"expected": str(dtype), "actual": str(schema[name])}
        for name, dtype in CAUSE_SPECIFIC_INPUT_DTYPES.items()
        if schema[name] != dtype
    }
    if mismatches:
        raise CauseSpecificModelError(
            f"Cause-specific input has incompatible column types: {mismatches}."
        )

    expected_default = (pl.col("event_type") == "DEFAULT").cast(pl.Int8)
    expected_prepayment = (pl.col("event_type") == "PREPAYMENT").cast(pl.Int8)
    valid_event = (
        pl.col("event_type").is_in(["DEFAULT", "PREPAYMENT", "CENSOR"])
        & pl.col("default_event").is_in([0, 1])
        & pl.col("prepayment_event").is_in([0, 1])
        & (pl.col("default_event") == expected_default)
        & (pl.col("prepayment_event") == expected_prepayment)
        & ((pl.col("default_event") + pl.col("prepayment_event")) <= 1)
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
        pl.col("default_event").sum().alias("default_events"),
        pl.col("prepayment_event").sum().alias("prepayment_events"),
    ).collect().to_dicts()[0]

    if stats["rows"] == 0:
        raise CauseSpecificModelError("Cause-specific input is empty.")
    if stats["missing_loan_id"]:
        raise CauseSpecificModelError("Cause-specific input contains null loan_id values.")
    if stats["rows"] != stats["unique_loans"]:
        raise CauseSpecificModelError("Cause-specific input contains duplicate loan_id values.")
    if stats["invalid_event"]:
        raise CauseSpecificModelError(
            f"Cause-specific input has {stats['invalid_event']} invalid or "
            "inconsistent event row(s)."
        )
    if stats["invalid_time"]:
        raise CauseSpecificModelError(
            f"Cause-specific input has {stats['invalid_time']} invalid "
            "entry/exit/duration row(s)."
        )
    if stats["incomplete_predictors"]:
        raise CauseSpecificModelError(
            f"Cause-specific input has {stats['incomplete_predictors']} row(s) "
            "with missing or non-finite predictors."
        )
    for label in ("default_events", "prepayment_events"):
        if stats[label] == 0 or stats[label] == stats["rows"]:
            raise CauseSpecificModelError(
                "Paired cause-specific input must contain each research cause "
                "and non-event rows."
            )
    return source.collect()


def _warning_text(records: list[warnings.WarningMessage]) -> str:
    messages = [
        str(record.message)
        for record in records
        if issubclass(record.category, ConvergenceWarning)
    ]
    return " | ".join(dict.fromkeys(messages))


def fit_cause_specific_model(
    frame: FrameLike,
    cause: str,
    confidence_level: float = 0.95,
) -> CauseSpecificFitResult:
    """Fit one locked unpenalized cause-specific Cox model."""
    endpoint = _validate_cause(cause)
    if not isinstance(confidence_level, (int, float)) or isinstance(
        confidence_level, bool
    ):
        raise CauseSpecificModelError("confidence_level must be numeric.")
    if not 0.0 < float(confidence_level) < 1.0:
        raise CauseSpecificModelError(
            "confidence_level must be strictly between 0 and 1."
        )

    data = validate_cause_specific_input(frame)
    event_column = EVENT_COLUMNS[endpoint]
    fit_input = data.select(
        "entry_time_month", "exit_time_month", event_column, *CORE_COLUMNS
    ).to_pandas()
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
                fit_input,
                duration_col="exit_time_month",
                event_col=event_column,
                entry_col="entry_time_month",
                robust=False,
                batch_mode=None,
                show_progress=False,
            )
    except (ConvergenceError, np.linalg.LinAlgError) as exc:
        raise CauseSpecificModelError(
            f"{endpoint} cause-specific Cox fit failed to converge: {exc}"
        ) from exc
    except Exception as exc:
        raise CauseSpecificModelError(
            f"{endpoint} cause-specific Cox fit failed: {exc}"
        ) from exc

    convergence_warning = _warning_text(caught)
    summary = estimator.summary.loc[CORE_COLUMNS]
    coefficient_ci = estimator.confidence_intervals_.loc[CORE_COLUMNS]
    lower_hr = np.exp(coefficient_ci.iloc[:, 0])
    upper_hr = np.exp(coefficient_ci.iloc[:, 1])
    coefficient_rows = [
        {
            "model_type": "CAUSE_SPECIFIC_COX",
            "endpoint": endpoint,
            "variable": variable,
            "coefficient": float(summary.loc[variable, "coef"]),
            "hazard_ratio": float(summary.loc[variable, "exp(coef)"]),
            "standard_error": float(summary.loc[variable, "se(coef)"]),
            "ci_lower": float(lower_hr.loc[variable]),
            "ci_upper": float(upper_hr.loc[variable]),
            "p_value": float(summary.loc[variable, "p"]),
            "z_statistic": float(summary.loc[variable, "z"]),
        }
        for variable in CORE_COLUMNS
    ]
    coefficients = pl.DataFrame(
        coefficient_rows, schema=CAUSE_SPECIFIC_RESULT_DTYPES
    )

    n_observations = data.height
    n_events = int(data[event_column].sum())
    diagnostic_row = {
        "model_type": "CAUSE_SPECIFIC_COX",
        "endpoint": endpoint,
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
        [diagnostic_row], schema=CAUSE_SPECIFIC_DIAGNOSTIC_DTYPES
    )
    result = CauseSpecificFitResult(estimator, coefficients, diagnostics)
    validate_cause_specific_results(coefficients, endpoint=endpoint)
    validate_cause_specific_diagnostics(diagnostics, endpoint=endpoint)
    return result


def fit_paired_cause_specific_models(
    frame: FrameLike,
    confidence_level: float = 0.95,
) -> CauseSpecificPairResult:
    """Fit DEFAULT and PREPAYMENT cause-specific models on identical rows."""
    data = validate_cause_specific_input(frame)
    return CauseSpecificPairResult(
        default=fit_cause_specific_model(data, "DEFAULT", confidence_level),
        prepayment=fit_cause_specific_model(data, "PREPAYMENT", confidence_level),
    )


def _validate_schema(
    frame: FrameLike,
    expected: dict[str, pl.DataType],
    label: str,
) -> pl.DataFrame:
    source = _as_lazy(frame)
    schema = source.collect_schema()
    if schema.names() != list(expected):
        raise CauseSpecificModelError(
            f"{label} columns do not match the canonical order: {list(expected)}."
        )
    mismatches = {
        name: {"expected": str(dtype), "actual": str(schema[name])}
        for name, dtype in expected.items()
        if schema[name] != dtype
    }
    if mismatches:
        raise CauseSpecificModelError(
            f"{label} has incompatible column types: {mismatches}."
        )
    return source.collect()


def validate_cause_specific_results(
    frame: FrameLike,
    endpoint: str | None = None,
) -> pl.DataFrame:
    """Validate a five-row cause-specific coefficient artifact."""
    data = _validate_schema(
        frame, CAUSE_SPECIFIC_RESULT_DTYPES, "Cause-specific results"
    )
    expected_endpoint = _validate_cause(endpoint) if endpoint is not None else None
    endpoints = data["endpoint"].unique().to_list()
    if (
        data.height != len(CORE_COLUMNS)
        or data["variable"].to_list() != CORE_COLUMNS
        or data["model_type"].unique().to_list() != ["CAUSE_SPECIFIC_COX"]
        or len(endpoints) != 1
        or endpoints[0] not in CAUSES
        or (expected_endpoint is not None and endpoints[0] != expected_endpoint)
    ):
        raise CauseSpecificModelError(
            "Cause-specific results have invalid identity or predictor rows."
        )
    numeric = data.select(
        pl.exclude("model_type", "endpoint", "variable")
    ).to_numpy()
    limits = data.select(
        (pl.col("hazard_ratio") > 0)
        & (pl.col("ci_lower") > 0)
        & (pl.col("ci_lower") <= pl.col("hazard_ratio"))
        & (pl.col("hazard_ratio") <= pl.col("ci_upper"))
    ).to_series()
    if not np.isfinite(numeric).all() or not limits.all():
        raise CauseSpecificModelError(
            "Cause-specific results contain invalid or non-finite estimates."
        )
    return data


def validate_cause_specific_diagnostics(
    frame: FrameLike,
    endpoint: str | None = None,
) -> pl.DataFrame:
    """Validate one cause-specific model diagnostic row."""
    data = _validate_schema(
        frame, CAUSE_SPECIFIC_DIAGNOSTIC_DTYPES, "Cause-specific diagnostics"
    )
    if data.height != 1:
        raise CauseSpecificModelError(
            "Cause-specific diagnostics must contain exactly one row."
        )
    row = data.row(0, named=True)
    expected_endpoint = _validate_cause(endpoint) if endpoint is not None else None
    if row["model_type"] != "CAUSE_SPECIFIC_COX" or row["endpoint"] not in CAUSES:
        raise CauseSpecificModelError("Cause-specific diagnostic identity is invalid.")
    if expected_endpoint is not None and row["endpoint"] != expected_endpoint:
        raise CauseSpecificModelError("Cause-specific diagnostic endpoint is invalid.")
    if row["n_events"] + row["n_censored"] != row["n_observations"]:
        raise CauseSpecificModelError("Cause-specific diagnostic counts are inconsistent.")
    if row["n_predictors"] != len(CORE_COLUMNS):
        raise CauseSpecificModelError("Cause-specific predictor count is inconsistent.")
    if row["convergence_status"] not in {"PASS", "WARNING"}:
        raise CauseSpecificModelError("Cause-specific convergence status is invalid.")
    if row["convergence_status"] == "PASS" and row["convergence_warning"]:
        raise CauseSpecificModelError("PASS diagnostics cannot contain a warning.")
    if not np.isfinite([
        row["log_likelihood"], row["partial_aic"], row["concordance_index"]
    ]).all():
        raise CauseSpecificModelError("Cause-specific diagnostics are non-finite.")
    return data


def write_cause_specific_artifacts(
    result: CauseSpecificFitResult,
    coefficients_path: PathSource,
    diagnostics_path: PathSource,
) -> tuple[Path, Path]:
    """Validate and atomically write one cause-specific model's artifacts."""
    endpoint = result.coefficients["endpoint"].item(0)
    coefficients = validate_cause_specific_results(
        result.coefficients, endpoint=endpoint
    )
    diagnostics = validate_cause_specific_diagnostics(
        result.diagnostics, endpoint=endpoint
    )
    outputs = (Path(coefficients_path), Path(diagnostics_path))
    temporary_paths: list[Path] = []
    try:
        for output_frame, output in zip(
            (coefficients, diagnostics), outputs, strict=True
        ):
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
