"""Script sinh Mock Data (mô phỏng 1 năm vừa qua) cho thư mục query/."""

from pathlib import Path
import numpy as np
import pandas as pd

# 1. Khởi tạo thư mục query/
QUERY_DIR = Path(__file__).parent / "query"
QUERY_DIR.mkdir(exist_ok=True)

print("⏳ Đang khởi tạo Mock Data...")

# ---------------------------------------------------------
# 1. portfolio_summary.csv (Dữ liệu Trang 1)
# ---------------------------------------------------------
df_portfolio = pd.DataFrame(
    [
        {
            "total_loans": 12500,
            "total_upb": 2_850_000_000,
            "default_rate": 0.032,
            "prepayment_rate": 0.085,
            "avg_ltv": 0.76,
            "avg_dti": 0.34,
            "avg_credit_score": 712,
        }
    ]
)
df_portfolio.to_csv(QUERY_DIR / "portfolio_summary.csv", index=False)
print("  Created: query/portfolio_summary.csv")

# ---------------------------------------------------------
# 2. pd_results.csv (Dữ liệu Trang 1 & 2)
# ---------------------------------------------------------
horizons = [6, 12, 18, 24, 30, 36, 48, 60]
df_pd = pd.DataFrame(
    {
        "horizon": horizons,
        "cif_default": [0.005, 0.012, 0.019, 0.026, 0.031, 0.035, 0.042, 0.048],
        "cif_prepayment": [0.010, 0.025, 0.045, 0.068, 0.082, 0.098, 0.125, 0.150],
    }
)
df_pd.to_csv(QUERY_DIR / "pd_results.csv", index=False)
print("  Created: query/pd_results.csv")

# ---------------------------------------------------------
# 3. survival_results.csv (Dữ liệu Trang 1 & 5)
# ---------------------------------------------------------
months = np.arange(1, 61)
group_a = np.exp(-0.001 * months)
group_b = np.exp(-0.0025 * months)

df_survival_a = pd.DataFrame(
    {
        "analysis_time": months,
        "survival": group_a,
        "ci_low": group_a - 0.01,
        "ci_high": group_a + 0.01,
        "group_value": "FICO >= 700",
    }
)
df_survival_b = pd.DataFrame(
    {
        "analysis_time": months,
        "survival": group_b,
        "ci_low": group_b - 0.02,
        "ci_high": group_b + 0.02,
        "group_value": "FICO < 700",
    }
)
df_survival = pd.concat([df_survival_a, df_survival_b], ignore_index=True)
df_survival.to_csv(QUERY_DIR / "survival_results.csv", index=False)
print("  Created: query/survival_results.csv")

# ---------------------------------------------------------
# 4. risk_driver_results.csv (Dữ liệu Trang 3 - Cox/Fine-Gray)
# ---------------------------------------------------------
df_risk_drivers = pd.DataFrame(
    [
        {"variable": "Credit Score (<650)", "hr_shr": 1.85, "ci_low": 1.42, "ci_high": 2.41, "p_value": 0.001, "model_type": "Fine-Gray"},
        {"variable": "LTV (>80%)", "hr_shr": 1.52, "ci_low": 1.21, "ci_high": 1.91, "p_value": 0.003, "model_type": "Fine-Gray"},
        {"variable": "DTI (>45%)", "hr_shr": 1.34, "ci_low": 1.05, "ci_high": 1.71, "p_value": 0.018, "model_type": "Fine-Gray"},
        {"variable": "Interest Rate (+1%)", "hr_shr": 1.18, "ci_low": 1.02, "ci_high": 1.36, "p_value": 0.025, "model_type": "Fine-Gray"},
        {"variable": "Loan Term (30Y vs 15Y)", "hr_shr": 1.12, "ci_low": 0.95, "ci_high": 1.32, "p_value": 0.180, "model_type": "Fine-Gray"},
    ]
)
df_risk_drivers.to_csv(QUERY_DIR / "risk_driver_results.csv", index=False)
print("  Created: query/risk_driver_results.csv")

