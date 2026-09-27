"""
Data service — lớp truy cập DUY NHẤT vào query layer.

Theo đúng nguyên tắc trong Project_Specification_Mortgage_Survival_Analysis.docx
(mục 7 "Frontend chỉ nhận query-layer contracts" và mục 8–9 Frontend Data
Contracts): dashboard KHÔNG đọc raw/model internals, KHÔNG tự định nghĩa lại
metric — chỉ đọc 8 dataset đã được publish sẵn ở thư mục `query/`.

Cột bắt buộc từng dataset (đúng mục 9 của specification):

- portfolio_summary: horizon, vintage, score_band, ltv_band, dti_band,
  loan_count, default_count, prepayment_count, default_cif, km_survival?
- pd_results: horizon, group, group_value, vintage, cif_default,
  cif_prepayment, number_at_risk, follow_up_flag
- survival_results: analysis_time, group, group_value, survival,
  ci_low, ci_high
- risk_driver_results: model_type, endpoint, variable, coefficient,
  hr_shr, ci_low, ci_high, p_value, direction, model_version
- vintage_results: vintage, horizon, loan_count, default_cif,
  prepayment_cif, ci_low, ci_high
- loan_profile: loan_id, origination_vintage, credit_score, original_ltv,
  original_dti, original_interest_rate, original_loan_term,
  first_payment_date, maturity_date
- loan_timeline: loan_id, performance_month, analysis_time_month,
  current_delinquency_status, current_actual_upb, current_interest_rate,
  zero_balance_code, event_type
- model_diagnostics: model_type, model_version, diagnostic_name, metric,
  value, threshold, interpretation
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import streamlit as st

# Thư mục query/ — mặc định ngang hàng với app/, override bằng env var
# MORTGAGE_QUERY_DIR (đúng path convention ở mục 7.1 của specification).
_DEFAULT_QUERY_DIR = Path(__file__).resolve().parents[2] / "query"
QUERY_DIR = Path(os.environ.get("MORTGAGE_QUERY_DIR", _DEFAULT_QUERY_DIR))

_FILES = {
    "portfolio_summary": "portfolio_summary.parquet",
    "pd_results": "pd_results.parquet",
    "survival_results": "survival_results.parquet",
    "risk_driver_results": "risk_driver_results.parquet",
    "vintage_results": "vintage_results.parquet",
    "loan_profile": "loan_profile.parquet",
    "loan_timeline": "loan_timeline.parquet",
    "model_diagnostics": "model_diagnostics.parquet",
}


class QueryDatasetMissing(Exception):
    """Raised khi 1 file query-layer chưa tồn tại."""


@st.cache_data(show_spinner=False)
def _load(name: str) -> pd.DataFrame:
    path = QUERY_DIR / _FILES[name]
    if not path.exists():
        raise QueryDatasetMissing(
            f"Chưa có dataset '{name}' tại {path}. "
            f"Kiểm tra lại pipeline Backend/Data hoặc biến môi trường "
            f"MORTGAGE_QUERY_DIR."
        )
    return pd.read_parquet(path)


def try_load(name: str) -> tuple[pd.DataFrame | None, str | None]:
    """Trả về (df, None) nếu OK, hoặc (None, error_message) nếu thiếu file.
    Dùng ở page-level để hiện cảnh báo thay vì crash cả app."""
    try:
        return _load(name), None
    except QueryDatasetMissing as e:
        return None, str(e)
    except Exception as e:  # lỗi đọc file khác (schema, corrupt...)
        return None, f"Lỗi khi đọc '{name}': {e}"


# ---- Accessor tiện dụng cho từng trang --------------------------------------

def get_portfolio_summary(**filters) -> pd.DataFrame:
    df, err = try_load("portfolio_summary")
    if df is None:
        return pd.DataFrame()
    return _apply_filters(df, filters)


def get_pd_results(**filters) -> pd.DataFrame:
    df, err = try_load("pd_results")
    if df is None:
        return pd.DataFrame()
    return _apply_filters(df, filters)


def get_survival_results(**filters) -> pd.DataFrame:
    df, err = try_load("survival_results")
    if df is None:
        return pd.DataFrame()
    return _apply_filters(df, filters)


def get_risk_driver_results(**filters) -> pd.DataFrame:
    df, err = try_load("risk_driver_results")
    if df is None:
        return pd.DataFrame()
    return _apply_filters(df, filters)


def get_vintage_results(**filters) -> pd.DataFrame:
    df, err = try_load("vintage_results")
    if df is None:
        return pd.DataFrame()
    return _apply_filters(df, filters)


def get_loan_profile(loan_id: str | None = None) -> pd.DataFrame:
    df, err = try_load("loan_profile")
    if df is None:
        return pd.DataFrame()
    if loan_id:
        df = df[df["loan_id"] == loan_id]
    return df


def get_loan_timeline(loan_id: str | None = None) -> pd.DataFrame:
    df, err = try_load("loan_timeline")
    if df is None:
        return pd.DataFrame()
    if loan_id:
        df = df[df["loan_id"] == loan_id]
    return df


def get_model_diagnostics(**filters) -> pd.DataFrame:
    df, err = try_load("model_diagnostics")
    if df is None:
        return pd.DataFrame()
    return _apply_filters(df, filters)


def dataset_status() -> dict[str, bool]:
    """Dùng cho 1 khối "Data health" nhỏ — dataset nào đã sẵn sàng."""
    status = {}
    for name in _FILES:
        df, err = try_load(name)
        status[name] = df is not None
    return status


def _apply_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    out = df
    for col, value in filters.items():
        if value is None or col not in out.columns:
            continue
        if isinstance(value, (list, tuple, set)):
            out = out[out[col].isin(value)]
        else:
            out = out[out[col] == value]
    return out
