from __future__ import annotations

from pathlib import Path

import polars as pl

from src.config import (
    MODEL_DIR,
    orig_parquet_path,
    perf_parquet_path,
)


# =========================================================
# HELPERS
# =========================================================

def _yyyymm_to_date(column: str) -> pl.Expr:
    """
    Convert YYYYMM string to a Date representing
    the first day of that month.
    """

    return (
        pl.concat_str(
            [
                pl.col(column),
                pl.lit("01"),
            ]
        )
        .str.strptime(
            pl.Date,
            "%Y%m%d",
            strict=False,
        )
    )


def _clean_not_available_numeric(
    raw_column: str,
    not_available_code: str,
    dtype: pl.DataType,
) -> pl.Expr:
    """
    Convert Freddie Mac special Not Available code
    to null, otherwise cast to numeric.
    """

    return (
        pl.when(
            pl.col(raw_column)
            == not_available_code
        )
        .then(None)
        .otherwise(
            pl.col(raw_column)
            .cast(
                dtype,
                strict=False,
            )
        )
    )


# =========================================================
# CLEAN ORIGINATION
# =========================================================

def clean_origination_year(
    year: int,
    force: bool = False,
) -> Path:

    year = int(year)

    input_file = (
        orig_parquet_path(year)
    )

    output_file = (
        MODEL_DIR
        / f"orig_clean_{year}.parquet"
    )

    temp_file = (
        MODEL_DIR
        / f"orig_clean_{year}.tmp.parquet"
    )

    MODEL_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    if not input_file.exists():

        raise FileNotFoundError(
            f"Không tìm thấy Origination input:\n"
            f"{input_file}"
        )

    if (
        output_file.exists()
        and not force
    ):

        print(
            f"✓ Origination clean {year} "
            f"đã tồn tại, bỏ qua."
        )

        return output_file

    temp_file.unlink(
        missing_ok=True
    )

    # =====================================================
    # LOAD + PRESERVE RAW SPECIAL-CODE COLUMNS
    # =====================================================

    df = (
        pl.scan_parquet(
            input_file
        )

        .rename(
            {
                "fico":
                    "fico_raw",

                "original_dti":
                    "original_dti_raw",

                "original_ltv":
                    "original_ltv_raw",

                "original_cltv":
                    "original_cltv_raw",

                "vantagescore_4":
                    "vantagescore_4_raw",

                "number_borrowers":
                    "number_borrowers_raw",

                "occupancy_status":
                    "occupancy_status_raw",

                "property_type":
                    "property_type_raw",

                "loan_purpose":
                    "loan_purpose_raw",
            }
        )

        # =================================================
        # FIRST CLEANING PASS
        # =================================================

        .with_columns(

            # =============================================
            # FICO
            # 9999 = Not Available
            # =============================================

            (
                pl.col(
                    "fico_raw"
                )
                == "9999"
            )
            .alias(
                "fico_not_available_flag"
            ),

            _clean_not_available_numeric(
                "fico_raw",
                "9999",
                pl.Int16,
            )
            .alias(
                "fico"
            ),


            # =============================================
            # DTI
            # 999 = Not Available
            # =============================================

            (
                pl.col(
                    "original_dti_raw"
                )
                == "999"
            )
            .alias(
                "dti_not_available_flag"
            ),

            _clean_not_available_numeric(
                "original_dti_raw",
                "999",
                pl.Float64,
            )
            .alias(
                "original_dti"
            ),


            # =============================================
            # ORIGINAL LTV
            # 999 = Not Available
            # =============================================

            (
                pl.col(
                    "original_ltv_raw"
                )
                == "999"
            )
            .alias(
                "ltv_not_available_flag"
            ),

            _clean_not_available_numeric(
                "original_ltv_raw",
                "999",
                pl.Float64,
            )
            .alias(
                "original_ltv"
            ),


            # =============================================
            # ORIGINAL CLTV
            # 999 = Not Available
            # =============================================

            (
                pl.col(
                    "original_cltv_raw"
                )
                == "999"
            )
            .alias(
                "cltv_not_available_flag"
            ),

            _clean_not_available_numeric(
                "original_cltv_raw",
                "999",
                pl.Float64,
            )
            .alias(
                "original_cltv"
            ),


            # =============================================
            # VANTAGESCORE 4.0
            # 9999 = Not Available
            # =============================================

            (
                pl.col(
                    "vantagescore_4_raw"
                )
                == "9999"
            )
            .alias(
                "vantagescore_not_available_flag"
            ),

            _clean_not_available_numeric(
                "vantagescore_4_raw",
                "9999",
                pl.Int16,
            )
            .alias(
                "vantagescore_4"
            ),


            # =============================================
            # NUMBER OF BORROWERS
            #
            # 99 = Not Available
            #
            # 2018Q1 and prior:
            #   1 = exactly 1 borrower
            #   2 = more than 1 borrower
            #
            # 2018Q2 and later:
            #   1, 2, 3... = exact borrower count
            # =============================================

            (
                pl.col(
                    "number_borrowers_raw"
                )
                == "99"
            )
            .alias(
                "number_borrowers_not_available_flag"
            ),

            # Loan ID example:
            # F16Q1xxxxxxx
            # position 4 = origination quarter
            pl.col(
                "loan_id"
            )
            .str.slice(
                4,
                1,
            )
            .cast(
                pl.Int8,
                strict=False,
            )
            .alias(
                "origination_quarter"
            ),


            # =============================================
            # OCCUPANCY STATUS
            # 9 = Not Available
            # =============================================

            pl.when(
                pl.col(
                    "occupancy_status_raw"
                )
                == "9"
            )
            .then(None)
            .otherwise(
                pl.col(
                    "occupancy_status_raw"
                )
            )
            .alias(
                "occupancy_status"
            ),


            # =============================================
            # PROPERTY TYPE
            # 99 = Not Available
            # =============================================

            pl.when(
                pl.col(
                    "property_type_raw"
                )
                == "99"
            )
            .then(None)
            .otherwise(
                pl.col(
                    "property_type_raw"
                )
            )
            .alias(
                "property_type"
            ),


            # =============================================
            # LOAN PURPOSE
            # 9 = Not Available
            # =============================================

            pl.when(
                pl.col(
                    "loan_purpose_raw"
                )
                == "9"
            )
            .then(None)
            .otherwise(
                pl.col(
                    "loan_purpose_raw"
                )
            )
            .alias(
                "loan_purpose"
            ),


            # =============================================
            # STANDARD NUMERIC VARIABLES
            # =============================================

            pl.col(
                "original_upb"
            )
            .cast(
                pl.Float64,
                strict=False,
            ),

            pl.col(
                "original_interest_rate"
            )
            .cast(
                pl.Float64,
                strict=False,
            ),

            pl.col(
                "original_loan_term"
            )
            .cast(
                pl.Int16,
                strict=False,
            ),

            pl.col(
                "vintage_year"
            )
            .cast(
                pl.Int16,
                strict=False,
            ),


            # =============================================
            # DATE VARIABLES
            # =============================================

            _yyyymm_to_date(
                "first_payment_date"
            )
            .alias(
                "first_payment_month"
            ),

            _yyyymm_to_date(
                "maturity_date"
            )
            .alias(
                "maturity_month"
            ),

        )


        # =================================================
        # SECOND CLEANING PASS
        # =================================================

        .with_columns(

            # =============================================
            # LTV / CLTV FLAGS
            # =============================================

            (
                pl.col(
                    "original_ltv"
                )
                .is_not_null()
                &
                (
                    pl.col(
                        "original_ltv"
                    )
                    > 100
                )
            )
            .alias(
                "ltv_above_100_flag"
            ),

            (
                pl.col(
                    "original_cltv"
                )
                .is_not_null()
                &
                (
                    pl.col(
                        "original_cltv"
                    )
                    > 100
                )
            )
            .alias(
                "cltv_above_100_flag"
            ),


            # =============================================
            # NUMBER OF BORROWERS DISCLOSURE REGIME
            # =============================================

            (
                (
                    pl.col(
                        "vintage_year"
                    )
                    < 2018
                )
                |
                (
                    (
                        pl.col(
                            "vintage_year"
                        )
                        == 2018
                    )
                    &
                    (
                        pl.col(
                            "origination_quarter"
                        )
                        <= 1
                    )
                )
            )
            .alias(
                "legacy_number_borrowers_encoding_flag"
            ),


            # =============================================
            # MULTIPLE BORROWERS FLAG
            #
            # Useful across both disclosure regimes.
            # =============================================

            pl.when(
                pl.col(
                    "number_borrowers_raw"
                )
                == "99"
            )
            .then(None)
            .otherwise(
                pl.col(
                    "number_borrowers_raw"
                )
                .cast(
                    pl.Int16,
                    strict=False,
                )
                >= 2
            )
            .alias(
                "multiple_borrowers_flag"
            ),


            # =============================================
            # EXACT NUMBER OF BORROWERS
            #
            # 2018Q1 and prior:
            #   raw 1 -> exact 1
            #   raw 2 -> only know ">1"
            #            therefore exact count = null
            #
            # 2018Q2 and later:
            #   raw value is exact borrower count.
            # =============================================

            pl.when(
                pl.col(
                    "number_borrowers_raw"
                )
                == "99"
            )
            .then(None)

            .when(
                (
                    pl.col(
                        "vintage_year"
                    )
                    < 2018
                )
                |
                (
                    (
                        pl.col(
                            "vintage_year"
                        )
                        == 2018
                    )
                    &
                    (
                        pl.col(
                            "origination_quarter"
                        )
                        <= 1
                    )
                )
            )
            .then(
                pl.when(
                    pl.col(
                        "number_borrowers_raw"
                    )
                    == "1"
                )
                .then(
                    pl.lit(
                        1,
                        dtype=pl.Int16,
                    )
                )
                .otherwise(
                    None
                )
            )

            .otherwise(
                pl.col(
                    "number_borrowers_raw"
                )
                .cast(
                    pl.Int16,
                    strict=False,
                )
            )
            .alias(
                "number_borrowers"
            ),

        )
    )


    # =====================================================
    # WRITE PARQUET
    # =====================================================

    df.sink_parquet(
        temp_file,
        compression="zstd",
    )

    temp_file.replace(
        output_file
    )

    return output_file