# ---------------------------------------------------------
# 5. vintage_results.csv (Dữ liệu Trang 2 - Vintage Analysis)
# ---------------------------------------------------------
vintages = ["2023-Q1", "2023-Q2", "2023-Q3", "2023-Q4", "2024-Q1", "2024-Q2"]
vintage_rows = []
for v in vintages:
    for age in range(1, 13):
        base_rate = 0.0015 * age * (1.2 if "2023" in v else 0.9)
        vintage_rows.append({"origination_vintage": v, "loan_age": age, "cumulative_default_rate": base_rate})

df_vintage = pd.DataFrame(vintage_rows)
df_vintage.to_csv(QUERY_DIR / "vintage_results.csv", index=False)
print("  Created: query/vintage_results.csv")

# ---------------------------------------------------------
# 6. loan_profile.csv (Dữ liệu Trang 4 - Tra cứu khoản vay)
# ---------------------------------------------------------
np.random.seed(42)
loan_ids = [f"LN{1000 + i}" for i in range(50)]
df_loans = pd.DataFrame(
    {
        "loan_id": loan_ids,
        "origination_year": np.random.choice([2022, 2023, 2024], size=50),
        "credit_score": np.random.randint(600, 820, size=50),
        "ltv": np.round(np.random.uniform(0.50, 0.95, size=50), 2),
        "dti": np.round(np.random.uniform(0.20, 0.50, size=50), 2),
        "interest_rate": np.round(np.random.uniform(0.035, 0.075, size=50), 3),
        "loan_term": np.random.choice([15, 30], size=50),
        "current_status": np.random.choice(["Active", "Active", "Active", "DEFAULT", "VOLUNTARY_PREPAYMENT"], size=50),
        "loan_age": np.random.randint(6, 36, size=50),
    }
)
df_loans.to_csv(QUERY_DIR / "loan_profile.csv", index=False)
print("  Created: query/loan_profile.csv")

# ---------------------------------------------------------
# 7. loan_timeline.csv (Dữ liệu Trang 4 - Timeline khoản vay)
# ---------------------------------------------------------
timeline_rows = []
for lid in loan_ids[:10]:  # Tạo timeline mẫu cho 10 khoản vay đầu
    max_m = np.random.randint(12, 36)
    for m in range(0, max_m + 1):
        evt = "ACTIVE"
        if m == max_m:
            evt = np.random.choice(["ACTIVE", "DEFAULT", "VOLUNTARY_PREPAYMENT"])
        timeline_rows.append({"loan_id": lid, "analysis_time_month": m, "event_type": evt})

df_timeline = pd.DataFrame(timeline_rows)
df_timeline.to_csv(QUERY_DIR / "loan_timeline.csv", index=False)
print("  Created: query/loan_timeline.csv")

# ---------------------------------------------------------
# 8. model_diagnostics.csv (Dữ liệu Trang 5 - Model Insights)
# ---------------------------------------------------------
df_diagnostics = pd.DataFrame(
    [
        {"model_name": "Kaplan-Meier", "concordance_index": 0.50, "brier_score": 0.082, "log_likelihood": -1250.4, "aic": 2502.8},
        {"model_name": "Cox PH", "concordance_index": 0.72, "brier_score": 0.054, "log_likelihood": -980.1, "aic": 1972.2},
        {"model_name": "Fine-Gray (Competing Risk)", "concordance_index": 0.78, "brier_score": 0.041, "log_likelihood": -890.5, "aic": 1795.0},
    ]
)
df_diagnostics.to_csv(QUERY_DIR / "model_diagnostics.csv", index=False)
print("  Created: query/model_diagnostics.csv")

print("\n SẢN XUẤT MOCK DATA HOÀN TẤT! Bạn có thể bật Streamlit ngay.")