from pathlib import Path
import sys

import polars as pl


# =========================================================
# PROJECT ROOT
# =========================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# =========================================================
# PROJECT IMPORTS
# =========================================================

from src.config import (
    STUDY_YEARS,
    MODEL_DIR,
    TABLES_DIR,
    ensure_directories,
)


# =========================================================
# OUTPUT FILES
# =========================================================

NEGATIVE_FILE = (
    TABLES_DIR
    / "negative_duration_cases.csv"
)

NONPOSITIVE_FILE = (
    TABLES_DIR
    / "nonpositive_duration_summary.csv"
)

MISMATCH_DISTRIBUTION_FILE = (
    TABLES_DIR
    / "unmodified_age_mismatch_distribution.csv"
)

MISMATCH_LOANS_FILE = (
    TABLES_DIR
    / "unmodified_age_mismatch_loans.csv"
)


# =========================================================
# HELPERS
# =========================================================

def yyyymm_index(column: str) -> pl.Expr:

    return (
        (
            pl.col(column)
            // 100
        )
        * 12
        +
        (
            pl.col(column)
            % 100
        )
    )


def date_index(column: str) -> pl.Expr:

    return (
        pl.col(column)
        .dt.year()
        * 12
        +
        pl.col(column)
        .dt.month()
    )


# =========================================================
# MAIN
# =========================================================

