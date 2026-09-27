from __future__ import annotations

from pathlib import Path

import polars as pl

from src.config import MODEL_DIR


# =========================================================
# HELPERS
# =========================================================


def _date_month_index(
    column: str,
) -> pl.Expr:
    """
    Convert a Polars Date column to continuous month index.
    """

    return (
        pl.col(column).dt.year() * 12
        + pl.col(column).dt.month()
    )


def _yyyymm_month_index(
    column: str,
) -> pl.Expr:
    """
    Convert YYYYMM integer column to continuous month index.
    """

    return (
        (pl.col(column) // 100) * 12
        + (pl.col(column) % 100)
    )


# =========================================================
# BUILD LOAN-LEVEL SURVIVAL DURATION
# =========================================================


def build_survival_duration(
    event_map: pl.LazyFrame,
) -> pl.LazyFrame:
    """
    Build one loan-level survival-duration record per loan.

    Time origin
    -----------
    Original First Payment Month.

    Duration
    --------
    duration_months =
        event_month - first_payment_month + 1

    Eligibility
    -----------
    event_month < first_payment_month:
        survival_eligible = False

    event_month >= first_payment_month:
        survival_eligible = True

    IMPORTANT
    ---------
    Loans that terminate before First Payment Month are retained
    for audit but excluded from the survival risk set.

    Event at First Payment Month has duration = 1.
    """

    result = (
        event_map

        # =================================================
        # MONTH INDICES
        # =================================================

        .with_columns(

            _date_month_index(
                "first_payment_month"
            )
            .alias(
                "_first_payment_index"
            ),

            _yyyymm_month_index(
                "event_month"
            )
            .alias(
                "_event_index"
            ),

        )

        # =================================================
        # RAW DURATION
        # =================================================

        .with_columns(

            (
                pl.col("_event_index")
                - pl.col("_first_payment_index")
                + 1
            )
            .cast(pl.Int32)
            .alias(
                "raw_duration_months"
            )

        )

        # =================================================
        # RISK-SET ENTRY
        # =================================================

        .with_columns(

            (
                pl.col("event_month")
                >=
                (
                    pl.col("first_payment_month")
                    .dt.year() * 100
                    +
                    pl.col("first_payment_month")
                    .dt.month()
                )
            )
            .alias(
                "survival_eligible"
            )

        )

        # =================================================
        # FINAL DURATION
        #
        # Do NOT clamp pre-entry events to 1.
        # They are outside the survival risk set.
        # =================================================

        .with_columns(

            pl.when(
                pl.col("survival_eligible")
            )
            .then(
                pl.col("raw_duration_months")
            )
            .otherwise(
                None
            )
            .cast(pl.Int32)
            .alias(
                "duration_months"
            ),

            pl.when(
                pl.col("survival_eligible")
            )
            .then(
                pl.lit(None, dtype=pl.String)
            )
            .otherwise(
                pl.lit(
                    "EVENT_BEFORE_FIRST_PAYMENT"
                )
            )
            .alias(
                "survival_exclusion_reason"
            ),

        )

        # =================================================
        # MODEL-SPECIFIC EVENT FLAGS
        # =================================================

        .with_columns(

            # Cause-specific Default Cox:
            # Prepayment and other censoring are censored.
            (
                pl.col("event_type")
                == "DEFAULT"
            )
            .cast(pl.Int8)
            .alias(
                "default_event"
            ),

            # Cause-specific Prepayment Cox:
            # Default and other censoring are censored.
            (
                pl.col("event_type")
                == "PREPAYMENT"
            )
            .cast(pl.Int8)
            .alias(
                "prepayment_event"
            ),

            # Competing-risk coding:
            # 0 = censor
            # 1 = default
            # 2 = prepayment
            pl.col("event_code")
            .cast(pl.Int8)
            .alias(
                "competing_event_code"
            ),

        )

        # =================================================
        # OUTPUT
        # =================================================

        .select(
            [
                "loan_id",
                "vintage_year",

                "first_payment_month",
                "maturity_month",

                "event_type",
                "event_code",
                "event_month",
                "event_date",
                "event_source",

                "raw_duration_months",
                "duration_months",

                "survival_eligible",
                "survival_exclusion_reason",

                "default_event",
                "prepayment_event",
                "competing_event_code",

                "default_flag",
                "prepayment_flag",
                "censor_flag",

                "same_month_default_prepay_flag",
                "raw_zero_balance_code",

                "last_observed_month",

                # -----------------------------------------
                # Audit evidence
                # -----------------------------------------

                "first_d90_month",
                "first_ra_month",

                "first_zb02_month",
                "first_zb03_month",
                "first_zb09_month",

                "first_default_month",
                "default_source",

                "first_prepay_month",
                "first_maturity_month",

                "first_zb15_month",
                "first_zb16_month",
                "first_zb96_month",

                "first_admin_termination_month",
                "admin_source",
            ]
        )

        .sort(
            "loan_id"
        )
    )

    return result


# =========================================================
# BUILD ONE YEAR
# =========================================================


def build_survival_duration_year(
    year: int,
    force: bool = False,
) -> Path:

    year = int(year)

    event_path = (
        MODEL_DIR
        / f"event_map_{year}.parquet"
    )

    output_path = (
        MODEL_DIR
        / f"survival_duration_{year}.parquet"
    )

    temp_path = (
        MODEL_DIR
        / f"survival_duration_{year}.tmp.parquet"
    )


    if not event_path.exists():

        raise FileNotFoundError(
            f"Không tìm thấy:\n{event_path}"
        )


    if output_path.exists() and not force:

        print(
            f"✓ survival_duration_{year}.parquet "
            f"đã tồn tại, bỏ qua."
        )

        return output_path


    temp_path.unlink(
        missing_ok=True
    )


    event_map = (
        pl.scan_parquet(
            event_path
        )
    )


    survival = (
        build_survival_duration(
            event_map
        )
    )


    survival.sink_parquet(
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


def validate_survival_duration_year(
    year: int,
) -> dict:

    year = int(year)

    event_path = (
        MODEL_DIR
        / f"event_map_{year}.parquet"
    )

    survival_path = (
        MODEL_DIR
        / f"survival_duration_{year}.parquet"
    )


    events = (
        pl.scan_parquet(
            event_path
        )
    )

    survival = (
        pl.scan_parquet(
            survival_path
        )
    )


    # =====================================================
    # BASIC COUNTS
    # =====================================================

    event_rows = (
        events
        .select(
            pl.len().alias("n")
        )
        .collect()["n"][0]
    )


    survival_rows = (
        survival
        .select(
            pl.len().alias("n")
        )
        .collect()["n"][0]
    )


    unique_loans = (
        survival
        .select(
            pl.col("loan_id")
            .n_unique()
            .alias("n")
        )
        .collect()["n"][0]
    )


    # =====================================================
    # ELIGIBILITY
    # =====================================================

    eligible = (
        survival
        .filter(
            pl.col("survival_eligible")
        )
        .select(
            pl.len().alias("n")
        )
        .collect()["n"][0]
    )


    excluded_preentry = (
        survival
        .filter(
            ~pl.col("survival_eligible")
        )
        .select(
            pl.len().alias("n")
        )
        .collect()["n"][0]
    )


    # =====================================================
    # INVALID DURATIONS
    # =====================================================

    eligible_invalid_duration = (
        survival
        .filter(
            pl.col("survival_eligible")
            &
            (
                pl.col("duration_months")
                <= 0
            )
        )
        .select(
            pl.len().alias("n")
        )
        .collect()["n"][0]
    )


    excluded_nonnull_duration = (
        survival
        .filter(
            (~pl.col("survival_eligible"))
            &
            pl.col("duration_months")
            .is_not_null()
        )
        .select(
            pl.len().alias("n")
        )
        .collect()["n"][0]
    )


    # =====================================================
    # EVENT FLAGS
    # =====================================================

    invalid_default_event = (
        survival
        .filter(
            (
                pl.col("default_event")
                == 1
            )
            !=
            (
                pl.col("event_type")
                == "DEFAULT"
            )
        )
        .select(
            pl.len().alias("n")
        )
        .collect()["n"][0]
    )


    invalid_prepay_event = (
        survival
        .filter(
            (
                pl.col("prepayment_event")
                == 1
            )
            !=
            (
                pl.col("event_type")
                == "PREPAYMENT"
            )
        )
        .select(
            pl.len().alias("n")
        )
        .collect()["n"][0]
    )


    # =====================================================
    # COUNTS BY EVENT TYPE FOR ELIGIBLE SAMPLE
    # =====================================================

    eligible_counts = (
        survival

        .filter(
            pl.col("survival_eligible")
        )

        .group_by(
            "event_type"
        )

        .len()

        .collect()
    )


    count_dict = {
        row["event_type"]: row["len"]
        for row in eligible_counts.iter_rows(
            named=True
        )
    }


    # =====================================================
    # HARD VALIDATION
    # =====================================================

    if survival_rows != event_rows:

        raise RuntimeError(
            f"{year}: survival rows != event rows."
        )


    if unique_loans != survival_rows:

        raise RuntimeError(
            f"{year}: survival duration "
            f"không unique theo Loan ID."
        )


    if eligible_invalid_duration != 0:

        raise RuntimeError(
            f"{year}: Có eligible loan "
            f"duration <= 0."
        )


    if excluded_nonnull_duration != 0:

        raise RuntimeError(
            f"{year}: Pre-entry loan vẫn có "
            f"duration_months."
        )


    if invalid_default_event != 0:

        raise RuntimeError(
            f"{year}: default_event mapping sai."
        )


    if invalid_prepay_event != 0:

        raise RuntimeError(
            f"{year}: prepayment_event mapping sai."
        )


    # =====================================================
    # RESULT
    # =====================================================

    result = {

        "year":
            year,

        "loans":
            int(
                survival_rows
            ),

        "eligible":
            int(
                eligible
            ),

        "excluded_preentry":
            int(
                excluded_preentry
            ),

        "eligible_default":
            int(
                count_dict.get(
                    "DEFAULT",
                    0,
                )
            ),

        "eligible_prepayment":
            int(
                count_dict.get(
                    "PREPAYMENT",
                    0,
                )
            ),

        "eligible_censor":
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
        f"SURVIVAL DURATION VALIDATION - {year}"
    )

    print(
        "=" * 70
    )

    print(
        f"Loans:                     "
        f"{result['loans']:,}"
    )

    print(
        f"Eligible:                  "
        f"{result['eligible']:,}"
    )

    print(
        f"Excluded before FP:        "
        f"{result['excluded_preentry']:,}"
    )

    print(
        f"Eligible DEFAULT:          "
        f"{result['eligible_default']:,}"
    )

    print(
        f"Eligible PREPAYMENT:       "
        f"{result['eligible_prepayment']:,}"
    )

    print(
        f"Eligible CENSOR:           "
        f"{result['eligible_censor']:,}"
    )

    print(
        "\n✓ SURVIVAL DURATION VALIDATION PASS"
    )

    print(
        "=" * 70
    )


    return result
