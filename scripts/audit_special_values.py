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
# HELPER
# =========================================================

def to_number(column: str) -> pl.Expr:
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


# =========================================================
# 1. ORIGINATION SPECIAL VALUES
# =========================================================

def audit_origination_special_values():

    records = []

    for year in STUDY_YEARS:

        print(
            f"  Origination {year}..."
        )

        df = pl.scan_parquet(
            orig_parquet_path(year)
        )

        stats = (
            df
            .select(

                # -----------------------------------------
                # NUMBER OF LOANS
                # -----------------------------------------

                pl.len()
                .alias(
                    "loans"
                ),


                # -----------------------------------------
                # FICO
                # 9999 = Not Available
                # -----------------------------------------

                (
                    pl.col(
                        "fico"
                    )
                    == "9999"
                )
                .sum()
                .alias(
                    "fico_9999"
                ),


                # -----------------------------------------
                # DTI
                # 999 = Not Available
                # -----------------------------------------

                (
                    pl.col(
                        "original_dti"
                    )
                    == "999"
                )
                .sum()
                .alias(
                    "dti_999"
                ),

                to_number(
                    "original_dti"
                )
                .filter(
                    pl.col(
                        "original_dti"
                    )
                    != "999"
                )
                .min()
                .alias(
                    "dti_min_excluding_999"
                ),

                to_number(
                    "original_dti"
                )
                .filter(
                    pl.col(
                        "original_dti"
                    )
                    != "999"
                )
                .max()
                .alias(
                    "dti_max_excluding_999"
                ),


                # -----------------------------------------
                # ORIGINAL LTV
                # -----------------------------------------

                (
                    pl.col(
                        "original_ltv"
                    )
                    == "999"
                )
                .sum()
                .alias(
                    "ltv_999"
                ),

                to_number(
                    "original_ltv"
                )
                .filter(
                    pl.col(
                        "original_ltv"
                    )
                    != "999"
                )
                .min()
                .alias(
                    "ltv_min_excluding_999"
                ),

                to_number(
                    "original_ltv"
                )
                .filter(
                    pl.col(
                        "original_ltv"
                    )
                    != "999"
                )
                .max()
                .alias(
                    "ltv_max_excluding_999"
                ),

                # FIXED:
                # Count valid LTV observations > 100
                (
                    (
                        to_number(
                            "original_ltv"
                        )
                        > 100
                    )
                    &
                    (
                        pl.col(
                            "original_ltv"
                        )
                        != "999"
                    )
                )
                .sum()
                .alias(
                    "ltv_above_100"
                ),


                # -----------------------------------------
                # ORIGINAL CLTV
                # -----------------------------------------

                (
                    pl.col(
                        "original_cltv"
                    )
                    == "999"
                )
                .sum()
                .alias(
                    "cltv_999"
                ),

                to_number(
                    "original_cltv"
                )
                .filter(
                    pl.col(
                        "original_cltv"
                    )
                    != "999"
                )
                .min()
                .alias(
                    "cltv_min_excluding_999"
                ),

                to_number(
                    "original_cltv"
                )
                .filter(
                    pl.col(
                        "original_cltv"
                    )
                    != "999"
                )
                .max()
                .alias(
                    "cltv_max_excluding_999"
                ),

                (
                    (
                        to_number(
                            "original_cltv"
                        )
                        > 100
                    )
                    &
                    (
                        pl.col(
                            "original_cltv"
                        )
                        != "999"
                    )
                )
                .sum()
                .alias(
                    "cltv_above_100"
                ),


                # -----------------------------------------
                # VANTAGESCORE 4.0
                # 9999 = Not Available
                # -----------------------------------------

                (
                    pl.col(
                        "vantagescore_4"
                    )
                    == "9999"
                )
                .sum()
                .alias(
                    "vantagescore_9999"
                ),

                to_number(
                    "vantagescore_4"
                )
                .filter(
                    pl.col(
                        "vantagescore_4"
                    )
                    != "9999"
                )
                .min()
                .alias(
                    "vantagescore_min"
                ),

                to_number(
                    "vantagescore_4"
                )
                .filter(
                    pl.col(
                        "vantagescore_4"
                    )
                    != "9999"
                )
                .max()
                .alias(
                    "vantagescore_max"
                ),

            )
            .collect()
            .to_dicts()[0]
        )

        stats["year"] = year

        records.append(
            stats
        )


    return (
        pl.DataFrame(
            records
        )
        .select(
            "year",
            pl.exclude("year"),
        )
        .sort(
            "year"
        )
    )


# =========================================================
# 2. XX BY VINTAGE + LOAN AGE
# =========================================================

def audit_xx_by_loan_age():

    tables = []

    for year in STUDY_YEARS:

        print(
            f"  XX by loan age {year}..."
        )

        table = (
            pl.scan_parquet(
                perf_parquet_path(year)
            )
            .filter(
                pl.col(
                    "delinquency_status"
                )
                == "XX"
            )
            .with_columns(
                pl.col(
                    "loan_age"
                )
                .cast(
                    pl.Int64,
                    strict=False,
                )
                .alias(
                    "loan_age_num"
                )
            )
            .group_by(
                "loan_age_num"
            )
            .len()
            .with_columns(
                pl.lit(
                    year
                )
                .alias(
                    "year"
                )
            )
            .collect()
        )

        if table.height > 0:

            tables.append(
                table
            )


    if not tables:

        return pl.DataFrame(
            schema={
                "year": pl.Int64,
                "loan_age_num": pl.Int64,
                "len": pl.UInt32,
            }
        )


    return (
        pl.concat(
            tables,
            how="vertical",
        )
        .select(
            "year",
            "loan_age_num",
            "len",
        )
        .sort(
            [
                "year",
                "loan_age_num",
            ]
        )
    )


