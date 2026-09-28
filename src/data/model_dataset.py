from __future__ import annotations

from pathlib import Path

import polars as pl

from src.config import MODEL_DIR


# =========================================================
# BUILD MODEL DATASET
# =========================================================


def build_model_dataset(
    orig: pl.LazyFrame,
    survival: pl.LazyFrame,
) -> pl.LazyFrame:
    """
    Build the loan-level survival model dataset.

    Population
    ----------
    Only loans with:
        survival_eligible == True

    Primary covariates
    ------------------
    - FICO
    - Original LTV
    - Original DTI
    - Original Interest Rate
    - Original Loan Term
    - Vintage Year

    Missing values are NOT imputed here.

    Instead, core_covariates_complete_flag identifies loans
    with all primary Cox covariates available.
    """

    # =====================================================
    # ORIGINATION COVARIATES
    # =====================================================

    orig_features = (
        orig

        .select(
            [
                "loan_id",

                # -----------------------------------------
                # Primary model covariates
                # -----------------------------------------

                "fico",
                "original_ltv",
                "original_dti",
                "original_interest_rate",
                "original_loan_term",

                # -----------------------------------------
                # Additional numeric controls
                # -----------------------------------------

                "original_cltv",
                "original_upb",

                # -----------------------------------------
                # Borrower / property controls
                # -----------------------------------------

                "occupancy_status",
                "property_type",
                "loan_purpose",
                "property_state",

                "number_borrowers",
                "multiple_borrowers_flag",

                # -----------------------------------------
                # Missingness / audit flags
                # -----------------------------------------

                "fico_not_available_flag",
                "dti_not_available_flag",
                "ltv_not_available_flag",
                "cltv_not_available_flag",

                "number_borrowers_not_available_flag",
                "legacy_number_borrowers_encoding_flag",

                "ltv_above_100_flag",
                "cltv_above_100_flag",

                "origination_quarter",
            ]
        )
    )


    # =====================================================
    # SURVIVAL-ELIGIBLE POPULATION
    # =====================================================

    survival_eligible = (
        survival

        .filter(
            pl.col(
                "survival_eligible"
            )
        )
    )


    # =====================================================
    # JOIN
    # =====================================================

    result = (
        survival_eligible

        .join(
            orig_features,
            on="loan_id",
            how="left",
        )
    )


    # =====================================================
    # CORE COVARIATE COMPLETENESS
    # =====================================================

    result = (
        result

        .with_columns(

            (
                pl.col("fico")
                .is_not_null()

                &

                pl.col("original_ltv")
                .is_not_null()

                &

                pl.col("original_dti")
                .is_not_null()

                &

                pl.col("original_interest_rate")
                .is_not_null()

                &

                pl.col("original_loan_term")
                .is_not_null()
            )
            .alias(
                "core_covariates_complete_flag"
            )

        )
    )


    # =====================================================
    # MODEL EVENT CODING
    # =====================================================

    result = (
        result

        .with_columns(

            # ---------------------------------------------
            # Kaplan-Meier / cause-specific Cox for default
            #
            # 1 = Default
            # 0 = everything else censored
            # ---------------------------------------------

            (
                pl.col("event_type")
                == "DEFAULT"
            )
            .cast(pl.Int8)
            .alias(
                "km_default_event"
            ),


            # ---------------------------------------------
            # Cause-specific Cox for prepayment
            #
            # 1 = Prepayment
            # 0 = everything else censored
            # ---------------------------------------------

            (
                pl.col("event_type")
                == "PREPAYMENT"
            )
            .cast(pl.Int8)
            .alias(
                "km_prepayment_event"
            ),


            # ---------------------------------------------
            # Competing risks:
            #
            # 0 = Censor
            # 1 = Default
            # 2 = Prepayment
            # ---------------------------------------------

            pl.col(
                "competing_event_code"
            )
            .cast(pl.Int8)
            .alias(
                "cr_event_code"
            ),

        )
    )


    # =====================================================
    # OUTPUT
    # =====================================================

    return (
        result

        .select(
            [
                # =========================================
                # ID / VINTAGE
                # =========================================

                "loan_id",
                "vintage_year",
                "origination_quarter",

                # =========================================
                # SURVIVAL TIME
                # =========================================

                "first_payment_month",

                "event_month",
                "event_date",

                "duration_months",

                # =========================================
                # FINAL EVENT
                # =========================================

                "event_type",
                "event_code",
                "event_source",

                "default_event",
                "prepayment_event",

                "km_default_event",
                "km_prepayment_event",

                "competing_event_code",
                "cr_event_code",

                # =========================================
                # PRIMARY MODEL COVARIATES
                # =========================================

                "fico",
                "original_ltv",
                "original_dti",
                "original_interest_rate",
                "original_loan_term",

                # =========================================
                # ADDITIONAL CONTROLS
                # =========================================

                "original_cltv",
                "original_upb",

                "occupancy_status",
                "property_type",
                "loan_purpose",
                "property_state",

                "number_borrowers",
                "multiple_borrowers_flag",

                # =========================================
                # DATA QUALITY FLAGS
                # =========================================

                "core_covariates_complete_flag",

                "fico_not_available_flag",
                "dti_not_available_flag",
                "ltv_not_available_flag",
                "cltv_not_available_flag",

                "number_borrowers_not_available_flag",
                "legacy_number_borrowers_encoding_flag",

                "ltv_above_100_flag",
                "cltv_above_100_flag",

                # =========================================
                # EVENT AUDIT
                # =========================================

                "same_month_default_prepay_flag",
                "raw_zero_balance_code",
                "last_observed_month",

                "first_default_month",
                "default_source",

                "first_prepay_month",
                "first_maturity_month",

                "first_admin_termination_month",
                "admin_source",
            ]
        )

        .sort(
            "loan_id"
        )
    )


