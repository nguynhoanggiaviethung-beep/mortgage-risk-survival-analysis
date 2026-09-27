"""
Trang 5 — Kết quả mô hình (trang học thuật/model)

Cho phép chuyển giữa Kaplan-Meier / Cox PH / Time-varying Cox /
Cause-specific Hazard / Aalen-Johansen (CIF) / Fine-Gray, và trả lời:
"Nếu coi competing risk thế nào thì kết quả Default risk thay đổi ra sao?"

Nguồn dữ liệu: survival_results, pd_results, risk_driver_results,
model_diagnostics.
"""

import streamlit as st

from app.components.charts import cif_chart, forest_plot, km_vs_cif_compare_chart, survival_curve_chart
from app.components.styling import section_title
from app.config import MODEL_TYPE_OPTIONS
from app.services import data_service as ds

_HAZARD_MODELS = {"Cox PH", "Time-varying Cox", "Cause-specific Hazard"}
_CIF_MODELS = {"Aalen-Johansen / CIF", "Fine-Gray"}


def render() -> None:
    st.caption("Trang 5 · Kết quả mô hình")

    model_type = st.selectbox("Model", MODEL_TYPE_OPTIONS)

    diagnostics = ds.get_model_diagnostics(model_type=model_type)

    if model_type == "Kaplan-Meier":
        _render_km()
    elif model_type in _HAZARD_MODELS:
        _render_hazard_model(model_type)
    elif model_type in _CIF_MODELS:
        _render_cif_model(model_type)

    section_title("Model diagnostics")
    if diagnostics.empty:
        st.info(f"Chưa có model_diagnostics cho '{model_type}'.")
    else:
        show_cols = [c for c in [
            "model_version", "diagnostic_name", "metric", "value", "threshold", "interpretation",
        ] if c in diagnostics.columns]
        st.dataframe(diagnostics[show_cols].reset_index(drop=True), width="stretch")

    st.divider()
    _render_competing_risk_comparison()


def _render_km() -> None:
    section_title("Kaplan–Meier survival")
    survival = ds.get_survival_results(group="portfolio")
    if survival.empty:
        survival = ds.get_survival_results()
    if survival.empty:
        st.info("Chưa có survival_results.")
        return
    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    st.plotly_chart(survival_curve_chart(survival), width="stretch")
    st.markdown("</div>", unsafe_allow_html=True)
    st.caption(
        "S(t) = P(T > t) — KM coi mọi termination event (kể cả Voluntary "
        "Prepayment) như censoring nếu không được tách competing-risk."
    )


def _render_hazard_model(model_type: str) -> None:
    section_title(f"{model_type} — Hazard Ratios")
    risk_df = ds.get_risk_driver_results(model_type=model_type)
    if risk_df.empty:
        st.info(f"Chưa có risk_driver_results cho model_type='{model_type}'.")
        return
    endpoints = sorted(risk_df["endpoint"].dropna().unique())
    endpoint = st.radio("Endpoint", endpoints, horizontal=True) if len(endpoints) > 1 else endpoints[0]
    sub = risk_df[risk_df["endpoint"] == endpoint]
    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    st.plotly_chart(forest_plot(sub), width="stretch")
    st.markdown("</div>", unsafe_allow_html=True)


def _render_cif_model(model_type: str) -> None:
    section_title(f"{model_type} — Cumulative Incidence")
    pd_res = ds.get_pd_results(group="portfolio")
    if pd_res.empty:
        pd_res = ds.get_pd_results()
    if pd_res.empty:
        st.info("Chưa có pd_results.")
        return
    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    st.plotly_chart(cif_chart(pd_res), width="stretch")
    st.markdown("</div>", unsafe_allow_html=True)

    if model_type == "Fine-Gray":
        risk_df = ds.get_risk_driver_results(model_type="Fine-Gray")
        if not risk_df.empty:
            section_title("Sub-distribution Hazard Ratios (SHR)")
            endpoints = sorted(risk_df["endpoint"].dropna().unique())
            endpoint = st.radio("Endpoint", endpoints, horizontal=True, key="fg_endpoint") \
                if len(endpoints) > 1 else endpoints[0]
            st.markdown('<div class="chart-card">', unsafe_allow_html=True)
            st.plotly_chart(forest_plot(risk_df[risk_df["endpoint"] == endpoint]), width="stretch")
            st.markdown("</div>", unsafe_allow_html=True)


def _render_competing_risk_comparison() -> None:
    section_title(
        "So sánh: censoring (KM) vs competing risk (CIF)",
        "LOCKED RULE (specification, mục 5): khi Voluntary Prepayment là "
        "competing event, 1 − KM survival KHÔNG được dùng như Default CIF.",
    )
    km = ds.get_survival_results(group="portfolio")
    if km.empty:
        km = ds.get_survival_results()
    cif = ds.get_pd_results(group="portfolio")
    if cif.empty:
        cif = ds.get_pd_results()

    if km.empty or cif.empty:
        st.info("Cần cả survival_results và pd_results để vẽ so sánh này.")
        return

    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    st.plotly_chart(km_vs_cif_compare_chart(km, cif), width="stretch")
    st.markdown("</div>", unsafe_allow_html=True)

    # Gap tại horizon lớn nhất có trong pd_results
    horizon = int(cif["horizon"].max())
    cif_val = cif.loc[cif["horizon"] == horizon, "cif_default"].mean()
    km_row = km.sort_values("analysis_time")
    km_at_h = km_row.loc[km_row["analysis_time"] <= horizon, "survival"]
    if not km_at_h.empty and cif_val == cif_val:
        one_minus_km = 1 - km_at_h.iloc[-1]
        gap = one_minus_km - cif_val
        st.metric(
            f"Chênh lệch tại {horizon}M: (1 − KM) − Default CIF",
            f"{gap:+.2%}",
            help="Chênh lệch dương nghĩa là bỏ qua competing risk sẽ overstate Default probability.",
        )
