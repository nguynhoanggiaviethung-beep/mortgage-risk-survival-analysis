from pathlib import Path
import sys
import zipfile

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
    MODEL_DIR,
    TABLES_DIR,
    sample_zip_path,
    orig_parquet_path,
    perf_parquet_path,
    ensure_directories,
)


# =========================================================
# CONFIG
# =========================================================

PERFORMANCE_CUTOFF = 202603

REPORTS_DIR = PROJECT_ROOT / "reports"

FINAL_CSV = (
    TABLES_DIR
    / "final_data_validation.csv"
)

RAW_REPORT = (
    REPORTS_DIR
    / "raw_validation.md"
)

CLEAN_REPORT = (
    REPORTS_DIR
    / "clean_validation.md"
)


# =========================================================
# REQUIRED SCHEMA
# =========================================================

REQUIRED_ORIG_PROCESSED = {
    "loan_id",
    "fico",
    "first_payment_date",
    "maturity_date",
    "original_cltv",
    "original_dti",
    "original_upb",
    "original_ltv",
    "original_interest_rate",
    "occupancy_status",
    "amortization_type",
    "property_state",
    "property_type",
    "loan_purpose",
    "original_loan_term",
    "number_borrowers",
    "vantagescore_4",
    "vintage_year",
}


REQUIRED_PERF_PROCESSED = {
    "loan_id",
    "monthly_reporting_period",
    "current_actual_upb",
    "delinquency_status",
    "loan_age",
    "remaining_months_maturity",
    "modification_flag",
    "zero_balance_code",
    "zero_balance_effective_date",
    "current_interest_rate",
    "ddlpi",
    "payment_deferral_flag",
    "estimated_ltv",
    "delinquency_due_to_disaster",
    "borrower_assistance_plan",
    "current_interest_bearing_upb",
    "vintage_year",
}


REQUIRED_ORIG_CLEAN = {
    "loan_id",
    "fico_raw",
    "fico",
    "original_dti_raw",
    "original_dti",
    "original_ltv_raw",
    "original_ltv",
    "original_cltv_raw",
    "original_cltv",
    "number_borrowers_raw",
    "number_borrowers",
    "multiple_borrowers_flag",
    "legacy_number_borrowers_encoding_flag",
    "first_payment_month",
    "maturity_month",
    "ltv_above_100_flag",
    "cltv_above_100_flag",
}


REQUIRED_PERF_CLEAN = {
    "loan_id",
    "monthly_reporting_period",
    "reporting_period_num",
    "reporting_month",
    "loan_age",
    "delinquency_status_raw",
    "delinquency_num",
    "is_xx",
    "is_ra",
    "estimated_ltv_raw",
    "estimated_ltv",
    "estimated_ltv_not_available_flag",
    "is_loan_age_zero",
    "zero_balance_code",
    "has_zero_balance_event",
}


# =========================================================
# HELPERS
# =========================================================

def scalar(lf: pl.LazyFrame, expr: pl.Expr):

    return (
        lf
        .select(
            expr.alias("value")
        )
        .collect()
        .item()
    )


def row_count(lf: pl.LazyFrame) -> int:

    return int(
        scalar(
            lf,
            pl.len(),
        )
    )


def check_schema(
    path: Path,
    required_columns: set,
):

    schema = (
        pl.scan_parquet(path)
        .collect_schema()
    )

    actual = set(
        schema.names()
    )

    missing = sorted(
        required_columns
        - actual
    )

    return (
        len(missing) == 0,
        missing,
    )


# =========================================================
# ZIP STRUCTURE VALIDATION
# =========================================================

def validate_zip_structure(
    year: int,
):

    path = sample_zip_path(year)

    if not path.exists():

        return False, "ZIP missing"


    if not zipfile.is_zipfile(path):

        return False, "Invalid ZIP"


    expected_files = {
        f"sample_orig_{year}.txt",
        f"sample_perf_{year}.txt",
    }


    try:

        with zipfile.ZipFile(
            path,
            "r",
        ) as zf:

            info_list = (
                zf.infolist()
            )

            basenames = {
                Path(info.filename).name
                for info in info_list
            }


            missing = (
                expected_files
                - basenames
            )


            if missing:

                return (
                    False,
                    "Missing members: "
                    + ", ".join(
                        sorted(missing)
                    ),
                )


            for expected in expected_files:

                matching = [
                    info
                    for info in info_list
                    if Path(
                        info.filename
                    ).name
                    == expected
                ]

                if not matching:

                    return (
                        False,
                        f"{expected} not found",
                    )

                if matching[0].file_size <= 0:

                    return (
                        False,
                        f"{expected} empty",
                    )


    except Exception as error:

        return (
            False,
            str(error),
        )


    return (
        True,
        "OK",
    )