# =========================================================
# CLEAN PERFORMANCE
# =========================================================

def clean_performance_year(
    year: int,
    force: bool = False,
) -> Path:

    year = int(year)

    input_file = (
        perf_parquet_path(year)
    )

    output_file = (
        MODEL_DIR
        / f"perf_clean_{year}.parquet"
    )

    temp_file = (
        MODEL_DIR
        / f"perf_clean_{year}.tmp.parquet"
    )

    MODEL_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    if not input_file.exists():

        raise FileNotFoundError(
            f"Không tìm thấy Performance input:\n"
            f"{input_file}"
        )

    if (
        output_file.exists()
        and not force
    ):

        print(
            f"✓ Performance clean {year} "
            f"đã tồn tại, bỏ qua."
        )

        return output_file

    temp_file.unlink(
        missing_ok=True
    )


    # =====================================================
    # LOAD
    # =====================================================

    df = (
        pl.scan_parquet(
            input_file
        )

        .rename(
            {
                "delinquency_status":
                    "delinquency_status_raw",

                "estimated_ltv":
                    "estimated_ltv_raw",
            }
        )


        # =================================================
        # FIRST CLEANING PASS
        # =================================================

        .with_columns(

            # =============================================
            # REPORTING PERIOD
            # =============================================

            pl.col(
                "monthly_reporting_period"
            )
            .cast(
                pl.Int32,
                strict=False,
            )
            .alias(
                "reporting_period_num"
            ),

            _yyyymm_to_date(
                "monthly_reporting_period"
            )
            .alias(
                "reporting_month"
            ),


            # =============================================
            # LOAN AGE
            # =============================================

            pl.col(
                "loan_age"
            )
            .cast(
                pl.Int16,
                strict=False,
            ),

            pl.col(
                "remaining_months_maturity"
            )
            .cast(
                pl.Int16,
                strict=False,
            ),


            # =============================================
            # BALANCE / INTEREST RATE
            # =============================================

            pl.col(
                "current_actual_upb"
            )
            .cast(
                pl.Float64,
                strict=False,
            ),

            pl.col(
                "current_interest_rate"
            )
            .cast(
                pl.Float64,
                strict=False,
            ),

            pl.col(
                "current_interest_bearing_upb"
            )
            .cast(
                pl.Float64,
                strict=False,
            ),


            # =============================================
            # DELINQUENCY
            # =============================================

            pl.col(
                "delinquency_status_raw"
            )
            .cast(
                pl.Int16,
                strict=False,
            )
            .alias(
                "delinquency_num"
            ),

            (
                pl.col(
                    "delinquency_status_raw"
                )
                == "XX"
            )
            .alias(
                "is_xx"
            ),

            (
                pl.col(
                    "delinquency_status_raw"
                )
                == "RA"
            )
            .alias(
                "is_ra"
            ),


            # =============================================
            # ESTIMATED LTV
            # 999 = Not Available
            # =============================================

            (
                pl.col(
                    "estimated_ltv_raw"
                )
                == "999"
            )
            .alias(
                "estimated_ltv_not_available_flag"
            ),

            _clean_not_available_numeric(
                "estimated_ltv_raw",
                "999",
                pl.Float64,
            )
            .alias(
                "estimated_ltv"
            ),


            # =============================================
            # DATE VARIABLES
            # =============================================

            _yyyymm_to_date(
                "zero_balance_effective_date"
            )
            .alias(
                "zero_balance_effective_month"
            ),

            _yyyymm_to_date(
                "ddlpi"
            )
            .alias(
                "ddlpi_month"
            ),


            # =============================================
            # VINTAGE
            # =============================================

            pl.col(
                "vintage_year"
            )
            .cast(
                pl.Int16,
                strict=False,
            ),

        )


        # =================================================
        # SECOND PASS FLAGS
        # =================================================

        .with_columns(

            (
                pl.col(
                    "loan_age"
                )
                == 0
            )
            .alias(
                "is_loan_age_zero"
            ),


            # =============================================
            # ELTV STRUCTURAL PERIOD
            # =============================================

            (
                pl.col(
                    "reporting_period_num"
                )
                < 201704
            )
            .alias(
                "estimated_ltv_pre_201704_flag"
            ),


            # =============================================
            # ZERO BALANCE
            # =============================================

            pl.col(
                "zero_balance_code"
            )
            .is_not_null()
            .alias(
                "has_zero_balance_event"
            ),

        )
    )


    # =====================================================
    # WRITE PARQUET
    # =====================================================

    df.sink_parquet(
        temp_file,
        compression="zstd",
    )

    temp_file.replace(
        output_file
    )

    return output_file


