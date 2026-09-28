"""Validated adapters for loan-level survival-model inputs.

The canonical model grain is one row per loan.  A loan-month source can be
adapted for tests, but event classification and survival-time construction are
delegated to the existing data-pipeline functions so this module does not
create a second copy of those business rules.
"""

from __future__ import annotations

from os import PathLike
from pathlib import Path
from typing import TypeAlias

import polars as pl

from src.data.event_definition import build_event_mapping
from src.data.model_dataset import CORE_COLUMNS, FEATURE_COLUMNS, build_model_dataset
from src.data.survival_duration import build_survival_duration


FrameLike: TypeAlias = pl.DataFrame | pl.LazyFrame
PathSource: TypeAlias = str | PathLike[str]

START_YEAR = 2016
END_YEAR = 2026

LOAN_LEVEL_DTYPES: dict[str, pl.DataType] = {
    "loan_id": pl.String,
    "vintage_year": pl.Int16,
    "entry_time_month": pl.Int32,
    "exit_time_month": pl.Int32,
    "duration_months": pl.Int32,
    "event_type": pl.String,
    "event_code": pl.Int8,
    "survival_eligible": pl.Boolean,
    "default_event": pl.Int8,
    "prepayment_event": pl.Int8,
    "competing_event_code": pl.Int8,
    "fico": pl.Int16,
    "original_ltv": pl.Float64,
    "original_dti": pl.Float64,
    "original_interest_rate": pl.Float64,
    "original_loan_term": pl.Int16,
    "core_covariates_complete_flag": pl.Boolean,
    "km_default_event": pl.Int8,
    "km_prepayment_event": pl.Int8,
    "cr_event_code": pl.Int8,
}

LOAN_MONTH_DTYPES: dict[str, pl.DataType] = {
    "loan_id": pl.String,
    "performance_month": pl.Date,
    "reporting_period_num": pl.Int32,
    "zero_balance_code": pl.String,
    "zero_balance_effective_date": pl.String,
    "vintage_year": pl.Int16,
    "first_payment_month": pl.Date,
    "maturity_month": pl.Date,
    "fico": pl.Int16,
    "original_ltv": pl.Float64,
    "original_dti": pl.Float64,
    "original_interest_rate": pl.Float64,
    "original_loan_term": pl.Int16,
    "original_cltv": pl.Float64,
    "original_upb": pl.Float64,
    "occupancy_status": pl.String,
    "property_type": pl.String,
    "loan_purpose": pl.String,
    "property_state": pl.String,
    "number_borrowers": pl.Int16,
    "multiple_borrowers_flag": pl.Boolean,
    "origination_quarter": pl.Int8,
}

STATIC_MONTHLY_COLUMNS = [
    "vintage_year",
    "first_payment_month",
    "maturity_month",
    *[name for name in FEATURE_COLUMNS if name != "loan_id"],
]

SURVIVAL_INPUT_COLUMNS = [
    "loan_id",
    "vintage_year",
    "entry_time_month",
    "exit_time_month",
    "duration_months",
    "km_default_event",
    "event_type",
]

COX_INPUT_COLUMNS = [
    "loan_id",
    "vintage_year",
    "entry_time_month",
    "exit_time_month",
    "duration_months",
    "default_event",
    "event_type",
    *CORE_COLUMNS,
]

COMPETING_RISK_INPUT_COLUMNS = [
    "loan_id",
    "vintage_year",
    "entry_time_month",
    "exit_time_month",
    "duration_months",
    "cr_event_code",
    "event_type",
]


class ModelInputError(ValueError):
    """Raised when a source violates the model-input contract."""


def _as_lazy(frame: FrameLike) -> pl.LazyFrame:
    if isinstance(frame, pl.DataFrame):
        return frame.lazy()
    if isinstance(frame, pl.LazyFrame):
        return frame
    raise TypeError("Expected a Polars DataFrame or LazyFrame.")


def _validate_schema(
    frame: pl.LazyFrame,
    expected: dict[str, pl.DataType],
    source_name: str,
) -> None:
    schema = frame.collect_schema()
    missing = [name for name in expected if name not in schema]
    if missing:
        raise ModelInputError(
            f"{source_name} is missing required columns: {missing}."
        )

    mismatches = {
        name: {"expected": str(dtype), "actual": str(schema[name])}
        for name, dtype in expected.items()
        if schema[name] != dtype
    }
    if mismatches:
        raise ModelInputError(
            f"{source_name} has incompatible column types: {mismatches}."
        )


