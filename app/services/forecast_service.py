"""Individual competing-risk forecasts for new mortgage profiles.

The score is derived from paired cause-specific Cox models fitted to the
project's canonical complete-case loan-level data. No dashboard/group CIF is
used as an individual prediction.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import polars as pl
import streamlit as st

from src.competing_risks.cause_specific import (
    CauseSpecificPairResult,
    fit_paired_cause_specific_models,
)
from src.data.model_dataset import CORE_COLUMNS

from app.services import data_service as ds


FORECAST_HORIZONS = (12, 24, 36)
TRAIN_LAST_VINTAGE = 2020
VALIDATION_VINTAGE = 2021
MIN_VALIDATION_LOANS = 1_000


class ForecastError(ValueError):
    """Raised when a validated individual forecast cannot be produced."""


@dataclass(frozen=True)
class ForecastBundle:
    models: CauseSpecificPairResult
    validation_summary: pd.DataFrame
    ranges: dict[str, tuple[float, float]]
    max_supported_month: int
    n_train: int
    n_validation: int
    default_convergence: str
    prepayment_convergence: str


def _load_complete_cases() -> pl.DataFrame:
    path = ds.PROJECT_ROOT / "data/model/baseline_complete_cases_2016_2026.parquet"
    if not path.is_file():
        raise ForecastError(
            "Không tìm thấy bộ dữ liệu baseline complete-case. Cần có "
            "data/model/baseline_complete_cases_2016_2026.parquet trên máy chạy app."
        )
    try:
        data = pl.read_parquet(path)
    except Exception as exc:
        raise ForecastError(f"Không đọc được dữ liệu mô hình: {exc}") from exc
    required = {
        "vintage_year", "entry_time_month", "exit_time_month", "duration_months",
        "default_event", "prepayment_event", "event_type", *CORE_COLUMNS,
    }
    missing = sorted(required - set(data.columns))
    if missing:
        raise ForecastError(f"Bảng dữ liệu mô hình thiếu các trường: {', '.join(missing)}.")
    if data.is_empty():
        raise ForecastError("Bảng dữ liệu complete-case không có bản ghi.")
    return data


def _survival_vector(models: CauseSpecificPairResult, profiles: pd.DataFrame):
    """Calculate paired CIF and event-free survival on a piecewise-exponential clock."""
    default_model = models.default.model
    prepay_model = models.prepayment.model
    try:
        default_score = default_model.predict_partial_hazard(profiles[CORE_COLUMNS])
        prepay_score = prepay_model.predict_partial_hazard(profiles[CORE_COLUMNS])
    except Exception as exc:
        raise ForecastError(f"Không chấm được hồ sơ bằng mô hình competing-risk: {exc}") from exc
    score_default = np.asarray(default_score, dtype=float).reshape(-1)
    score_prepay = np.asarray(prepay_score, dtype=float).reshape(-1)

    def increments(model) -> dict[float, float]:
        cumulative = model.baseline_cumulative_hazard_.iloc[:, 0].astype(float)
        values = cumulative.to_numpy(dtype=float)
        times = cumulative.index.to_numpy(dtype=float)
        changes = np.diff(np.r_[0.0, values])
        if not np.isfinite(values).all() or not np.isfinite(times).all():
            raise ForecastError("Baseline hazard của mô hình chứa giá trị không hữu hạn.")
        if (changes < -1e-10).any():
            raise ForecastError("Baseline cumulative hazard giảm theo thời gian; dừng dự báo để tránh kết quả sai.")
        return {float(t): max(float(dh), 0.0) for t, dh in zip(times, changes, strict=True)}

    default_dh = increments(default_model)
    prepay_dh = increments(prepay_model)
    times = sorted(set(default_dh) | set(prepay_dh))
    if not times:
        raise ForecastError("Mô hình không có baseline hazard để tạo đường dự báo.")

    n = len(profiles)
    survival = np.ones(n, dtype=float)
    default_cif = np.zeros(n, dtype=float)
    prepay_cif = np.zeros(n, dtype=float)
    curves = {
        "months": [0.0],
        "default_cif": [default_cif.copy()],
        "prepay_cif": [prepay_cif.copy()],
        "survival": [survival.copy()],
    }
    for time in times:
        rate_default = default_dh.get(time, 0.0) * score_default
        rate_prepay = prepay_dh.get(time, 0.0) * score_prepay
        rate_total = rate_default + rate_prepay
        event_probability = -np.expm1(-rate_total)
        share_default = np.divide(
            rate_default, rate_total, out=np.zeros_like(rate_total), where=rate_total > 0
        )
        share_prepay = np.divide(
            rate_prepay, rate_total, out=np.zeros_like(rate_total), where=rate_total > 0
        )
        default_cif = default_cif + survival * event_probability * share_default
        prepay_cif = prepay_cif + survival * event_probability * share_prepay
        survival = survival * np.exp(-rate_total)
        curves["months"].append(float(time))
        curves["default_cif"].append(default_cif.copy())
        curves["prepay_cif"].append(prepay_cif.copy())
        curves["survival"].append(survival.copy())

    curves["months"] = np.asarray(curves["months"], dtype=float)
    for key in ("default_cif", "prepay_cif", "survival"):
        curves[key] = np.vstack(curves[key])
    total_probability = curves["default_cif"] + curves["prepay_cif"] + curves["survival"]
    if not np.isfinite(total_probability).all() or not np.allclose(total_probability, 1.0, atol=1e-8):
        raise ForecastError("Dự báo không thỏa mãn tổng CIF Default + CIF trả trước + chưa sự kiện = 1.")
    return curves


def _at_horizon(curves: dict[str, np.ndarray], horizon: int) -> dict[str, np.ndarray]:
    index = int(np.searchsorted(curves["months"], horizon, side="right") - 1)
    index = max(index, 0)
    return {
        "default_cif": curves["default_cif"][index],
        "prepay_cif": curves["prepay_cif"][index],
        "survival": curves["survival"][index],
    }


def _validation_metrics(models: CauseSpecificPairResult, valid: pl.DataFrame) -> pd.DataFrame:
    profiles = valid.select(CORE_COLUMNS).to_pandas()
    curves = _survival_vector(models, profiles)
    rows = []
    event_type = valid["event_type"].cast(pl.String).str.to_uppercase().to_numpy()
    duration = valid["duration_months"].cast(pl.Float64).to_numpy()
    for horizon in FORECAST_HORIZONS:
        # Include events observed by the horizon, plus loans followed through
        # the horizon. Exclude early right-censoring from the no-event class.
        eligible = (duration >= horizon) | (
            np.isin(event_type, ["DEFAULT", "PREPAYMENT"]) & (duration <= horizon)
        )
        n_eligible = int(eligible.sum())
        if n_eligible < MIN_VALIDATION_LOANS:
            raise ForecastError(
                f"Vintage {VALIDATION_VINTAGE} chỉ có {n_eligible:,} hồ sơ đủ follow-up ở mốc {horizon} tháng; "
                "không đủ ngưỡng kiểm định tối thiểu để bật dự báo."
            )
        y_default = (event_type == "DEFAULT") & (duration <= horizon)
        y_prepay = (event_type == "PREPAYMENT") & (duration <= horizon)
        actual = np.full(len(valid), 2, dtype=np.int8)
        actual[y_default] = 0
        actual[y_prepay] = 1
        prediction = _at_horizon(curves, horizon)
        probabilities = np.column_stack([
            prediction["default_cif"], prediction["prepay_cif"], prediction["survival"]
        ])
        probabilities = np.clip(probabilities, 1e-12, 1.0)
        probabilities /= probabilities.sum(axis=1, keepdims=True)
        observed = np.eye(3, dtype=float)[actual]
        chosen = eligible
        multiclass_brier = float(np.mean(np.sum((probabilities[chosen] - observed[chosen]) ** 2, axis=1)))
        log_loss = float(-np.mean(np.log(probabilities[chosen, actual[chosen]])))
        rows.append({
            "Horizon (tháng)": horizon,
            "Số hồ sơ kiểm định": n_eligible,
            "Default quan sát": int(y_default[chosen].sum()),
            "Trả trước quan sát": int(y_prepay[chosen].sum()),
            "Brier đa lớp (thấp tốt hơn)": multiclass_brier,
            "Log-loss (thấp tốt hơn)": log_loss,
            "CIF Default dự báo TB": float(probabilities[chosen, 0].mean()),
            "Default quan sát TB": float(observed[chosen, 0].mean()),
        })
    return pd.DataFrame(rows)


@st.cache_resource(show_spinner=False)
def load_forecast_bundle() -> ForecastBundle:
    """Fit full paired model once per app process and validate on later vintage."""
    data = _load_complete_cases()
    train = data.filter(pl.col("vintage_year") <= TRAIN_LAST_VINTAGE)
    valid = data.filter(pl.col("vintage_year") == VALIDATION_VINTAGE)
    if train.is_empty() or valid.is_empty():
        raise ForecastError("Thiếu dữ liệu cho tập huấn luyện hoặc vintage kiểm định theo thời gian.")

    train_models = fit_paired_cause_specific_models(train)
    validation_summary = _validation_metrics(train_models, valid)
    full_models = fit_paired_cause_specific_models(data)
    max_time = min(
        float(full_models.default.model.baseline_cumulative_hazard_.index.max()),
        float(full_models.prepayment.model.baseline_cumulative_hazard_.index.max()),
    )
    max_supported_month = int(np.floor(max_time))
    if max_supported_month < max(FORECAST_HORIZONS):
        raise ForecastError(
            f"Baseline hazard chỉ hỗ trợ đến {max_supported_month} tháng; cần ít nhất {max(FORECAST_HORIZONS)} tháng."
        )

    ranges = {}
    for column in CORE_COLUMNS:
        values = data[column].cast(pl.Float64, strict=False).drop_nulls()
        if values.len() == 0:
            continue
        ranges[column] = (float(values.min()), float(values.max()))
    return ForecastBundle(
        models=full_models,
        validation_summary=validation_summary,
        ranges=ranges,
        max_supported_month=max_supported_month,
        n_train=train.height,
        n_validation=valid.height,
        default_convergence=str(full_models.default.diagnostics["convergence_status"][0]),
        prepayment_convergence=str(full_models.prepayment.diagnostics["convergence_status"][0]),
    )


def predict_profile(bundle: ForecastBundle, values: dict[str, float]) -> dict[str, object]:
    """Score one original-loan profile and return CIF paths + horizon estimates."""
    profile = pd.DataFrame([{
        "fico": values["fico"],
        "original_ltv": values["ltv"],
        "original_dti": values["dti"],
        "original_interest_rate": values["rate"],
        "original_loan_term": values["term"],
    },], columns=CORE_COLUMNS)
    curves = _survival_vector(bundle.models, profile)
    max_horizon = min(bundle.max_supported_month, int(values["term"]), max(FORECAST_HORIZONS))
    horizons = [h for h in FORECAST_HORIZONS if h <= max_horizon]
    if not horizons:
        raise ForecastError("Kỳ hạn khoản vay ngắn hơn mốc dự báo tối thiểu 12 tháng.")
    points = curves["months"] <= max_horizon
    output_curves = {key: curves[key][points, 0] for key in ("default_cif", "prepay_cif", "survival")}
    output_curves["months"] = curves["months"][points]
    estimates = {h: _at_horizon(curves, h) for h in horizons}
    outside = []
    for name, column in zip(("fico", "ltv", "dti", "rate", "term"), CORE_COLUMNS, strict=True):
        if column not in bundle.ranges:
            continue
        low, high = bundle.ranges[column]
        value = values[name]
        if value < low or value > high:
            outside.append(f"{column}: đầu vào {value:g}, phạm vi dữ liệu {low:g}–{high:g}")
    return {"curves": output_curves, "estimates": estimates, "horizons": horizons, "outside": outside}
