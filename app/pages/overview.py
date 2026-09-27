"""
Trang 1 — Tổng quan
Trả lời: "Danh mục khoản vay đang có mức rủi ro như thế nào?"

Hiển thị: Total Loans, Default Rate, Prepayment Rate, Default CIF,
PD 12/24/36M, Risk over Loan Age.

Nguồn dữ liệu: portfolio_summary, pd_results, survival_results
(query layer — xem app/services/data_service.py).
"""

import streamlit as st

from app.components.charts import cif_chart, survival_curve_chart
from app.components.kpi_card import kpi_row
from app.components.styling import section_title
from app.services import data_service as ds


def render() -> None:
    st.caption("Trang 1 · Tổng quan danh mục")

    summary = ds.get_portfolio_summary(vintage="All", score_band="All",
                                        ltv_band="All", dti_band="All")
    if summary.empty:
        # fallback: không có bản ghi "All" tổng hợp sẵn -> lấy toàn bộ và
        # coi horizon là chiều duy nhất còn lại
        summary = ds.get_portfolio_summary()

    pd_res = ds.get_pd_results(group="portfolio", vintage="All")
    if pd_res.empty:
        pd_res = ds.get_pd_results()

    survival = ds.get_survival_results(group="portfolio")
    if survival.empty:
        survival = ds.get_survival_results()

    if summary.empty and pd_res.empty:
        st.warning(
            "Chưa có dữ liệu portfolio_summary / pd_results trong query/. "
            "Trang này sẽ hiển thị đầy đủ khi Backend/Data publish 2 dataset đó."
        )
        return

    # ---- KPI row -----------------------------------------------------------
    section_title("Chỉ số tổng quan danh mục")

    total_loans = int(summary["loan_count"].max()) if "loan_count" in summary else None
    default_count = summary.loc[summary["loan_count"].idxmax(), "default_count"] \
        if "loan_count" in summary and not summary.empty else None
    prepay_count = summary.loc[summary["loan_count"].idxmax(), "prepayment_count"] \
        if "loan_count" in summary and not summary.empty else None

    default_rate = (default_count / total_loans) if total_loans and default_count is not None else None
    prepay_rate = (prepay_count / total_loans) if total_loans and prepay_count is not None else None

    latest_horizon = int(pd_res["horizon"].max()) if not pd_res.empty else None
    latest_cif = pd_res.loc[pd_res["horizon"] == latest_horizon, "cif_default"].mean() \
        if latest_horizon is not None else None

    kpi_items = [
        {
            "label": "Total Loans",
            "value": f"{total_loans:,}" if total_loans is not None else "—",
            "delta_positive_is_good": True,
        },
        {
            "label": "Default Rate",
            "value": f"{default_rate:.2%}" if default_rate is not None else "—",
            "help_text": "default_count / loan_count (portfolio_summary)",
        },
        {
            "label": "Prepayment Rate",
            "value": f"{prepay_rate:.2%}" if prepay_rate is not None else "—",
            "help_text": "prepayment_count / loan_count (portfolio_summary)",
        },
        {
            "label": f"Default CIF ({latest_horizon}M)" if latest_horizon else "Default CIF",
            "value": f"{latest_cif:.2%}" if latest_cif is not None else "—",
            "help_text": "Cumulative incidence of Default — PD(t) đã khóa trong specification",
        },
    ]
    kpi_row(kpi_items)

    # ---- PD 12/24/36M -------------------------------------------------------
    section_title("PD theo horizon", "Default CIF tại các horizon đã khóa (12/24/36M; 60M khi đủ follow-up)")
    if not pd_res.empty:
        cols = st.columns(len(pd_res["horizon"].unique()))
        for col, (_, row) in zip(cols, pd_res.sort_values("horizon").iterrows()):
            with col:
                flag = row.get("follow_up_flag", "")
                caption = "follow-up chưa đủ" if str(flag).lower() in ("false", "0", "no") else None
                st.metric(f"PD {int(row['horizon'])}M", f"{row['cif_default']:.2%}", help=caption)
    else:
        st.info("Chưa có pd_results để hiển thị PD theo horizon.")

    # ---- Risk over loan age --------------------------------------------------
    section_title("Risk over Loan Age", "Kaplan–Meier survival + Default CIF theo thời gian kể từ origination")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        if not survival.empty:
            st.plotly_chart(survival_curve_chart(survival), width="stretch")
        else:
            st.info("Chưa có survival_results.")
        st.markdown("</div>", unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        if not pd_res.empty:
            st.plotly_chart(cif_chart(pd_res), width="stretch")
        else:
            st.info("Chưa có pd_results.")
        st.markdown("</div>", unsafe_allow_html=True)