# =========================================================
# VALIDATE ONE YEAR
# =========================================================

def validate_year(
    year: int,
) -> dict:

    print(
        "\n"
        + "=" * 80
    )

    print(
        f"FINAL DATA VALIDATION - {year}"
    )

    print(
        "=" * 80
    )


    # =====================================================
    # PATHS
    # =====================================================

    orig_processed_path = (
        orig_parquet_path(year)
    )

    perf_processed_path = (
        perf_parquet_path(year)
    )

    orig_clean_path = (
        MODEL_DIR
        / f"orig_clean_{year}.parquet"
    )

    perf_clean_path = (
        MODEL_DIR
        / f"perf_clean_{year}.parquet"
    )


    # =====================================================
    # FILE EXISTENCE
    # =====================================================

    required_paths = [
        orig_processed_path,
        perf_processed_path,
        orig_clean_path,
        perf_clean_path,
    ]


    for path in required_paths:

        if not path.exists():

            raise FileNotFoundError(
                f"Không tìm thấy file:\n"
                f"{path}"
            )


    # =====================================================
    # ZIP STRUCTURE
    # =====================================================

    zip_ok, zip_message = (
        validate_zip_structure(
            year
        )
    )


    # =====================================================
    # SCHEMA
    # =====================================================

    (
        orig_schema_ok,
        orig_schema_missing,
    ) = check_schema(
        orig_processed_path,
        REQUIRED_ORIG_PROCESSED,
    )


    (
        perf_schema_ok,
        perf_schema_missing,
    ) = check_schema(
        perf_processed_path,
        REQUIRED_PERF_PROCESSED,
    )


    (
        orig_clean_schema_ok,
        orig_clean_schema_missing,
    ) = check_schema(
        orig_clean_path,
        REQUIRED_ORIG_CLEAN,
    )


    (
        perf_clean_schema_ok,
        perf_clean_schema_missing,
    ) = check_schema(
        perf_clean_path,
        REQUIRED_PERF_CLEAN,
    )


    schema_ok = all(
        [
            orig_schema_ok,
            perf_schema_ok,
            orig_clean_schema_ok,
            perf_clean_schema_ok,
        ]
    )


    # =====================================================
    # LOAD LAZY DATA
    # =====================================================

    orig_processed = (
        pl.scan_parquet(
            orig_processed_path
        )
    )

    perf_processed = (
        pl.scan_parquet(
            perf_processed_path
        )
    )

    orig_clean = (
        pl.scan_parquet(
            orig_clean_path
        )
    )

    perf_clean = (
        pl.scan_parquet(
            perf_clean_path
        )
    )


    # =====================================================
    # ROW COUNTS
    # =====================================================

    orig_processed_rows = (
        row_count(
            orig_processed
        )
    )

    perf_processed_rows = (
        row_count(
            perf_processed
        )
    )

    orig_clean_rows = (
        row_count(
            orig_clean
        )
    )

    perf_clean_rows = (
        row_count(
            perf_clean
        )
    )


    orig_row_match = (
        orig_processed_rows
        == orig_clean_rows
    )

    perf_row_match = (
        perf_processed_rows
        == perf_clean_rows
    )


    # =====================================================
    # ORIGINATION DUPLICATE LOAN ID
    # =====================================================

    orig_duplicate_loan_ids = (
        orig_processed
        .group_by(
            "loan_id"
        )
        .len()
        .filter(
            pl.col("len")
            > 1
        )
        .select(
            pl.len()
            .alias(
                "value"
            )
        )
        .collect()
        .item()
    )


    # =====================================================
    # PERFORMANCE DUPLICATE LOAN-MONTH
    # =====================================================

    perf_duplicate_loan_month = (
        perf_processed
        .group_by(
            [
                "loan_id",
                "monthly_reporting_period",
            ]
        )
        .len()
        .filter(
            pl.col("len")
            > 1
        )
        .select(
            pl.len()
            .alias(
                "value"
            )
        )
        .collect()
        .item()
    )


    # =====================================================
    # ID COVERAGE
    # =====================================================

    orig_ids = (
        orig_processed
        .select(
            "loan_id"
        )
        .unique()
    )


    perf_ids = (
        perf_processed
        .select(
            "loan_id"
        )
        .unique()
    )


    perf_ids_not_in_orig = (
        perf_ids
        .join(
            orig_ids,
            on="loan_id",
            how="anti",
        )
        .select(
            pl.len()
            .alias(
                "value"
            )
        )
        .collect()
        .item()
    )


    orig_ids_without_perf = (
        orig_ids
        .join(
            perf_ids,
            on="loan_id",
            how="anti",
        )
        .select(
            pl.len()
            .alias(
                "value"
            )
        )
        .collect()
        .item()
    )


    # =====================================================
    # REPORTING PERIOD VALIDATION
    # =====================================================

    perf_period = (
        perf_clean
        .with_columns(

            pl.col(
                "reporting_period_num"
            )
            .cast(
                pl.Int32,
                strict=False,
            )
            .alias(
                "_period"
            )

        )
    )


    invalid_reporting_period = (
        scalar(

            perf_period,

            (
                pl.col(
                    "_period"
                )
                .is_null()

                |

                (
                    (
                        pl.col(
                            "_period"
                        )
                        % 100
                    )
                    < 1
                )

                |

                (
                    (
                        pl.col(
                            "_period"
                        )
                        % 100
                    )
                    > 12
                )
            )
            .sum()

        )
    )


    reporting_after_cutoff = (
        scalar(

            perf_period,

            (
                pl.col(
                    "_period"
                )
                > PERFORMANCE_CUTOFF
            )
            .sum()

        )
    )


    # =====================================================
    # TEMPORAL ORDER IN SOURCE
    # =====================================================

    reporting_order_violations = (
        perf_period

        .with_columns(

            pl.col(
                "_period"
            )
            .shift(1)
            .over(
                "loan_id"
            )
            .alias(
                "_previous_period"
            )

        )

        .filter(

            pl.col(
                "_previous_period"
            )
            .is_not_null()

            &

            (
                pl.col(
                    "_period"
                )
                <
                pl.col(
                    "_previous_period"
                )
            )

        )

        .select(
            pl.len()
            .alias(
                "value"
            )
        )

        .collect()
        .item()
    )


    # =====================================================
    # MONTHLY GAPS
    #
    # This is a warning, not an automatic failure.
    # =====================================================

    valid_period = (
        perf_period

        .filter(

            pl.col(
                "_period"
            )
            .is_not_null()

            &

            (
                (
                    pl.col(
                        "_period"
                    )
                    % 100
                )
                >= 1
            )

            &

            (
                (
                    pl.col(
                        "_period"
                    )
                    % 100
                )
                <= 12
            )

        )

        .with_columns(

            (
                (
                    (
                        pl.col(
                            "_period"
                        )
                        / 100
                    )
                    .floor()
                    .cast(
                        pl.Int32
                    )
                    * 12
                )

                +

                (
                    pl.col(
                        "_period"
                    )
                    % 100
                )
            )
            .alias(
                "_month_index"
            )

        )
    )


    gap_table = (
        valid_period

        .group_by(
            "loan_id"
        )

        .agg(

            pl.col(
                "_month_index"
            )
            .min()
            .alias(
                "_min_month"
            ),

            pl.col(
                "_month_index"
            )
            .max()
            .alias(
                "_max_month"
            ),

            pl.col(
                "_month_index"
            )
            .n_unique()
            .alias(
                "_observed_months"
            ),

        )

        .with_columns(

            (
                (
                    pl.col(
                        "_max_month"
                    )
                    -
                    pl.col(
                        "_min_month"
                    )
                    + 1
                )
                -
                pl.col(
                    "_observed_months"
                )
            )
            .alias(
                "_missing_months"
            )

        )

        .filter(
            pl.col(
                "_missing_months"
            )
            > 0
        )
    )


    loans_with_reporting_gaps = (
        gap_table
        .select(
            pl.len()
            .alias(
                "value"
            )
        )
        .collect()
        .item()
    )


    total_missing_reporting_months = (
        gap_table
        .select(

            pl.col(
                "_missing_months"
            )
            .sum()
            .fill_null(0)
            .alias(
                "value"
            )

        )
        .collect()
        .item()
    )


    # =====================================================
    # DATE VALIDATION
    # =====================================================

    invalid_first_payment_date = (
        scalar(

            orig_clean,

            pl.col(
                "first_payment_month"
            )
            .is_null()
            .sum()

        )
    )


    invalid_maturity_date = (
        scalar(

            orig_clean,

            pl.col(
                "maturity_month"
            )
            .is_null()
            .sum()

        )
    )


    maturity_before_first_payment = (
        scalar(

            orig_clean,

            (
                pl.col(
                    "maturity_month"
                )
                <
                pl.col(
                    "first_payment_month"
                )
            )
            .fill_null(False)
            .sum()

        )
    )


    # =====================================================
    # LOAN AGE VALIDATION
    # =====================================================

    negative_loan_age = (
        scalar(

            perf_clean,

            (
                pl.col(
                    "loan_age"
                )
                < 0
            )
            .fill_null(False)
            .sum()

        )
    )


    # =====================================================
    # CLEANING CONSISTENCY - ORIGINATION
    # =====================================================

    orig_special_checks = (
        orig_clean

        .select(

            (
                (
                    pl.col(
                        "fico_raw"
                    )
                    == "9999"
                )
                &
                pl.col(
                    "fico"
                )
                .is_not_null()
            )
            .sum()
            .alias(
                "fico_bad"
            ),


            (
                (
                    pl.col(
                        "original_dti_raw"
                    )
                    == "999"
                )
                &
                pl.col(
                    "original_dti"
                )
                .is_not_null()
            )
            .sum()
            .alias(
                "dti_bad"
            ),


            (
                (
                    pl.col(
                        "original_ltv_raw"
                    )
                    == "999"
                )
                &
                pl.col(
                    "original_ltv"
                )
                .is_not_null()
            )
            .sum()
            .alias(
                "ltv_bad"
            ),


            (
                (
                    pl.col(
                        "original_cltv_raw"
                    )
                    == "999"
                )
                &
                pl.col(
                    "original_cltv"
                )
                .is_not_null()
            )
            .sum()
            .alias(
                "cltv_bad"
            ),


            (
                pl.col(
                    "legacy_number_borrowers_encoding_flag"
                )

                &

                (
                    pl.col(
                        "number_borrowers_raw"
                    )
                    == "2"
                )

                &

                pl.col(
                    "number_borrowers"
                )
                .is_not_null()
            )
            .sum()
            .alias(
                "borrower_legacy_bad"
            ),

        )

        .collect()
    )


    orig_cleaning_violations = sum(
        int(
            orig_special_checks[
                column
            ][0]
        )
        for column in (
            orig_special_checks.columns
        )
    )


    # =====================================================
    # CLEANING CONSISTENCY - PERFORMANCE
    # =====================================================

    perf_special_checks = (
        perf_clean

        .select(

            (
                (
                    pl.col(
                        "delinquency_status_raw"
                    )
                    == "XX"
                )
                &
                pl.col(
                    "delinquency_num"
                )
                .is_not_null()
            )
            .sum()
            .alias(
                "xx_bad"
            ),


            (
                (
                    pl.col(
                        "delinquency_status_raw"
                    )
                    == "RA"
                )
                &
                pl.col(
                    "delinquency_num"
                )
                .is_not_null()
            )
            .sum()
            .alias(
                "ra_bad"
            ),


            (
                (
                    pl.col(
                        "estimated_ltv_raw"
                    )
                    == "999"
                )
                &
                pl.col(
                    "estimated_ltv"
                )
                .is_not_null()
            )
            .sum()
            .alias(
                "eltv_bad"
            ),


            (
                pl.col(
                    "delinquency_status_raw"
                )
                .is_not_null()

                &

                ~pl.col(
                    "delinquency_status_raw"
                )
                .is_in(
                    [
                        "XX",
                        "RA",
                    ]
                )

                &

                pl.col(
                    "delinquency_num"
                )
                .is_null()
            )
            .sum()
            .alias(
                "delinquency_parse_bad"
            ),

        )

        .collect()
    )


    perf_cleaning_violations = sum(
        int(
            perf_special_checks[
                column
            ][0]
        )
        for column in (
            perf_special_checks.columns
        )
    )


    cleaning_violations = (
        orig_cleaning_violations
        +
        perf_cleaning_violations
    )


    # =====================================================
    # STATUS
    # =====================================================

    critical_fail = any(
        [
            not zip_ok,
            not schema_ok,
            not orig_row_match,
            not perf_row_match,

            orig_duplicate_loan_ids > 0,

            perf_duplicate_loan_month > 0,

            perf_ids_not_in_orig > 0,

            invalid_reporting_period > 0,

            reporting_after_cutoff > 0,

            reporting_order_violations > 0,

            invalid_first_payment_date > 0,

            invalid_maturity_date > 0,

            maturity_before_first_payment > 0,

            negative_loan_age > 0,

            cleaning_violations > 0,
        ]
    )


    warning = any(
        [
            orig_ids_without_perf > 0,
            loans_with_reporting_gaps > 0,
        ]
    )


    if critical_fail:

        status = "FAIL"

    elif warning:

        status = "PASS_WITH_WARNING"

    else:

        status = "PASS"


    # =====================================================
    # RESULT
    # =====================================================

    result = {

        "year":
            year,

        "zip_ok":
            zip_ok,

        "schema_ok":
            schema_ok,

        "orig_processed_rows":
            orig_processed_rows,

        "orig_clean_rows":
            orig_clean_rows,

        "perf_processed_rows":
            perf_processed_rows,

        "perf_clean_rows":
            perf_clean_rows,

        "orig_row_match":
            orig_row_match,

        "perf_row_match":
            perf_row_match,

        "orig_duplicate_loan_ids":
            orig_duplicate_loan_ids,

        "perf_duplicate_loan_month":
            perf_duplicate_loan_month,

        "perf_ids_not_in_orig":
            perf_ids_not_in_orig,

        "orig_ids_without_perf":
            orig_ids_without_perf,

        "invalid_reporting_period":
            invalid_reporting_period,

        "reporting_after_cutoff":
            reporting_after_cutoff,

        "reporting_order_violations":
            reporting_order_violations,

        "loans_with_reporting_gaps":
            loans_with_reporting_gaps,

        "total_missing_reporting_months":
            total_missing_reporting_months,

        "invalid_first_payment_date":
            invalid_first_payment_date,

        "invalid_maturity_date":
            invalid_maturity_date,

        "maturity_before_first_payment":
            maturity_before_first_payment,

        "negative_loan_age":
            negative_loan_age,

        "cleaning_violations":
            cleaning_violations,

        "status":
            status,

        "zip_message":
            zip_message,

        "orig_schema_missing":
            ",".join(
                orig_schema_missing
            ),

        "perf_schema_missing":
            ",".join(
                perf_schema_missing
            ),

        "orig_clean_schema_missing":
            ",".join(
                orig_clean_schema_missing
            ),

        "perf_clean_schema_missing":
            ",".join(
                perf_clean_schema_missing
            ),

    }


    # =====================================================
    # TERMINAL REPORT
    # =====================================================

    print(
        f"ZIP structure:                  "
        f"{'PASS' if zip_ok else 'FAIL'}"
    )

    print(
        f"Schema:                         "
        f"{'PASS' if schema_ok else 'FAIL'}"
    )

    print(
        f"Orig rows processed/clean:      "
        f"{orig_processed_rows:,} / "
        f"{orig_clean_rows:,}"
    )

    print(
        f"Perf rows processed/clean:      "
        f"{perf_processed_rows:,} / "
        f"{perf_clean_rows:,}"
    )

    print(
        f"Duplicate Orig Loan ID:         "
        f"{orig_duplicate_loan_ids:,}"
    )

    print(
        f"Duplicate Performance loan-mo:  "
        f"{perf_duplicate_loan_month:,}"
    )

    print(
        f"Perf IDs not in Orig:           "
        f"{perf_ids_not_in_orig:,}"
    )

    print(
        f"Orig IDs without Perf:          "
        f"{orig_ids_without_perf:,}"
    )

    print(
        f"Invalid reporting periods:      "
        f"{invalid_reporting_period:,}"
    )

    print(
        f"Reporting > 202603:             "
        f"{reporting_after_cutoff:,}"
    )

    print(
        f"Temporal order violations:      "
        f"{reporting_order_violations:,}"
    )

    print(
        f"Loans with reporting gaps:      "
        f"{loans_with_reporting_gaps:,}"
    )

    print(
        f"Missing reporting months total: "
        f"{total_missing_reporting_months:,}"
    )

    print(
        f"Negative Loan Age:              "
        f"{negative_loan_age:,}"
    )

    print(
        f"Cleaning-rule violations:       "
        f"{cleaning_violations:,}"
    )

    print(
        f"\nSTATUS: {status}"
    )


    return result