def validate_loan_month_source(frame: FrameLike) -> pl.LazyFrame:
    """Validate an enriched loan-month source without changing its rows."""
    source = _as_lazy(frame)
    _validate_schema(source, LOAN_MONTH_DTYPES, "Loan-month source")

    key_stats = source.select(
        pl.len().alias("rows"),
        pl.col("loan_id").null_count().alias("missing_loan_id"),
        pl.struct(["loan_id", "performance_month"])
        .n_unique()
        .alias("unique_keys"),
        (
            pl.col("performance_month").is_null()
            | pl.col("reporting_period_num").is_null()
            | (
                pl.col("reporting_period_num")
                != (
                    pl.col("performance_month").dt.year() * 100
                    + pl.col("performance_month").dt.month()
                )
            )
        )
        .sum()
        .alias("invalid_reporting_month"),
    ).collect().to_dicts()[0]

    if key_stats["missing_loan_id"]:
        raise ModelInputError("Loan-month source contains null loan_id values.")
    if key_stats["rows"] != key_stats["unique_keys"]:
        raise ModelInputError(
            "Loan-month source contains duplicate "
            "(loan_id, performance_month) keys."
        )
    if key_stats["invalid_reporting_month"]:
        raise ModelInputError(
            "performance_month and reporting_period_num are inconsistent."
        )

    inconsistent = (
        source.group_by("loan_id")
        .agg([
            pl.col(name).n_unique().alias(name)
            for name in STATIC_MONTHLY_COLUMNS
        ])
        .filter(
            pl.any_horizontal([
                pl.col(name) > 1
                for name in STATIC_MONTHLY_COLUMNS
            ])
        )
        .select("loan_id")
        .limit(5)
        .collect()
    )
    if inconsistent.height:
        raise ModelInputError(
            "Static/origination fields vary within a loan; examples: "
            f"{inconsistent['loan_id'].to_list()}."
        )

    return source


def validate_loan_level_input(frame: FrameLike) -> pl.LazyFrame:
    """Validate the canonical one-row-per-loan model input contract."""
    source = _as_lazy(frame)
    _validate_schema(source, LOAN_LEVEL_DTYPES, "Loan-level model input")

    expected_code = (
        pl.when(pl.col("event_type") == "DEFAULT")
        .then(pl.lit(1, dtype=pl.Int8))
        .when(pl.col("event_type") == "PREPAYMENT")
        .then(pl.lit(2, dtype=pl.Int8))
        .when(pl.col("event_type") == "CENSOR")
        .then(pl.lit(0, dtype=pl.Int8))
        .otherwise(None)
    )
    expected_default = (pl.col("event_type") == "DEFAULT").cast(pl.Int8)
    expected_prepayment = (pl.col("event_type") == "PREPAYMENT").cast(pl.Int8)
    complete_case = pl.all_horizontal([
        pl.col(name).is_not_null()
        & pl.col(name).cast(pl.Float64).is_finite().fill_null(False)
        for name in CORE_COLUMNS
    ])

    valid_event = (
        pl.col("event_type").is_in(["DEFAULT", "PREPAYMENT", "CENSOR"])
        & (pl.col("event_code") == expected_code)
        & (pl.col("competing_event_code") == expected_code)
        & (pl.col("cr_event_code") == expected_code)
        & (pl.col("default_event") == expected_default)
        & (pl.col("km_default_event") == expected_default)
        & (pl.col("prepayment_event") == expected_prepayment)
        & (pl.col("km_prepayment_event") == expected_prepayment)
    ).fill_null(False)

    valid_time = (
        pl.col("entry_time_month").is_not_null()
        & pl.col("exit_time_month").is_not_null()
        & pl.col("duration_months").is_not_null()
        & (pl.col("entry_time_month") >= 0)
        & (pl.col("exit_time_month") > pl.col("entry_time_month"))
        & (pl.col("duration_months") == pl.col("exit_time_month"))
    ).fill_null(False)

    stats = source.select(
        pl.len().alias("rows"),
        pl.col("loan_id").n_unique().alias("unique_loans"),
        pl.col("loan_id").null_count().alias("missing_loan_id"),
        (~valid_event).sum().alias("invalid_event"),
        (~valid_time).sum().alias("invalid_time"),
        (
            ~pl.col("vintage_year")
            .is_between(START_YEAR, END_YEAR)
            .fill_null(False)
        )
        .sum()
        .alias("outside_cohort"),
        (~pl.col("survival_eligible").fill_null(False))
        .sum()
        .alias("not_survival_eligible"),
        (
            pl.col("core_covariates_complete_flag")
            .ne(complete_case)
            .fill_null(True)
        )
        .sum()
        .alias("invalid_complete_case_flag"),
    ).collect().to_dicts()[0]

    if stats["missing_loan_id"]:
        raise ModelInputError("Loan-level model input contains null loan_id values.")
    if stats["rows"] != stats["unique_loans"]:
        raise ModelInputError("Loan-level model input contains duplicate loan_id values.")
    if stats["invalid_event"]:
        raise ModelInputError(
            f"Loan-level model input has {stats['invalid_event']} inconsistent "
            "event label/code row(s)."
        )
    if stats["invalid_time"]:
        raise ModelInputError(
            f"Loan-level model input has {stats['invalid_time']} invalid "
            "entry/exit/duration row(s)."
        )
    if stats["outside_cohort"]:
        raise ModelInputError(
            f"Loan-level model input has {stats['outside_cohort']} row(s) "
            "outside the 2016-2026 cohort."
        )
    if stats["not_survival_eligible"]:
        raise ModelInputError(
            "Loan-level model input must contain only survival-eligible loans."
        )
    if stats["invalid_complete_case_flag"]:
        raise ModelInputError(
            "core_covariates_complete_flag is inconsistent with the five "
            "required baseline predictors."
        )

    return source


