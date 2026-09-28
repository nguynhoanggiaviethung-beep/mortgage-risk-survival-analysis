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

from src.data.survival_duration import (
    build_survival_duration_year,
    validate_survival_duration_year,
)


# =========================================================
# OUTPUT
# =========================================================

SUMMARY_FILE = (
    TABLES_DIR
    / "survival_duration_summary_2016_2026.csv"
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
        "FREDDIE MAC SURVIVAL DURATION PIPELINE"
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
            f"PROCESS SURVIVAL DURATION - {year}"
        )

        print(
            "=" * 80
        )


        try:

            build_survival_duration_year(
                year,
                force=True,
            )


            validation = (
                validate_survival_duration_year(
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
                f"\n❌ SURVIVAL DURATION FAILED - {year}"
            )

            print(
                error
            )


    # =====================================================
    # SAVE SUMMARY
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


        total_loans = (
            summary[
                "loans"
            ]
            .sum()
        )

        total_eligible = (
            summary[
                "eligible"
            ]
            .sum()
        )

        total_excluded = (
            summary[
                "excluded_preentry"
            ]
            .sum()
        )

        total_default = (
            summary[
                "eligible_default"
            ]
            .sum()
        )

        total_prepayment = (
            summary[
                "eligible_prepayment"
            ]
            .sum()
        )

        total_censor = (
            summary[
                "eligible_censor"
            ]
            .sum()
        )


        print(
            "\n"
            + "=" * 80
        )

        print(
            "SURVIVAL DURATION TOTALS"
        )

        print(
            "=" * 80
        )

        print(
            f"Total loans:             "
            f"{total_loans:,}"
        )

        print(
            f"Survival eligible:       "
            f"{total_eligible:,}"
        )

        print(
            f"Excluded before FP:      "
            f"{total_excluded:,}"
        )

        print(
            f"Eligible DEFAULT:        "
            f"{total_default:,}"
        )

        print(
            f"Eligible PREPAYMENT:     "
            f"{total_prepayment:,}"
        )

        print(
            f"Eligible CENSOR:         "
            f"{total_censor:,}"
        )


        # =================================================
        # GLOBAL CONSISTENCY
        # =================================================

        eligible_classified = (
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
            f"Eligible event total     "
            f"= {eligible_classified:,}"
        )

        print(
            f"Survival eligible        "
            f"= {total_eligible:,}"
        )

        print(
            f"Eligible + excluded      "
            f"= {total_eligible + total_excluded:,}"
        )

        print(
            f"Total loans              "
            f"= {total_loans:,}"
        )


        if eligible_classified != total_eligible:

            raise RuntimeError(
                "Eligible event classification "
                "không bằng survival eligible."
            )


        if (
            total_eligible
            +
            total_excluded
            !=
            total_loans
        ):

            raise RuntimeError(
                "Eligible + excluded "
                "không bằng total loans."
            )


    # =====================================================
    # FINAL STATUS
    # =====================================================

    print(
        "\n"
        + "=" * 80
    )

    print(
        "FINAL SURVIVAL DURATION STATUS"
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
        "✓ ALL SURVIVAL DURATIONS 2016–2026 PASS"
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