"""Step 5A counting-process input for the time-varying default Cox model.

The locked loan-level event mapping supplies entry, exit, and event type.  A
performance value observed at time ``t`` is carried piecewise-constantly over
the interval after ``t``.  Consequently, a terminal-month performance value
is never used to predict the event ending in that same month.
"""

from __future__ import annotations

from typing import TypeAlias

import polars as pl

from src.data.model_dataset import CORE_COLUMNS
from src.survival.model_input import validate_loan_level_input


FrameLike: TypeAlias = pl.DataFrame | pl.LazyFrame

TIME_VARYING_COLUMNS = [
    "lag_current_actual_upb",
    "lag_current_interest_rate",
    "lag_dq_1m",
    "lag_dq_2m",
    "lag_dq_3plus",
    "lag_dq_xx",
    "lag_dq_ra",
]

TV_COX_TIME_VARYING_PREDICTORS = [
    "lag_current_actual_upb",
    "lag_current_interest_rate",
    "lag_dq_3plus",
]

STEP5A_PREDICTORS = [*CORE_COLUMNS, *TV_COX_TIME_VARYING_PREDICTORS]

TIME_VARYING_INPUT_DTYPES: dict[str, pl.DataType] = {
    "loan_id": pl.String,
    "vintage_year": pl.Int16,
    "covariate_month": pl.Date,
    "source_reporting_period_num": pl.Int32,
    "start_time_month": pl.Int32,
    "stop_time_month": pl.Int32,
    "interval_length_months": pl.Int32,
    "gap_interval_flag": pl.Boolean,
    "terminal_interval_flag": pl.Boolean,
    "default_event": pl.Int8,
    "event_type": pl.String,
    "fico": pl.Int16,
    "original_ltv": pl.Float64,
    "original_dti": pl.Float64,
    "original_interest_rate": pl.Float64,
    "original_loan_term": pl.Int16,
    "lag_current_actual_upb": pl.Float64,
    "lag_current_interest_rate": pl.Float64,
    "lag_dq_1m": pl.Int8,
    "lag_dq_2m": pl.Int8,
    "lag_dq_3plus": pl.Int8,
    "lag_dq_xx": pl.Int8,
    "lag_dq_ra": pl.Int8,
}

TIME_VARYING_INPUT_COLUMNS = list(TIME_VARYING_INPUT_DTYPES)

PERFORMANCE_DTYPES: dict[str, pl.DataType] = {
    "loan_id": pl.String,
    "performance_month": pl.Date,
    "reporting_period_num": pl.Int32,
    "current_actual_upb": pl.Float64,
    "current_interest_rate": pl.Float64,
    "current_delinquency_status": pl.String,
}

LOAN_TIMING_DTYPES: dict[str, pl.DataType] = {
    "first_observed_month": pl.Int32,
    "event_month": pl.Int32,
    "operational_origination_date": pl.Date,
}

ALLOWED_DELINQUENCY_STATUSES = [
    "00",
    "01",
    "02",
    *[f"{value:02d}" for value in range(3, 89)],
    "XX",
    "RA",
]


class TimeVaryingInputError(ValueError):
    """Raised when Step 5A source data or intervals violate the contract."""


def _as_lazy(frame: FrameLike) -> pl.LazyFrame:
    if isinstance(frame, pl.DataFrame):
        return frame.lazy()
    if isinstance(frame, pl.LazyFrame):
        return frame
    raise TypeError("Expected a Polars DataFrame or LazyFrame.")


def _validate_schema(
    frame: pl.LazyFrame,
    expected: dict[str, pl.DataType],
    label: str,
) -> None:
    schema = frame.collect_schema()
    missing = [name for name in expected if name not in schema]
    if missing:
        raise TimeVaryingInputError(
            f"{label} is missing required columns: {missing}."
        )
    mismatches = {
        name: {"expected": str(dtype), "actual": str(schema[name])}
        for name, dtype in expected.items()
        if schema[name] != dtype
    }
    if mismatches:
        raise TimeVaryingInputError(
            f"{label} has incompatible column types: {mismatches}."
        )


def _month_index(column: str) -> pl.Expr:
    return pl.col(column).dt.year() * 12 + pl.col(column).dt.month()


