"""Single-event Kaplan-Meier estimation for validated loan-level inputs.

The default endpoint is ``km_default_event``. Default is the event of
interest; prepayment and ordinary/administrative censoring are right-censored
for this estimator. Delayed entry is preserved by passing
``entry_time_month`` to lifelines.

``event_probability`` is ``1 - survival`` from a single-event Kaplan-Meier
model. It is not a competing-risk default CIF or the project's official
competing-risk PD(t).

Expected input comes from :mod:`src.survival.model_input` and has one row per
loan. Polars is retained outside the narrow pandas/lifelines fitting boundary.
"""

from __future__ import annotations

from os import PathLike
from pathlib import Path
from typing import TypeAlias

import pandas as pd
import polars as pl
from lifelines import KaplanMeierFitter


FrameLike: TypeAlias = pl.DataFrame | pl.LazyFrame
PathSource: TypeAlias = str | PathLike[str]

KM_INPUT_DTYPES: dict[str, pl.DataType] = {
    "loan_id": pl.String,
    "vintage_year": pl.Int16,
    "entry_time_month": pl.Int32,
    "exit_time_month": pl.Int32,
    "duration_months": pl.Int32,
    "km_default_event": pl.Int8,
    "event_type": pl.String,
}

KM_RESULT_DTYPES: dict[str, pl.DataType] = {
    "model_type": pl.String,
    "endpoint": pl.String,
    "group_name": pl.String,
    "group_value": pl.String,
    "analysis_time": pl.Int32,
    "survival": pl.Float64,
    "ci_lower": pl.Float64,
    "ci_upper": pl.Float64,
    "event_probability": pl.Float64,
    "n_at_risk": pl.UInt32,
    "n_events": pl.UInt32,
    "n_censored": pl.UInt32,
}

KM_RESULT_COLUMNS = list(KM_RESULT_DTYPES)


class KaplanMeierInputError(ValueError):
    """Raised when an input violates the Kaplan-Meier contract."""


def _as_lazy(frame: FrameLike) -> pl.LazyFrame:
    if isinstance(frame, pl.DataFrame):
        return frame.lazy()
    if isinstance(frame, pl.LazyFrame):
        return frame
    raise TypeError("Expected a Polars DataFrame or LazyFrame.")


def validate_km_input(
    frame: FrameLike,
    group_col: str | None = None,
) -> pl.DataFrame:
    """Validate and collect a one-row-per-loan Default-KM input.

    Extra columns are preserved so callers may supply an existing grouping
    column. Null grouping values are rejected rather than silently dropped or
    assigned to a synthetic category.
    """
    source = _as_lazy(frame)
    schema = source.collect_schema()

    missing = [name for name in KM_INPUT_DTYPES if name not in schema]
    if missing:
        raise KaplanMeierInputError(
            f"Kaplan-Meier input is missing required columns: {missing}."
        )

    mismatches = {
        name: {"expected": str(dtype), "actual": str(schema[name])}
        for name, dtype in KM_INPUT_DTYPES.items()
        if schema[name] != dtype
    }
    if mismatches:
        raise KaplanMeierInputError(
            f"Kaplan-Meier input has incompatible column types: {mismatches}."
        )

    if group_col is not None and group_col not in schema:
        raise KaplanMeierInputError(
            f"Grouping column does not exist: {group_col!r}."
        )

    expected_event = (pl.col("event_type") == "DEFAULT").cast(pl.Int8)
    valid_event = (
        pl.col("event_type").is_in(["DEFAULT", "PREPAYMENT", "CENSOR"])
        & pl.col("km_default_event").is_in([0, 1])
        & (pl.col("km_default_event") == expected_event)
    ).fill_null(False)
    valid_time = (
        pl.col("entry_time_month").is_not_null()
        & pl.col("exit_time_month").is_not_null()
        & pl.col("duration_months").is_not_null()
        & (pl.col("entry_time_month") >= 0)
        & (pl.col("exit_time_month") > pl.col("entry_time_month"))
        & (pl.col("duration_months") == pl.col("exit_time_month"))
    ).fill_null(False)

    expressions: list[pl.Expr] = [
        pl.len().alias("rows"),
        pl.col("loan_id").n_unique().alias("unique_loans"),
        pl.col("loan_id").null_count().alias("missing_loan_id"),
        (~valid_event).sum().alias("invalid_event"),
        (~valid_time).sum().alias("invalid_time"),
    ]
    if group_col is not None:
        expressions.append(
            pl.col(group_col).null_count().alias("missing_group")
        )

    stats = source.select(expressions).collect().to_dicts()[0]
    if stats["rows"] == 0:
        raise KaplanMeierInputError("Kaplan-Meier input is empty.")
    if stats["missing_loan_id"]:
        raise KaplanMeierInputError("Kaplan-Meier input contains null loan_id values.")
    if stats["rows"] != stats["unique_loans"]:
        raise KaplanMeierInputError(
            "Kaplan-Meier input contains duplicate loan_id values."
        )
    if stats["invalid_event"]:
        raise KaplanMeierInputError(
            f"Kaplan-Meier input has {stats['invalid_event']} invalid or "
            "inconsistent event row(s)."
        )
    if stats["invalid_time"]:
        raise KaplanMeierInputError(
            f"Kaplan-Meier input has {stats['invalid_time']} invalid "
            "entry/exit/duration row(s)."
        )
    if group_col is not None and stats["missing_group"]:
        raise KaplanMeierInputError(
            f"Grouping column {group_col!r} contains null values."
        )

    return source.collect()


