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
    orig_parquet_path,
    perf_parquet_path,
)


# =========================================================
# HELPERS
# =========================================================

def numeric_expr(column: str) -> pl.Expr:
    """
    Convert string column to Float64.
    Invalid values become null.
    """
    return (
        pl.col(column)
        .cast(
            pl.Float64,
            strict=False,
        )
    )


def empty_expr(column: str) -> pl.Expr:
    """
    Detect null or blank string.
    """
    return (
        pl.col(column).is_null()
        |
        (
            pl.col(column)
            .cast(pl.String)
            .str.strip_chars()
            == ""
        )
    )


# =========================================================
# ORIGINATION AUDIT
# =========================================================

def audit_origination(year: int) -> dict:

    file = orig_parquet_path(year)

    df = pl.scan_parquet(file)

    result = (
        df
        .select(

            pl.len().alias(
                "rows"
            ),

            # ---------------------------------------------
            # FICO
            # ---------------------------------------------

            empty_expr(
                "fico"
            )
            .sum()
            .alias(
                "fico_blank"
            ),

            (
                pl.col("fico")
                == "9999"
            )
            .sum()
            .alias(
                "fico_9999"
            ),

            (
                numeric_expr("fico")
                .is_not_null()
                &
                (
                    (
                        numeric_expr("fico")
                        < 300
                    )
                    |
                    (
                        numeric_expr("fico")
                        > 850
                    )
                )
            )
            .sum()
            .alias(
                "fico_outside_300_850"
            ),


            # ---------------------------------------------
            # ORIGINAL LTV
            # ---------------------------------------------

            empty_expr(
                "original_ltv"
            )
            .sum()
            .alias(
                "original_ltv_blank"
            ),

            numeric_expr(
                "original_ltv"
            )
            .min()
            .alias(
                "original_ltv_min"
            ),

            numeric_expr(
                "original_ltv"
            )
            .max()
            .alias(
                "original_ltv_max"
            ),


            # ---------------------------------------------
            # ORIGINAL CLTV
            # ---------------------------------------------

            empty_expr(
                "original_cltv"
            )
            .sum()
            .alias(
                "original_cltv_blank"
            ),

            numeric_expr(
                "original_cltv"
            )
            .min()
            .alias(
                "original_cltv_min"
            ),

            numeric_expr(
                "original_cltv"
            )
            .max()
            .alias(
                "original_cltv_max"
            ),


            # ---------------------------------------------
            # ORIGINAL DTI
            # ---------------------------------------------

            empty_expr(
                "original_dti"
            )
            .sum()
            .alias(
                "original_dti_blank"
            ),

            (
                pl.col(
                    "original_dti"
                )
                == "999"
            )
            .sum()
            .alias(
                "original_dti_999"
            ),

            numeric_expr(
                "original_dti"
            )
            .min()
            .alias(
                "original_dti_min"
            ),

            numeric_expr(
                "original_dti"
            )
            .max()
            .alias(
                "original_dti_max"
            ),


            # ---------------------------------------------
            # INTEREST RATE
            # ---------------------------------------------

            empty_expr(
                "original_interest_rate"
            )
            .sum()
            .alias(
                "interest_rate_blank"
            ),

            numeric_expr(
                "original_interest_rate"
            )
            .min()
            .alias(
                "interest_rate_min"
            ),

            numeric_expr(
                "original_interest_rate"
            )
            .max()
            .alias(
                "interest_rate_max"
            ),


            # ---------------------------------------------
            # ORIGINAL UPB
            # ---------------------------------------------

            empty_expr(
                "original_upb"
            )
            .sum()
            .alias(
                "original_upb_blank"
            ),

            numeric_expr(
                "original_upb"
            )
            .min()
            .alias(
                "original_upb_min"
            ),

            numeric_expr(
                "original_upb"
            )
            .max()
            .alias(
                "original_upb_max"
            ),


            # ---------------------------------------------
            # LOAN TERM
            # ---------------------------------------------

            empty_expr(
                "original_loan_term"
            )
            .sum()
            .alias(
                "loan_term_blank"
            ),

            numeric_expr(
                "original_loan_term"
            )
            .min()
            .alias(
                "loan_term_min"
            ),

            numeric_expr(
                "original_loan_term"
            )
            .max()
            .alias(
                "loan_term_max"
            ),


            # ---------------------------------------------
            # DATES
            # ---------------------------------------------

            empty_expr(
                "first_payment_date"
            )
            .sum()
            .alias(
                "first_payment_date_blank"
            ),

            empty_expr(
                "maturity_date"
            )
            .sum()
            .alias(
                "maturity_date_blank"
            ),


            # ---------------------------------------------
            # VANTAGESCORE
            # ---------------------------------------------

            empty_expr(
                "vantagescore_4"
            )
            .sum()
            .alias(
                "vantagescore_blank"
            ),

        )
        .collect()
        .to_dicts()[0]
    )

    result["year"] = year

    return result