# =========================================================
# MARKDOWN HELPERS
# =========================================================

def write_raw_report(
    results: pl.DataFrame,
):

    lines = []

    lines.append(
        "# Freddie Mac Sample Raw / Processed Validation"
    )

    lines.append("")

    lines.append(
        "Study vintages: 2016–2026"
    )

    lines.append(
        f"Performance cutoff used: "
        f"{PERFORMANCE_CUTOFF}"
    )

    lines.append("")

    lines.append(
        "Raw ZIP files are preserved unchanged. "
        "ZIP validation checks that each archive is readable, "
        "contains the expected Origination and Performance "
        "members, and that both members are non-empty. "
        "The ingestion pipeline has already successfully "
        "extracted and processed every vintage."
    )

    lines.append("")

    lines.append(
        "| Year | ZIP | Orig rows | Perf rows | Orig dup ID | Perf dup loan-month | Perf ID not Orig | Orig without Perf | Order violations | After cutoff | Reporting gaps | Status |"
    )

    lines.append(
        "|---:|:---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|"
    )


    for row in results.iter_rows(
        named=True
    ):

        lines.append(

            f"| {row['year']} "
            f"| {'PASS' if row['zip_ok'] else 'FAIL'} "
            f"| {row['orig_processed_rows']:,} "
            f"| {row['perf_processed_rows']:,} "
            f"| {row['orig_duplicate_loan_ids']:,} "
            f"| {row['perf_duplicate_loan_month']:,} "
            f"| {row['perf_ids_not_in_orig']:,} "
            f"| {row['orig_ids_without_perf']:,} "
            f"| {row['reporting_order_violations']:,} "
            f"| {row['reporting_after_cutoff']:,} "
            f"| {row['loans_with_reporting_gaps']:,} "
            f"| {row['status']} |"

        )


    lines.append("")

    lines.append(
        "## Interpretation"
    )

    lines.append("")

    lines.append(
        "- `Orig without Perf` is reported separately "
        "because a newly originated loan may legitimately "
        "have no available monthly performance record before "
        "the dataset cutoff."
    )

    lines.append(
        "- Reporting gaps are treated as warnings for review, "
        "not automatically as corrupted observations."
    )

    lines.append(
        "- Duplicate Loan ID, duplicate loan-month, unknown "
        "Performance Loan IDs, dates beyond cutoff, or temporal "
        "order violations are treated as critical validation failures."
    )


    RAW_REPORT.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def write_clean_report(
    results: pl.DataFrame,
):

    lines = []

    lines.append(
        "# Freddie Mac Clean Data Validation"
    )

    lines.append("")

    lines.append(
        "This report validates the cleaned Origination "
        "and Monthly Performance Parquet files used by "
        "the modelling pipeline."
    )

    lines.append("")

    lines.append(
        "| Year | Orig row match | Perf row match | Schema | Invalid first payment | Invalid maturity | Maturity < first payment | Negative loan age | Cleaning violations | Status |"
    )

    lines.append(
        "|---:|:---:|:---:|:---:|---:|---:|---:|---:|---:|:---:|"
    )


    for row in results.iter_rows(
        named=True
    ):

        lines.append(

            f"| {row['year']} "
            f"| {'PASS' if row['orig_row_match'] else 'FAIL'} "
            f"| {'PASS' if row['perf_row_match'] else 'FAIL'} "
            f"| {'PASS' if row['schema_ok'] else 'FAIL'} "
            f"| {row['invalid_first_payment_date']:,} "
            f"| {row['invalid_maturity_date']:,} "
            f"| {row['maturity_before_first_payment']:,} "
            f"| {row['negative_loan_age']:,} "
            f"| {row['cleaning_violations']:,} "
            f"| {row['status']} |"

        )


    lines.append("")

    lines.append(
        "## Cleaning principles"
    )

    lines.append("")

    lines.append(
        "- Processed ingestion files remain unchanged."
    )

    lines.append(
        "- Raw special values are preserved in `*_raw` columns."
    )

    lines.append(
        "- Freddie Mac Not Available codes are converted "
        "to null in analytical columns and retained using flags."
    )

    lines.append(
        "- `XX` and `RA` remain available in the raw "
        "delinquency field and are not forced into numeric "
        "delinquency categories."
    )

    lines.append(
        "- No default/prepayment event definition is applied "
        "during cleaning."
    )


    CLEAN_REPORT.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