def validate_time_varying_performance_source(
    frame: FrameLike,
) -> pl.LazyFrame:
    """Validate the standardized monthly fields locked for Step 5A."""
    source = _as_lazy(frame)
    _validate_schema(source, PERFORMANCE_DTYPES, "Performance source")

    valid_month = (
        pl.col("performance_month").is_not_null()
        & pl.col("reporting_period_num").is_not_null()
        & (
            pl.col("reporting_period_num")
            == (
                pl.col("performance_month").dt.year() * 100
                + pl.col("performance_month").dt.month()
            )
        )
    ).fill_null(False)
    complete_numeric = pl.all_horizontal([
        pl.col(name).is_not_null()
        & pl.col(name).is_finite().fill_null(False)
        for name in ("current_actual_upb", "current_interest_rate")
    ])
    valid_status = pl.col("current_delinquency_status").is_in(
        ALLOWED_DELINQUENCY_STATUSES
    ).fill_null(False)

    stats = source.select(
        pl.len().alias("rows"),
        pl.col("loan_id").null_count().alias("missing_loan_id"),
        pl.struct(["loan_id", "performance_month"])
        .n_unique()
        .alias("unique_keys"),
        (~valid_month).sum().alias("invalid_month"),
        (~complete_numeric).sum().alias("missing_or_nonfinite_numeric"),
        (~valid_status).sum().alias("invalid_delinquency"),
    ).collect().to_dicts()[0]

    if stats["rows"] == 0:
        raise TimeVaryingInputError("Performance source is empty.")
    if stats["missing_loan_id"]:
        raise TimeVaryingInputError("Performance source contains null loan_id values.")
    if stats["rows"] != stats["unique_keys"]:
        raise TimeVaryingInputError(
            "Performance source contains duplicate (loan_id, performance_month) keys."
        )
    if stats["invalid_month"]:
        raise TimeVaryingInputError(
            "performance_month and reporting_period_num are inconsistent."
        )
    if stats["missing_or_nonfinite_numeric"]:
        raise TimeVaryingInputError(
            "Selected monthly numeric source fields contain missing or non-finite values."
        )
    if stats["invalid_delinquency"]:
        raise TimeVaryingInputError(
            "current_delinquency_status contains missing or unsupported values."
        )
    return source