# =========================================================
# PERFORMANCE AUDIT
# =========================================================

def audit_performance(year: int) -> dict:

    file = perf_parquet_path(year)

    df = pl.scan_parquet(file)

    result = (
        df
        .select(

            pl.len().alias(
                "rows"
            ),

            # ---------------------------------------------
            # DELINQUENCY
            # ---------------------------------------------

            empty_expr(
                "delinquency_status"
            )
            .sum()
            .alias(
                "delinquency_blank"
            ),

            (
                pl.col(
                    "delinquency_status"
                )
                == "RA"
            )
            .sum()
            .alias(
                "delinquency_RA"
            ),

            (
                pl.col(
                    "delinquency_status"
                )
                == "XX"
            )
            .sum()
            .alias(
                "delinquency_XX"
            ),


            # ---------------------------------------------
            # MONTHLY REPORTING PERIOD
            # ---------------------------------------------

            empty_expr(
                "monthly_reporting_period"
            )
            .sum()
            .alias(
                "reporting_period_blank"
            ),


            # ---------------------------------------------
            # LOAN AGE
            # ---------------------------------------------

            empty_expr(
                "loan_age"
            )
            .sum()
            .alias(
                "loan_age_blank"
            ),

            numeric_expr(
                "loan_age"
            )
            .min()
            .alias(
                "loan_age_min"
            ),

            numeric_expr(
                "loan_age"
            )
            .max()
            .alias(
                "loan_age_max"
            ),


            # ---------------------------------------------
            # CURRENT UPB
            # ---------------------------------------------

            empty_expr(
                "current_actual_upb"
            )
            .sum()
            .alias(
                "current_upb_blank"
            ),

            numeric_expr(
                "current_actual_upb"
            )
            .min()
            .alias(
                "current_upb_min"
            ),

            numeric_expr(
                "current_actual_upb"
            )
            .max()
            .alias(
                "current_upb_max"
            ),


            # ---------------------------------------------
            # CURRENT INTEREST RATE
            # ---------------------------------------------

            empty_expr(
                "current_interest_rate"
            )
            .sum()
            .alias(
                "current_rate_blank"
            ),

            numeric_expr(
                "current_interest_rate"
            )
            .min()
            .alias(
                "current_rate_min"
            ),

            numeric_expr(
                "current_interest_rate"
            )
            .max()
            .alias(
                "current_rate_max"
            ),


            # ---------------------------------------------
            # ZERO BALANCE
            # ---------------------------------------------

            empty_expr(
                "zero_balance_code"
            )
            .sum()
            .alias(
                "zero_balance_blank"
            ),


            # ---------------------------------------------
            # ESTIMATED LTV
            # ---------------------------------------------

            empty_expr(
                "estimated_ltv"
            )
            .sum()
            .alias(
                "estimated_ltv_blank"
            ),

            (
                pl.col(
                    "estimated_ltv"
                )
                == "999"
            )
            .sum()
            .alias(
                "estimated_ltv_999"
            ),


            # ---------------------------------------------
            # DDLPI
            # ---------------------------------------------

            empty_expr(
                "ddlpi"
            )
            .sum()
            .alias(
                "ddlpi_blank"
            ),

        )
        .collect()
        .to_dicts()[0]
    )

    result["year"] = year

    return result


# =========================================================
# DISTRIBUTION TABLES
# =========================================================

