"""
Trang 5 — Kết quả mô hình (trang học thuật/model)
"""
import pandas as pd
import streamlit as st
from app.components.charts import cif_chart, forest_plot, km_vs_cif_compare_chart, survival_curve_chart
from app.components.styling import section_title
from app.config import MODEL_TYPE_OPTIONS
from app.services import data_service as ds

_HAZARD_MODELS = {"Cox PH", "Time-varying Cox", "Cause-specific Hazard"}
_CIF_MODELS = {"Aalen-Johansen / CIF", "Fine-Gray"}


def render() -> None:
    st.caption("Trang 5 · Kết quả mô hình")

    # -------------------------------------------------------------------------
    # BỔ SUNG: KHỐI BỘ LỌC PHẠM VI DỮ LIỆU (DATA SCOPE FILTERS)
    # -------------------------------------------------------------------------
    st.markdown("### 🎛️ Cấu hình Mô hình & Phạm vi Dữ liệu")
    
    col1, col2 = st.columns([2, 3])

    with col1:
        model_type = st.selectbox("Lựa chọn Mô hình (Model)", MODEL_TYPE_OPTIONS)
    with col2:
        st.info(
            "Ước lượng mô hình dùng cohort complete-case 2016–2026. "
            "Bảng PD theo vintage được xem riêng ở trang Rủi ro danh mục; "
            "dashboard chưa có hệ số mô hình phân tầng theo vintage hoặc nhóm điểm."
        )

    st.divider()

    # -------------------------------------------------------------------------
    diagnostics = ds.get_model_diagnostics(model_type=model_type)

    if model_type == "Kaplan-Meier":
        _render_km()
    elif model_type in _HAZARD_MODELS:
        _render_hazard_model(model_type)
    elif model_type in _CIF_MODELS:
        _render_cif_model(model_type)

    section_title("Model diagnostics")
    if model_type == "Kaplan-Meier":
        st.info(
            "Kaplan–Meier là phương pháp phi tham số, không ước lượng hệ số nên không có "
            "kiểm định hội tụ hay giả định proportional hazards. Dải tin cậy 95% được thể hiện "
            "trên biểu đồ survival phía trên."
        )
    elif diagnostics.empty:
        st.info(f"Chưa có model_diagnostics cho '{model_type}'.")
    else:
        show_cols = [c for c in [
            "model_version", "diagnostic_name", "metric", "value", "threshold", "interpretation",
        ] if c in diagnostics.columns]
        st.dataframe(diagnostics[show_cols].reset_index(drop=True), width="stretch")

    st.divider()
    _render_competing_risk_comparison()


def _render_km(group: str = "portfolio") -> None:
    section_title("Kaplan–Meier survival")
    survival = ds.get_survival_results(group=group)
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
    
    if "endpoint" in risk_df.columns:
        endpoints = sorted(risk_df["endpoint"].dropna().unique())
        endpoint = st.radio("Endpoint", endpoints, horizontal=True) if len(endpoints) > 1 else (endpoints[0] if len(endpoints) > 0 else None)
        sub = risk_df[risk_df["endpoint"] == endpoint] if endpoint else risk_df
    else:
        sub = risk_df

    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    st.plotly_chart(forest_plot(sub), width="stretch")
    st.markdown("</div>", unsafe_allow_html=True)


