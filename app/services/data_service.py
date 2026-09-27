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
def get_portfolio_summary(vintage="All", score_band="All", ltv_band="All", dti_band="All", term="All"):
    """Lấy dữ liệu portfolio_summary và trả về dưới dạng dict hoặc DataFrame."""
    df = load_data("portfolio_summary")
    if df.empty:
        return {}
    return df.iloc[0].to_dict() if len(df) > 0 else {}
    