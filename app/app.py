"""
Entry point của dashboard — điều hướng 5 trang đúng thứ tự trong
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
from app.config import APP_SUBTITLE, APP_TITLE, PAGE_ICONS
from app.pages import loan_explorer, model_insights, overview, portfolio_risk, risk_drivers
from app.services import data_service as ds

st.set_page_config(
    page_title="Mortgage Risk Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Inject CSS để đồng bộ giao diện
inject_global_css()

def _page_overview():
    app_header(APP_TITLE, APP_SUBTITLE)
    overview.render()


def _page_portfolio_risk():
    app_header(APP_TITLE, APP_SUBTITLE)
    portfolio_risk.render()


def _page_risk_drivers():
    app_header(APP_TITLE, APP_SUBTITLE)
    risk_drivers.render()


def _page_loan_explorer():
    app_header(APP_TITLE, APP_SUBTITLE)
    loan_explorer.render()


def _page_model_insights():
    app_header(APP_TITLE, APP_SUBTITLE)
    model_insights.render()


PAGES = [
    st.Page(_page_overview, title="Tổng quan", icon=PAGE_ICONS["overview"], default=True),
    st.Page(_page_portfolio_risk, title="Rủi ro danh mục", icon=PAGE_ICONS["portfolio_risk"]),
    st.Page(_page_risk_drivers, title="Yếu tố rủi ro", icon=PAGE_ICONS["risk_drivers"]),
    st.Page(_page_loan_explorer, title="Tra cứu khoản vay", icon=PAGE_ICONS["loan_explorer"]),
    st.Page(_page_model_insights, title="Kết quả mô hình", icon=PAGE_ICONS["model_insights"]),
]

# ---- Sidebar: data health, để nhóm biết dataset nào query/ còn thiếu -----------
with st.sidebar:
    st.markdown("### Trạng thái dữ liệu (query/)")
    status = ds.dataset_status()
    for name, ok in status.items():
        icon = "🟢" if ok else "🔴"
        st.markdown(f"{icon} `{name}`")
    st.caption(f"Query dir: `{ds.QUERY_DIR}`")

nav = st.navigation(PAGES)
nav.run()