# =========================================================
# 3. XX BY REPORTING PERIOD
# =========================================================

def audit_xx_by_reporting_period():

    tables = []

    for year in STUDY_YEARS:

        print(
            f"  XX by reporting period {year}..."
        )

        table = (
            pl.scan_parquet(
                perf_parquet_path(year)
            )
            .filter(
                pl.col(
                    "delinquency_status"
                )
                == "XX"
            )
            .group_by(
                "monthly_reporting_period"
            )
            .len()
            .with_columns(
                pl.lit(
                    year
                )
                .alias(
                    "year"
                )
            )
            .collect()
        )

        if table.height > 0:

            tables.append(
                table
            )


    if not tables:

        return pl.DataFrame(
            schema={
                "year": pl.Int64,
                "monthly_reporting_period": pl.String,
                "len": pl.UInt32,
            }
        )


    return (
        pl.concat(
            tables,
            how="vertical",
        )
        .select(
            "year",
            "monthly_reporting_period",
            "len",
        )
        .sort(
            [
                "year",
                "monthly_reporting_period",
            ]
        )
    )


# =========================================================
# 4. XX + ZERO BALANCE RELATIONSHIP
# =========================================================

def audit_xx_zero_balance():

    records = []

    for year in STUDY_YEARS:

        print(
            f"  XX / Zero Balance {year}..."
        )

        df = (
            pl.scan_parquet(
                perf_parquet_path(year)
            )
            .filter(
                pl.col(
                    "delinquency_status"
                )
                == "XX"
            )
        )


        stats = (
            df
            .select(

                pl.len()
                .alias(
                    "xx_rows"
                ),

                pl.col(
                    "zero_balance_code"
                )
                .is_not_null()
                .sum()
                .alias(
                    "xx_with_zero_balance"
                ),

                pl.col(
                    "zero_balance_code"
                )
                .is_null()
                .sum()
                .alias(
                    "xx_without_zero_balance"
                ),

            )
            .collect()
            .to_dicts()[0]
        )


        stats["year"] = year

        records.append(
            stats
        )


    result = (
        pl.DataFrame(
            records
        )
        .select(
            "year",
            pl.exclude("year"),
        )
        .sort(
            "year"
        )
    )


    result = (
        result
        .with_columns(

            pl.when(
                pl.col(
                    "xx_rows"
                )
                > 0
            )
            .then(
                (
                    pl.col(
                        "xx_with_zero_balance"
                    )
                    /
                    pl.col(
                        "xx_rows"
                    )
                    * 100
                )
            )
            .otherwise(
                None
            )
            .round(
                2
            )
            .alias(
                "pct_xx_with_zero_balance"
            )

        )
    )


    return result


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
        "FREDDIE MAC SPECIAL VALUE AUDIT"
    )

    print(
        "2016–2026"
    )

    print(
        "=" * 90
    )


    # =====================================================
    # 1. ORIGINATION SPECIAL VALUES
    # =====================================================

    print(
        "\n[1/4] Checking Origination special values..."
    )

    orig_special = (
        audit_origination_special_values()
    )


    # =====================================================
    # 2. XX BY LOAN AGE
    # =====================================================

    print(
        "\n[2/4] Checking XX by loan age..."
    )

    xx_age = (
        audit_xx_by_loan_age()
    )


    # =====================================================
    # 3. XX BY REPORTING PERIOD
    # =====================================================

    print(
        "\n[3/4] Checking XX by reporting period..."
    )

    xx_period = (
        audit_xx_by_reporting_period()
    )


    # =====================================================
    # 4. XX VS ZERO BALANCE
    # =====================================================

    print(
        "\n[4/4] Checking XX vs Zero Balance..."
    )

    xx_zero = (
        audit_xx_zero_balance()
    )


    # =====================================================
    # OUTPUT FILE PATHS
    # =====================================================

    orig_output = (
        TABLES_DIR
        / "audit_special_origination.csv"
    )

    xx_age_output = (
        TABLES_DIR
        / "audit_xx_by_loan_age.csv"
    )

    xx_period_output = (
        TABLES_DIR
        / "audit_xx_by_reporting_period.csv"
    )

    xx_zero_output = (
        TABLES_DIR
        / "audit_xx_zero_balance.csv"
    )


    # =====================================================
    # SAVE FILES
    # =====================================================

    orig_special.write_csv(
        orig_output
    )

    xx_age.write_csv(
        xx_age_output
    )

    xx_period.write_csv(
        xx_period_output
    )

    xx_zero.write_csv(
        xx_zero_output
    )


    # =====================================================
    # DISPLAY
    # =====================================================

    print(
        "\n"
        + "=" * 90
    )

    print(
        "ORIGINATION SPECIAL VALUES"
    )

    print(
        "=" * 90
    )

    print(
        orig_special
    )


    print(
        "\n"
        + "=" * 90
    )

    print(
        "XX BY LOAN AGE"
    )

    print(
        "=" * 90
    )

    print(
        xx_age
    )


    print(
        "\n"
        + "=" * 90
    )

    print(
        "XX / ZERO BALANCE"
    )

    print(
        "=" * 90
    )

    print(
        xx_zero
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
        orig_output
    )

    print(
        xx_age_output
    )

    print(
        xx_period_output
    )

    print(
        xx_zero_output
    )


    print(
        "\n"
        + "=" * 90
    )

    print(
        "✓ SPECIAL VALUE AUDIT HOÀN THÀNH"
    )

    print(
        "=" * 90
    )


if __name__ == "__main__":
    main()