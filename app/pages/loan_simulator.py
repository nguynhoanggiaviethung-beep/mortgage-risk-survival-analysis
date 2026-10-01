"""Ước lượng mô phỏng rủi ro quá hạn 30+ DPD theo hồ sơ ban đầu."""

from __future__ import annotations

import numpy as np
import pandas as pd
import polars as pl
import streamlit as st
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from app.components.page_blocks import (
    BLUE, GREEN, RED, TINT_BLUE, TINT_GREEN, TINT_RED,
    callout, section_heading, stat_card,
)
from app.services import data_service as ds

FEATURES = ["fico", "original_ltv", "original_dti", "original_interest_rate", "original_loan_term"]
LABELS = {0: "Quá hạn lần đầu từ 30 ngày (30+ DPD)", 1: "ZBC 01 · trả trước/đáo hạn (gộp)", 2: "Chưa ghi nhận hai sự kiện trong horizon"}
OUTCOME_ORDER = [0, 1, 2]


@st.cache_data(show_spinner="Đang chuẩn bị dữ liệu sự kiện 30+ DPD từ lịch sử khoản vay…")
def _training_frame() -> pd.DataFrame:
    """Build one row per loan; early censoring is excluded separately per horizon."""
    if not ds.ANALYSIS_PATH.exists() or not ds.PERFORMANCE_PATH.exists():
        raise FileNotFoundError("Thiếu dữ liệu model hoặc lịch sử performance Parquet.")
    base = pl.scan_parquet(ds.ANALYSIS_PATH).filter(
        pl.col("survival_eligible").fill_null(False)
    ).select(["loan_id", "vintage_year", "duration_months", "event_type", *FEATURES])

    # 30+ DPD is the first recorded monthly delinquency_num >= 1, not the
    # project's 90+ DPD/RA default definition. Study time follows its locked
    # first-payment-minus-one-month proxy (performance month 1 is first payment).
    perf = pl.scan_parquet(ds.PERFORMANCE_PATH).select(
        "loan_id", "reporting_period_num", "delinquency_num"
    ).with_columns(
        pl.col("reporting_period_num").cast(pl.Int32),
        pl.col("delinquency_num").cast(pl.Int16, strict=False),
    ).filter(pl.col("reporting_period_num") <= 202603)
    first_dq = perf.filter(pl.col("delinquency_num") >= 1).group_by("loan_id").agg(
        pl.col("reporting_period_num").min().alias("first_30dpd_yyyymm")
    )
    # Use operational loan exit age for ZBC01 from the already validated event
    # mapping. A censor before horizon removes that loan from the label set.
    frame = base.join(first_dq, on="loan_id", how="left").collect()
    data = frame.to_pandas()
    yyyymm = pd.to_numeric(data.pop("first_30dpd_yyyymm"), errors="coerce")
    yy = np.floor(yyyymm / 100)
    mm = yyyymm % 100
    # first payment month is analysis month 1; event month in mapping is the
    # reporting month. Therefore month difference + 1 is the research clock.
    # `duration_months` is the terminal observed month on that same clock.
    # Exact first-payment date is not duplicated in this compact analysis table;
    # reconstruct event age from vintage is not valid, so load it from origination.
    orig_path = ds.PROJECT_ROOT / "data/processed/origination.parquet"
    if not orig_path.exists():
        raise FileNotFoundError("Thiếu origination.parquet để quy đổi thời điểm 30+ DPD.")
    first_pay = pl.scan_parquet(orig_path).select("loan_id", "first_payment_date").collect().to_pandas()
    data = data.merge(first_pay, on="loan_id", how="left", validate="one_to_one")
    fpd = pd.to_datetime(data.pop("first_payment_date"), errors="coerce")
    event_age = (yy - fpd.dt.year) * 12 + (mm - fpd.dt.month) + 1
    data["first_30dpd_age"] = event_age
    data["event_type"] = data["event_type"].astype(str).str.upper()
    return data


