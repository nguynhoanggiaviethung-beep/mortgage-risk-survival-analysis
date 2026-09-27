import streamlit as st

def init_filter_state():
    if "global_filters" not in st.session_state:
        st.session_state.global_filters = {
            "vintages": ["All"],
            "terms": ["All"],
            "credit_score_band": "All",
            "ltv_band": "All",
            "dti_band": "All",
            "cutoff_date": None
        }

def render_filter_bar():
    init_filter_state()
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🎛️ Bộ lọc danh mục")
    
    vintages = st.sidebar.multiselect("Năm giải ngân (Vintage)", ["All", "2022", "2023", "2024"], default=["All"])
    terms = st.sidebar.multiselect("Kỳ hạn (Loan Term)", ["All", "15 Y", "30 Y"], default=["All"])
    cs_band = st.sidebar.selectbox("Credit Score Band", ["All", "<650", "650-699", "700-749", "750+"])
    ltv_band = st.sidebar.selectbox("LTV Band", ["All", "<70%", "70%-80%", ">80%"])
    dti_band = st.sidebar.selectbox("DTI Band", ["All", "<36%", "36%-45%", ">45%"])
    
    if st.sidebar.button("🔄 Reset Bộ Lọc", use_container_width=True):
        st.session_state.global_filters = {
            "vintages": ["All"], "terms": ["All"],
            "credit_score_band": "All", "ltv_band": "All",
            "dti_band": "All", "cutoff_date": None
        }
        st.rerun()
        
    st.session_state.global_filters.update({
        "vintages": vintages, "terms": terms,
        "credit_score_band": cs_band, "ltv_band": ltv_band, "dti_band": dti_band
    })
    return st.session_state.global_filters