"""Generate the exact 4 Figures for Chapter 4 matching the thesis template.

Figures produced:
    1. outputs/figures/chapter4/figure_4_01_km_survival_curve.png
       (Hình 4.1. Kaplan–Meier Survival Curve)
    2. outputs/figures/chapter4/figure_4_02_cif_default_and_prepayment.png
       (Hình 4.2. Cumulative Incidence Function của Default và Voluntary Prepayment)
    3. outputs/figures/chapter4/figure_4_03_km_by_vintage.png
       (Hình 4.3. Kaplan–Meier Survival Curve theo Mortgage Vintage)
    4. outputs/figures/chapter4/figure_4_04_default_cif_by_vintage.png
       (Hình 4.4. Default CIF theo Mortgage Vintage)
"""

from __future__ import annotations

from pathlib import Path
import sys
import numpy as np
import pandas as pd
import polars as pl
from lifelines import KaplanMeierFitter
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DATA_PATH = PROJECT_ROOT / "data" / "model" / "baseline_complete_cases_2016_2026.parquet"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "figures" / "chapter4"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def compute_aalen_johansen(df: pd.DataFrame, max_time: int = 60) -> pd.DataFrame:
    """Counting-process multi-state Aalen-Johansen estimator with delayed entry."""
    event_times = sorted(df[df["cr_event_code"] > 0]["exit_time_month"].unique())
    entries = df["entry_time_month"].values
    exits = df["exit_time_month"].values
    codes = df["cr_event_code"].values

    S = 1.0
    cif_def = 0.0
    cif_prep = 0.0

    rows = [{
        "analysis_time": 0,
        "survival": 1.0,
        "default_cif": 0.0,
        "prepayment_cif": 0.0,
        "n_at_risk": len(df),
    }]

    for t in event_times:
        if t > max_time:
            break
        at_risk = (entries < t) & (exits >= t)
        n_at_risk = int(np.count_nonzero(at_risk))
        ev_t = exits == t
        d_def = int(np.count_nonzero(ev_t & (codes == 1)))
        d_prep = int(np.count_nonzero(ev_t & (codes == 2)))
        d_all = d_def + d_prep
        if n_at_risk > 0:
            cif_def += S * (d_def / n_at_risk)
            cif_prep += S * (d_prep / n_at_risk)
            S *= (1.0 - d_all / n_at_risk)
        rows.append({
            "analysis_time": t,
            "survival": S,
            "default_cif": cif_def,
            "prepayment_cif": cif_prep,
            "n_at_risk": n_at_risk,
        })
    return pd.DataFrame(rows)


