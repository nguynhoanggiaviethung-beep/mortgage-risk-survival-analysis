"""DEFAULT CIF horizon extraction and origination-vintage analytics.

This module transforms output from the existing Aalen-Johansen estimator. It
does not define events, rebuild analysis time, or implement another survival
estimator. Fixed-horizon PD is exactly the DEFAULT cumulative incidence.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from os import PathLike
from pathlib import Path
from typing import TypeAlias

import numpy as np
import polars as pl

from src.competing_risks.aalen_johansen import (
    AJ_INPUT_DTYPES,
    AJ_RESULT_DTYPES,
    fit_aalen_johansen,
    validate_aalen_johansen_input,
    validate_aalen_johansen_results,
)


FrameLike: TypeAlias = pl.DataFrame | pl.LazyFrame
PathSource: TypeAlias = str | PathLike[str]

PRIMARY_HORIZONS = (12, 24, 36)
SUPPLEMENTARY_HORIZONS = (60,)
ALLOWED_HORIZONS = (*PRIMARY_HORIZONS, *SUPPLEMENTARY_HORIZONS)
PERFORMANCE_CUTOFF_DATE = date(2026, 3, 31)
START_VINTAGE = 2016
END_VINTAGE = 2026

ELIGIBLE = "ELIGIBLE"
INSUFFICIENT_FOLLOW_UP = "INSUFFICIENT_FOLLOW_UP"
INSUFFICIENT_OBSERVED_SUPPORT = "INSUFFICIENT_OBSERVED_SUPPORT"

PD_VINTAGE_INPUT_DTYPES: dict[str, pl.DataType] = {
    **AJ_INPUT_DTYPES,
    "operational_origination_date": pl.Date,
}
PD_VINTAGE_INPUT_COLUMNS = list(PD_VINTAGE_INPUT_DTYPES)

OVERALL_PD_DTYPES: dict[str, pl.DataType] = {
    "model_type": pl.String,
    "endpoint": pl.String,
    "group_name": pl.String,
    "group_value": pl.String,
    "horizon_months": pl.Int16,
    "horizon_role": pl.String,
    "default_cif": pl.Float64,
    "pd": pl.Float64,
    "loan_count": pl.UInt32,
    "n_at_risk": pl.UInt32,
    "default_count": pl.UInt32,
    "prepayment_count": pl.UInt32,
    "follow_up_eligible": pl.Boolean,
    "follow_up_status": pl.String,
}
OVERALL_PD_COLUMNS = list(OVERALL_PD_DTYPES)

VINTAGE_CIF_DTYPES: dict[str, pl.DataType] = {
    "model_type": pl.String,
    "endpoint": pl.String,
    "vintage_year": pl.Int16,
    "analysis_time": pl.Int32,
    "cumulative_incidence": pl.Float64,
    "ci_lower": pl.Float64,
    "ci_upper": pl.Float64,
    "loan_count": pl.UInt32,
    "n_at_risk": pl.UInt32,
    "default_count": pl.UInt32,
    "prepayment_count": pl.UInt32,
}
VINTAGE_CIF_COLUMNS = list(VINTAGE_CIF_DTYPES)

VINTAGE_HORIZON_DTYPES: dict[str, pl.DataType] = {
    "model_type": pl.String,
    "vintage_year": pl.Int16,
    "horizon_months": pl.Int16,
    "horizon_role": pl.String,
    "default_cif": pl.Float64,
    "prepayment_cif": pl.Float64,
    "pd": pl.Float64,
    "loan_count": pl.UInt32,
    "n_at_risk": pl.UInt32,
    "default_count": pl.UInt32,
    "prepayment_count": pl.UInt32,
    "latest_origination_date": pl.Date,
    "performance_cutoff": pl.Date,
    "follow_up_eligible": pl.Boolean,
    "follow_up_status": pl.String,
}
VINTAGE_HORIZON_COLUMNS = list(VINTAGE_HORIZON_DTYPES)


class PDVintageError(ValueError):
    """Raised when Phase-3 input or analytical output is invalid."""


@dataclass(frozen=True)
class PDVintageResult:
    """Three validated Phase-3 analytical result contracts."""

    overall_pd_horizons: pl.DataFrame
    vintage_cif: pl.DataFrame
    vintage_horizons: pl.DataFrame


def _as_lazy(frame: FrameLike) -> pl.LazyFrame:
    if isinstance(frame, pl.DataFrame):
        return frame.lazy()
    if isinstance(frame, pl.LazyFrame):
        return frame
    raise TypeError("Expected a Polars DataFrame or LazyFrame.")


def add_calendar_months(value: date, months: int) -> date:
    """Add whole calendar months, clipping the day at the target month end."""
    if not isinstance(value, date):
        raise PDVintageError("Calendar-month input must be a date.")
    if not isinstance(months, int) or isinstance(months, bool) or months < 0:
        raise PDVintageError("Calendar-month offset must be a non-negative integer.")
    month_index = value.year * 12 + value.month - 1 + months
    target_year, zero_based_month = divmod(month_index, 12)
    target_month = zero_based_month + 1
    target_day = min(value.day, calendar.monthrange(target_year, target_month)[1])
    return date(target_year, target_month, target_day)


def vintage_horizon_is_eligible(
    latest_origination_date: date,
    horizon_months: int,
    performance_cutoff: date = PERFORMANCE_CUTOFF_DATE,
) -> bool:
    """Apply the locked full-seasoning rule with calendar-month arithmetic."""
    if performance_cutoff != PERFORMANCE_CUTOFF_DATE:
        raise PDVintageError("Performance cutoff must be 2026-03-31.")
    _validate_horizons((horizon_months,))
    return (
        add_calendar_months(latest_origination_date, horizon_months)
        <= performance_cutoff
    )


def _validate_horizons(horizons: tuple[int, ...] | list[int]) -> tuple[int, ...]:
    values = tuple(horizons)
    if not values:
        raise PDVintageError("At least one fixed horizon is required.")
    if len(values) != len(set(values)):
        raise PDVintageError("Fixed horizons must be unique.")
    invalid = [
        value
        for value in values
        if not isinstance(value, int)
        or isinstance(value, bool)
        or value not in ALLOWED_HORIZONS
    ]
    if invalid:
        raise PDVintageError(
            f"Unsupported fixed horizon(s) {invalid}; expected only "
            f"{ALLOWED_HORIZONS}."
        )
    return values


def validate_pd_vintage_input(frame: FrameLike) -> pl.DataFrame:
    """Validate canonical dates, vintage, events, and survival-time semantics."""
    source = _as_lazy(frame)
    schema = source.collect_schema()
    missing = [name for name in PD_VINTAGE_INPUT_DTYPES if name not in schema]
    if missing:
        raise PDVintageError(
            f"PD/vintage input is missing required columns: {missing}."
        )
    mismatches = {
        name: {"expected": str(dtype), "actual": str(schema[name])}
        for name, dtype in PD_VINTAGE_INPUT_DTYPES.items()
        if schema[name] != dtype
    }
    if mismatches:
        raise PDVintageError(
            f"PD/vintage input has incompatible column types: {mismatches}."
        )
    selected = source.select(PD_VINTAGE_INPUT_COLUMNS).collect()
    try:
        validate_aalen_johansen_input(selected.select(list(AJ_INPUT_DTYPES)))
    except Exception as exc:
        raise PDVintageError(f"PD/vintage canonical AJ input is invalid: {exc}") from exc
    invalid_metadata = selected.select(
        (
            pl.col("operational_origination_date").is_null()
            | (pl.col("operational_origination_date") > PERFORMANCE_CUTOFF_DATE)
        ).sum().alias("invalid_origin"),
        (
            ~pl.col("vintage_year")
            .is_between(START_VINTAGE, END_VINTAGE)
            .fill_null(False)
        ).sum().alias("invalid_vintage"),
    ).row(0, named=True)
    if invalid_metadata["invalid_origin"]:
        raise PDVintageError(
            "PD/vintage input contains a missing or post-cutoff operational "
            "origination date."
        )
    if invalid_metadata["invalid_vintage"]:
        raise PDVintageError(
            "PD/vintage input contains a vintage outside 2016-2026."
        )
    return selected


def _group_counts(data: pl.DataFrame) -> pl.DataFrame:
    return (
        data.group_by("vintage_year")
        .agg(
            pl.len().cast(pl.UInt32).alias("loan_count"),
            (pl.col("event_type") == "DEFAULT")
            .sum().cast(pl.UInt32).alias("default_count"),
            (pl.col("event_type") == "PREPAYMENT")
            .sum().cast(pl.UInt32).alias("prepayment_count"),
            pl.col("operational_origination_date")
            .max().alias("latest_origination_date"),
        )
        .sort("vintage_year")
    )


def _portfolio_counts(data: pl.DataFrame) -> dict[str, int]:
    return data.select(
        pl.len().alias("loan_count"),
        (pl.col("event_type") == "DEFAULT").sum().alias("default_count"),
        (pl.col("event_type") == "PREPAYMENT")
        .sum().alias("prepayment_count"),
    ).row(0, named=True)


def _n_at_risk(data: pl.DataFrame, horizon: int) -> int:
    # R counting-process Surv uses the interval convention (start, stop].
    return int(
        data.select(
            (
                (pl.col("entry_time_month") < horizon)
                & (pl.col("exit_time_month") >= horizon)
            ).sum()
        ).item()
    )


def evaluate_cif_step(
    aj_results: FrameLike,
    *,
    endpoint: str,
    horizon_months: int,
    group_name: str,
    group_value: str,
) -> float | None:
    """Evaluate the right-continuous AJ step function without extrapolation."""
    _validate_horizons((horizon_months,))
    if endpoint not in {"DEFAULT", "PREPAYMENT"}:
        raise PDVintageError("CIF endpoint must be DEFAULT or PREPAYMENT.")
    try:
        data = validate_aalen_johansen_results(aj_results)
    except Exception as exc:
        raise PDVintageError(f"AJ result is invalid: {exc}") from exc
    group = data.filter(
        (pl.col("group_name") == group_name)
        & (pl.col("group_value") == group_value)
        & (pl.col("endpoint") == endpoint)
    ).sort("analysis_time")
    if group.height == 0:
        raise PDVintageError(
            f"AJ result has no {endpoint} curve for {group_name}={group_value}."
        )
    if horizon_months > group["analysis_time"].max():
        return None
    preceding = group.filter(pl.col("analysis_time") <= horizon_months)
    if preceding.height == 0:
        return 0.0
    return float(preceding["cumulative_incidence"][-1])


def build_overall_pd_horizons(
    frame: FrameLike,
    aj_results: FrameLike,
    horizons: tuple[int, ...] | list[int] = ALLOWED_HORIZONS,
) -> pl.DataFrame:
    """Create portfolio PD(H), where PD(H) is exactly DEFAULT CIF(H)."""
    data = validate_pd_vintage_input(frame)
    requested = _validate_horizons(horizons)
    try:
        aj = validate_aalen_johansen_results(aj_results)
    except Exception as exc:
        raise PDVintageError(f"Overall AJ result is invalid: {exc}") from exc
    if (
        aj["group_name"].unique().to_list() != ["portfolio"]
        or aj["group_value"].unique().to_list() != ["all"]
    ):
        raise PDVintageError("Overall AJ result must identify portfolio=all.")
    counts = _portfolio_counts(data)
    rows: list[dict[str, object]] = []
    for horizon in requested:
        n_at_risk = _n_at_risk(data, horizon)
        cif = evaluate_cif_step(
            aj,
            endpoint="DEFAULT",
            horizon_months=horizon,
            group_name="portfolio",
            group_value="all",
        )
        supported = cif is not None and n_at_risk > 0
        value = cif if supported else None
        rows.append({
            "model_type": "PD_HORIZON",
            "endpoint": "DEFAULT",
            "group_name": "portfolio",
            "group_value": "all",
            "horizon_months": horizon,
            "horizon_role": (
                "PRIMARY" if horizon in PRIMARY_HORIZONS else "SUPPLEMENTARY"
            ),
            "default_cif": value,
            "pd": value,
            **counts,
            "n_at_risk": n_at_risk,
            "follow_up_eligible": supported,
            "follow_up_status": ELIGIBLE if supported else INSUFFICIENT_OBSERVED_SUPPORT,
        })
    result = pl.DataFrame(rows, schema=OVERALL_PD_DTYPES)
    return validate_overall_pd_results(result)


def fit_vintage_cif(
    frame: FrameLike,
    *,
    confidence_level: float = 0.95,
    rscript: Path | None = None,
) -> pl.DataFrame:
    """Fit existing AJ curves independently by canonical origination vintage."""
    data = validate_pd_vintage_input(frame)
    aj = fit_aalen_johansen(
        data.select(list(AJ_INPUT_DTYPES)),
        group_col="vintage_year",
        confidence_level=confidence_level,
        rscript=rscript,
    )
    counts = _group_counts(data).drop("latest_origination_date")
    result = (
        aj.with_columns(
            pl.lit("VINTAGE_AALEN_JOHANSEN").alias("model_type"),
            pl.col("group_value").cast(pl.Int16).alias("vintage_year"),
        )
        .drop("group_name", "group_value")
        .join(counts, on="vintage_year", how="left", validate="m:1")
        .select(VINTAGE_CIF_COLUMNS)
        .cast(VINTAGE_CIF_DTYPES)
        .sort(["vintage_year", "analysis_time", "endpoint"])
    )
    return validate_vintage_cif_results(result)


def _vintage_curve_as_aj(curves: pl.DataFrame) -> pl.DataFrame:
    return curves.select(
        pl.lit("AALEN_JOHANSEN").alias("model_type"),
        "endpoint",
        pl.lit("vintage_year").alias("group_name"),
        pl.col("vintage_year").cast(pl.String).alias("group_value"),
        "analysis_time",
        "cumulative_incidence",
        "ci_lower",
        "ci_upper",
        "n_at_risk",
    ).cast(AJ_RESULT_DTYPES)


def build_vintage_horizons(
    frame: FrameLike,
    vintage_cif: FrameLike,
    horizons: tuple[int, ...] | list[int] = ALLOWED_HORIZONS,
    *,
    performance_cutoff: date = PERFORMANCE_CUTOFF_DATE,
) -> pl.DataFrame:
    """Create every vintage×horizon row under locked full-seasoning rules."""
    if performance_cutoff != PERFORMANCE_CUTOFF_DATE:
        raise PDVintageError("Performance cutoff must be 2026-03-31.")
    data = validate_pd_vintage_input(frame)
    curves = validate_vintage_cif_results(vintage_cif)
    requested = _validate_horizons(horizons)
    input_vintages = sorted(data["vintage_year"].unique().to_list())
    curve_vintages = sorted(curves["vintage_year"].unique().to_list())
    if input_vintages != curve_vintages:
        raise PDVintageError("Vintage CIF groups do not match the input vintages.")
    aj = _vintage_curve_as_aj(curves)
    counts = _group_counts(data)
    rows: list[dict[str, object]] = []
    for group in counts.iter_rows(named=True):
        vintage = int(group["vintage_year"])
        vintage_data = data.filter(pl.col("vintage_year") == vintage)
        for horizon in requested:
            full_seasoning = vintage_horizon_is_eligible(
                group["latest_origination_date"], horizon, performance_cutoff
            )
            n_at_risk = _n_at_risk(vintage_data, horizon)
            default_cif = evaluate_cif_step(
                aj,
                endpoint="DEFAULT",
                horizon_months=horizon,
                group_name="vintage_year",
                group_value=str(vintage),
            )
            prepayment_cif = evaluate_cif_step(
                aj,
                endpoint="PREPAYMENT",
                horizon_months=horizon,
                group_name="vintage_year",
                group_value=str(vintage),
            )
            observed_support = (
                default_cif is not None
                and prepayment_cif is not None
                and n_at_risk > 0
            )
            estimable = full_seasoning and observed_support
            if not full_seasoning:
                status = INSUFFICIENT_FOLLOW_UP
            elif not observed_support:
                status = INSUFFICIENT_OBSERVED_SUPPORT
            else:
                status = ELIGIBLE
            rows.append({
                "model_type": "VINTAGE_PD_HORIZON",
                "vintage_year": vintage,
                "horizon_months": horizon,
                "horizon_role": (
                    "PRIMARY" if horizon in PRIMARY_HORIZONS else "SUPPLEMENTARY"
                ),
                "default_cif": default_cif if estimable else None,
                "prepayment_cif": prepayment_cif if estimable else None,
                "pd": default_cif if estimable else None,
                "loan_count": group["loan_count"],
                "n_at_risk": n_at_risk,
                "default_count": group["default_count"],
                "prepayment_count": group["prepayment_count"],
                "latest_origination_date": group["latest_origination_date"],
                "performance_cutoff": performance_cutoff,
                "follow_up_eligible": full_seasoning,
                "follow_up_status": status,
            })
    result = pl.DataFrame(rows, schema=VINTAGE_HORIZON_DTYPES).sort(
        ["vintage_year", "horizon_months"]
    )
    return validate_vintage_horizon_results(result)


def fit_pd_vintage_analysis(
    frame: FrameLike,
    horizons: tuple[int, ...] | list[int] = ALLOWED_HORIZONS,
    *,
    confidence_level: float = 0.95,
    rscript: Path | None = None,
) -> PDVintageResult:
    """Run existing AJ estimation once overall and once by vintage, then transform."""
    data = validate_pd_vintage_input(frame)
    requested = _validate_horizons(horizons)
    aj_input = data.select(list(AJ_INPUT_DTYPES))
    overall_aj = fit_aalen_johansen(
        aj_input,
        confidence_level=confidence_level,
        rscript=rscript,
    )
    vintage_cif = fit_vintage_cif(
        data,
        confidence_level=confidence_level,
        rscript=rscript,
    )
    result = PDVintageResult(
        overall_pd_horizons=build_overall_pd_horizons(
            data, overall_aj, requested
        ),
        vintage_cif=vintage_cif,
        vintage_horizons=build_vintage_horizons(
            data, vintage_cif, requested
        ),
    )
    return result


def _validate_schema(
    frame: FrameLike,
    expected: dict[str, pl.DataType],
    label: str,
) -> pl.DataFrame:
    source = _as_lazy(frame)
    schema = source.collect_schema()
    if schema.names() != list(expected):
        raise PDVintageError(
            f"{label} columns do not match canonical order: {list(expected)}."
        )
    mismatches = {
        name: {"expected": str(dtype), "actual": str(schema[name])}
        for name, dtype in expected.items()
        if schema[name] != dtype
    }
    if mismatches:
        raise PDVintageError(f"{label} has incompatible types: {mismatches}.")
    return source.collect()


def _validate_common_counts(data: pl.DataFrame, label: str) -> None:
    valid = data.select(
        (pl.col("loan_count") > 0)
        & (pl.col("n_at_risk") <= pl.col("loan_count"))
        & (pl.col("default_count") <= pl.col("loan_count"))
        & (pl.col("prepayment_count") <= pl.col("loan_count"))
        & (
            pl.col("default_count") + pl.col("prepayment_count")
            <= pl.col("loan_count")
        )
    ).to_series()
    if not valid.all():
        raise PDVintageError(f"{label} contains invalid support/event counts.")


def validate_overall_pd_results(frame: FrameLike) -> pl.DataFrame:
    """Validate portfolio fixed-horizon DEFAULT CIF/PD results."""
    data = _validate_schema(frame, OVERALL_PD_DTYPES, "Overall PD results")
    if data.height == 0 or data.select("horizon_months").n_unique() != data.height:
        raise PDVintageError("Overall PD result keys are empty or duplicated.")
    _validate_horizons(data["horizon_months"].to_list())
    if (
        data["model_type"].unique().to_list() != ["PD_HORIZON"]
        or data["endpoint"].unique().to_list() != ["DEFAULT"]
        or data["group_name"].unique().to_list() != ["portfolio"]
        or data["group_value"].unique().to_list() != ["all"]
    ):
        raise PDVintageError("Overall PD result identity is invalid.")
    _validate_common_counts(data, "Overall PD results")
    for row in data.iter_rows(named=True):
        expected_role = (
            "PRIMARY" if row["horizon_months"] in PRIMARY_HORIZONS
            else "SUPPLEMENTARY"
        )
        if row["horizon_role"] != expected_role:
            raise PDVintageError("Overall PD horizon role is invalid.")
        estimates = (row["default_cif"], row["pd"])
        if row["follow_up_eligible"]:
            if row["follow_up_status"] != ELIGIBLE or any(
                value is None or not np.isfinite(value) or not 0 <= value <= 1
                for value in estimates
            ):
                raise PDVintageError("Eligible overall PD row is invalid.")
            if not np.isclose(estimates[0], estimates[1], rtol=0, atol=1e-15):
                raise PDVintageError("PD must equal DEFAULT CIF.")
        elif (
            row["follow_up_status"] != INSUFFICIENT_OBSERVED_SUPPORT
            or any(value is not None for value in estimates)
        ):
            raise PDVintageError("Unsupported overall PD row must contain NA estimates.")
    return data


def validate_vintage_cif_results(frame: FrameLike) -> pl.DataFrame:
    """Validate full observed vintage AJ curves and attached support counts."""
    data = _validate_schema(frame, VINTAGE_CIF_DTYPES, "Vintage CIF results")
    if data.height == 0:
        raise PDVintageError("Vintage CIF results are empty.")
    if data["model_type"].unique().to_list() != ["VINTAGE_AALEN_JOHANSEN"]:
        raise PDVintageError("Vintage CIF model identity is invalid.")
    if not data["vintage_year"].is_between(START_VINTAGE, END_VINTAGE).all():
        raise PDVintageError("Vintage CIF contains a vintage outside 2016-2026.")
    _validate_common_counts(data, "Vintage CIF results")
    try:
        validate_aalen_johansen_results(_vintage_curve_as_aj(data))
    except Exception as exc:
        raise PDVintageError(f"Vintage CIF AJ values are invalid: {exc}") from exc
    duplicate_keys = data.select(
        pl.struct("vintage_year", "analysis_time", "endpoint").n_unique()
    ).item() != data.height
    if duplicate_keys:
        raise PDVintageError("Vintage CIF contains duplicate analytical keys.")
    stable_counts = (
        data.group_by("vintage_year")
        .agg(
            pl.col("loan_count").n_unique().alias("loan_count"),
            pl.col("default_count").n_unique().alias("default_count"),
            pl.col("prepayment_count").n_unique().alias("prepayment_count"),
        )
        .select(pl.all_horizontal(pl.exclude("vintage_year") == 1))
        .to_series()
    )
    if not stable_counts.all():
        raise PDVintageError("Vintage CIF group counts are not stable.")
    return data


def validate_vintage_horizon_results(frame: FrameLike) -> pl.DataFrame:
    """Validate vintage fixed horizons, seasoning, support, and NA behavior."""
    data = _validate_schema(
        frame, VINTAGE_HORIZON_DTYPES, "Vintage horizon results"
    )
    if data.height == 0:
        raise PDVintageError("Vintage horizon results are empty.")
    if data["model_type"].unique().to_list() != ["VINTAGE_PD_HORIZON"]:
        raise PDVintageError("Vintage horizon model identity is invalid.")
    if not data["vintage_year"].is_between(START_VINTAGE, END_VINTAGE).all():
        raise PDVintageError("Vintage horizon contains a vintage outside 2016-2026.")
    _validate_horizons(sorted(data["horizon_months"].unique().to_list()))
    if data.select(
        pl.struct("vintage_year", "horizon_months").n_unique()
    ).item() != data.height:
        raise PDVintageError("Vintage horizon contains duplicate analytical keys.")
    _validate_common_counts(data, "Vintage horizon results")
    for row in data.iter_rows(named=True):
        if row["performance_cutoff"] != PERFORMANCE_CUTOFF_DATE:
            raise PDVintageError("Vintage horizon cutoff must be 2026-03-31.")
        expected_eligibility = vintage_horizon_is_eligible(
            row["latest_origination_date"], row["horizon_months"]
        )
        if row["follow_up_eligible"] != expected_eligibility:
            raise PDVintageError("Vintage full-seasoning eligibility is inconsistent.")
        expected_role = (
            "PRIMARY" if row["horizon_months"] in PRIMARY_HORIZONS
            else "SUPPLEMENTARY"
        )
        if row["horizon_role"] != expected_role:
            raise PDVintageError("Vintage horizon role is invalid.")
        estimates = (
            row["default_cif"], row["prepayment_cif"], row["pd"]
        )
        if row["follow_up_status"] == ELIGIBLE:
            if not row["follow_up_eligible"] or any(
                value is None or not np.isfinite(value) or not 0 <= value <= 1
                for value in estimates
            ):
                raise PDVintageError("Eligible vintage horizon estimate is invalid.")
            if not np.isclose(estimates[0], estimates[2], rtol=0, atol=1e-15):
                raise PDVintageError("Vintage PD must equal DEFAULT CIF.")
            if estimates[0] + estimates[1] > 1.0 + 1e-12:
                raise PDVintageError("Vintage paired CIF values exceed one.")
        elif row["follow_up_status"] in {
            INSUFFICIENT_FOLLOW_UP,
            INSUFFICIENT_OBSERVED_SUPPORT,
        }:
            if any(value is not None for value in estimates):
                raise PDVintageError(
                    "Ineligible/unsupported vintage horizon must contain NA estimates."
                )
            if (
                row["follow_up_status"] == INSUFFICIENT_FOLLOW_UP
                and row["follow_up_eligible"]
            ):
                raise PDVintageError("Insufficient follow-up row cannot be eligible.")
        else:
            raise PDVintageError("Vintage horizon follow-up status is invalid.")
    return data


def write_pd_vintage_results(
    result: PDVintageResult,
    overall_path: PathSource,
    vintage_cif_path: PathSource,
    vintage_horizon_path: PathSource,
) -> tuple[Path, Path, Path]:
    """Validate and atomically write all three Phase-3 analytical artifacts."""
    if not isinstance(result, PDVintageResult):
        raise PDVintageError("result must be a PDVintageResult.")
    frames = (
        validate_overall_pd_results(result.overall_pd_horizons),
        validate_vintage_cif_results(result.vintage_cif),
        validate_vintage_horizon_results(result.vintage_horizons),
    )
    outputs = (Path(overall_path), Path(vintage_cif_path), Path(vintage_horizon_path))
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