def _monthly_counts(
    event_table: pd.DataFrame,
    timeline: list[int],
) -> pd.DataFrame:
    """Return beginning-of-time risk sets and removals on a monthly grid.

    The risk set is the denominator immediately before event/censor removals at
    time ``t`` and after entries at ``t``. Equivalently, a loan contributes at
    ``t`` exactly when ``entry_time_month <= t <= exit_time_month``.
    """
    table = event_table.reindex(timeline, fill_value=0)
    prior_removed = table["removed"].cumsum().shift(1, fill_value=0)
    table["n_at_risk"] = table["entrance"].cumsum() - prior_removed
    return table[["n_at_risk", "observed", "censored"]]


def _fit_one_curve(
    data: pl.DataFrame,
    group_name: str,
    group_value: str,
    confidence_level: float,
) -> pl.DataFrame:
    minimum_time = int(data["entry_time_month"].min())
    maximum_time = int(data["exit_time_month"].max())
    timeline = list(range(minimum_time, maximum_time + 1))

    fit_data = data.select(
        "exit_time_month",
        "km_default_event",
        "entry_time_month",
    ).to_pandas()

    estimator = KaplanMeierFitter(alpha=1.0 - confidence_level)
    estimator.fit(
        durations=fit_data["exit_time_month"],
        event_observed=fit_data["km_default_event"],
        entry=fit_data["entry_time_month"],
        timeline=timeline,
        label="survival",
        ci_labels=("ci_lower", "ci_upper"),
    )

    estimates = estimator.survival_function_.join(
        estimator.confidence_interval_survival_function_
    )
    counts = _monthly_counts(estimator.event_table, timeline)
    result = estimates.join(counts).reset_index(names="analysis_time")
    result["event_probability"] = 1.0 - result["survival"]
    result["model_type"] = "kaplan_meier"
    result["endpoint"] = "default"
    result["group_name"] = group_name
    result["group_value"] = group_value
    result = result.rename(
        columns={"observed": "n_events", "censored": "n_censored"}
    )

    return pl.from_pandas(result[KM_RESULT_COLUMNS]).cast(KM_RESULT_DTYPES)


def fit_kaplan_meier(
    frame: FrameLike,
    group_col: str | None = None,
    confidence_level: float = 0.95,
) -> pl.DataFrame:
    """Fit overall or grouped single-event Default Kaplan-Meier curves.

    Each curve uses an integer monthly grid from its minimum entry time through
    its maximum exit time. No value is extrapolated outside that curve's
    observed follow-up range. Confidence intervals are produced by the
    installed ``KaplanMeierFitter`` implementation using lifelines' Greenwood
    exponential/log-log method.
    """
    if not isinstance(confidence_level, (int, float)) or isinstance(
        confidence_level, bool
    ):
        raise KaplanMeierInputError("confidence_level must be numeric.")
    if not 0.0 < float(confidence_level) < 1.0:
        raise KaplanMeierInputError(
            "confidence_level must be strictly between 0 and 1."
        )

    data = validate_km_input(frame, group_col=group_col)
    level = float(confidence_level)

    if group_col is None:
        return _fit_one_curve(data, "portfolio", "all", level)

    results = []
    for group in data.sort(group_col).partition_by(
        group_col,
        maintain_order=True,
    ):
        group_value = str(group[group_col][0])
        results.append(
            _fit_one_curve(group, group_col, group_value, level)
        )

    return pl.concat(results).sort(["group_value", "analysis_time"])


def validate_km_results(frame: FrameLike) -> pl.DataFrame:
    """Validate the persisted/public Kaplan-Meier result schema and values."""
    source = _as_lazy(frame)
    schema = source.collect_schema()
    if schema.names() != KM_RESULT_COLUMNS:
        raise KaplanMeierInputError(
            "Kaplan-Meier result columns do not match the canonical order: "
            f"{KM_RESULT_COLUMNS}."
        )
    mismatches = {
        name: {"expected": str(dtype), "actual": str(schema[name])}
        for name, dtype in KM_RESULT_DTYPES.items()
        if schema[name] != dtype
    }
    if mismatches:
        raise KaplanMeierInputError(
            f"Kaplan-Meier result has incompatible types: {mismatches}."
        )

    valid_probability = (
        pl.col("survival").is_between(0.0, 1.0)
        & pl.col("ci_lower").is_between(0.0, 1.0)
        & pl.col("ci_upper").is_between(0.0, 1.0)
        & (pl.col("ci_lower") <= pl.col("survival"))
        & (pl.col("survival") <= pl.col("ci_upper"))
        & (
            (pl.col("event_probability") - (1.0 - pl.col("survival")))
            .abs()
            <= 1e-12
        )
    ).fill_null(False)
    stats = source.select(
        pl.len().alias("rows"),
        (~valid_probability).sum().alias("invalid_probability"),
        pl.any_horizontal(
            [pl.col(name).is_null() for name in KM_RESULT_COLUMNS]
        ).sum().alias("null_rows"),
    ).collect().to_dicts()[0]
    if stats["rows"] == 0:
        raise KaplanMeierInputError("Kaplan-Meier result is empty.")
    if stats["invalid_probability"] or stats["null_rows"]:
        raise KaplanMeierInputError(
            f"Kaplan-Meier result contains invalid values: {stats}."
        )
    return source.collect()


def write_km_results(frame: FrameLike, path: PathSource) -> Path:
    """Validate and atomically write a Kaplan-Meier result Parquet file."""
    result = validate_km_results(frame)
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".tmp.parquet")
    result.write_parquet(temporary, compression="zstd")
    temporary.replace(output)
    return output
