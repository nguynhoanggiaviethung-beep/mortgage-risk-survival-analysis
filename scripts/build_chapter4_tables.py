"""PyCharm & CLI Entrypoint: Build all Chapter 4 empirical tables and figures.

Usage in PyCharm:
    Right-click this file -> Run 'build_chapter4_tables'

Outputs generated:
    outputs/tables/chapter4/table_4_01_sample_selection.csv ... table_4_20_hypothesis_summary.csv
    outputs/tables/chapter4/Chapter4_All_Tables.xlsx (Consolidated Excel workbook with 20 sheets)
    outputs/tables/chapter4/Chapter4_Results_Report.md (Consolidated markdown thesis report)
    outputs/figures/chapter4/figure_4_01_km_vs_cif_bias.png
    outputs/figures/chapter4/figure_4_02_forest_plot_hr_vs_shr.png
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.results.chapter4_tables import (
    build_all_chapter4_tables,
    export_chapter4_tables,
    generate_chapter4_figures,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "outputs" / "tables" / "chapter4",
        help="Target folder for Chapter 4 CSV, Excel, and Markdown tables.",
    )
    parser.add_argument(
        "--figures-dir",
        type=Path,
        default=PROJECT_ROOT / "outputs" / "figures" / "chapter4",
        help="Target folder for Chapter 4 academic figures.",
    )
    parser.add_argument(
        "--no-excel",
        action="store_true",
        help="Skip Excel workbook generation.",
    )
    parser.add_argument(
        "--no-figures",
        action="store_true",
        help="Skip figure generation.",
    )

    args = parser.parse_args()

    print("=" * 70)
    print("MORTGAGE RISK SURVIVAL ANALYSIS - CHAPTER 4 BUILDER")
    print("=" * 70)
    print(f"Target Tables Directory : {args.output_dir}")
    print(f"Target Figures Directory: {args.figures_dir}")
    print("-" * 70)

    print("[1/3] Computing 20 empirical tables on final complete cases (499,393 loans)...")
    tables = build_all_chapter4_tables()
    print(f"      Calculated {len(tables)} tables successfully.")

    print("[2/3] Exporting tables to CSV, Excel, and Markdown...")
    exported = export_chapter4_tables(
        tables=tables,
        output_dir=args.output_dir,
        export_csv=True,
        export_excel=not args.no_excel,
        export_markdown=True,
    )
    for key, path in exported.items():
        if key.startswith("excel") or key.startswith("markdown"):
            print(f"      Saved: {path.name}")
    print(f"      Exported {len(tables)} CSV tables.")

    if not args.no_figures:
        print("[3/3] Generating publication-grade figures for Chapter 4...")
        figs = generate_chapter4_figures(output_dir=args.figures_dir)
        for key, path in figs.items():
            print(f"      Generated figure: {path.name}")
    else:
        print("[3/3] Figure generation skipped (--no-figures).")

    print("-" * 70)
    print("ALL CHAPTER 4 ARTIFACTS BUILT SUCCESSFULLY.")
    print("=" * 70)


if __name__ == "__main__":
    main()
