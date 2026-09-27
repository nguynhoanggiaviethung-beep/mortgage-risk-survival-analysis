# run_pipeline.py
from pathlib import Path
import pandas as pd

# Import các module từ src/
from src.data.load_data import load_raw_data
from src.survival.kaplan_meier import run_km_analysis
from src.survival.cox_model import fit_cox_model
from src.competing_risks.fine_gray import fit_fine_gray

def main():
    query_dir = Path("query")
    query_dir.mkdir(exist_ok=True)
    
    print("1. Loading & Cleaning Data...")
    # df = load_raw_data()
    
    print("2. Running Survival & Risk Models...")
    # km_df = run_km_analysis(...)
    # cox_df = fit_cox_model(...)
    
    print("3. Exporting query datasets to query/...")
    # km_df.to_csv(query_dir / "survival_results.csv", index=False)
    # cox_df.to_csv(query_dir / "risk_driver_results.csv", index=False)
    # ... xuất đủ 8 file vào folder query/
    
    print("Pipeline executed successfully. You can now launch Streamlit!")

if __name__ == "__main__":
    main()