def _render_cif_model(model_type: str) -> None:
    section_title(f"{model_type} — Cumulative Incidence (Xác suất Vỡ nợ dồn tích)")
    pd_res = ds.get_pd_results(group="portfolio")
    if pd_res.empty:
        pd_res = ds.get_pd_results()
    if pd_res.empty:
        st.info("Chưa có dữ liệu dự báo pd_results.")
        return
        
    # 1. Hiển thị Biểu đồ CIF
    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    st.plotly_chart(cif_chart(pd_res), width="stretch")
    st.markdown("</div>", unsafe_allow_html=True)

    # 2. BỔ SUNG: BẢNG BÁO CÁO XÁC SUẤT VỠ NỢ DỰ BÁO (PD FORECAST TABLE)
    st.subheader("📊 Bảng Kết quả Dự báo Khả năng Vỡ nợ (Default Probability - PD)")
    if "horizon" in pd_res.columns and "cif_default" in pd_res.columns:
        # Lọc các mốc horizon chính (12M, 24M, 36M, 60M)
        summary_pd = pd_res[["horizon", "cif_default"]].drop_duplicates().sort_values("horizon")
        summary_pd["Tên mốc (Horizon)"] = summary_pd["horizon"].apply(lambda x: f"{int(x)} tháng ({int(x/12)} năm)" if x >= 12 else f"{int(x)} tháng")
        summary_pd["Tỷ lệ Vỡ nợ Dự báo (PD %)" ] = (summary_pd["cif_default"] * 100).map("{:.2f}%".format)
        
        st.dataframe(
            summary_pd[["Tên mốc (Horizon)", "Tỷ lệ Vỡ nợ Dự báo (PD %)"]].reset_index(drop=True),
            width="stretch"
        )
        
    if model_type == "Fine-Gray":
        risk_df = ds.get_risk_driver_results(model_type="Fine-Gray")
        if not risk_df.empty:
            section_title("Sub-distribution Hazard Ratios (SHR)")
            if "endpoint" in risk_df.columns:
                endpoints = sorted(risk_df["endpoint"].dropna().unique())
                endpoint = st.radio("Endpoint", endpoints, horizontal=True, key="fg_endpoint") \
                    if len(endpoints) > 1 else (endpoints[0] if len(endpoints) > 0 else None)
                sub_df = risk_df[risk_df["endpoint"] == endpoint] if endpoint else risk_df
            else:
                sub_df = risk_df
                
            st.markdown('<div class="chart-card">', unsafe_allow_html=True)
            st.plotly_chart(forest_plot(sub_df), width="stretch")
            st.markdown("</div>", unsafe_allow_html=True)


def _render_competing_risk_comparison(group: str = "portfolio") -> None:
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

    # 1. Vẽ Biểu đồ So sánh
    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    st.plotly_chart(km_vs_cif_compare_chart(km, cif), width="stretch")
    st.markdown("</div>", unsafe_allow_html=True)

    # 2. Hiển thị Metric Tổng quan
    horizon = int(cif["horizon"].max()) if "horizon" in cif.columns else 60
    cif_val = cif.loc[cif["horizon"] == horizon, "cif_default"].mean() if "horizon" in cif.columns else 0
    
    if "analysis_time" in km.columns:
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

    # 3. BỔ SUNG: BẢNG CHI TIẾT KẾT QUẢ DỰ BÁO CÁC MỐC THỜI GIAN
    st.markdown("#### 📋 Bảng Chi tiết Xác suất Vỡ nợ Dự báo (Default Probability)")
    
    if "horizon" in cif.columns and "cif_default" in cif.columns and "analysis_time" in km.columns:
        horizons_to_show = [12, 24, 36, 48, 60]
        rows = []
        
        for h in horizons_to_show:
            cif_sub = cif[cif["horizon"] == h]
            km_sub = km[km["analysis_time"] <= h]
            
            if not cif_sub.empty and not km_sub.empty:
                val_cif = cif_sub["cif_default"].values[0]
                val_km_pd = 1 - km_sub.sort_values("analysis_time")["survival"].values[-1]
                diff = val_km_pd - val_cif
                
                rows.append({
                    "Mốc theo dõi (Horizon)": f"{h} Tháng",
                    "KM Naive PD (Bỏ qua Prepayment)": f"{val_km_pd:.2%}",
                    "Aalen–Johansen Default CIF (Competing Risk)": f"{val_cif:.2%}",
                    "Mức Thổi phồng Rủi ro (Overestimate Gap)": f"+{diff:.2%}"
                })
        
        if rows:
            st.dataframe(pd.DataFrame(rows), width="stretch")