def build_delinquency_distribution():

    tables = []

    for year in STUDY_YEARS:

        df = (
            pl.scan_parquet(
                perf_parquet_path(year)
            )
            .group_by(
                "delinquency_status"
            )
            .len()
            .with_columns(
                pl.lit(year)
                .alias("year")
            )
            .collect()
        )

        tables.append(df)

    return (
        pl.concat(
            tables,
            how="vertical",
        )
        .select(
            "year",
            "delinquency_status",
            "len",
        )
        .sort(
            [
                "year",
                "delinquency_status",
            ]
        )
    )


def build_zero_balance_distribution():

    tables = []

    for year in STUDY_YEARS:

        df = (
            pl.scan_parquet(
                perf_parquet_path(year)
            )
            .filter(
                pl.col(
                    "zero_balance_code"
                )
                .is_not_null()
            )
            .group_by(
                "zero_balance_code"
            )
            .len()
            .with_columns(
                pl.lit(year)
                .alias("year")
            )
            .collect()
        )

        tables.append(df)

    return (
        pl.concat(
            tables,
            how="vertical",
        )
        .select(
            "year",
            "zero_balance_code",
            "len",
        )
        .sort(
            [
                "year",
                "zero_balance_code",
            ]
        )
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
        "FREDDIE MAC VARIABLE QUALITY AUDIT"
    )

    print(
        "2016–2026"
    )

    print(
        "=" * 90
    )


    # =====================================================
    # ORIGINATION AUDIT
    # =====================================================

    print(
        "\n[1/4] Auditing Origination variables..."
    )

    orig_records = []

    for year in STUDY_YEARS:

        print(
            f"  Origination {year}..."
        )

        orig_records.append(
            audit_origination(year)
        )


    orig_audit = (
        pl.DataFrame(
            orig_records
        )
        .select(
            "year",
            pl.exclude("year"),
        )
        .sort(
            "year"
        )
    )


    # =====================================================
    # PERFORMANCE AUDIT
    # =====================================================

    print(
        "\n[2/4] Auditing Performance variables..."
    )

    perf_records = []

    for year in STUDY_YEARS:

        print(
            f"  Performance {year}..."
        )

        perf_records.append(
            audit_performance(year)
        )


    perf_audit = (
        pl.DataFrame(
            perf_records
        )
        .select(
            "year",
            pl.exclude("year"),
        )
        .sort(
            "year"
        )
    )


    # =====================================================
    # DISTRIBUTIONS
    # =====================================================

    print(
        "\n[3/4] Building delinquency distribution..."
    )

    delinquency_distribution = (
        build_delinquency_distribution()
    )


    print(
        "\n[4/4] Building zero balance distribution..."
    )

    zero_balance_distribution = (
        build_zero_balance_distribution()
    )


    # =====================================================
    # SAVE FILES
    # =====================================================

    orig_csv = (
        TABLES_DIR
        / "audit_origination_variables.csv"
    )

    perf_csv = (
        TABLES_DIR
        / "audit_performance_variables.csv"
    )

    delinquency_csv = (
        TABLES_DIR
        / "audit_delinquency_codes.csv"
    )

    zero_balance_csv = (
        TABLES_DIR
        / "audit_zero_balance_codes.csv"
    )


    orig_audit.write_csv(
        orig_csv
    )

    perf_audit.write_csv(
        perf_csv
    )

    delinquency_distribution.write_csv(
        delinquency_csv
    )

    zero_balance_distribution.write_csv(
        zero_balance_csv
    )


    # =====================================================
    # CONSOLE SUMMARY
    # =====================================================

    print(
        "\n"
        + "=" * 90
    )

    print(
        "ORIGINATION AUDIT"
    )

    print(
        "=" * 90
    )

    print(
        orig_audit
    )


    print(
        "\n"
        + "=" * 90
    )

    print(
        "PERFORMANCE AUDIT"
    )

    print(
        "=" * 90
    )

    print(
        perf_audit
    )


    print(
        "\n"
        + "=" * 90
    )

    print(
        "FILES CREATED"
    )

    print(
        "=" * 90
    )

    print(
        orig_csv
    )

    print(
        perf_csv
    )

    print(
        delinquency_csv
    )

    print(
        zero_balance_csv
    )


    print(
        "\n"
        + "=" * 90
    )

    print(
        "✓ VARIABLE QUALITY AUDIT HOÀN THÀNH"
    )

    print(
        "=" * 90
    )


if __name__ == "__main__":
    main()