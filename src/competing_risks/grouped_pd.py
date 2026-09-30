"""Competing-risk CIF estimates for original-loan risk bands."""

from __future__ import annotations

from os import PathLike
from pathlib import Path
from typing import TypeAlias

import polars as pl

from src.competing_risks.aalen_johansen import (
    AJ_INPUT_DTYPES,
    fit_aalen_johansen,
    validate_aalen_johansen_results,
)
from src.competing_risks.pd_vintage import (
    ALLOWED_HORIZONS,
    ELIGIBLE,
    INSUFFICIENT_OBSERVED_SUPPORT,
    PRIMARY_HORIZONS,
    _n_at_risk,
    _portfolio_counts,
    evaluate_cif_step,
)

FrameLike: TypeAlias = pl.DataFrame | pl.LazyFrame
PathSource: TypeAlias = str | PathLike[str]

GROUP_BANDS = {
    "fico_band": ("<650", "650–699", "700–749", "750+", "Missing"),
    "ltv_band": ("≤60%", ">60–70%", ">70–80%", ">80%", "Missing"),
    "dti_band": ("≤30%", ">30–40%", ">40–50%", ">50%", "Missing"),
}
GROUPED_PD_DTYPES = {
    "feature": pl.String,
    "group_value": pl.String,
    "horizon_months": pl.Int16,
    "horizon_role": pl.String,
    "default_cif": pl.Float64,
    "prepayment_cif": pl.Float64,
    "pd": pl.Float64,
    "loan_count": pl.UInt32,
    "n_at_risk": pl.UInt32,
    "default_count": pl.UInt32,
    "prepayment_count": pl.UInt32,
    "follow_up_eligible": pl.Boolean,
    "follow_up_status": pl.String,
}


def _band_expr(source: str, feature: str) -> pl.Expr:
    x = pl.col(source).cast(pl.Float64, strict=False)
    expr = pl.when(x.is_null() | ~x.is_finite()).then(pl.lit("Missing"))
    if feature == "fico_band":
        expr = expr.when(x < 650).then(pl.lit("<650")).when(x < 700).then(pl.lit("650–699")).when(x < 750).then(pl.lit("700–749")).otherwise(pl.lit("750+"))
    elif feature == "ltv_band":
        expr = expr.when(x <= 60).then(pl.lit("≤60%")).when(x <= 70).then(pl.lit(">60–70%")).when(x <= 80).then(pl.lit(">70–80%")).otherwise(pl.lit(">80%"))
    else:
        expr = expr.when(x <= 30).then(pl.lit("≤30%")).when(x <= 40).then(pl.lit(">30–40%")).when(x <= 50).then(pl.lit(">40–50%")).otherwise(pl.lit(">50%"))
    return expr.alias(feature)


def add_group_bands(frame: FrameLike) -> pl.DataFrame:
    data = frame.collect() if isinstance(frame, pl.LazyFrame) else frame.clone()
    required = {*AJ_INPUT_DTYPES, "fico", "original_ltv", "original_dti"}
    missing = sorted(required - set(data.columns))
    if missing:
        raise ValueError(f"Grouped CIF input is missing columns: {missing}.")
    return data.with_columns(
        _band_expr("fico", "fico_band"),
        _band_expr("original_ltv", "ltv_band"),
        _band_expr("original_dti", "dti_band"),
    )


def _validate_grouped_pd(frame: pl.DataFrame) -> pl.DataFrame:
    if frame.columns != list(GROUPED_PD_DTYPES):
        raise ValueError("Grouped PD result columns do not match contract.")
    frame = frame.cast(GROUPED_PD_DTYPES)
    if frame.is_empty() or frame.select(pl.struct("feature", "group_value", "horizon_months").n_unique()).item() != frame.height:
        raise ValueError("Grouped PD results are empty or contain duplicate keys.")
    for feature, bands in GROUP_BANDS.items():
        subset = frame.filter(pl.col("feature") == feature)
        if set(subset["group_value"].unique()) != set(bands):
            raise ValueError(f"{feature} group inventory is invalid.")
        if subset.group_by("horizon_months").agg(pl.col("loan_count").sum()).filter(pl.col("loan_count") == 0).height:
            raise ValueError(f"{feature} contains an empty risk band.")
    if not frame.filter(pl.col("follow_up_eligible")).select(
        pl.all_horizontal([
            pl.col("default_cif").is_not_null(), pl.col("prepayment_cif").is_not_null(),
            pl.col("pd").is_not_null(), pl.col("pd") == pl.col("default_cif"),
            pl.col("default_cif").is_between(0, 1), pl.col("prepayment_cif").is_between(0, 1),
            pl.col("default_cif") + pl.col("prepayment_cif") <= 1 + 1e-12,
        ]).all()
    ).item():
        raise ValueError("Eligible grouped CIF values are invalid.")
    if frame.filter(~pl.col("follow_up_eligible")).select(
        (pl.col("default_cif").is_null() & pl.col("prepayment_cif").is_null() & pl.col("pd").is_null()).all()
    ).item() is False:
        raise ValueError("Unsupported grouped CIF values must be null.")
    return frame.sort(["feature", "group_value", "horizon_months"])


def build_grouped_pd(
    frame: FrameLike,
    *,
    rscript: Path | None = None,
    horizons: tuple[int, ...] = ALLOWED_HORIZONS,
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Fit subgroup AJ curves and derive non-extrapolated fixed-horizon CIFs."""
    data = add_group_bands(frame)
    curve_frames: list[pl.DataFrame] = []
    horizon_rows: list[dict[str, object]] = []
    for feature, bands in GROUP_BANDS.items():
        curves = fit_aalen_johansen(
            data.select([*AJ_INPUT_DTYPES, feature]), group_col=feature, rscript=rscript
        )
        curve_frames.append(curves)
        for band in bands:
            subset = data.filter(pl.col(feature) == band)
            counts = _portfolio_counts(subset)
            for horizon in horizons:
                at_risk = _n_at_risk(subset, horizon)
                default = evaluate_cif_step(
                    curves, endpoint="DEFAULT", horizon_months=horizon,
                    group_name=feature, group_value=band,
                )
                prepay = evaluate_cif_step(
                    curves, endpoint="PREPAYMENT", horizon_months=horizon,
                    group_name=feature, group_value=band,
                )
                eligible = default is not None and prepay is not None and at_risk > 0
                horizon_rows.append({
                    "feature": feature, "group_value": band,
                    "horizon_months": horizon,
                    "horizon_role": "PRIMARY" if horizon in PRIMARY_HORIZONS else "SUPPLEMENTARY",
                    "default_cif": default if eligible else None,
                    "prepayment_cif": prepay if eligible else None,
                    "pd": default if eligible else None,
                    **counts, "n_at_risk": at_risk,
                    "follow_up_eligible": eligible,
                    "follow_up_status": ELIGIBLE if eligible else INSUFFICIENT_OBSERVED_SUPPORT,
                })
    curves = pl.concat(curve_frames, how="vertical").pipe(validate_aalen_johansen_results)
    horizons_result = _validate_grouped_pd(pl.DataFrame(horizon_rows, schema=GROUPED_PD_DTYPES))
    return curves, horizons_result


def write_grouped_pd(curves: pl.DataFrame, horizons: pl.DataFrame, curves_path: PathSource, horizons_path: PathSource) -> None:
    for frame, path in ((validate_aalen_johansen_results(curves), Path(curves_path)), (_validate_grouped_pd(horizons), Path(horizons_path))):
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".tmp.parquet")
        frame.write_parquet(temp, compression="zstd")
        temp.replace(path)