# =========================================================
# VALIDATE CLEAN DATA
# =========================================================

def validate_clean_year(
    year: int,
) -> dict:

    year = int(year)


    orig_raw_file = (
        orig_parquet_path(year)
    )

    perf_raw_file = (
        perf_parquet_path(year)
    )


    orig_clean_file = (
        MODEL_DIR
        / f"orig_clean_{year}.parquet"
    )

    perf_clean_file = (
        MODEL_DIR
        / f"perf_clean_{year}.parquet"
    )


    if not orig_clean_file.exists():

        raise FileNotFoundError(
            f"Không tìm thấy:\n"
            f"{orig_clean_file}"
        )

    if not perf_clean_file.exists():

        raise FileNotFoundError(
            f"Không tìm thấy:\n"
            f"{perf_clean_file}"
        )


    orig_raw = (
        pl.scan_parquet(
            orig_raw_file
        )
    )

    perf_raw = (
        pl.scan_parquet(
            perf_raw_file
        )
    )

    orig_clean = (
        pl.scan_parquet(
            orig_clean_file
        )
    )

    perf_clean = (
        pl.scan_parquet(
            perf_clean_file
        )
    )


    # =====================================================
    # ROW COUNTS MUST NOT CHANGE
    # =====================================================

    raw_orig_rows = (
        orig_raw
        .select(
            pl.len()
            .alias(
                "rows"
            )
        )
        .collect()["rows"][0]
    )

    clean_orig_rows = (
        orig_clean
        .select(
            pl.len()
            .alias(
                "rows"
            )
        )
        .collect()["rows"][0]
    )

    raw_perf_rows = (
        perf_raw
        .select(
            pl.len()
            .alias(
                "rows"
            )
        )
        .collect()["rows"][0]
    )

    clean_perf_rows = (
        perf_clean
        .select(
            pl.len()
            .alias(
                "rows"
            )
        )
        .collect()["rows"][0]
    )


    if raw_orig_rows != clean_orig_rows:

        raise RuntimeError(
            f"{year}: Origination row count "
            f"thay đổi sau cleaning."
        )

    if raw_perf_rows != clean_perf_rows:

        raise RuntimeError(
            f"{year}: Performance row count "
            f"thay đổi sau cleaning."
        )


    # =====================================================
    # ORIGINATION CHECKS
    # =====================================================

    orig_checks = (
        orig_clean
        .select(

            (
                pl.col(
                    "fico_raw"
                )
                == "9999"
            )
            .sum()
            .alias(
                "fico_9999_raw"
            ),

            pl.col(
                "fico_not_available_flag"
            )
            .sum()
            .alias(
                "fico_flagged"
            ),


            (
                pl.col(
                    "original_dti_raw"
                )
                == "999"
            )
            .sum()
            .alias(
                "dti_999_raw"
            ),

            pl.col(
                "dti_not_available_flag"
            )
            .sum()
            .alias(
                "dti_flagged"
            ),


            (
                pl.col(
                    "original_ltv_raw"
                )
                == "999"
            )
            .sum()
            .alias(
                "ltv_999_raw"
            ),

            pl.col(
                "ltv_not_available_flag"
            )
            .sum()
            .alias(
                "ltv_flagged"
            ),


            (
                pl.col(
                    "original_cltv_raw"
                )
                == "999"
            )
            .sum()
            .alias(
                "cltv_999_raw"
            ),

            pl.col(
                "cltv_not_available_flag"
            )
            .sum()
            .alias(
                "cltv_flagged"
            ),


            (
                pl.col(
                    "number_borrowers_raw"
                )
                == "99"
            )
            .sum()
            .alias(
                "number_borrowers_99_raw"
            ),

            pl.col(
                "number_borrowers_not_available_flag"
            )
            .sum()
            .alias(
                "number_borrowers_flagged"
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
                "legacy_multi_incorrect_exact_count"
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
            )
            .sum()
            .alias(
                "legacy_multiple_borrower_rows"
            ),

        )
        .collect()
    )


    # =====================================================
    # PERFORMANCE CHECKS
    # =====================================================

    perf_checks = (
        perf_clean
        .select(

            (
                pl.col(
                    "delinquency_status_raw"
                )
                == "XX"
            )
            .sum()
            .alias(
                "xx_raw"
            ),

            pl.col(
                "is_xx"
            )
            .sum()
            .alias(
                "xx_flagged"
            ),


            (
                pl.col(
                    "delinquency_status_raw"
                )
                == "RA"
            )
            .sum()
            .alias(
                "ra_raw"
            ),

            pl.col(
                "is_ra"
            )
            .sum()
            .alias(
                "ra_flagged"
            ),


            (
                pl.col(
                    "estimated_ltv_raw"
                )
                == "999"
            )
            .sum()
            .alias(
                "eltv_999_raw"
            ),

            pl.col(
                "estimated_ltv_not_available_flag"
            )
            .sum()
            .alias(
                "eltv_flagged"
            ),

        )
        .collect()
    )


    # =====================================================
    # FLAG CONSISTENCY
    # =====================================================

    if (
        orig_checks[
            "fico_9999_raw"
        ][0]
        !=
        orig_checks[
            "fico_flagged"
        ][0]
    ):

        raise RuntimeError(
            f"{year}: FICO cleaning flag "
            f"không khớp."
        )


    if (
        orig_checks[
            "dti_999_raw"
        ][0]
        !=
        orig_checks[
            "dti_flagged"
        ][0]
    ):

        raise RuntimeError(
            f"{year}: DTI cleaning flag "
            f"không khớp."
        )


    if (
        orig_checks[
            "ltv_999_raw"
        ][0]
        !=
        orig_checks[
            "ltv_flagged"
        ][0]
    ):

        raise RuntimeError(
            f"{year}: LTV cleaning flag "
            f"không khớp."
        )


    if (
        orig_checks[
            "cltv_999_raw"
        ][0]
        !=
        orig_checks[
            "cltv_flagged"
        ][0]
    ):

        raise RuntimeError(
            f"{year}: CLTV cleaning flag "
            f"không khớp."
        )


    if (
        orig_checks[
            "number_borrowers_99_raw"
        ][0]
        !=
        orig_checks[
            "number_borrowers_flagged"
        ][0]
    ):

        raise RuntimeError(
            f"{year}: Number of Borrowers "
            f"Not Available flag không khớp."
        )


    if (
        orig_checks[
            "legacy_multi_incorrect_exact_count"
        ][0]
        != 0
    ):

        raise RuntimeError(
            f"{year}: Có borrower count cũ "
            f"được hiểu sai thành số chính xác."
        )


    if (
        perf_checks[
            "xx_raw"
        ][0]
        !=
        perf_checks[
            "xx_flagged"
        ][0]
    ):

        raise RuntimeError(
            f"{year}: XX cleaning flag "
            f"không khớp."
        )


    if (
        perf_checks[
            "ra_raw"
        ][0]
        !=
        perf_checks[
            "ra_flagged"
        ][0]
    ):

        raise RuntimeError(
            f"{year}: RA cleaning flag "
            f"không khớp."
        )


    if (
        perf_checks[
            "eltv_999_raw"
        ][0]
        !=
        perf_checks[
            "eltv_flagged"
        ][0]
    ):

        raise RuntimeError(
            f"{year}: Estimated LTV flag "
            f"không khớp."
        )


    # =====================================================
    # RESULT
    # =====================================================

    result = {

        "year":
            year,

        "orig_rows":
            clean_orig_rows,

        "perf_rows":
            clean_perf_rows,

        "fico_not_available":
            orig_checks[
                "fico_flagged"
            ][0],

        "dti_not_available":
            orig_checks[
                "dti_flagged"
            ][0],

        "ltv_not_available":
            orig_checks[
                "ltv_flagged"
            ][0],

        "cltv_not_available":
            orig_checks[
                "cltv_flagged"
            ][0],

        "number_borrowers_not_available":
            orig_checks[
                "number_borrowers_flagged"
            ][0],

        "legacy_multiple_borrower_rows":
            orig_checks[
                "legacy_multiple_borrower_rows"
            ][0],

        "xx_rows":
            perf_checks[
                "xx_flagged"
            ][0],

        "ra_rows":
            perf_checks[
                "ra_flagged"
            ][0],

        "estimated_ltv_not_available":
            perf_checks[
                "eltv_flagged"
            ][0],

        "status":
            "PASS",
    }


    # =====================================================
    # REPORT
    # =====================================================

    print(
        "\n"
        + "=" * 70
    )

    print(
        f"CLEAN DATA VALIDATION - {year}"
    )

    print(
        "=" * 70
    )


    print(
        f"Origination rows: "
        f"{clean_orig_rows:,}"
    )

    print(
        f"Performance rows: "
        f"{clean_perf_rows:,}"
    )


    print(
        f"FICO 9999 -> null: "
        f"{result['fico_not_available']:,}"
    )

    print(
        f"DTI 999 -> null: "
        f"{result['dti_not_available']:,}"
    )

    print(
        f"LTV 999 -> null: "
        f"{result['ltv_not_available']:,}"
    )

    print(
        f"CLTV 999 -> null: "
        f"{result['cltv_not_available']:,}"
    )

    print(
        f"Number Borrowers 99 -> null: "
        f"{result['number_borrowers_not_available']:,}"
    )

    print(
        f"Legacy '>1 borrower' rows kept "
        f"without fake exact count: "
        f"{result['legacy_multiple_borrower_rows']:,}"
    )


    print(
        f"XX flagged: "
        f"{result['xx_rows']:,}"
    )

    print(
        f"RA flagged: "
        f"{result['ra_rows']:,}"
    )

    print(
        f"Estimated LTV 999 -> null: "
        f"{result['estimated_ltv_not_available']:,}"
    )


    print(
        "\n✓ CLEAN VALIDATION PASS"
    )

    print(
        "=" * 70
    )


    return result


