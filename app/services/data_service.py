from pathlib import Path
import pandas as pd
import streamlit as st

# Định vị thư mục query/ ở gốc dự án
BASE_DIR = Path(__file__).resolve().parent.parent.parent
QUERY_DIR = BASE_DIR / "query"

def get_query_dir() -> Path:
    """Trả về đường dẫn tuyệt đối của thư mục query."""
    return QUERY_DIR

def dataset_status() -> dict:
    """
    Kiểm tra trạng thái tồn tại của 8 file dữ liệu trong thư mục query/.
    Trả về dictionary với key là tên dataset và value là True/False.
    """
    required_datasets = [
        "portfolio_summary",
        "pd_results",
        "survival_results",
        "risk_driver_results",
        "vintage_results",
        "loan_profile",
        "loan_timeline",
        "model_diagnostics"
    ]
    
    status = {}
    for ds in required_datasets:
        csv_path = QUERY_DIR / f"{ds}.csv"
        parquet_path = QUERY_DIR / f"{ds}.parquet"
        status[ds] = csv_path.exists() or parquet_path.exists()
        
    return status

@st.cache_data(show_spinner=False)
def load_data(dataset_name: str) -> pd.DataFrame:
    """Đọc dữ liệu từ file CSV hoặc Parquet trong thư mục query/."""
    csv_path = QUERY_DIR / f"{dataset_name}.csv"
    parquet_path = QUERY_DIR / f"{dataset_name}.parquet"
    
    if csv_path.exists():
        return pd.read_csv(csv_path)
    elif parquet_path.exists():
        return pd.read_parquet(parquet_path)
    else:
        return pd.DataFrame()

# ==============================================================================
# HÀM LẤY DỮ LIỆU CHO CÁC TRANG (ĐẢM BẢO LUÔN TRẢ VỀ pd.DataFrame)
# ==============================================================================

def get_portfolio_summary(vintage="All", score_band="All", ltv_band="All", dti_band="All", term="All") -> pd.DataFrame:
    """Lấy dữ liệu portfolio_summary dưới dạng pd.DataFrame."""
    df = load_data("portfolio_summary")
    return df

def get_pd_results(group=None, group_value=None) -> pd.DataFrame:
    """Lấy dữ liệu pd_results."""
    df = load_data("pd_results")
    if df.empty:
        return pd.DataFrame()
    
    if group and group_value and group in df.columns:
        df = df[df[group] == group_value]
    return df

def get_survival_results() -> pd.DataFrame:
    """Lấy dữ liệu survival_results."""
    return load_data("survival_results")

def get_risk_driver_results() -> pd.DataFrame:
    """Lấy dữ liệu risk_driver_results (Trang 3)."""
    return load_data("risk_driver_results")

def get_vintage_results() -> pd.DataFrame:
    """Lấy dữ liệu vintage_results (Trang 2)."""
    return load_data("vintage_results")

def get_loan_profile(loan_id: str = None) -> pd.DataFrame:
    """Lấy hồ sơ khoản vay (Trang 4)."""
    df = load_data("loan_profile")
    if df.empty:
        return pd.DataFrame()
    if loan_id:
        df = df[df["loan_id"].astype(str) == str(loan_id)]
    return df

def get_loan_timeline(loan_id: str = None) -> pd.DataFrame:
    """Lấy timeline quan sát khoản vay (Trang 4)."""
    df = load_data("loan_timeline")
    if df.empty:
        return pd.DataFrame()
    if loan_id:
        df = df[df["loan_id"].astype(str) == str(loan_id)]
    return df

# app/services/data_service.py

def get_model_diagnostics(model_type: str = None) -> pd.DataFrame:
    """Lấy chỉ số đánh giá mô hình (Trang 5)."""
    df = load_data("model_diagnostics")
    if df.empty:
        return pd.DataFrame()
    if model_type and "model_name" in df.columns:
        df_filtered = df[df["model_name"] == model_type]
        return df_filtered if not df_filtered.empty else df
    return df

def get_risk_driver_results(model_type: str = None) -> pd.DataFrame:
    """Lấy kết quả yếu tố rủi ro HR / SHR (Trang 3 & Trang 5)."""
    df = load_data("risk_driver_results")
    if df.empty:
        return pd.DataFrame()
    if model_type and "model_type" in df.columns:
        df = df[df["model_type"] == model_type]
    return df

def get_survival_results(group: str = None) -> pd.DataFrame:
    """Lấy kết quả sinh tồn Kaplan-Meier."""
    df = load_data("survival_results")
    if df.empty:
        return pd.DataFrame()
    if group and "group" in df.columns:
        df = df[df["group"] == group]
    return df

def get_pd_results(group: str = None, group_value: str = None) -> pd.DataFrame:
    """Lấy kết quả PD / CIF."""
    df = load_data("pd_results")
    if df.empty:
        return pd.DataFrame()
    if group and group in df.columns:
        if group_value:
            df = df[df[group] == group_value]
    return df