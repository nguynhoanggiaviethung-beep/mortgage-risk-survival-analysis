"""
Entry point của dashboard — điều hướng các trang phân tích và mô phỏng
Gói_1_Dự_án_4.docx, giao diện đồng bộ với Project Specification (docx).

Chạy: streamlit run app/app.py
"""

import sys
from pathlib import Path

import streamlit as st

# Cho phép chạy `streamlit run app/app.py` từ bất kỳ thư mục nào — thêm
# project root (cha của app/) vào sys.path để "import app.xxx" hoạt động.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.components.styling import app_header, inject_global_css
from app.config import ACCENT, APP_SUBTITLE, APP_TITLE, PAGE_ICONS, PRIMARY, PRIMARY_DARK, TEXT_MUTED
from app.pages import loan_explorer, loan_simulator, model_insights, overview, portfolio_risk, risk_drivers
from app.services import data_service as ds

# Phạm vi dữ liệu đã khóa trong Project Specification (mục 1)
COHORT_DEFAULT = "2016 – 2026"
PERFORMANCE_CUTOFF = "31/03/2026"

st.set_page_config(
    page_title=APP_TITLE,
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_global_css()


def _page_overview():
    app_header(
        "Mortgage risk overview",
        "Theo dõi xác suất vỡ nợ và trả trước từ dữ liệu khoản vay Freddie Mac.",
        "LOAN BOOK / 01",
    )
    overview.render()


def _page_portfolio_risk():
    app_header("Rủi ro danh mục", "Đo lường xác suất vỡ nợ và trả trước theo nhóm khoản vay.", "PORTFOLIO / 02")
    portfolio_risk.render()


def _page_risk_drivers():
    app_header("Yếu tố rủi ro", "Đọc chiều hướng và độ bất định của các yếu tố liên quan đến rủi ro.", "RISK DRIVERS / 03")
    risk_drivers.render()


def _page_loan_explorer():
    app_header("Tra cứu khoản vay", "Xem đặc điểm và lịch sử quan sát của một khoản vay theo Loan ID.", "LOAN BOOK / 04")
    loan_explorer.render()


def _page_model_insights():
    app_header("Kết quả mô hình", "Đánh giá đường cong sống sót, xác suất tích lũy và giả định mô hình.", "MODEL REVIEW / 05")
    model_insights.render()


def _page_loan_simulator():
    app_header("Mô phỏng khoản vay", "Ước lượng sự kiện quá hạn 30+ ngày theo đặc điểm khoản vay ban đầu.", "SIMULATION / 06")
    loan_simulator.render()


PAGES = [
    st.Page(_page_overview, title="Tổng quan", icon=PAGE_ICONS["overview"], default=True),
    st.Page(_page_portfolio_risk, title="Rủi ro danh mục", icon=PAGE_ICONS["portfolio_risk"]),
    st.Page(_page_risk_drivers, title="Yếu tố rủi ro", icon=PAGE_ICONS["risk_drivers"]),
    st.Page(_page_loan_explorer, title="Tra cứu khoản vay", icon=PAGE_ICONS["loan_explorer"]),
    st.Page(_page_model_insights, title="Kết quả mô hình", icon=PAGE_ICONS["model_insights"]),
    st.Page(_page_loan_simulator, title="Mô phỏng khoản vay", icon="🧮"),
]


def _vintage_counts():
    """Số khoản vay theo năm origination (Series index=năm). None nếu chưa có dữ liệu.
    Ưu tiên vintage_results -> portfolio_summary -> loan_profile."""
    try:
        v = ds.get_vintage_results()
        if not v.empty and {"vintage", "loan_count"}.issubset(v.columns):
            return v.groupby("vintage")["loan_count"].max().sort_index()
    except Exception:
        pass
    try:
        s = ds.get_portfolio_summary()
        if not s.empty and {"vintage", "loan_count"}.issubset(s.columns):
            s = s[s["vintage"].astype(str) != "All"]
            if not s.empty:
                return s.groupby("vintage")["loan_count"].max().sort_index()
    except Exception:
        pass
    try:
        p = ds.get_loan_profile()
        if not p.empty and "origination_vintage" in p.columns:
            return p.groupby("origination_vintage").size().sort_index()
    except Exception:
        pass
    return None


def _render_sidebar_dataset_card() -> None:
    counts = _vintage_counts()

    if counts is not None and len(counts) > 0:
        years = [str(y) for y in counts.index]
        cohort = f"{years[0]} – {years[-1]}" if len(years) > 1 else years[0]
        total = int(counts.sum())
        peak = float(counts.max()) or 1.0
        rows = "".join(
            f"""
            <div style="display:flex;align-items:center;gap:8px;margin:5px 0;">
              <span style="width:34px;font-size:12px;color:{PRIMARY_DARK};font-weight:600;">{y}</span>
              <div style="flex:1;background:#46594D;border-radius:3px;height:9px;">
                <div style="width:{max(int(c / peak * 100), 3)}%;background:{PRIMARY};height:9px;border-radius:4px;"></div>
              </div>
              <span style="width:58px;text-align:right;font-size:11px;color:{TEXT_MUTED};">{int(c):,}</span>
            </div>"""
            for y, c in zip(years, counts.values)
        )
        total_html = f"""
            <div style="font-size:11px;color:{TEXT_MUTED};text-transform:uppercase;letter-spacing:.03em;">Tổng số khoản vay</div>
            <div style="font-size:22px;font-weight:700;color:{PRIMARY_DARK};margin-bottom:8px;">{total:,}</div>"""
        by_year_html = f"""
            <div style="font-size:11px;color:{TEXT_MUTED};text-transform:uppercase;letter-spacing:.03em;margin-top:6px;">Theo năm origination</div>
            {rows}"""
    else:
        cohort = COHORT_DEFAULT
        total_html = ""
        by_year_html = f"""
            <div style="font-size:12px;color:{TEXT_MUTED};margin-top:6px;">
              Chưa đọc được số liệu theo năm — sẽ hiện khi có dữ liệu trong query/.
            </div>"""

    with st.expander(f"Dữ liệu khoản vay · {cohort}"):
        st.html(
            f"""
            <div style="background:#F6F3E9;border:1px solid #DCD7C8;border-left:3px solid #B99B53;
                        padding:10px 12px;color:{PRIMARY_DARK};">
              <div style="font-size:11px;color:{TEXT_MUTED};text-transform:uppercase;letter-spacing:.06em;">Origination vintage</div>
              <div style="font-size:18px;font-weight:700;color:{PRIMARY_DARK};">{cohort}</div>
              <div style="font-size:11px;color:{TEXT_MUTED};margin-top:2px;">Performance đến {PERFORMANCE_CUTOFF}</div>
              {total_html}
              {by_year_html}
            </div>
            """
        )

    # Trạng thái dữ liệu vẫn có sẵn nhưng không chiếm phần nhận diện / điều hướng.
    status = ds.dataset_status()
    ready = sum(1 for ok in status.values() if ok)
    with st.expander(f"Kiểm tra dữ liệu · {ready}/{len(status)} sẵn sàng"):
        for name, ok in status.items():
            st.markdown(f"{'✅' if ok else '⚪'} `{name}`")
        st.caption(f"Nguồn dữ liệu cục bộ: `{ds.PROJECT_ROOT}`")

    st.html(
        """
        <div class="sidebar-brand-footer">
          <div class="sidebar-brand-mark">FM</div>
          <div class="sidebar-brand-copy">Freddie Mac
            <span class="sidebar-brand-subtitle">Single-Family Loans</span>
          </div>
          <span class="sidebar-brand-dot"></span>
        </div>
        """
    )


with st.sidebar:
    _render_sidebar_dataset_card()

nav = st.navigation(PAGES)
nav.run()