def build_time_varying_cox_input(
    performance: FrameLike,
    loan_level: FrameLike,
) -> pl.LazyFrame:
    """Build the locked Step 5A piecewise-constant start-stop input.

    Only complete-case loans under the Step 3 static-predictor rule enter the
    result. Missing monthly values are rejected; rows and loans are never
    silently discarded for predictor missingness.
    """
    monthly = validate_time_varying_performance_source(performance)
    loans = validate_loan_level_input(loan_level)
    _validate_schema(loans, LOAN_TIMING_DTYPES, "Loan-level model input")

    loans = (
        loans.filter(pl.col("core_covariates_complete_flag"))
        .select(
            "loan_id",
            "vintage_year",
            "first_observed_month",
            "event_month",
            "operational_origination_date",
            "entry_time_month",
            "exit_time_month",
            "event_type",
            *CORE_COLUMNS,
        )
    )

    source = (
        monthly.select(*PERFORMANCE_DTYPES)
        .join(loans, on="loan_id", how="inner", validate="m:1")
        .with_columns(
            (
                _month_index("performance_month")
                - _month_index("operational_origination_date")
            )
            .cast(pl.Int32)
            .alias("_analysis_time")
        )
        # The terminal-month value is excluded: an observation at t predicts
        # only the hazard after t, never an event ending at t.
        .filter(
            (pl.col("_analysis_time") >= pl.col("entry_time_month"))
            & (pl.col("_analysis_time") < pl.col("exit_time_month"))
        )
        .sort(["loan_id", "_analysis_time"])
        .with_columns(
            pl.col("_analysis_time")
            .shift(-1)
            .over("loan_id")
            .alias("_next_analysis_time")
        )
        .with_columns(
            pl.col("_analysis_time").alias("start_time_month"),
            pl.coalesce("_next_analysis_time", "exit_time_month")
            .cast(pl.Int32)
            .alias("stop_time_month"),
        )
        .with_columns(
            (
                pl.col("stop_time_month") - pl.col("start_time_month")
            )
            .cast(pl.Int32)
            .alias("interval_length_months"),
            (pl.col("stop_time_month") == pl.col("exit_time_month"))
            .alias("terminal_interval_flag"),
            pl.col("current_actual_upb").alias("lag_current_actual_upb"),
            pl.col("current_interest_rate").alias(
                "lag_current_interest_rate"
            ),
            (pl.col("current_delinquency_status") == "01")
            .cast(pl.Int8)
            .alias("lag_dq_1m"),
            (pl.col("current_delinquency_status") == "02")
            .cast(pl.Int8)
            .alias("lag_dq_2m"),
            pl.col("current_delinquency_status")
            .is_in([f"{value:02d}" for value in range(3, 89)])
            .cast(pl.Int8)
            .alias("lag_dq_3plus"),
            (pl.col("current_delinquency_status") == "XX")
            .cast(pl.Int8)
            .alias("lag_dq_xx"),
            (pl.col("current_delinquency_status") == "RA")
            .cast(pl.Int8)
            .alias("lag_dq_ra"),
        )
        .with_columns(
            (pl.col("interval_length_months") > 1).alias(
                "gap_interval_flag"
            ),
            (
                pl.col("terminal_interval_flag")
                & (pl.col("event_type") == "DEFAULT")
            )
            .cast(pl.Int8)
            .alias("default_event"),
        )
        .select(
            "loan_id",
            "vintage_year",
            pl.col("performance_month").alias("covariate_month"),
            pl.col("reporting_period_num").alias(
                "source_reporting_period_num"
            ),
            "start_time_month",
            "stop_time_month",
            "interval_length_months",
            "gap_interval_flag",
            "terminal_interval_flag",
            "default_event",
            "event_type",
            *CORE_COLUMNS,
            *TIME_VARYING_COLUMNS,
        )
    )

    missing_interval_loans = (
        loans.select("loan_id")
        .join(source.select("loan_id").unique(), on="loan_id", how="anti")
        .limit(5)
        .collect()
    )
    if missing_interval_loans.height:
        raise TimeVaryingInputError(
            "Complete-case eligible loans have no usable pre-exit performance "
            f"interval; examples: {missing_interval_loans['loan_id'].to_list()}."
        )

    boundary_mismatches = (
        source.group_by("loan_id")
        .agg(
            pl.col("start_time_month").min().alias("first_start"),
            pl.col("stop_time_month").max().alias("final_stop"),
        )
        .join(
            loans.select(
                "loan_id",
                "entry_time_month",
                "exit_time_month",
            ),
            on="loan_id",
            how="inner",
            validate="1:1",
        )
        .filter(
            (pl.col("first_start") != pl.col("entry_time_month"))
            | (pl.col("final_stop") != pl.col("exit_time_month"))
        )
        .select("loan_id")
        .limit(5)
        .collect()
    )
    if boundary_mismatches.height:
        raise TimeVaryingInputError(
            "Constructed intervals do not preserve locked entry/exit times; "
            f"examples: {boundary_mismatches['loan_id'].to_list()}."
        )

    return validate_time_varying_cox_input(source).lazy()


