import streamlit as st

def init_filter_state():
    """Khởi tạo trạng thái bộ lọc trong Session State nếu chưa có."""
    if "filters" not in st.session_state:
        st.session_state.filters = {
            "vintages": ["2022", "2023", "2024"],
            "loan_terms": [15, 30],
            "credit_score_range": (600, 850),
            "ltv_range": (0.0, 1.0),
            "dti_range": (0.0, 0.6),
        }

def render_sidebar_filters():
    """Render bộ lọc ở Sidebar và lưu thông số vào Session State."""
    init_filter_state()
    st.sidebar.markdown("### 🎛️ Bộ lọc danh mục")
    
    # 1. Vintage Filter
    vintages = st.sidebar.multiselect(
        "Năm/Kỳ giải ngân (Vintage)",
        options=["2022", "2023", "2024"],
        default=st.session_state.filters["vintages"]
    )
    
    # 2. Loan Term
    terms = st.sidebar.multiselect(
        "Kỳ hạn vay (Loan Term - Năm)",
        options=[15, 30],
        default=st.session_state.filters["loan_terms"]
    )
    
    # 3. Sliders
    cs_range = st.sidebar.slider("Thang điểm tín dụng (Credit Score)", 300, 850, st.session_state.filters["credit_score_range"])
    ltv_range = st.sidebar.slider("Tỷ lệ LTV", 0.0, 1.0, st.session_state.filters["ltv_range"], step=0.05)
    
    # Reset Button
    if st.sidebar.button("🔄 Đặt lại bộ lọc", use_container_width=True):
        st.session_state.filters = {
            "vintages": ["2022", "2023", "2024"],
            "loan_terms": [15, 30],
            "credit_score_range": (600, 850),
            "ltv_range": (0.0, 1.0),
            "dti_range": (0.0, 0.6),
        }
        st.rerun()

    # Cập nhật state
    st.session_state.filters.update({
        "vintages": vintages,
        "loan_terms": terms,
        "credit_score_range": cs_range,
        "ltv_range": ltv_range
    })
    return st.session_state.filters