from pathlib import Path
import json
import pandas as pd
import streamlit as st

MOCK_DIR = Path(__file__).resolve().parent.parent / "mock"

class DataService:
    @staticmethod
    @st.cache_data(show_spinner=False)
    def load_dataset(dataset_name: str):
        """Đọc mock dataset (.parquet hoặc .json/.csv) từ app/mock/."""
        try:
            # 1. Thử tìm file Parquet
            parquet_path = MOCK_DIR / f"{dataset_name}.parquet"
            if parquet_path.exists():
                return pd.read_parquet(parquet_path), "OK"
            
            # 2. Thử tìm file JSON
            json_path = MOCK_DIR / f"{dataset_name}.json"
            if json_path.exists():
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return (pd.DataFrame(data) if isinstance(data, list) else data), "OK"
            
            # 3. Thử tìm file CSV
            csv_path = MOCK_DIR / f"{dataset_name}.csv"
            if csv_path.exists():
                return pd.read_csv(csv_path), "OK"

            return None, "EMPTY"
        except Exception as e:
            return None, f"ERROR: {str(e)}"

def render_status_sidebar():
    """Hiển thị trạng thái dữ liệu ở Sidebar chuẩn contract."""
    st.sidebar.markdown("---")
    st.sidebar.caption("Trạng thái Mock Data (`app/mock/`)")
    
    datasets = [
        "portfolio_summary", "pd_results", "survival_results",
        "risk_driver_results", "vintage_results", "loan_profile",
        "loan_timeline", "model_diagnostics"
    ]
    
    for ds in datasets:
        _, status = DataService.load_dataset(ds)
        if status == "OK":
            st.sidebar.markdown(f"🟢 `{ds}`")
        else:
            st.sidebar.markdown(f"🔴 `{ds}`")