# =========================================================
# CLEAN ONE COMPLETE VINTAGE
# =========================================================

def clean_sample_year(
    year: int,
    force: bool = False,
) -> dict:

    year = int(year)


    print(
        "\n"
        + "=" * 70
    )

    print(
        f"CLEAN FREDDIE MAC SAMPLE - {year}"
    )

    print(
        "=" * 70
    )


    # =====================================================
    # ORIGINATION
    # =====================================================

    print(
        "\n[1/3] Cleaning Origination..."
    )

    orig_output = (
        clean_origination_year(
            year,
            force=force,
        )
    )

    print(
        f"✓ {orig_output.name}"
    )


    # =====================================================
    # PERFORMANCE
    # =====================================================

    print(
        "\n[2/3] Cleaning Performance..."
    )

    perf_output = (
        clean_performance_year(
            year,
            force=force,
        )
    )

    print(
        f"✓ {perf_output.name}"
    )


    # =====================================================
    # VALIDATION
    # =====================================================

    print(
        "\n[3/3] Validating clean data..."
    )

    result = (
        validate_clean_year(
            year
        )
    )


    print(
        "\n"
        + "=" * 70
    )

    print(
        f"✓ CLEANING {year} HOÀN TẤT"
    )

    print(
        "=" * 70
    )


    return result