# =========================================================
# MAIN
# =========================================================

def main():

    ensure_directories()

    REPORTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    TABLES_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


    print(
        "\n"
        + "=" * 80
    )

    print(
        "FREDDIE MAC FINAL DATA PREPARATION VALIDATION"
    )

    print(
        "2016–2026"
    )

    print(
        "=" * 80
    )


    records = []


    for year in STUDY_YEARS:

        try:

            result = (
                validate_year(
                    year
                )
            )

            records.append(
                result
            )

        except Exception as error:

            print(
                "\n"
                + "=" * 80
            )

            print(
                f"❌ VALIDATION FAILED - {year}"
            )

            print(
                "=" * 80
            )

            print(
                error
            )

            records.append(
                {
                    "year":
                        year,

                    "zip_ok":
                        False,

                    "schema_ok":
                        False,

                    "orig_processed_rows":
                        0,

                    "orig_clean_rows":
                        0,

                    "perf_processed_rows":
                        0,

                    "perf_clean_rows":
                        0,

                    "orig_row_match":
                        False,

                    "perf_row_match":
                        False,

                    "orig_duplicate_loan_ids":
                        -1,

                    "perf_duplicate_loan_month":
                        -1,

                    "perf_ids_not_in_orig":
                        -1,

                    "orig_ids_without_perf":
                        -1,

                    "invalid_reporting_period":
                        -1,

                    "reporting_after_cutoff":
                        -1,

                    "reporting_order_violations":
                        -1,

                    "loans_with_reporting_gaps":
                        -1,

                    "total_missing_reporting_months":
                        -1,

                    "invalid_first_payment_date":
                        -1,

                    "invalid_maturity_date":
                        -1,

                    "maturity_before_first_payment":
                        -1,

                    "negative_loan_age":
                        -1,

                    "cleaning_violations":
                        -1,

                    "status":
                        "FAIL",

                    "zip_message":
                        str(error),

                    "orig_schema_missing":
                        "",

                    "perf_schema_missing":
                        "",

                    "orig_clean_schema_missing":
                        "",

                    "perf_clean_schema_missing":
                        "",
                }
            )


    # =====================================================
    # SAVE RESULTS
    # =====================================================

    result_df = (
        pl.DataFrame(
            records
        )
        .sort(
            "year"
        )
    )


    result_df.write_csv(
        FINAL_CSV
    )


    write_raw_report(
        result_df
    )

    write_clean_report(
        result_df
    )


    # =====================================================
    # FINAL SUMMARY
    # =====================================================

    pass_count = (
        result_df
        .filter(
            pl.col(
                "status"
            )
            == "PASS"
        )
        .height
    )

    warning_count = (
        result_df
        .filter(
            pl.col(
                "status"
            )
            == "PASS_WITH_WARNING"
        )
        .height
    )

    fail_count = (
        result_df
        .filter(
            pl.col(
                "status"
            )
            == "FAIL"
        )
        .height
    )


    print(
        "\n"
        + "=" * 80
    )

    print(
        "FINAL VALIDATION SUMMARY"
    )

    print(
        "=" * 80
    )

    print(
        f"PASS:              "
        f"{pass_count}"
    )

    print(
        f"PASS_WITH_WARNING: "
        f"{warning_count}"
    )

    print(
        f"FAIL:              "
        f"{fail_count}"
    )


    print(
        "\nFILES CREATED:"
    )

    print(
        f"  {FINAL_CSV}"
    )

    print(
        f"  {RAW_REPORT}"
    )

    print(
        f"  {CLEAN_REPORT}"
    )


    print(
        "\n"
        + "=" * 80
    )

    if fail_count > 0:

        print(
            "❌ DATA PREPARATION CHƯA THỂ ĐÓNG"
        )

    else:

        print(
            "✓ DATA PREPARATION VALIDATION HOÀN THÀNH"
        )

    print(
        "=" * 80
    )


    if fail_count > 0:

        sys.exit(1)


if __name__ == "__main__":
    main()