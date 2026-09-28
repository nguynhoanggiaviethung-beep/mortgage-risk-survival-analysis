"""
Trang 1 — Tổng quan
Trả lời: "Danh mục khoản vay đang có mức rủi ro như thế nào?"

Hiển thị: Total Loans, Default Rate, Prepayment Rate, Default CIF,
PD 12/24/36M, Risk over Loan Age.

Nguồn dữ liệu (query layer): portfolio_summary, pd_results, survival_results.

Lưu ý: trang này chỉ gọi ds.get_xxx() KHÔNG truyền tham số, sau đó tự lọc
bằng pandas -> không phụ thuộc chữ ký hàm trong data_service.py.
"""

import pandas as pd
import streamlit as st

from app.components.charts import cif_chart, survival_curve_chart
from app.components.kpi_card import kpi_row
from app.components.styling import section_title
from app.services import data_service as ds


def _pick(df: pd.DataFrame, **conds) -> pd.DataFrame:
    """Lọc df theo các cột có tồn tại. Nếu lọc xong rỗng -> trả lại df gốc."""
    if df is None or df.empty:
        return pd.DataFrame()
    out = df
    for col, val in conds.items():
        if col in out.columns:
            out = out[out[col].astype(str) == str(val)]
    return out if not out.empty else df


def _per_horizon(df: pd.DataFrame, value_col: str) -> pd.DataFrame:
    """Mỗi horizon 1 dòng (lấy trung bình nếu còn nhiều dòng)."""
    if df.empty or "horizon" not in df.columns or value_col not in df.columns:
        return pd.DataFrame()
    return (
        df.groupby("horizon", as_index=False)[value_col]
        .mean()
        .sort_values("horizon")
    )


def _fmt_pct(v) -> str:
    return f"{v:.2%}" if v is not None and pd.notna(v) else "—"


def render() -> None:
    st.caption("Trang 1 · Tổng quan danh mục")

    summary_raw = ds.get_portfolio_summary()
    pd_raw = ds.get_pd_results()
    surv_raw = ds.get_survival_results()

    if summary_raw.empty and pd_raw.empty:
        st.warning(
            "Chưa đọc được dữ liệu portfolio_summary / pd_results. "
            "Kiểm tra thư mục query/ (xem cột 'Trạng thái dữ liệu' bên trái) "
            "hoặc đặt biến môi trường MORTGAGE_QUERY_DIR."
        )
        return

    summary = _pick(summary_raw, vintage="All", score_band="All", ltv_band="All", dti_band="All")
    pd_res = _pick(pd_raw, group="portfolio", vintage="All")
    survival = _pick(surv_raw, group="portfolio")

    # ---- KPI -------------------------------------------------------------------
    section_title("Chỉ số tổng quan danh mục")

    total_loans = default_rate = prepay_rate = None
    if not summary.empty and "loan_count" in summary.columns:
        top = summary.loc[summary["loan_count"].idxmax()]
        total_loans = int(top["loan_count"])
        if total_loans and "default_count" in summary.columns:
            default_rate = top["default_count"] / total_loans
        if total_loans and "prepayment_count" in summary.columns:
            prepay_rate = top["prepayment_count"] / total_loans

    cif_by_h = _per_horizon(pd_res, "cif_default")
    latest_h = int(cif_by_h["horizon"].max()) if not cif_by_h.empty else None
    latest_cif = (
        float(cif_by_h.loc[cif_by_h["horizon"] == latest_h, "cif_default"].iloc[0])
        if latest_h is not None else None
    )

    kpi_row([
        {"label": "Total Loans",
         "value": f"{total_loans:,}" if total_loans is not None else "—",
         "help_text": "portfolio_summary.loan_count"},
        {"label": "Default Rate", "value": _fmt_pct(default_rate),
         "help_text": "default_count / loan_count"},
        {"label": "Prepayment Rate", "value": _fmt_pct(prepay_rate),
         "help_text": "prepayment_count / loan_count"},
        {"label": f"Default CIF ({latest_h}M)" if latest_h else "Default CIF",
         "value": _fmt_pct(latest_cif),
         "help_text": "PD(t) = Default CIF (specification, mục 5)"},
    ])

    # ---- PD theo horizon ---------------------------------------------------------
    section_title("PD theo horizon",
                  "Default CIF tại các horizon đã khóa (12/24/36M; 60M khi đủ follow-up)")
    if cif_by_h.empty:
        st.info("Chưa có cif_default trong pd_results.")
    else:
        cols = st.columns(len(cif_by_h))
        for col, (_, row) in zip(cols, cif_by_h.iterrows()):
            with col:
                st.metric(f"PD {int(row['horizon'])}M", _fmt_pct(row["cif_default"]))

    # ---- Risk over loan age -------------------------------------------------------
    section_title("Risk over Loan Age",
                  "Kaplan–Meier survival và Default CIF theo thời gian kể từ origination")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        if not survival.empty and {"analysis_time", "survival"}.issubset(survival.columns):
            st.plotly_chart(survival_curve_chart(survival), width="stretch")
        else:
            st.info("Chưa có survival_results (cần cột analysis_time, survival).")
        st.markdown("</div>", unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        if not pd_res.empty and {"horizon", "cif_default"}.issubset(pd_res.columns):
            chart_df = (
                pd_res.groupby("horizon", as_index=False)
                .agg({c: "mean" for c in ["cif_default", "cif_prepayment"] if c in pd_res.columns})
            )
            st.plotly_chart(cif_chart(chart_df), width="stretch")
        else:
            st.info("Chưa có pd_results (cần cột horizon, cif_default).")
        st.markdown("</div>", unsafe_allow_html=True)