# =========================================================
# BUILD ONE YEAR
# =========================================================


def build_model_dataset_year(
    year: int,
    force: bool = False,
) -> Path:

    year = int(year)


    orig_path = (
        MODEL_DIR
        / f"orig_clean_{year}.parquet"
    )

    survival_path = (
        MODEL_DIR
        / f"survival_duration_{year}.parquet"
    )

    output_path = (
        MODEL_DIR
        / f"model_dataset_{year}.parquet"
    )

    temp_path = (
        MODEL_DIR
        / f"model_dataset_{year}.tmp.parquet"
    )


    if not orig_path.exists():

        raise FileNotFoundError(
            f"Không tìm thấy:\n{orig_path}"
        )


    if not survival_path.exists():

        raise FileNotFoundError(
            f"Không tìm thấy:\n{survival_path}"
        )


    if output_path.exists() and not force:

        print(
            f"✓ model_dataset_{year}.parquet "
            f"đã tồn tại, bỏ qua."
        )

        return output_path


    temp_path.unlink(
        missing_ok=True
    )


    orig = (
        pl.scan_parquet(
            orig_path
        )
    )

    survival = (
        pl.scan_parquet(
            survival_path
        )
    )


    model_data = (
        build_model_dataset(
            orig,
            survival,
        )
    )


    model_data.sink_parquet(
        temp_path,
        compression="zstd",
    )


    temp_path.replace(
        output_path
    )


    return output_path


# =========================================================
# VALIDATE ONE YEAR
# =========================================================


