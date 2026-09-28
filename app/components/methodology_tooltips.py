import streamlit as st

GLOSSARY = {
    "PD": "Probability of Default (Xác suất vỡ nợ dồn tích tại mốc 12/24/36M).",
    "CIF": "Cumulative Incidence Function (Hàm biến cố dồn tích trong môi trường Competing Risks như Prepayment).",
    "HR": "Hazard Ratio (Mô hình Cox PH: Tỷ lệ rủi ro vỡ nợ tức thời tại thời điểm t).",
    "SHR": "Subdistribution Hazard Ratio (Mô hình Fine-Gray: Tỷ lệ rủi ro tác động trực tiếp lên hàm CIF).",
    "Event": "Sự kiện vỡ nợ (DEFAULT). Sau mốc này ngừng theo dõi khoản vay hoàn toàn.",
    "Censoring": "Khoản vay kết thúc do Trả nợ trước hạn (VOLUNTARY_PREPAYMENT) hoặc hết hạn quan sát."
}

def render_tooltip(term: str):
    """Hiển thị chú giải nhỏ gọn ngay dưới tiêu đề các trang"""
    if term in GLOSSARY:
        st.caption(f"💡 **{term}**: {GLOSSARY[term]}")

def render_glossary_expander():
    """Hiển thị bảng tra cứu thuật ngữ đầy đủ (thích hợp nhét vào Trang 5)"""
    with st.expander("📚 Chú giải Thuật ngữ Phương pháp luận (Methodology Tooltips)"):
        for term, desc in GLOSSARY.items():
            st.markdown(f"**{term}**: {desc}")