def load_loan_month_source(path: PathSource) -> pl.LazyFrame:
    """Lazy-scan and validate an enriched loan-month Parquet source."""
    source_path = Path(path)
    if not source_path.is_file():
        raise FileNotFoundError(f"Loan-month source not found: {source_path}")
    return validate_loan_month_source(pl.scan_parquet(source_path))


def load_loan_level_input(path: PathSource) -> pl.LazyFrame:
    """Lazy-scan and validate a canonical loan-level Parquet source."""
    source_path = Path(path)
    if not source_path.is_file():
        raise FileNotFoundError(f"Loan-level model input not found: {source_path}")
    return validate_loan_level_input(pl.scan_parquet(source_path))


def build_loan_level_input(frame: FrameLike) -> pl.LazyFrame:
    """Adapt an enriched loan-month source to the canonical loan-level grain.

    Static columns are validated before the source is split into the in-memory
    origination and performance views required by the existing pipeline.
    """
    monthly = validate_loan_month_source(frame)

    origination_columns = [
        "loan_id",
        "vintage_year",
        "first_payment_month",
        "maturity_month",
        *[name for name in FEATURE_COLUMNS if name != "loan_id"],
    ]
    origination = monthly.select(origination_columns).unique(
        subset=["loan_id"],
        keep="first",
        maintain_order=True,
    )
    performance = monthly.select(
        "loan_id",
        "reporting_period_num",
        "zero_balance_code",
        "zero_balance_effective_date",
    )

    events = build_event_mapping(origination, performance)
    survival = build_survival_duration(events)
    model_input = build_model_dataset(origination, survival)
    return validate_loan_level_input(model_input)


def to_survival_input(frame: FrameLike) -> pl.LazyFrame:
    """Return the default-endpoint KM/survival view, retaining entry and exit."""
    return validate_loan_level_input(frame).select(SURVIVAL_INPUT_COLUMNS)


def to_cox_input(frame: FrameLike) -> pl.LazyFrame:
    """Return the complete-case baseline Cox view with delayed entry intact."""
    return (
        validate_loan_level_input(frame)
        .filter(pl.col("core_covariates_complete_flag"))
        .select(COX_INPUT_COLUMNS)
    )


def to_competing_risk_input(frame: FrameLike) -> pl.LazyFrame:
    """Return the competing-risk view, retaining entry, exit and cause code."""
    return validate_loan_level_input(frame).select(
        COMPETING_RISK_INPUT_COLUMNS
    )