def validate_model_dataset_year(
    year: int,
) -> dict:

    year = int(year)


    survival_path = (
        MODEL_DIR
        / f"survival_duration_{year}.parquet"
    )

    model_path = (
        MODEL_DIR
        / f"model_dataset_{year}.parquet"
    )


    survival = (
        pl.scan_parquet(
            survival_path
        )
    )

    model = (
        pl.scan_parquet(
            model_path
        )
    )


    # =====================================================
    # EXPECTED ELIGIBLE POPULATION
    # =====================================================

    expected_eligible = (
        survival

        .filter(
            pl.col(
                "survival_eligible"
            )
        )

        .select(
            pl.len()
            .alias("n")
        )

        .collect()["n"][0]
    )


    # =====================================================
    # MODEL ROWS
    # =====================================================

    rows = (
        model

        .select(
            pl.len()
            .alias("n")
        )

        .collect()["n"][0]
    )


    unique_loans = (
        model

        .select(
            pl.col(
                "loan_id"
            )
            .n_unique()
            .alias("n")
        )

        .collect()["n"][0]
    )


    # =====================================================
    # INVALID SURVIVAL TIME
    # =====================================================

    invalid_duration = (
        model

        .filter(
            pl.col(
                "duration_months"
            )
            <= 0
        )

        .select(
            pl.len()
            .alias("n")
        )

        .collect()["n"][0]
    )


    # =====================================================
    # MISSING PRIMARY COVARIATES
    # =====================================================

    missing_fico = (
        model

        .filter(
            pl.col("fico")
            .is_null()
        )

        .select(
            pl.len()
            .alias("n")
        )

        .collect()["n"][0]
    )


    missing_ltv = (
        model

        .filter(
            pl.col("original_ltv")
            .is_null()
        )

        .select(
            pl.len()
            .alias("n")
        )

        .collect()["n"][0]
    )


    missing_dti = (
        model

        .filter(
            pl.col("original_dti")
            .is_null()
        )

        .select(
            pl.len()
            .alias("n")
        )

        .collect()["n"][0]
    )


    missing_rate = (
        model

        .filter(
            pl.col("original_interest_rate")
            .is_null()
        )

        .select(
            pl.len()
            .alias("n")
        )

        .collect()["n"][0]
    )


    missing_term = (
        model

        .filter(
            pl.col("original_loan_term")
            .is_null()
        )

        .select(
            pl.len()
            .alias("n")
        )

        .collect()["n"][0]
    )


    # =====================================================
    # COMPLETE CASE COUNT
    # =====================================================

    complete_case = (
        model

        .filter(
            pl.col(
                "core_covariates_complete_flag"
            )
        )

        .select(
            pl.len()
            .alias("n")
        )

        .collect()["n"][0]
    )


    # =====================================================
    # EVENT COUNTS
    # =====================================================

    event_counts = (
        model

        .group_by(
            "event_type"
        )

        .len()

        .collect()
    )


    count_dict = {
        row["event_type"]: row["len"]
        for row in event_counts.iter_rows(
            named=True
        )
    }


    # =====================================================
    # VALIDATION
    # =====================================================

    if rows != expected_eligible:

        raise RuntimeError(
            f"{year}: Model rows không bằng "
            f"survival eligible."
        )


    if rows != unique_loans:

        raise RuntimeError(
            f"{year}: Model dataset "
            f"không unique theo loan_id."
        )


    if invalid_duration != 0:

        raise RuntimeError(
            f"{year}: Có duration_months <= 0."
        )


    # =====================================================
    # RESULT
    # =====================================================

    result = {

        "year":
            year,

        "rows":
            int(rows),

        "complete_case":
            int(complete_case),

        "missing_fico":
            int(missing_fico),

        "missing_ltv":
            int(missing_ltv),

        "missing_dti":
            int(missing_dti),

        "missing_rate":
            int(missing_rate),

        "missing_term":
            int(missing_term),

        "default":
            int(
                count_dict.get(
                    "DEFAULT",
                    0,
                )
            ),

        "prepayment":
            int(
                count_dict.get(
                    "PREPAYMENT",
                    0,
                )
            ),

        "censor":
            int(
                count_dict.get(
                    "CENSOR",
                    0,
                )
            ),

        "status":
            "PASS",
    }


    print(
        "\n"
        + "=" * 70
    )

    print(
        f"MODEL DATASET VALIDATION - {year}"
    )

    print(
        "=" * 70
    )

    print(
        f"Rows:                    "
        f"{result['rows']:,}"
    )

    print(
        f"Complete core cases:     "
        f"{result['complete_case']:,}"
    )

    print(
        f"Missing FICO:            "
        f"{result['missing_fico']:,}"
    )

    print(
        f"Missing LTV:             "
        f"{result['missing_ltv']:,}"
    )

    print(
        f"Missing DTI:             "
        f"{result['missing_dti']:,}"
    )

    print(
        f"Missing Interest Rate:   "
        f"{result['missing_rate']:,}"
    )

    print(
        f"Missing Loan Term:       "
        f"{result['missing_term']:,}"
    )

    print(
        f"DEFAULT:                 "
        f"{result['default']:,}"
    )

    print(
        f"PREPAYMENT:              "
        f"{result['prepayment']:,}"
    )

    print(
        f"CENSOR:                  "
        f"{result['censor']:,}"
    )

    print(
        "\n✓ MODEL DATASET VALIDATION PASS"
    )

    print(
        "=" * 70
    )


    return result