def validate_time_varying_cox_input(frame: FrameLike) -> pl.DataFrame:
    """Validate and collect the canonical Step 5A interval table."""
    source = _as_lazy(frame)
    _validate_schema(source, TIME_VARYING_INPUT_DTYPES, "Time-varying Cox input")
    schema = source.collect_schema()
    if schema.names() != TIME_VARYING_INPUT_COLUMNS:
        raise TimeVaryingInputError(
            "Time-varying Cox input columns do not match the canonical order."
        )

    data = source.collect().sort(["loan_id", "start_time_month"])
    if data.height == 0:
        raise TimeVaryingInputError("Time-varying Cox input is empty.")

    complete_predictors = pl.all_horizontal([
        pl.col(name).is_not_null()
        & pl.col(name).cast(pl.Float64).is_finite().fill_null(False)
        for name in STEP5A_PREDICTORS
    ])
    valid_flags = (
        pl.all_horizontal([
            pl.col(name).is_in([0, 1])
            for name in TIME_VARYING_COLUMNS[2:]
        ])
        & (
            pl.sum_horizontal([
                pl.col(name) for name in TIME_VARYING_COLUMNS[2:]
            ])
            <= 1
        )
    ).fill_null(False)
    valid_interval = (
        (pl.col("start_time_month") >= 0)
        & (pl.col("stop_time_month") > pl.col("start_time_month"))
        & (
            pl.col("interval_length_months")
            == pl.col("stop_time_month") - pl.col("start_time_month")
        )
        & (
            pl.col("gap_interval_flag")
            == (pl.col("interval_length_months") > 1)
        )
    ).fill_null(False)
    previous_stop = pl.col("stop_time_month").shift(1).over("loan_id")
    previous_loan = pl.col("loan_id").shift(1)
    contiguous = (
        (pl.col("loan_id") != previous_loan)
        | (pl.col("start_time_month") == previous_stop)
    ).fill_null(True)

    stats = data.lazy().select(
        pl.len().alias("rows"),
        pl.col("loan_id").null_count().alias("missing_loan_id"),
        pl.struct(["loan_id", "start_time_month", "stop_time_month"])
        .n_unique()
        .alias("unique_keys"),
        (~valid_interval).sum().alias("invalid_interval"),
        (~contiguous).sum().alias("noncontiguous_or_overlapping"),
        (~complete_predictors).sum().alias("missing_or_nonfinite_predictors"),
        (~valid_flags).sum().alias("invalid_delinquency_flags"),
    ).collect().to_dicts()[0]

    if stats["missing_loan_id"]:
        raise TimeVaryingInputError("Time-varying input contains null loan_id values.")
    if stats["rows"] != stats["unique_keys"]:
        raise TimeVaryingInputError("Time-varying input contains duplicate interval keys.")
    if stats["invalid_interval"]:
        raise TimeVaryingInputError(
            "Time-varying input contains invalid start-stop intervals or flags."
        )
    if stats["noncontiguous_or_overlapping"]:
        raise TimeVaryingInputError(
            "Intervals within a loan must be ordered, contiguous, and non-overlapping."
        )
    if stats["missing_or_nonfinite_predictors"]:
        raise TimeVaryingInputError(
            "Time-varying input contains missing or non-finite predictors."
        )
    if stats["invalid_delinquency_flags"]:
        raise TimeVaryingInputError(
            "Lagged delinquency indicators must be mutually exclusive binary values."
        )

    static_variation = (
        data.lazy()
        .group_by("loan_id")
        .agg([pl.col(name).n_unique().alias(name) for name in CORE_COLUMNS])
        .filter(pl.any_horizontal([pl.col(name) != 1 for name in CORE_COLUMNS]))
        .limit(5)
        .collect()
    )
    if static_variation.height:
        raise TimeVaryingInputError(
            "Static predictors vary within a loan; examples: "
            f"{static_variation['loan_id'].to_list()}."
        )

    loan_checks = (
        data.lazy()
        .group_by("loan_id")
        .agg(
            pl.col("event_type").n_unique().alias("event_types"),
            pl.col("event_type").first().alias("event_type"),
            pl.col("default_event").sum().alias("events"),
            pl.col("terminal_interval_flag").sum().alias("terminal_rows"),
            pl.col("default_event").last().alias("last_event"),
            pl.col("terminal_interval_flag").last().alias("last_terminal"),
        )
        .with_columns(
            pl.when(pl.col("event_type") == "DEFAULT")
            .then(pl.lit(1))
            .otherwise(pl.lit(0))
            .alias("expected_events")
        )
        .filter(
            (pl.col("event_types") != 1)
            | ~pl.col("event_type").is_in(["DEFAULT", "PREPAYMENT", "CENSOR"])
            | (pl.col("events") != pl.col("expected_events"))
            | (pl.col("terminal_rows") != 1)
            | ~pl.col("last_terminal")
            | (pl.col("last_event") != pl.col("expected_events"))
        )
        .limit(5)
        .collect()
    )
    if loan_checks.height:
        raise TimeVaryingInputError(
            "Time-varying input has inconsistent terminal event semantics; "
            f"examples: {loan_checks['loan_id'].to_list()}."
        )

    return data
