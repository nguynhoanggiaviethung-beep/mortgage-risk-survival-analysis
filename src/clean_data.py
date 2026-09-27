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