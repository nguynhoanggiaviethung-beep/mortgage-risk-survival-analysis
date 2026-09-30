"""Frontend data access for published analysis results and loan histories."""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import polars as pl
import streamlit as st

from src.results.dashboard import (
    model_diagnostics,
    pd_results,
    grouped_pd_results,
    portfolio_summary,
    resolve_dashboard_release,
    risk_driver_results,
    survival_results,
    vintage_results,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
QUERY_DIR = Path(os.environ.get("MORTGAGE_QUERY_DIR", PROJECT_ROOT / "query"))
ANALYSIS_PATH = PROJECT_ROOT / "data/model/analysis_loans_2016_2026.parquet"
PERFORMANCE_PATH = PROJECT_ROOT / "data/processed/performance.parquet"


def get_query_dir() -> Path:
    """Legacy query directory, kept for projects without a published release."""
    return QUERY_DIR


@st.cache_resource(show_spinner=False)
def _release():
    return resolve_dashboard_release(PROJECT_ROOT)


def _current_release():
    try:
        return _release()
    except (FileNotFoundError, ValueError, KeyError, OSError):
        return None


def _to_pandas(frame: pl.DataFrame) -> pd.DataFrame:
    return frame.to_pandas()


def _legacy(dataset_name: str) -> pd.DataFrame:
    csv_path = QUERY_DIR / f"{dataset_name}.csv"
    parquet_path = QUERY_DIR / f"{dataset_name}.parquet"
    if csv_path.exists():
        return pd.read_csv(csv_path)
    if parquet_path.exists():
        return pd.read_parquet(parquet_path)
    return pd.DataFrame()


def dataset_status() -> dict[str, bool]:
    """Report which dashboard data sources are available locally."""
    release = _current_release()
    if release is None:
        return {
            name: (QUERY_DIR / f"{name}.csv").exists()
            or (QUERY_DIR / f"{name}.parquet").exists()
            for name in (
                "portfolio_summary", "pd_results", "survival_results",
                "risk_driver_results", "vintage_results", "loan_profile",
                "loan_timeline", "model_diagnostics",
            )
        }
    return {
        "portfolio_summary": True,
        "pd_results": True,
        "survival_results": True,
        "risk_driver_results": True,
        "vintage_results": True,
        "loan_profile": ANALYSIS_PATH.exists(),
        "loan_timeline": ANALYSIS_PATH.exists() and PERFORMANCE_PATH.exists(),
        "model_diagnostics": True,
    }


@st.cache_data(show_spinner=False)
def load_data(dataset_name: str) -> pd.DataFrame:
    """Load a known dashboard projection; retain legacy query fallback."""
    release = _current_release()
    if release is None:
        return _legacy(dataset_name)
    loaders = {
        "portfolio_summary": get_portfolio_summary,
        "pd_results": get_pd_results,
        "survival_results": get_survival_results,
        "risk_driver_results": get_risk_driver_results,
        "vintage_results": get_vintage_results,
        "model_diagnostics": get_model_diagnostics,
    }
    loader = loaders.get(dataset_name)
    return loader() if loader else _legacy(dataset_name)


@st.cache_data(show_spinner=False)
def get_portfolio_summary(vintage="All", score_band="All", ltv_band="All", dti_band="All", term="All") -> pd.DataFrame:
    release = _current_release()
    if release is None:
        return _legacy("portfolio_summary")
    df = _to_pandas(portfolio_summary(release)).rename(columns={"total_loans": "loan_count"})
    df["vintage"] = "All"
    for name in ("score_band", "ltv_band", "dti_band", "term"):
        df[name] = "All"
    return df


@st.cache_data(show_spinner=False)
def get_pd_results(group=None, group_value=None) -> pd.DataFrame:
    release = _current_release()
    if release is None:
        df = _legacy("pd_results")
    else:
        pd_frame = _to_pandas(pd_results(release)).rename(
            columns={"horizon_months": "horizon", "default_cif": "cif_default"}
        )
        survival_frame = _to_pandas(survival_results(release))
        prepay = survival_frame[
            (survival_frame["model"] == "AALEN_JOHANSEN")
            & (survival_frame["endpoint"] == "PREPAYMENT")
        ][["analysis_time", "cumulative_incidence"]].sort_values("analysis_time")
        prepay_rows = []
        for horizon in pd_frame["horizon"].dropna().unique():
            at_horizon = prepay[prepay["analysis_time"] <= horizon]
            prepay_rows.append({
                "horizon": int(horizon),
                "cif_prepayment": float(at_horizon.iloc[-1]["cumulative_incidence"])
                if not at_horizon.empty else 0.0,
            })
        df = pd_frame.merge(pd.DataFrame(prepay_rows), on="horizon", how="left")
        df["group"] = "portfolio"
        df["group_value"] = "all"
        df["vintage"] = "All"
        df["number_at_risk"] = df["n_at_risk"]
        df["follow_up_flag"] = df["follow_up_eligible"]
        grouped = _to_pandas(grouped_pd_results(release)).rename(
            columns={"feature": "group", "horizon_months": "horizon", "default_cif": "cif_default", "prepayment_cif": "cif_prepayment", "n_at_risk": "number_at_risk"}
        )
        grouped["vintage"] = "All"
        grouped["follow_up_flag"] = grouped["follow_up_eligible"]
        df = pd.concat([df, grouped], ignore_index=True, sort=False)
    if df.empty:
        return df
    if group:
        if group == "credit_score_band":
            group = "fico_band"
        if group in df.columns:
            if group_value is not None:
                df = df[df[group].astype(str) == str(group_value)]
        elif group_value is not None:
            return pd.DataFrame()
    return df


@st.cache_data(show_spinner=False)
def get_survival_results(group: str | None = None) -> pd.DataFrame:
    release = _current_release()
    if release is None:
        df = _legacy("survival_results")
    else:
        df = _to_pandas(survival_results(release))
        df = df[(df["model"] == "KAPLAN_MEIER") & (df["endpoint"] == "DEFAULT")].copy()
        df = df.rename(columns={
            "survival_probability": "survival",
            "ci_lower": "ci_low",
            "ci_upper": "ci_high",
        })
        df["group"] = "portfolio"
    if group and "group" in df.columns:
        df = df[df["group"] == group]
    return df


@st.cache_data(show_spinner=False)
def get_risk_driver_results(model_type: str | None = None) -> pd.DataFrame:
    release = _current_release()
    if release is None:
        df = _legacy("risk_driver_results")
    else:
        df = _to_pandas(risk_driver_results(release)).rename(
            columns={"predictor": "variable", "ci_lower": "ci_low", "ci_upper": "ci_high"}
        )
        labels = {
            "BASELINE_COX": "Cox PH",
            "TV_COX": "Time-varying Cox",
            "FINE_GRAY_DEFAULT": "Fine-Gray",
            "CAUSE_SPECIFIC_DEFAULT": "Cause-specific Hazard",
            "CAUSE_SPECIFIC_PREPAYMENT": "Cause-specific Hazard",
        }
        df["model_type"] = df["model"].map(labels).fillna(df["model"])
        df["hr_shr"] = df["subdistribution_hazard_ratio"].fillna(df["hazard_ratio"])
        df["direction"] = df["coefficient"].map(
            lambda value: "increase" if value > 0 else "decrease" if value < 0 else "neutral"
        )
        df["endpoint"] = df["endpoint"].str.title()
    if model_type:
        df = df[df["model_type"].astype(str).str.casefold() == model_type.casefold()]
    return df


@st.cache_data(show_spinner=False)
def get_vintage_results() -> pd.DataFrame:
    release = _current_release()
    if release is None:
        return _legacy("vintage_results")
    df = _to_pandas(vintage_results(release)).rename(
        columns={"vintage_year": "vintage", "horizon_months": "horizon", "default_cif": "default_cif"}
    )
    df["vintage"] = df["vintage"].astype(int)
    return df


@st.cache_data(show_spinner=False)
def get_model_diagnostics(model_type: str | None = None) -> pd.DataFrame:
    release = _current_release()
    if release is None:
        df = _legacy("model_diagnostics")
    else:
        df = _to_pandas(model_diagnostics(release))
        labels = {
            "BASELINE_COX": "Cox PH",
            "TV_COX": "Time-varying Cox",
            "FINE_GRAY_DEFAULT": "Fine-Gray",
            "CAUSE_SPECIFIC_DEFAULT": "Cause-specific Hazard",
            "CAUSE_SPECIFIC_PREPAYMENT": "Cause-specific Hazard",
        }
        df["model_name"] = df["model"].map(labels).fillna(df["model"])
        df["diagnostic_name"] = df["diagnostic_type"].astype(str)
        df["metric"] = df["predictor"].fillna(df["status"])
        df["value"] = df["p_value"]
        df["interpretation"] = df["status"]
    if model_type and "model_name" in df.columns:
        matched = df[df["model_name"].astype(str).str.casefold() == model_type.casefold()]
        df = matched
    return df


@st.cache_data(show_spinner=False)
def get_loan_profile(loan_id: str | None = None) -> pd.DataFrame:
    if not loan_id or not ANALYSIS_PATH.exists():
        return _legacy("loan_profile")
    source = pl.scan_parquet(ANALYSIS_PATH).filter(pl.col("loan_id") == str(loan_id)).limit(1)
    df = source.collect().to_pandas().rename(columns={
        "fico": "credit_score", "vintage_year": "origination_vintage",
        "first_payment_month": "first_payment_date", "maturity_month": "maturity_date",
    })
    return df


@st.cache_data(show_spinner=False)
def get_loan_catalog() -> pd.DataFrame:
    """Return a small, representative, searchable set of eligible loan examples."""
    if not ANALYSIS_PATH.exists():
        return _legacy("loan_profile").head(40)

    columns = [
        "loan_id", "vintage_year", "event_type", "fico", "original_ltv",
        "original_dti", "original_loan_term", "duration_months",
    ]
    catalog = (
        pl.scan_parquet(ANALYSIS_PATH)
        .filter(pl.col("survival_eligible"))
        .select(columns)
        .unique(subset=["vintage_year", "event_type"], keep="first", maintain_order=True)
        .sort(["vintage_year", "event_type"])
        .collect()
        .to_pandas()
        .rename(columns={"vintage_year": "origination_vintage"})
    )
    return catalog


@st.cache_data(show_spinner=False)
def get_loan_timeline(loan_id: str | None = None) -> pd.DataFrame:
    if not loan_id or not PERFORMANCE_PATH.exists() or not ANALYSIS_PATH.exists():
        return _legacy("loan_timeline")
    loan = pl.scan_parquet(ANALYSIS_PATH).filter(pl.col("loan_id") == str(loan_id)).select(
        "loan_id", "operational_origination_date", "event_month", "event_type",
        "survival_eligible",
    ).limit(1).collect()
    if loan.is_empty() or not loan["survival_eligible"][0]:
        return pd.DataFrame()
    master = loan.row(0, named=True)
    origin_index = master["operational_origination_date"].year * 12 + master["operational_origination_date"].month
    monthly = (
        pl.scan_parquet(PERFORMANCE_PATH)
        .filter((pl.col("loan_id") == str(loan_id)) & (pl.col("reporting_period_num") <= 202603))
        .with_columns(
            ((pl.col("performance_month").dt.year() * 12 + pl.col("performance_month").dt.month()) - origin_index)
            .cast(pl.Int32).alias("analysis_time_month"),
        )
        .filter(
            (pl.col("analysis_time_month") >= 0)
            & (pl.col("reporting_period_num") <= master["event_month"])
        )
        .select(
            "loan_id", "reporting_period_num", "performance_month", "analysis_time_month", "current_delinquency_status",
            "current_actual_upb", "current_interest_rate", "zero_balance_code",
        )
        .sort("analysis_time_month")
        .collect()
    )
    if monthly.is_empty():
        return pd.DataFrame()
    monthly = monthly.with_columns(
        pl.when(pl.col("reporting_period_num") == master["event_month"])
        .then(
            pl.lit("VOLUNTARY_PREPAYMENT")
            if master["event_type"] == "PREPAYMENT"
            else pl.lit(master["event_type"])
        )
        .otherwise(pl.lit("CENSORED"))
        .alias("event_type")
    )
    return monthly.to_pandas()