def _labels_for_horizon(data: pd.DataFrame, horizon: int) -> pd.DataFrame:
    out = data.copy()
    duration = pd.to_numeric(out["duration_months"], errors="coerce")
    dq_age = pd.to_numeric(out["first_30dpd_age"], errors="coerce")
    dq_age = dq_age.where((dq_age >= 1) & (dq_age <= duration))
    prepay_age = duration.where(out["event_type"].eq("PREPAYMENT"))
    earliest = pd.concat([dq_age.rename("dq"), prepay_age.rename("prepay")], axis=1).min(axis=1)
    observable = (earliest <= horizon) | (duration >= horizon)
    out = out.loc[observable].copy()
    dq_age, prepay_age = dq_age.loc[observable], prepay_age.loc[observable]
    label = np.full(len(out), 2, dtype=int)
    # Same-month priority is overdue first; prepayment only wins if it occurs earlier.
    label = pd.Series(label, index=out.index)
    label.loc[dq_age.notna() & (dq_age <= horizon) & (dq_age <= prepay_age.fillna(np.inf))] = 0
    label.loc[prepay_age.notna() & (prepay_age <= horizon) & (prepay_age < dq_age.fillna(np.inf))] = 1
    out["target"] = label
    return out


@st.cache_resource(show_spinner=False)
def _fit_model(horizon: int):
    data = _labels_for_horizon(_training_frame(), horizon)
    # Temporal holdout: train on earlier originations, validate on later cohorts.
    train = data[data["vintage_year"] <= 2022]
    valid = data[data["vintage_year"] >= 2023]
    if train.empty or valid.empty or set(train["target"].unique()) != set(OUTCOME_ORDER):
        raise ValueError("Tập huấn luyện theo vintage chưa có đủ cả ba kết cục để ước lượng xác suất đáng tin cậy.")
    model = make_pipeline(
        SimpleImputer(strategy="median", add_indicator=True),
        StandardScaler(),
        LogisticRegression(max_iter=500, solver="lbfgs"),
    )
    model.fit(train[FEATURES], train["target"])
    probabilities = model.predict_proba(valid[FEATURES])
    classes = model[-1].classes_
    metrics = {
        "n_train": len(train), "n_valid": len(valid),
        "accuracy": accuracy_score(valid["target"], model.predict(valid[FEATURES])),
        "log_loss": log_loss(valid["target"], probabilities, labels=classes),
        "classes": list(classes),
        "feature_ranges": {
            column: (float(train[column].min()), float(train[column].max()))
            for column in FEATURES if pd.to_numeric(train[column], errors="coerce").notna().any()
        },
    }
    auc = {}
    brier = {}
    for cls in classes:
        binary = (valid["target"] == cls).astype(int)
        auc[int(cls)] = roc_auc_score(binary, probabilities[:, list(classes).index(cls)]) if binary.nunique() == 2 else np.nan
        brier[int(cls)] = brier_score_loss(binary, probabilities[:, list(classes).index(cls)])
    metrics["auc"] = auc
    metrics["brier"] = brier
    metrics["valid_counts"] = valid["target"].value_counts().to_dict()
    return model, metrics


