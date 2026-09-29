"""
Trang 3 — Yếu tố rủi ro
Nơi đưa kết quả Cox / Fine-Gray vào dashboard: forest plot HR/SHR,
Confidence Interval, p-value, direction, interpretation.

Nguồn dữ liệu: risk_driver_results
(model_type, endpoint, variable, coefficient, hr_shr, ci_low, ci_high,
p_value, direction, model_version).
"""

import streamlit as st

from app.components.charts import forest_plot
from app.components.styling import section_title, status_pill
from app.services import data_service as ds

_DIRECTION_ARROW = {"up": "↑", "increase": "↑", "down": "↓", "decrease": "↓"}


def _interpretation_line(row) -> str:
    var = row["variable"]
    direction = str(row.get("direction", "")).lower()
    endpoint = row.get("endpoint", "Default")
    arrow_var = "↑"
    if direction in ("up", "increase", "positive"):
        arrow_endpoint = "↑"
    elif direction in ("down", "decrease", "negative"):
        arrow_endpoint = "↓"
    else:
        arrow_endpoint = "→"
    hazard_word = "hazard" if "hazard" in str(row.get("model_type", "")).lower() or True else "risk"
    return f"{var} {arrow_var} → {endpoint} {hazard_word} {arrow_endpoint}"


def render() -> None:
    st.caption("Trang 3 · Yếu tố rủi ro (Cox / Fine-Gray)")

    risk_df = ds.get_risk_driver_results()
    if risk_df.empty:
        st.warning("Chưa có risk_driver_results trong query/. Trang này cần model results đã publish.")
        return

    c1, c2, c3 = st.columns(3)
    with c1:
        model_type = st.selectbox("Model", sorted(risk_df["model_type"].dropna().unique()))
    endpoints = sorted(risk_df.loc[risk_df["model_type"] == model_type, "endpoint"].dropna().unique())
    with c2:
        endpoint = st.selectbox("Endpoint", endpoints)
    versions = sorted(risk_df.loc[
        (risk_df["model_type"] == model_type) & (risk_df["endpoint"] == endpoint), "model_version"
    ].dropna().unique())
    with c3:
        model_version = st.selectbox("Model version", versions) if versions else None

    sub = risk_df[
        (risk_df["model_type"] == model_type)
        & (risk_df["endpoint"] == endpoint)
        & ((risk_df["model_version"] == model_version) if model_version else True)
    ].copy()

    if sub.empty:
        st.info("Không có hệ số nào khớp với lựa chọn hiện tại.")
        return

    metric_label = "SHR" if "fine-gray" in model_type.lower() else "HR"

    section_title(f"Forest plot — {model_type} ({endpoint})",
                  f"{metric_label} với 95% Confidence Interval. Đường đứt nét = {metric_label} = 1.")
    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    st.plotly_chart(forest_plot(sub), width="stretch")
    st.markdown("</div>", unsafe_allow_html=True)

    section_title("Chi tiết hệ số")
    sub["Ý nghĩa"] = sub.apply(_interpretation_line, axis=1)
    sub["p-value"] = sub["p_value"].map(lambda v: f"{v:.4f}" if v is not None else "—")
    sub[metric_label] = sub["hr_shr"].map(lambda v: f"{v:.3f}")
    sub["95% CI"] = sub.apply(lambda r: f"[{r['ci_low']:.3f}, {r['ci_high']:.3f}]", axis=1)

    display_cols = ["variable", metric_label, "95% CI", "p-value", "direction", "Ý nghĩa"]
    st.dataframe(
        sub[display_cols].rename(columns={"variable": "Variable"}).reset_index(drop=True),
        width="stretch",
    )

    significant = sub[sub["p_value"].astype(float) < 0.05] if "p_value" in sub.columns else sub.iloc[0:0]
    if not significant.empty:
        st.markdown(
            "**Diễn giải nhanh (p < 0.05):** " +
            " · ".join(significant.apply(_interpretation_line, axis=1)),
        )
    st.caption(
        "Lưu ý: đây là interpretation tự sinh theo dấu hệ số thực tế trong "
        "risk_driver_results — không phải giả định trước; nếu direction rỗng, "
        "dòng đó sẽ không xuất hiện trong diễn giải."
    )
