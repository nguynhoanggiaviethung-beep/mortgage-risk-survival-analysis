"""
Trang 4 — Tra cứu khoản vay
Trả lời: "Khoản vay cụ thể này có lịch sử và trạng thái như thế nào?"

Có: Loan ID search, loan characteristics, monthly timeline, event status,
loan age, current status, comparable-group risk.

Nguồn dữ liệu: loan_profile, loan_timeline, pd_results (cho comparable group).
"""

import streamlit as st

from app.components.charts import loan_timeline_chart
from app.components.styling import section_title, status_pill
from app.services import data_service as ds


def _credit_score_band(score: float) -> str:
    if score < 650:
        return "<650"
    if score < 700:
        return "650–699"
    if score < 750:
        return "700–749"
    return "750+"


def render() -> None:
    st.caption("Trang 4 · Tra cứu khoản vay")

    loan_id = st.text_input("Loan ID", placeholder="Nhập Loan Sequence Number, ví dụ: F16Q10001234")
    if not loan_id:
        st.info("Nhập Loan ID để xem hồ sơ khoản vay.")
        return

    profile = ds.get_loan_profile(loan_id=loan_id)
    timeline = ds.get_loan_timeline(loan_id=loan_id)

    if profile.empty:
        st.error(f"Không tìm thấy Loan ID '{loan_id}' trong loan_profile.")
        return

    p = profile.iloc[0]

    # ---- Loan profile card ---------------------------------------------------
    section_title("Loan Profile")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Loan ID", str(p.get("loan_id", "—")))
    c1.metric("Origination", str(p.get("origination_vintage", "—")))
    c2.metric("Credit Score", f"{p.get('credit_score', float('nan')):.0f}"
              if p.get("credit_score") == p.get("credit_score") else "—")
    c2.metric("LTV", f"{p.get('original_ltv', float('nan')):.0f}%"
              if p.get("original_ltv") == p.get("original_ltv") else "—")
    c3.metric("DTI", f"{p.get('original_dti', float('nan')):.0f}%"
              if p.get("original_dti") == p.get("original_dti") else "—")
    c3.metric("Interest Rate", f"{p.get('original_interest_rate', float('nan')):.2f}%"
              if p.get("original_interest_rate") == p.get("original_interest_rate") else "—")
    c4.metric("Loan Term", f"{p.get('original_loan_term', '—')} months")
    c4.metric("Maturity Date", str(p.get("maturity_date", "—"))[:10])

    # ---- Current status --------------------------------------------------------
    section_title("Current Status")
    if timeline.empty:
        st.info("Chưa có loan_timeline cho khoản vay này.")
        loan_age = None
    else:
        last_row = timeline.sort_values("analysis_time_month").iloc[-1]
        loan_age = int(last_row["analysis_time_month"])
        event_type = last_row.get("event_type", "CENSORED")
        if event_type == "DEFAULT":
            pill = status_pill("Default", "bad")
        elif event_type == "VOLUNTARY_PREPAYMENT":
            pill = status_pill("Prepaid", "warn")
        else:
            pill = status_pill("Active", "ok")

        c1, c2, c3 = st.columns(3)
        c1.markdown(f"**Status**<br>{pill}", unsafe_allow_html=True)
        c2.metric("Loan Age", f"{loan_age} months")
        c3.metric("Current Delinquency", str(last_row.get("current_delinquency_status", "—")))

    # ---- Timeline ----------------------------------------------------------------
    section_title("Timeline", "Trục thời gian kể từ Operational Origination Date đã khóa trong specification (mục 5.1.2)")
    if not timeline.empty:
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        st.plotly_chart(loan_timeline_chart(timeline, loan_age=loan_age), width="stretch")
        st.markdown("</div>", unsafe_allow_html=True)
        with st.expander("Xem bảng monthly timeline"):
            show_cols = [c for c in [
                "performance_month", "analysis_time_month", "current_delinquency_status",
                "current_actual_upb", "current_interest_rate", "zero_balance_code", "event_type",
            ] if c in timeline.columns]
            st.dataframe(
                timeline[show_cols].sort_values("analysis_time_month").reset_index(drop=True),
                width="stretch",
            )

    # ---- Comparable-group risk ----------------------------------------------------
    section_title("Comparable-group risk", "Default CIF của nhóm khoản vay cùng Credit Score band (pd_results)")
    score = p.get("credit_score")
    if score == score:  # not NaN
        band = _credit_score_band(score)
        comp = ds.get_pd_results(group="credit_score_band", group_value=band)
        if comp.empty:
            st.info(f"Chưa có pd_results cho nhóm Credit Score {band}.")
        else:
            cols = st.columns(len(comp["horizon"].unique()))
            for col, (_, row) in zip(cols, comp.sort_values("horizon").iterrows()):
                with col:
                    st.metric(f"Nhóm {band} — PD {int(row['horizon'])}M", f"{row['cif_default']:.2%}")
    else:
        st.info("Không xác định được Credit Score band do thiếu credit_score.")