def main() -> None:
    print(f"Loading data from: {DATA_PATH}")
    df_pl = pl.read_parquet(DATA_PATH)
    pdf = df_pl.select([
        "entry_time_month", "exit_time_month", "duration_months",
        "default_flag", "prepayment_flag", "cr_event_code", "vintage_year"
    ]).to_pandas()
    n_loans = len(pdf)
    print(f"Loaded {n_loans:,} loans.")

    # Configure style
    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.size"] = 10
    plt.rcParams["axes.titlesize"] = 12
    plt.rcParams["axes.labelsize"] = 10
    plt.rcParams["figure.titlesize"] = 13

    # =========================================================================
    # HÌNH 4.1. Kaplan–Meier Survival Curve
    # =========================================================================
    print("Generating Hinh 4.1 (Kaplan-Meier Survival Curve)...")
    kmf = KaplanMeierFitter()
    kmf.fit(
        durations=pdf["exit_time_month"],
        event_observed=pdf["default_flag"],
        entry=pdf["entry_time_month"],
        label="Kaplan–Meier S(t)"
    )

    fig, ax = plt.subplots(figsize=(9, 5.5), dpi=300)
    times = np.arange(0, 61)
    surv_probs = [kmf.predict(t) for t in times]
    ci = kmf.confidence_interval_survival_function_

    # Plot survival curve S(t)
    ax.plot(times, surv_probs, color="#1b4965", linewidth=2.4, label="Đường sống còn Kaplan–Meier $S(t)$")
    
    # Milestone markers at 12, 24, 36, 60
    for h in [12, 24, 36, 60]:
        s_val = kmf.predict(h)
        ax.plot(h, s_val, marker="o", markersize=6, color="#c1121f")
        ax.annotate(
            f"Tháng {h}\n$S(t)={s_val:.5f}$\n$1-S(t)={((1-s_val)*100):.4f}\\%$",
            xy=(h, s_val),
            xytext=(h - 4 if h > 30 else h + 1.5, s_val - 0.00018 if h <= 36 else s_val - 0.00025),
            arrowprops=dict(arrowstyle="->", color="#c1121f", lw=1.0),
            fontsize=8.5,
            bbox=dict(boxstyle="round,pad=0.3", fc="#fdf0d5", ec="#c1121f", alpha=0.9),
        )

    ax.set_title("Hình 4.1. Kaplan–Meier Survival Curve cho Rủi ro Vỡ nợ (Default)", fontweight="bold", pad=12)
    ax.set_xlabel("Tuổi khoản vay - Loan Age (tháng)", fontweight="bold")
    ax.set_ylabel("Xác suất sống còn $S(t)$", fontweight="bold")
    ax.set_xlim(-1, 65)
    ax.set_ylim(0.9991, 1.0001)
    ax.set_xticks([0, 12, 24, 36, 48, 60])
    ax.yaxis.set_major_formatter(matplotlib.ticker.FormatStrFormatter("%.4f"))
    ax.legend(loc="lower left", frameon=True, facecolor="white", edgecolor="#cccccc")

    # Add explanatory textbox
    text_box = (
        "Ghi chú: Mô hình ước lượng trên 499.393 khoản vay Complete Cases (2016–2026).\n"
        "Bảo lưu cấu trúc delayed entry theo chuẩn Freddie Mac. Voluntary Prepayment được xử lý như Censoring."
    )
    ax.text(0.02, 0.95, text_box, transform=ax.transAxes, fontsize=8,
            verticalalignment="top", bbox=dict(boxstyle="round,pad=0.4", fc="#f8f9fa", ec="#ced4da"))

    plt.tight_layout()
    p1 = OUTPUT_DIR / "figure_4_01_km_survival_curve.png"
    fig.savefig(p1)
    plt.close(fig)
    print(f"Saved: {p1}")

    # =========================================================================
    # HÌNH 4.2. Cumulative Incidence Function của Default và Voluntary Prepayment
    # =========================================================================
    print("Generating Hinh 4.2 (Cumulative Incidence Function)...")
    aj_res = compute_aalen_johansen(pdf, max_time=60)

    fig, (ax_prep, ax_def) = plt.subplots(1, 2, figsize=(13, 5), dpi=300)

    # Panel A: Voluntary Prepayment CIF
    ax_prep.plot(aj_res["analysis_time"], aj_res["prepayment_cif"] * 100, color="#0077b6", linewidth=2.4)
    ax_prep.fill_between(aj_res["analysis_time"], 0, aj_res["prepayment_cif"] * 100, color="#0077b6", alpha=0.15)
    for h in [12, 24, 36, 60]:
        sub = aj_res[aj_res["analysis_time"] <= h]
        val = sub.iloc[-1]["prepayment_cif"] * 100
        ax_prep.plot(h, val, marker="o", color="#03045e", markersize=6)
        ax_prep.annotate(f"{val:.2f}%", (h, val), textcoords="offset points", xytext=(-10, 8), fontweight="bold", fontsize=8.5)

    ax_prep.set_title("Panel A: CIF Voluntary Prepayment (Rủi ro cạnh tranh)", fontweight="bold")
    ax_prep.set_xlabel("Tuổi khoản vay - Loan Age (tháng)", fontweight="bold")
    ax_prep.set_ylabel("Tỷ lệ sự cố tích lũy CIF (%)", fontweight="bold")
    ax_prep.set_xlim(0, 62)
    ax_prep.set_ylim(0, 58)
    ax_prep.set_xticks([0, 12, 24, 36, 48, 60])

    # Panel B: Default CIF
    ax_def.plot(aj_res["analysis_time"], aj_res["default_cif"] * 100, color="#c1121f", linewidth=2.4)
    ax_def.fill_between(aj_res["analysis_time"], 0, aj_res["default_cif"] * 100, color="#c1121f", alpha=0.15)
    for h in [12, 24, 36, 60]:
        sub = aj_res[aj_res["analysis_time"] <= h]
        val = sub.iloc[-1]["default_cif"] * 100
        ax_def.plot(h, val, marker="s", color="#780000", markersize=6)
        ax_def.annotate(f"{val:.4f}%", (h, val), textcoords="offset points", xytext=(-12, 8), fontweight="bold", fontsize=8.5)

    ax_def.set_title("Panel B: CIF Default (Có kiểm soát Prepayment)", fontweight="bold")
    ax_def.set_xlabel("Tuổi khoản vay - Loan Age (tháng)", fontweight="bold")
    ax_def.set_ylabel("Tỷ lệ sự cố tích lũy CIF (%)", fontweight="bold")
    ax_def.set_xlim(0, 62)
    ax_def.set_ylim(0, 0.055)
    ax_def.set_xticks([0, 12, 24, 36, 48, 60])

    fig.suptitle("Hình 4.2. Cumulative Incidence Function (CIF) của Default và Voluntary Prepayment (Aalen–Johansen)",
                 fontweight="bold", fontsize=12, y=1.02)
    plt.tight_layout()
    p2 = OUTPUT_DIR / "figure_4_02_cif_default_and_prepayment.png"
    fig.savefig(p2, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {p2}")

    # =========================================================================
    # HÌNH 4.3. Kaplan–Meier Survival Curve theo Mortgage Vintage
    # =========================================================================
    print("Generating Hinh 4.3 (KM Survival Curve by Vintage)...")
    fig, ax = plt.subplots(figsize=(9.5, 5.5), dpi=300)
    vintages = [2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024]
    palette = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22"]

    for y, color in zip(vintages, palette):
        sub_y = pdf[pdf["vintage_year"] == y]
        if len(sub_y) == 0:
            continue
        max_fup = min(60, int(sub_y["duration_months"].max()))
        kmf_y = KaplanMeierFitter()
        kmf_y.fit(
            durations=sub_y["exit_time_month"],
            event_observed=sub_y["default_flag"],
            entry=sub_y["entry_time_month"],
            label=f"Vintage {y}"
        )
        t_grid = np.arange(0, max_fup + 1)
        s_grid = [kmf_y.predict(t) for t in t_grid]
        ax.plot(t_grid, s_grid, color=color, linewidth=1.8, label=f"Cohort {y}")

    ax.set_title("Hình 4.3. Kaplan–Meier Survival Curve theo Mortgage Vintage (2016–2024)", fontweight="bold", pad=12)
    ax.set_xlabel("Tuổi khoản vay - Loan Age (tháng)", fontweight="bold")
    ax.set_ylabel("Xác suất sống còn $S(t)$", fontweight="bold")
    ax.set_xlim(0, 62)
    ax.set_ylim(0.9985, 1.0001)
    ax.set_xticks([0, 12, 24, 36, 48, 60])
    ax.yaxis.set_major_formatter(matplotlib.ticker.FormatStrFormatter("%.4f"))
    ax.legend(loc="lower left", frameon=True, facecolor="white", edgecolor="#cccccc", ncol=3, fontsize=8.5)

    plt.tight_layout()
    p3 = OUTPUT_DIR / "figure_4_03_km_by_vintage.png"
    fig.savefig(p3)
    plt.close(fig)
    print(f"Saved: {p3}")

    # =========================================================================
    # HÌNH 4.4. Default CIF theo Mortgage Vintage
    # =========================================================================
    print("Generating Hinh 4.4 (Default CIF by Vintage)...")
    fig, ax = plt.subplots(figsize=(9.5, 5.5), dpi=300)

    for y, color in zip(vintages, palette):
        sub_y = pdf[pdf["vintage_year"] == y]
        if len(sub_y) == 0:
            continue
        max_fup = min(60, int(sub_y["duration_months"].max()))
        aj_y = compute_aalen_johansen(sub_y, max_time=max_fup)
        ax.plot(aj_y["analysis_time"], aj_y["default_cif"] * 100, color=color, linewidth=1.8, label=f"Cohort {y}")

    ax.set_title("Hình 4.4. Default CIF theo Mortgage Vintage (Aalen–Johansen Competing Risks)", fontweight="bold", pad=12)
    ax.set_xlabel("Tuổi khoản vay - Loan Age (tháng)", fontweight="bold")
    ax.set_ylabel("Default CIF tích lũy (%)", fontweight="bold")
    ax.set_xlim(0, 62)
    ax.set_ylim(0, 0.08)
    ax.set_xticks([0, 12, 24, 36, 48, 60])
    ax.legend(loc="upper left", frameon=True, facecolor="white", edgecolor="#cccccc", ncol=3, fontsize=8.5)

    # Explanation of incomplete follow-up
    ax.text(0.55, 0.15, "Ghi chú: Các cohort gần (2023–2024) có đường cong ngắn\ndo thời gian theo dõi đến cutoff 31/03/2026 chưa đạt 60 tháng.",
            transform=ax.transAxes, fontsize=8, bbox=dict(boxstyle="round,pad=0.4", fc="#f8f9fa", ec="#ced4da"))

    plt.tight_layout()
    p4 = OUTPUT_DIR / "figure_4_04_default_cif_by_vintage.png"
    fig.savefig(p4)
    plt.close(fig)
    print(f"Saved: {p4}")

    print("=" * 60)
    print("ALL 4 THESIS FIGURES CREATED SUCCESSFULLY.")
    print("=" * 60)


if __name__ == "__main__":
    main()