def render() -> None:
    st.caption("MÔ PHỎNG · RỦI RO QUÁ HẠN 30+ DPD")
    callout(
        "Quy ước riêng của mô phỏng: sự kiện trễ hạn là lần đầu ghi nhận delinquency_num ≥ 1 (từ 30 ngày quá hạn); "
        "ZBC 01 (trả trước hoặc đáo hạn gộp) là sự kiện cạnh tranh; ZBC 15/16/96 và kết thúc dữ liệu là kiểm duyệt. "
        "Nếu trễ 30+ và ZBC 01 cùng tháng, trễ 30+ được ưu tiên. Khoản bị kiểm duyệt trước horizon bị loại khỏi nhãn “chưa ghi nhận sự kiện”. "
        "Định nghĩa này khác với Default 90+ DPD/RA dùng trong nghiên cứu chính."
    )
    section_heading(1, "Chọn đặc điểm khoản vay", "Kết quả là xác suất mô hình theo nhóm sự kiện trong horizon, không phải quyết định tín dụng hay PD 90+.")
    a, b, c = st.columns(3)
    with a:
        fico = st.number_input("Điểm FICO", 300, 850, 720, step=1)
        ltv = st.number_input("LTV ban đầu (%)", 1.0, 200.0, 80.0, step=1.0)
    with b:
        dti = st.number_input("DTI ban đầu (%)", 0.0, 100.0, 35.0, step=1.0)
        rate = st.number_input("Lãi suất ban đầu (%)", 0.0, 30.0, 4.0, step=0.1)
    with c:
        term = st.selectbox("Kỳ hạn ban đầu (tháng)", [120, 180, 240, 300, 360], index=4)
        horizon = st.selectbox("Khoảng dự báo", [12, 24, 36], index=2, format_func=lambda x: f"{x} tháng")

    if not st.button("Huấn luyện, kiểm định và mô phỏng", type="primary"):
        st.info("Nhấn nút để hệ thống tạo nhãn 30+ DPD từ dữ liệu tháng, kiểm định theo vintage rồi mới hiển thị xác suất.")
        return
    try:
        with st.spinner("Đang huấn luyện và kiểm định trên các nhóm vintage…"):
            model, metrics = _fit_model(int(horizon))
        profile = pd.DataFrame([{
            "fico": fico, "original_ltv": ltv, "original_dti": dti,
            "original_interest_rate": rate, "original_loan_term": term,
        }])
        probabilities = model.predict_proba(profile)[0]
        classes = model[-1].classes_
    except Exception as exc:
        st.error(f"Chưa thể tạo mô phỏng: {exc}")
        return

    section_heading(2, f"Kết quả mô phỏng trong {horizon} tháng", "Các xác suất phụ thuộc vào mẫu huấn luyện và giả định của mô hình.")
    input_values = profile.iloc[0].to_dict()
    outside = [
        f"{name}: {input_values[name]:g} (mẫu huấn luyện {low:g}–{high:g})"
        for name, (low, high) in metrics["feature_ranges"].items()
        if input_values[name] < low or input_values[name] > high
    ]
    if outside:
        st.warning("Một số đầu vào nằm ngoài khoảng mô hình từng quan sát; kết quả là ngoại suy và có thể kém tin cậy: " + "; ".join(outside))
    cards = st.columns(3)
    palettes = {0: (RED, TINT_RED), 1: (BLUE, TINT_BLUE), 2: (GREEN, TINT_GREEN)}
    for i, cls in enumerate(OUTCOME_ORDER):
        probability = float(probabilities[list(classes).index(cls)]) if cls in classes else 0.0
        with cards[i]:
            stat_card(
                LABELS[cls], f"{probability:.1%}",
                "Xác suất ước lượng trong horizon đã chọn.", *palettes[cls],
            )
    with st.expander("Kiểm định mô hình và cách hiểu kết quả", expanded=True):
        st.write(f"Tập huấn luyện (vintage đến 2022): {metrics['n_train']:,} khoản; tập kiểm định (vintage 2023 trở đi): {metrics['n_valid']:,} khoản.")
        st.write(f"Độ chính xác phân lớp: {metrics['accuracy']:.1%} · Log-loss: {metrics['log_loss']:.4f} (thấp hơn tốt hơn).")
        auc_text = " · ".join(f"{LABELS[k]}: {v:.3f}" for k, v in metrics["auc"].items() if np.isfinite(v))
        st.write("AUC một-vs-còn-lại: " + (auc_text or "không tính được cho lớp thiếu ở tập kiểm định"))
        st.write("Số ca kiểm định theo kết cục: " + " · ".join(
            f"{LABELS[k]}: {metrics['valid_counts'].get(k, metrics['valid_counts'].get(str(k), 0)):,}"
            for k in OUTCOME_ORDER
        ))
        st.write("Brier score theo lớp (thấp hơn tốt hơn): " + " · ".join(
            f"{LABELS[k]}: {v:.4f}" for k, v in metrics["brier"].items()
        ))
        st.warning(
            "Đây là mô hình logistic đa lớp nền, chưa hiệu chỉnh xác suất (calibration) và chưa được duyệt làm mô hình quyết định. "
            "“Chưa ghi nhận sự kiện” chỉ có nghĩa là không có 30+ DPD hoặc ZBC 01 quan sát được đến horizon; "
            "không khẳng định người vay luôn thanh toán đúng hạn. Mô hình không thay thế kết quả survival/competing-risk 90+ DPD."
        )
