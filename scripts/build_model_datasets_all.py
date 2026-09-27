from pathlib import Path
import sys

import polars as pl


# =========================================================
# PROJECT ROOT
# =========================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )


# =========================================================
# PROJECT IMPORTS
# =========================================================

from src.config import (
    STUDY_YEARS,
    TABLES_DIR,
    ensure_directories,
)

from src.data.model_dataset import (
    build_model_dataset_year,
    validate_model_dataset_year,
)


# =========================================================
# OUTPUT
# =========================================================

SUMMARY_FILE = (
    TABLES_DIR
    / "model_dataset_summary_2016_2026.csv"
)


# =========================================================
# MAIN
# =========================================================

def main():

    ensure_directories()

    print(
        "\n"
        + "=" * 80
    )

    print(
        "FREDDIE MAC MODEL DATASET PIPELINE"
    )

    print(
        "2016–2026"
    )

    print(
        "=" * 80
    )


    results = []
    failed = []


    # =====================================================
    # BUILD + VALIDATE EACH YEAR
    # =====================================================

    for year in STUDY_YEARS:

        print(
            "\n"
            + "=" * 80
        )

        print(
            f"PROCESS MODEL DATASET - {year}"
        )

        print(
            "=" * 80
        )


        try:

            build_model_dataset_year(
                year,
                force=True,
            )


            validation = (
                validate_model_dataset_year(
                    year
                )
            )


            results.append(
                validation
            )


        except Exception as error:

            failed.append(
                {
                    "year": year,
                    "error": str(error),
                }
            )


            print(
                f"\n❌ MODEL DATASET FAILED - {year}"
            )

            print(
                error
            )


    # =====================================================
    # SUMMARY
    # =====================================================

    if results:

        summary = (
            pl.DataFrame(
                results
            )
            .sort(
                "year"
            )
        )


        summary.write_csv(
            SUMMARY_FILE
        )


        total_rows = (
            summary[
                "rows"
            ]
            .sum()
        )

        total_complete = (
            summary[
                "complete_case"
            ]
            .sum()
        )

        missing_fico = (
            summary[
                "missing_fico"
            ]
            .sum()
        )

        missing_ltv = (
            summary[
                "missing_ltv"
            ]
            .sum()
        )

        missing_dti = (
            summary[
                "missing_dti"
            ]
            .sum()
        )

        missing_rate = (
            summary[
                "missing_rate"
            ]
            .sum()
        )

        missing_term = (
            summary[
                "missing_term"
            ]
            .sum()
        )

        total_default = (
            summary[
                "default"
            ]
            .sum()
        )

        total_prepayment = (
            summary[
                "prepayment"
            ]
            .sum()
        )

        total_censor = (
            summary[
                "censor"
            ]
            .sum()
        )


        complete_rate = (
            total_complete
            /
            total_rows
            *
            100
        )


        print(
            "\n"
            + "=" * 80
        )

        print(
            "MODEL DATASET TOTALS"
        )

        print(
            "=" * 80
        )


        print(
            f"Model rows:              "
            f"{total_rows:,}"
        )

        print(
            f"Complete core cases:     "
            f"{total_complete:,}"
        )

        print(
            f"Complete-case rate:      "
            f"{complete_rate:.2f}%"
        )


        print(
            "\nPRIMARY COVARIATE MISSINGNESS"
        )

        print(
            f"Missing FICO:            "
            f"{missing_fico:,}"
        )

        print(
            f"Missing LTV:             "
            f"{missing_ltv:,}"
        )

        print(
            f"Missing DTI:             "
            f"{missing_dti:,}"
        )

        print(
            f"Missing Interest Rate:   "
            f"{missing_rate:,}"
        )

        print(
            f"Missing Loan Term:       "
            f"{missing_term:,}"
        )


        print(
            "\nEVENT DISTRIBUTION"
        )

        print(
            f"DEFAULT:                 "
            f"{total_default:,}"
        )

        print(
            f"PREPAYMENT:              "
            f"{total_prepayment:,}"
        )

        print(
            f"CENSOR:                  "
            f"{total_censor:,}"
        )


        # =================================================
        # GLOBAL CONSISTENCY
        # =================================================

        classified = (
            total_default
            +
            total_prepayment
            +
            total_censor
        )


        print(
            "\nConsistency:"
        )

        print(
            f"DEFAULT + PREPAYMENT + CENSOR "
            f"= {classified:,}"
        )

        print(
            f"Model rows                    "
            f"= {total_rows:,}"
        )


        if classified != total_rows:

            raise RuntimeError(
                "Global event count "
                "không bằng model rows."
            )


    # =====================================================
    # FINAL STATUS
    # =====================================================

    print(
        "\n"
        + "=" * 80
    )

    print(
        "FINAL MODEL DATASET STATUS"
    )

    print(
        "=" * 80
    )


    if failed:

        print(
            f"❌ Có {len(failed)} vintage bị lỗi:"
        )

        for item in failed:

            print(
                f"  {item['year']}: "
                f"{item['error']}"
            )

        sys.exit(1)


    print(
        "✓ ALL MODEL DATASETS 2016–2026 PASS"
    )

    print(
        f"\nSummary saved:\n"
        f"{SUMMARY_FILE}"
    )

    print(
        "=" * 80
    )


if __name__ == "__main__":
    main()