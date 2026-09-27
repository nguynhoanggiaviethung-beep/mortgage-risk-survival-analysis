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
# IMPORT PROJECT MODULES
# =========================================================

from src.config import (
    STUDY_YEARS,
    TABLES_DIR,
    ensure_directories,
)

from src.validate import (
    validate_year,
)


# =========================================================
# MAIN
# =========================================================

def main():

    ensure_directories()

    print(
        "\n"
        + "=" * 90
    )

    print(
        "FREDDIE MAC DATA AUDIT"
    )

    print(
        "VINTAGES 2016–2026"
    )

    print(
        "=" * 90
    )


    # -----------------------------------------------------
    # KẾT QUẢ
    # -----------------------------------------------------

    records = []

    failed = []


    # -----------------------------------------------------
    # AUDIT TỪNG VINTAGE
    # -----------------------------------------------------

    for year in STUDY_YEARS:

        print(
            f"\nĐang kiểm tra {year}..."
        )

        try:

            result = validate_year(
                year,
                show_report=False,
            )


            records.append(
                {
                    "year":
                        result["year"],

                    "status":
                        result["status"],

                    "orig_rows":
                        result["orig_rows"],

                    "orig_unique_loans":
                        result["orig_unique_loans"],

                    "perf_rows":
                        result["perf_rows"],

                    "perf_unique_loans":
                        result["perf_unique_loans"],

                    "perf_missing_in_orig":
                        result[
                            "perf_missing_in_orig"
                        ],

                    "orig_missing_in_perf":
                        result[
                            "orig_missing_in_perf"
                        ],

                    "missing_before_cutoff":
                        result[
                            "orig_missing_before_cutoff"
                        ],

                    "missing_at_after_cutoff":
                        result[
                            "orig_missing_at_or_after_cutoff"
                        ],

                    "first_period":
                        result["first_period"],

                    "last_period":
                        result["last_period"],

                    "min_loan_age":
                        result["min_loan_age"],

                    "max_loan_age":
                        result["max_loan_age"],

                    "RA_rows":
                        result["RA_rows"],

                    "XX_rows":
                        result["XX_rows"],

                    "orig_size_mb":
                        round(
                            result["orig_size_mb"],
                            2,
                        ),

                    "perf_size_mb":
                        round(
                            result["perf_size_mb"],
                            2,
                        ),
                }
            )


            print(
                f"✓ {year}: "
                f"{result['status']}"
            )


        except Exception as error:

            failed.append(
                {
                    "year": year,
                    "error": str(error),
                }
            )

            print(
                f"❌ {year}: {error}"
            )


    # -----------------------------------------------------
    # KHÔNG CÓ KẾT QUẢ
    # -----------------------------------------------------

    if not records:

        print(
            "\nKhông có vintage nào "
            "audit thành công."
        )

        sys.exit(1)


    # -----------------------------------------------------
    # TẠO DATAFRAME
    # -----------------------------------------------------

    audit = (
        pl.DataFrame(
            records
        )
        .sort(
            "year"
        )
    )


    # -----------------------------------------------------
    # HIỂN THỊ BẢNG TỔNG HỢP
    # -----------------------------------------------------

    print(
        "\n"
        + "=" * 90
    )

    print(
        "AUDIT SUMMARY"
    )

    print(
        "=" * 90
    )

    print(
        audit
    )


    # -----------------------------------------------------
    # TỔNG SỐ DỮ LIỆU
    # -----------------------------------------------------

    total_orig_rows = (
        audit[
            "orig_rows"
        ]
        .sum()
    )

    total_perf_rows = (
        audit[
            "perf_rows"
        ]
        .sum()
    )

    total_orig_loans = (
        audit[
            "orig_unique_loans"
        ]
        .sum()
    )

    total_perf_loans = (
        audit[
            "perf_unique_loans"
        ]
        .sum()
    )

    total_orig_missing = (
        audit[
            "orig_missing_in_perf"
        ]
        .sum()
    )

    total_perf_missing = (
        audit[
            "perf_missing_in_orig"
        ]
        .sum()
    )

    total_ra = (
        audit[
            "RA_rows"
        ]
        .sum()
    )

    total_xx = (
        audit[
            "XX_rows"
        ]
        .sum()
    )


    # -----------------------------------------------------
    # DATASET TOTALS
    # -----------------------------------------------------

    print(
        "\n"
        + "=" * 90
    )

    print(
        "DATASET TOTALS"
    )

    print(
        "=" * 90
    )

    print(
        f"Origination rows:          "
        f"{total_orig_rows:,}"
    )

    print(
        f"Origination unique loans:  "
        f"{total_orig_loans:,}"
    )

    print(
        f"Performance rows:          "
        f"{total_perf_rows:,}"
    )

    print(
        f"Performance unique loans:  "
        f"{total_perf_loans:,}"
    )

    print(
        f"Orig missing in Perf:      "
        f"{total_orig_missing:,}"
    )

    print(
        f"Perf missing in Orig:      "
        f"{total_perf_missing:,}"
    )

    print(
        f"RA rows:                   "
        f"{total_ra:,}"
    )

    print(
        f"XX rows:                   "
        f"{total_xx:,}"
    )


    # -----------------------------------------------------
    # STATUS DISTRIBUTION
    # -----------------------------------------------------

    print(
        "\nSTATUS:"
    )

    status_summary = (
        audit
        .group_by(
            "status"
        )
        .len()
        .sort(
            "status"
        )
    )

    print(
        status_summary
    )


    # -----------------------------------------------------
    # SAVE OUTPUT
    # -----------------------------------------------------

    csv_output = (
        TABLES_DIR
        / "data_audit_2016_2026.csv"
    )

    parquet_output = (
        TABLES_DIR
        / "data_audit_2016_2026.parquet"
    )


    audit.write_csv(
        csv_output
    )

    audit.write_parquet(
        parquet_output
    )


    print(
        "\n"
        + "=" * 90
    )

    print(
        "AUDIT FILES CREATED"
    )

    print(
        "=" * 90
    )

    print(
        csv_output
    )

    print(
        parquet_output
    )


    # -----------------------------------------------------
    # FAILED CHECKS
    # -----------------------------------------------------

    if failed:

        print(
            "\n⚠ CÓ VINTAGE AUDIT THẤT BẠI:"
        )

        for item in failed:

            print(
                f"{item['year']}: "
                f"{item['error']}"
            )

        sys.exit(1)


    # -----------------------------------------------------
    # DONE
    # -----------------------------------------------------

    print(
        "\n"
        + "=" * 90
    )

    print(
        "✓ DATA AUDIT HOÀN THÀNH"
    )

    print(
        "=" * 90
    )


if __name__ == "__main__":
    main()