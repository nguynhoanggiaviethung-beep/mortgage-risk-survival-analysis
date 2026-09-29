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

from src.data.event_definition import (
    build_event_mapping_year,
    validate_event_mapping_year,
)


# =========================================================
# OUTPUT
# =========================================================

SUMMARY_FILE = (
    TABLES_DIR
    / "event_mapping_summary_2016_2026.csv"
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
        "FREDDIE MAC EVENT MAPPING PIPELINE"
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
            f"PROCESS EVENT MAP - {year}"
        )

        print(
            "=" * 80
        )


        try:

            build_event_mapping_year(
                year,
                force=True,
            )

            validation = (
                validate_event_mapping_year(
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
                f"\n❌ EVENT MAPPING FAILED - {year}"
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

        total_conflicts = (
            summary[
                "same_month_conflicts"
            ]
            .sum()
        )

        total_excluded = (
            summary["excluded_missing_effective_date"].sum()
        )


        print(
            "\n"
            + "=" * 80
        )

        print(
            "EVENT MAPPING TOTALS"
        )

        print(
            "=" * 80
        )

        print(
            f"Loans:                 "
            f"{total_loans:,}"
        )

        print(
            f"DEFAULT:               "
            f"{total_default:,}"
        )

        print(
            f"PREPAYMENT:            "
            f"{total_prepayment:,}"
        )

        print(
            f"CENSOR:                "
            f"{total_censor:,}"
        )

        print(
            f"Excluded (invalid event date): {total_excluded:,}"
        )

        print(
            f"Same-month conflicts:  "
            f"{total_conflicts:,}"
        )


        classified_total = (
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
            f"= {classified_total:,}"
        )

        print(
            f"Total Performance loans       "
            f"= {total_loans + total_excluded:,} "
            f"({total_loans:,} classified + {total_excluded:,} excluded)"
        )


        if classified_total != total_loans:

            raise RuntimeError(
                "Global event classification "
                "không bằng tổng số loans."
            )


    # =====================================================
    # FINAL STATUS
    # =====================================================

    print(
        "\n"
        + "=" * 80
    )

    print(
        "FINAL EVENT MAPPING STATUS"
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
        "✓ ALL EVENT MAPS 2016–2026 PASS"
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