# =========================================================
# XUẤT HAI BẢNG CHUẨN HÓA THEO PCCV
# Chưa tạo event, chưa ghép loan-month model input.
# =========================================================

def export_standardized_tables():
    import json
    from collections import Counter
    from datetime import datetime

    import pandas as pd
    import pyarrow.parquet as pq

    from src.config import (
        PROJECT_ROOT,
        PROCESSED_DIR,
        STUDY_YEARS,
        ensure_directories,
    )

    cutoff = pd.Timestamp("2026-03-31")
    reports = PROJECT_ROOT / "reports"
    ensure_directories()
    reports.mkdir(parents=True, exist_ok=True)

    # 1. Kiểm tra đủ Parquet đầu vào trước khi làm sạch.
    inputs = [
        path
        for year in STUDY_YEARS
        for path in [orig_parquet_path(year), perf_parquet_path(year)]
    ]
    missing = [str(path) for path in inputs if not path.exists()]

    if missing:
        raise FileNotFoundError(
            "Thiếu Parquet đầu vào. Chạy scripts/process_all.py trước:\n"
            + "\n".join(missing)
        )

    # 2. Dùng lại cleaning và validation hiện có của nhóm.
    orig_files, perf_files = [], []

    for year in STUDY_YEARS:
        clean_sample_year(year, force=True)
        orig_files.append(MODEL_DIR / f"orig_clean_{year}.parquet")
        perf_files.append(MODEL_DIR / f"perf_clean_{year}.parquet")

    def scan_files(paths):
        frame = pl.scan_parquet([str(path) for path in paths])

        # Chuẩn hóa chuỗi, giữ nguyên các cột *_raw để đối chiếu.
        text_columns = [
            name
            for name, dtype in frame.collect_schema().items()
            if dtype == pl.String and not name.endswith("_raw")
        ]
        return frame.with_columns([
            pl.col(name).str.strip_chars().replace("", None)
            for name in text_columns
        ])

    def numeric_raw(name, missing_code, dtype):
        # Chuyển mã thiếu thành null; giá trị sai định dạng sẽ báo lỗi.
        text = pl.col(name).cast(pl.String).str.strip_chars()
        return (
            pl.when(text.is_in(["", missing_code]))
            .then(None)
            .otherwise(text)
            .cast(dtype, strict=True)
        )

    def month_date(name):
        # YYYYMM -> ngày đầu tháng, không phải ngày sự kiện chính xác.
        return pl.concat_str([
            pl.col(name), pl.lit("01")
        ]).str.strptime(pl.Date, "%Y%m%d", strict=True)

    # 3. Hoàn thiện bảng Origination.
    score = numeric_raw("fico_raw", "9999", pl.Int16)
    dti = numeric_raw("original_dti_raw", "999", pl.Float64)

    orig = (
        scan_files(orig_files)
        .with_columns(
            pl.col("first_payment_date").alias("first_payment_date_raw"),
            pl.col("maturity_date").alias("maturity_date_raw"),

            # Mã missing và ngoài miền hợp lệ -> null, không impute.
            pl.when(score.is_between(300, 850))
            .then(score).otherwise(None).alias("fico"),

            pl.when(dti.is_between(0, 65))
            .then(dti).otherwise(None).alias("original_dti"),

            (score.is_not_null() & ~score.is_between(300, 850))
            .fill_null(False).alias("qc_credit_score_out_of_range"),

            (dti.is_not_null() & ~dti.is_between(0, 65))
            .fill_null(False).alias("qc_dti_out_of_range"),

            month_date("first_payment_date").alias("first_payment_date"),
            month_date("maturity_date").alias("maturity_date"),
        )
        .with_columns(
            # Giữ tên fico cho tương thích, thêm tên chuẩn credit_score.
            pl.col("fico").alias("credit_score"),
            pl.col("first_payment_date").alias("first_payment_month"),
            pl.col("maturity_date").alias("maturity_month"),
            pl.col("vintage_year").alias("origination_vintage"),

            # Operational definition đã khóa trong Project Specification.
            pl.col("first_payment_date").dt.offset_by("-1mo")
            .alias("operational_origination_date"),
        )
        .with_columns(
            pl.col("operational_origination_date").dt.year()
            .alias("operational_origination_year"),

            # Chỉ ghi cờ khác biệt, không tự đổi vintage nguồn.
            (
                pl.col("operational_origination_date").dt.year()
                != pl.col("origination_vintage")
            ).fill_null(False).alias("qc_proxy_year_differs_from_vintage"),

            (pl.col("original_upb") <= 0)
            .fill_null(False).alias("qc_original_upb_nonpositive"),

            (pl.col("original_loan_term") <= 0)
            .fill_null(False).alias("qc_original_term_nonpositive"),
        )
        .sort("loan_id")
    )

    # 4. Hoàn thiện bảng Performance.
    perf = (
        scan_files(perf_files)
        .with_columns(
            pl.col("zero_balance_effective_date")
            .alias("zero_balance_effective_date_raw"),

            month_date("monthly_reporting_period")
            .alias("performance_month"),

            month_date("zero_balance_effective_date")
            .alias("zero_balance_effective_date"),

            # Không dùng Freddie Loan Age thay analysis_time.
            pl.col("loan_age").alias("freddie_loan_age"),

            pl.col("delinquency_status_raw").str.strip_chars()
            .replace("", None).alias("current_delinquency_status"),

            (pl.col("current_actual_upb") < 0)
            .fill_null(False).alias("qc_current_upb_negative"),
        )
    )

    # Tháng báo cáo thiếu phải được xem lại, không âm thầm lọc bỏ.
    missing_months = perf.select(
        pl.col("performance_month").is_null().sum()
    ).collect().item()

    if missing_months:
        raise ValueError(f"Có {missing_months} dòng thiếu performance_month.")

    perf_before = sum(
        pq.ParquetFile(path).metadata.num_rows for path in perf_files
    )
    orig_before = sum(
        pq.ParquetFile(path).metadata.num_rows for path in orig_files
    )

    perf = (
        perf.filter(
            pl.col("performance_month") <= pl.lit(cutoff.date())
        )
        .sort(["loan_id", "performance_month"])
    )

    # 5. Ghi file tạm. Chỉ công bố file chính thức sau khi QC thành công.
    orig_temp = PROCESSED_DIR / "origination.partial.parquet"
    perf_temp = PROCESSED_DIR / "performance.partial.parquet"

    print("Đang xuất Origination...", flush=True)
    orig.sink_parquet(orig_temp, compression="zstd")

    print("Đang sắp xếp và xuất Performance...", flush=True)
    perf.sink_parquet(perf_temp, compression="zstd")

    def check_file(path, keys, allowed_ids=None):
        """Kiểm tra theo batch, gồm cả khóa trùng qua biên batch."""
        rows = 0
        previous_key = None
        missing_counts = Counter()
        flags = Counter()

        for batch in pq.ParquetFile(path).iter_batches(batch_size=100000):
            df = batch.to_pandas()

            if df[keys].isna().any().any():
                raise ValueError(f"{path.name}: có khóa bị thiếu.")

            index = pd.MultiIndex.from_frame(df[keys])
            first_key = tuple(df[keys].iloc[0])
            last_key = tuple(df[keys].iloc[-1])

            if index.has_duplicates:
                raise ValueError(f"{path.name}: có khóa trùng trong batch.")

            if previous_key is not None and first_key == previous_key:
                raise ValueError(f"{path.name}: khóa trùng qua biên batch.")

            if not index.is_monotonic_increasing:
                raise ValueError(f"{path.name}: chưa sắp xếp đúng.")

            if previous_key is not None and first_key < previous_key:
                raise ValueError(f"{path.name}: thứ tự sai qua biên batch.")

            if allowed_ids is not None:
                if not df["loan_id"].isin(allowed_ids).all():
                    raise ValueError("Performance có ID ngoài Origination.")

                months = pd.to_datetime(df["performance_month"])
                if months.gt(cutoff).any():
                    raise ValueError("Có tháng báo cáo sau cutoff.")

            rows += len(df)
            previous_key = last_key
            missing_counts.update({
                name: int(count)
                for name, count in df.isna().sum().items()
            })
            flags.update({
                name: int(df[name].fillna(False).sum())
                for name in df.columns if name.startswith("qc_")
            })

        if rows == 0:
            raise ValueError(f"{path.name}: bảng kết quả rỗng.")

        return {
            "rows": rows,
            "missing_keys": 0,
            "duplicate_keys": 0,
            "order_violations": 0,
            "null_counts": dict(missing_counts),
            "review_flags": dict(flags),
        }

    # 6. QC hai bảng, không tự drop_duplicates.
    orig_check = check_file(orig_temp, ["loan_id"])

    # Chỉ giữ tập ID trong RAM; không nạp cả bảng performance.
    loan_ids = set(
        pq.read_table(orig_temp, columns=["loan_id"])
        .column("loan_id").to_pylist()
    )
    perf_check = check_file(
        perf_temp, ["loan_id", "performance_month"], loan_ids
    )

    if orig_check["rows"] != orig_before:
        raise ValueError("Số dòng Origination thay đổi ngoài dự kiến.")

    perf_check["rows_before_cutoff"] = perf_before
    perf_check["rows_removed_after_cutoff"] = (
        perf_before - perf_check["rows"]
    )
    perf_check["performance_ids_not_in_origination"] = 0
    perf_check["rows_after_cutoff"] = 0

    # 7. Xuất schema, số null và kết quả QC.
    report = {
        "run_time": datetime.now().isoformat(timespec="seconds"),
        "source_years": list(STUDY_YEARS),
        "cutoff": cutoff.date().isoformat(),
        "analytical_cohort_filter_applied": False,
        "origination": orig_check,
        "performance": perf_check,
    }

    lines = [
        "# Báo cáo chuẩn hóa Origination và Performance",
        "",
        "Phạm vi: chuẩn hóa nguồn; chưa lọc cohort mô hình, "
        "chưa gán event và chưa ghép panel.",
        "",
        f"Origination: {orig_check['rows']:,} dòng.",
        f"Performance: {perf_check['rows']:,} dòng.",
        f"Loại sau cutoff: "
        f"{perf_check['rows_removed_after_cutoff']:,} dòng.",
        "",
        "Kiểm tra khóa, thứ tự và coverage đã qua. "
        "Các cờ qc_ vẫn cần xem xét; không đồng nghĩa "
        "toàn bộ model-input QC đã hoàn tất.",
        "",
        "Lãi suất/LTV/DTI giữ đơn vị phần trăm của nguồn; "
        "UPB là USD; kỳ hạn và tuổi báo cáo là tháng.",
        "Ngày đầu tháng biểu diễn tháng dữ liệu. "
        "Không điền mean/median và không loại complete-case ở bước này.",
    ]

    for name, path, result in [
        ("Origination", orig_temp, orig_check),
        ("Performance", perf_temp, perf_check),
    ]:
        lines += [
            "", f"## {name}", "",
            f"Cờ cần xem lại: `{result['review_flags']}`",
            "", "| Biến | Kiểu dữ liệu | Số null |",
            "|---|---|---:|",
        ]
        for field in pq.ParquetFile(path).schema_arrow:
            lines.append(
                f"| {field.name} | {field.type} | "
                f"{result['null_counts'].get(field.name, 0):,} |"
            )

    # Giữ các file theo năm cho script cũ; thêm hai file bàn giao tổng hợp.
    orig_temp.replace(PROCESSED_DIR / "origination.parquet")
    perf_temp.replace(PROCESSED_DIR / "performance.parquet")

    (reports / "standardization_validation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (reports / "standardization_report.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )

    print("Hoàn thành hai bảng chuẩn hóa. Xem reports/standardization_report.md")


if __name__ == "__main__":
    export_standardized_tables()