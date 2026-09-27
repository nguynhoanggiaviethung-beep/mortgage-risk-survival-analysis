"""
Trang 2 — Rủi ro danh mục
Trả lời: "Nhóm khoản vay nào có mức rủi ro khác nhau?"

Filter/so sánh theo: Credit Score, LTV, DTI, Interest Rate, Loan Term,
Origination Vintage.

Nguồn dữ liệu: pd_results (group / group_value theo từng chiều),
vintage_results cho riêng chiều Origination Vintage.
"""

import streamlit as st

from app.components.charts import risk_by_band_bar
from app.components.styling import section_title
from app.config import HORIZON_OPTIONS
from app.services import data_service as ds

_DIMENSIONS = {
    "Credit Score": "credit_score_band",
    "LTV": "ltv_band",
    "DTI": "dti_band",
    "Interest Rate": "interest_rate_band",
    "Loan Term": "loan_term_band",
    "Origination Vintage": "vintage_band",
}


def render() -> None:
    st.caption("Trang 2 · Rủi ro danh mục theo nhóm khoản vay")

    pd_all = ds.get_pd_results()
    if pd_all.empty:
        st.warning("Chưa có pd_results trong query/. Trang này cần dataset đó để so sánh nhóm.")
        return

    section_title("So sánh rủi ro theo đặc điểm khoản vay",
                  "Chọn 1 chiều so sánh và horizon — số liệu lấy trực tiếp từ pd_results, không tính lại.")

    c1, c2 = st.columns([2, 1])
    with c1:
        dim_label = st.radio(
            "So sánh theo", list(_DIMENSIONS.keys()), horizontal=True,
        )
    with c2:
        horizon = st.selectbox("Horizon", HORIZON_OPTIONS, index=2)  # default 36M

    group_key = _DIMENSIONS[dim_label]
    sub = pd_all[(pd_all.get("group") == group_key) & (pd_all.get("horizon") == horizon)]

    if sub.empty:
        st.info(
            f"Chưa có bản ghi pd_results với group='{group_key}', horizon={horizon}M. "
            f"Kiểm tra lại grouping dimension đã publish trong pipeline."
        )
        return

    sub = sub.sort_values("group_value")

    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    st.plotly_chart(
        risk_by_band_bar(sub, x_col="group_value", y_col="cif_default",
                          y_title=f"Default CIF {horizon}M"),
        width="stretch",
    )
    st.markdown("</div>", unsafe_allow_html=True)

    with st.expander("Xem bảng số liệu chi tiết"):
        show_cols = [c for c in [
            "group_value", "cif_default", "cif_prepayment", "number_at_risk", "follow_up_flag"
        ] if c in sub.columns]
        st.dataframe(sub[show_cols].reset_index(drop=True), width="stretch")

    # ---- Vintage riêng, dùng vintage_results (đúng dataset chuyên biệt) ----
    if dim_label == "Origination Vintage":
        section_title("Chi tiết theo vintage (vintage_results)")
        vintage = ds.get_vintage_results(horizon=horizon)
        if vintage.empty:
            st.info("Chưa có vintage_results cho horizon này.")
        else:
            vintage = vintage.sort_values("vintage")
            st.plotly_chart(
                risk_by_band_bar(vintage, x_col="vintage", y_col="default_cif",
                                  y_title=f"Default CIF {horizon}M theo vintage"),
                width="stretch",
            )