def main():

    ensure_directories()

    negative_tables = []
    nonpositive_tables = []
    mismatch_distribution_tables = []
    mismatch_loan_tables = []


    print(
        "\n"
        + "=" * 80
    )

    print(
        "LOAN AGE EDGE CASE INSPECTION"
    )

    print(
        "2016–2026"
    )

    print(
        "=" * 80
    )


    for year in STUDY_YEARS:

        print(
            f"\nInspecting {year}..."
        )


        # =================================================
        # PATHS
        # =================================================

        event_path = (
            MODEL_DIR
            / f"event_map_{year}.parquet"
        )

        perf_path = (
            MODEL_DIR
            / f"perf_clean_{year}.parquet"
        )


        # =================================================
        # EVENT DURATION
        # =================================================

        events = (
            pl.scan_parquet(
                event_path
            )

            .with_columns(

                date_index(
                    "first_payment_month"
                )
                .alias(
                    "_fp_index"
                ),

                yyyymm_index(
                    "event_month"
                )
                .alias(
                    "_event_index"
                ),

            )

            .with_columns(

                (
                    pl.col(
                        "_event_index"
                    )
                    -
                    pl.col(
                        "_fp_index"
                    )
                    + 1
                )
                .cast(
                    pl.Int32
                )
                .alias(
                    "duration_months"
                )

            )
        )


        # =================================================
        # NEGATIVE DURATION CASES
        # =================================================

        negative = (
            events

            .filter(
                pl.col(
                    "duration_months"
                )
                < 0
            )

            .with_columns(
                pl.lit(
                    year
                )
                .alias(
                    "year"
                )
            )

            .select(
                [
                    "year",
                    "loan_id",
                    "first_payment_month",
                    "event_type",
                    "event_source",
                    "event_month",
                    "event_date",
                    "duration_months",
                    "first_default_month",
                    "first_prepay_month",
                    "first_maturity_month",
                    "first_admin_termination_month",
                    "last_observed_month",
                    "raw_zero_balance_code",
                ]
            )

            .collect()
        )


        if negative.height > 0:

            negative_tables.append(
                negative
            )


        # =================================================
        # ALL NON-POSITIVE DURATION SUMMARY
        # =================================================

        nonpositive = (
            events

            .filter(
                pl.col(
                    "duration_months"
                )
                <= 0
            )

            .group_by(
                [
                    "event_type",
                    "event_source",
                    "duration_months",
                ]
            )

            .agg(
                pl.len()
                .alias(
                    "loans"
                )
            )

            .with_columns(
                pl.lit(
                    year
                )
                .alias(
                    "year"
                )
            )

            .select(
                [
                    "year",
                    "event_type",
                    "event_source",
                    "duration_months",
                    "loans",
                ]
            )

            .sort(
                [
                    "event_type",
                    "event_source",
                    "duration_months",
                ]
            )

            .collect()
        )


        if nonpositive.height > 0:

            nonpositive_tables.append(
                nonpositive
            )


        # =================================================
        # FIXED CLOCK ORIGIN FOR MONTHLY PERFORMANCE
        # =================================================

        origins = (
            events
            .select(
                [
                    "loan_id",
                    "first_payment_month",
                ]
            )
        )


        perf = (
            pl.scan_parquet(
                perf_path
            )

            .join(
                origins,
                on="loan_id",
                how="inner",
            )

            .with_columns(

                yyyymm_index(
                    "reporting_period_num"
                )
                .alias(
                    "_reporting_index"
                ),

                date_index(
                    "first_payment_month"
                )
                .alias(
                    "_fp_index"
                ),

            )

            .with_columns(

                (
                    pl.col(
                        "_reporting_index"
                    )
                    -
                    pl.col(
                        "_fp_index"
                    )
                    + 1
                )
                .cast(
                    pl.Int32
                )
                .alias(
                    "analysis_age_months"
                )

            )

            .with_columns(

                (
                    pl.col(
                        "loan_age"
                    )
                    .cast(
                        pl.Int32
                    )
                    -
                    pl.col(
                        "analysis_age_months"
                    )
                )
                .alias(
                    "age_difference"
                )

            )
        )


        # =================================================
        # UNMODIFIED MISMATCH ONLY
        # =================================================

        mismatch = (
            perf

            .filter(

                pl.col(
                    "modification_flag"
                )
                .is_null()

                &

                pl.col(
                    "loan_age"
                )
                .is_not_null()

                &

                (
                    pl.col(
                        "age_difference"
                    )
                    != 0
                )

            )
        )


        # =================================================
        # DIFFERENCE DISTRIBUTION
        # =================================================

        mismatch_distribution = (
            mismatch

            .group_by(
                "age_difference"
            )

            .agg(

                pl.len()
                .alias(
                    "rows"
                ),

                pl.col(
                    "loan_id"
                )
                .n_unique()
                .alias(
                    "loans"
                ),

            )

            .with_columns(
                pl.lit(
                    year
                )
                .alias(
                    "year"
                )
            )

            .select(
                [
                    "year",
                    "age_difference",
                    "rows",
                    "loans",
                ]
            )

            .sort(
                "age_difference"
            )

            .collect()
        )


        if mismatch_distribution.height > 0:

            mismatch_distribution_tables.append(
                mismatch_distribution
            )


        # =================================================
        # MISMATCH AT LOAN LEVEL
        # =================================================

        mismatch_loans = (
            mismatch

            .group_by(
                "loan_id"
            )

            .agg(

                pl.col(
                    "first_payment_month"
                )
                .first(),

                pl.col(
                    "reporting_period_num"
                )
                .min()
                .alias(
                    "first_mismatch_period"
                ),

                pl.col(
                    "reporting_period_num"
                )
                .max()
                .alias(
                    "last_mismatch_period"
                ),

                pl.col(
                    "age_difference"
                )
                .min()
                .alias(
                    "min_age_difference"
                ),

                pl.col(
                    "age_difference"
                )
                .max()
                .alias(
                    "max_age_difference"
                ),

                pl.len()
                .alias(
                    "mismatch_rows"
                ),

            )

            .with_columns(
                pl.lit(
                    year
                )
                .alias(
                    "year"
                )
            )

            .select(
                [
                    "year",
                    "loan_id",
                    "first_payment_month",
                    "first_mismatch_period",
                    "last_mismatch_period",
                    "min_age_difference",
                    "max_age_difference",
                    "mismatch_rows",
                ]
            )

            .collect()
        )


        if mismatch_loans.height > 0:

            mismatch_loan_tables.append(
                mismatch_loans
            )


        print(
            f"  Negative-duration loans: "
            f"{negative.height:,}"
        )

        print(
            f"  Unmodified mismatch rows: "
            f"{mismatch_distribution['rows'].sum() if mismatch_distribution.height else 0:,}"
        )

        print(
            f"  Unmodified mismatch loans: "
            f"{mismatch_loans.height:,}"
        )


    # =====================================================
    # CONCAT + SAVE
    # =====================================================

    if negative_tables:

        negative_df = (
            pl.concat(
                negative_tables,
                how="vertical_relaxed",
            )
        )

    else:

        negative_df = pl.DataFrame()


    if nonpositive_tables:

        nonpositive_df = (
            pl.concat(
                nonpositive_tables,
                how="vertical_relaxed",
            )
        )

    else:

        nonpositive_df = pl.DataFrame()


    if mismatch_distribution_tables:

        mismatch_distribution_df = (
            pl.concat(
                mismatch_distribution_tables,
                how="vertical_relaxed",
            )
        )

    else:

        mismatch_distribution_df = pl.DataFrame()


    if mismatch_loan_tables:

        mismatch_loans_df = (
            pl.concat(
                mismatch_loan_tables,
                how="vertical_relaxed",
            )
        )

    else:

        mismatch_loans_df = pl.DataFrame()


    negative_df.write_csv(
        NEGATIVE_FILE
    )

    nonpositive_df.write_csv(
        NONPOSITIVE_FILE
    )

    mismatch_distribution_df.write_csv(
        MISMATCH_DISTRIBUTION_FILE
    )

    mismatch_loans_df.write_csv(
        MISMATCH_LOANS_FILE
    )


    # =====================================================
    # FINAL OUTPUT
    # =====================================================

    print(
        "\n"
        + "=" * 80
    )

    print(
        "EDGE CASE TOTALS"
    )

    print(
        "=" * 80
    )

    print(
        f"Negative-duration loans:       "
        f"{negative_df.height:,}"
    )

    print(
        f"Unmodified mismatch rows:      "
        f"{mismatch_distribution_df['rows'].sum() if mismatch_distribution_df.height else 0:,}"
    )

    print(
        f"Unmodified mismatch loans:     "
        f"{mismatch_loans_df.height:,}"
    )


    print(
        "\nAGE DIFFERENCE DISTRIBUTION:"
    )

    if mismatch_distribution_df.height:

        overall_distribution = (
            mismatch_distribution_df

            .group_by(
                "age_difference"
            )

            .agg(

                pl.col(
                    "rows"
                )
                .sum()
                .alias(
                    "rows"
                ),

                pl.col(
                    "loans"
                )
                .sum()
                .alias(
                    "year_loan_counts"
                ),

            )

            .sort(
                "age_difference"
            )
        )

        print(
            overall_distribution
        )


    print(
        "\nFILES CREATED:"
    )

    print(
        f"  {NEGATIVE_FILE}"
    )

    print(
        f"  {NONPOSITIVE_FILE}"
    )

    print(
        f"  {MISMATCH_DISTRIBUTION_FILE}"
    )

    print(
        f"  {MISMATCH_LOANS_FILE}"
    )

    print(
        "\n✓ EDGE CASE INSPECTION HOÀN THÀNH"
    )


if __name__ == "__main__":
    main()