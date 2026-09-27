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
    MODEL_DIR,
    TABLES_DIR,
    ensure_directories,
)


# =========================================================
# OUTPUTS
# =========================================================

REPORTS_DIR = (
    PROJECT_ROOT
    / "reports"
)

CANDIDATE_SUMMARY_FILE = (
    TABLES_DIR
    / "event_candidate_summary_by_year.csv"
)

CONFLICT_SUMMARY_FILE = (
    TABLES_DIR
    / "event_conflict_summary_by_year.csv"
)

ZERO_BALANCE_FILE = (
    TABLES_DIR
    / "event_zero_balance_distribution.csv"
)

ZB01_FILE = (
    TABLES_DIR
    / "event_zb01_classification_by_year.csv"
)

CONFLICT_LOANS_FILE = (
    TABLES_DIR
    / "event_conflict_loans.csv"
)

REPORT_FILE = (
    REPORTS_DIR
    / "event_conflict_audit.md"
)


# =========================================================
# HELPERS
# =========================================================

def first_month_when(
    condition: pl.Expr,
    month_column: pl.Expr,
) -> pl.Expr:
    """
    Return first month satisfying a condition.
    """

    return (
        pl.when(
            condition
        )
        .then(
            month_column
        )
        .otherwise(
            None
        )
        .min()
    )


def bool_count(
    df: pl.DataFrame,
    expression: pl.Expr,
) -> int:
    """
    Count rows satisfying a boolean condition.
    """

    return int(
        df.select(
            expression
            .fill_null(False)
            .sum()
            .alias(
                "n"
            )
        )["n"][0]
    )


# =========================================================
# AUDIT ONE YEAR
# =========================================================

def audit_year(
    year: int,
):

    print(
        "\n"
        + "=" * 80
    )

    print(
        f"EVENT CONFLICT AUDIT - {year}"
    )

    print(
        "=" * 80
    )


    # =====================================================
    # FILES
    # =====================================================

    orig_path = (
        MODEL_DIR
        / f"orig_clean_{year}.parquet"
    )

    perf_path = (
        MODEL_DIR
        / f"perf_clean_{year}.parquet"
    )


    if not orig_path.exists():

        raise FileNotFoundError(
            f"Không tìm thấy:\n"
            f"{orig_path}"
        )


    if not perf_path.exists():

        raise FileNotFoundError(
            f"Không tìm thấy:\n"
            f"{perf_path}"
        )


    # =====================================================
    # LOAD
    # =====================================================

    orig = (
        pl.scan_parquet(
            orig_path
        )
    )

    perf = (
        pl.scan_parquet(
            perf_path
        )
    )


    # =====================================================
    # CREATE ZERO BALANCE EVENT MONTH
    #
    # Prefer official Zero Balance Effective Date.
    # If missing, fallback to monthly reporting period.
    # =====================================================

    perf = (
        perf
        .with_columns(

            pl.coalesce(
                [
                    pl.col(
                        "zero_balance_effective_date"
                    )
                    .cast(
                        pl.Int32,
                        strict=False,
                    ),

                    pl.col(
                        "reporting_period_num"
                    ),
                ]
            )
            .alias(
                "_zb_event_month"
            )

        )
    )


    # =====================================================
    # BASIC LOAN COUNTS
    # =====================================================

    orig_loans = (
        orig
        .select(
            pl.col(
                "loan_id"
            )
            .n_unique()
            .alias(
                "n"
            )
        )
        .collect()["n"][0]
    )


    perf_loans = (
        perf
        .select(
            pl.col(
                "loan_id"
            )
            .n_unique()
            .alias(
                "n"
            )
        )
        .collect()["n"][0]
    )


    # =====================================================
    # ZERO BALANCE CODE DISTRIBUTION
    # =====================================================

    zero_balance_distribution = (
        perf
        .filter(
            pl.col(
                "zero_balance_code"
            )
            .is_not_null()
        )
        .group_by(
            "zero_balance_code"
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
            "year",
            "zero_balance_code",
            "rows",
            "loans",
        )
        .sort(
            "zero_balance_code"
        )
        .collect()
    )


    # =====================================================
    # ZERO BALANCE EFFECTIVE DATE CONSISTENCY
    # =====================================================

    zb_date_audit = (
        perf
        .filter(
            pl.col(
                "zero_balance_code"
            )
            .is_not_null()
        )
        .select(

            pl.len()
            .alias(
                "zb_rows"
            ),

            (
                pl.col(
                    "zero_balance_effective_date"
                )
                .is_null()
            )
            .sum()
            .alias(
                "zb_effective_date_missing"
            ),

            (
                (
                    pl.col(
                        "zero_balance_effective_date"
                    )
                    .cast(
                        pl.Int32,
                        strict=False,
                    )
                    !=
                    pl.col(
                        "reporting_period_num"
                    )
                )
                &
                pl.col(
                    "zero_balance_effective_date"
                )
                .is_not_null()
            )
            .fill_null(False)
            .sum()
            .alias(
                "zb_reporting_month_mismatch"
            ),

        )
        .collect()
    )


    # =====================================================
    # ZB 01 AUDIT
    #
    # 01 = Prepaid OR Matured
    #
    # Primary classification:
    #   remaining maturity > 0  -> prepayment candidate
    #   remaining maturity <= 0 -> maturity
    #
    # If remaining maturity missing:
    # fallback to effective month vs maturity date.
    # =====================================================

    orig_maturity = (
        orig
        .select(
            [
                "loan_id",
                "maturity_month",
            ]
        )
    )


    zb01 = (
        perf
        .filter(
            pl.col(
                "zero_balance_code"
            )
            == "01"
        )
        .select(
            [
                "loan_id",
                "vintage_year",
                "reporting_period_num",
                "_zb_event_month",
                "zero_balance_effective_month",
                "remaining_months_maturity",
            ]
        )
        .join(
            orig_maturity,
            on="loan_id",
            how="left",
        )

        .with_columns(

            pl.when(
                pl.col(
                    "remaining_months_maturity"
                )
                > 0
            )
            .then(
                pl.lit(
                    "PREPAY_REMAINING_MATURITY"
                )
            )

            .when(
                pl.col(
                    "remaining_months_maturity"
                )
                <= 0
            )
            .then(
                pl.lit(
                    "MATURED_REMAINING_MATURITY"
                )
            )

            .when(
                pl.col(
                    "remaining_months_maturity"
                )
                .is_null()

                &

                pl.col(
                    "zero_balance_effective_month"
                )
                .is_not_null()

                &

                pl.col(
                    "maturity_month"
                )
                .is_not_null()

                &

                (
                    pl.col(
                        "zero_balance_effective_month"
                    )
                    <
                    pl.col(
                        "maturity_month"
                    )
                )
            )
            .then(
                pl.lit(
                    "PREPAY_FALLBACK_MATURITY_DATE"
                )
            )

            .when(
                pl.col(
                    "remaining_months_maturity"
                )
                .is_null()

                &

                pl.col(
                    "zero_balance_effective_month"
                )
                .is_not_null()

                &

                pl.col(
                    "maturity_month"
                )
                .is_not_null()

                &

                (
                    pl.col(
                        "zero_balance_effective_month"
                    )
                    >=
                    pl.col(
                        "maturity_month"
                    )
                )
            )
            .then(
                pl.lit(
                    "MATURED_FALLBACK_MATURITY_DATE"
                )
            )

            .otherwise(
                pl.lit(
                    "AMBIGUOUS"
                )
            )
            .alias(
                "zb01_classification"
            )

        )
    )


    zb01_classification = (
        zb01
        .group_by(
            "zb01_classification"
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
            "year",
            "zb01_classification",
            "rows",
            "loans",
        )
        .sort(
            "zb01_classification"
        )
        .collect()
    )


    # =====================================================
    # ZB01 LOAN-LEVEL FIRST MONTHS
    # =====================================================

    zb01_loan = (
        zb01
        .group_by(
            "loan_id"
        )
        .agg(

            first_month_when(

                pl.col(
                    "zb01_classification"
                )
                .is_in(
                    [
                        "PREPAY_REMAINING_MATURITY",
                        "PREPAY_FALLBACK_MATURITY_DATE",
                    ]
                ),

                pl.col(
                    "_zb_event_month"
                ),

            )
            .alias(
                "first_prepay_month"
            ),


            first_month_when(

                pl.col(
                    "zb01_classification"
                )
                .is_in(
                    [
                        "MATURED_REMAINING_MATURITY",
                        "MATURED_FALLBACK_MATURITY_DATE",
                    ]
                ),

                pl.col(
                    "_zb_event_month"
                ),

            )
            .alias(
                "first_maturity_month"
            ),


            first_month_when(

                pl.col(
                    "zb01_classification"
                )
                == "AMBIGUOUS",

                pl.col(
                    "_zb_event_month"
                ),

            )
            .alias(
                "first_zb01_ambiguous_month"
            ),

        )
        .collect()
    )


    # =====================================================
    # LOAN-LEVEL EVENT CANDIDATES
    # =====================================================

    loan_candidates = (
        perf
        .group_by(
            "loan_id"
        )
        .agg(

            # ---------------------------------------------
            # First serious delinquency: 90+ DPD
            # ---------------------------------------------

            first_month_when(

                pl.col(
                    "delinquency_num"
                )
                >= 3,

                pl.col(
                    "reporting_period_num"
                ),

            )
            .alias(
                "first_d90_month"
            ),


            # ---------------------------------------------
            # First REO Acquisition
            # ---------------------------------------------

            first_month_when(

                pl.col(
                    "is_ra"
                ),

                pl.col(
                    "reporting_period_num"
                ),

            )
            .alias(
                "first_ra_month"
            ),


            # ---------------------------------------------
            # Credit-related Zero Balance
            # 02 = Third Party Sale
            # 03 = Short Sale / Charge Off
            # 09 = REO Disposition
            # ---------------------------------------------

            first_month_when(

                pl.col(
                    "zero_balance_code"
                )
                .is_in(
                    [
                        "02",
                        "03",
                        "09",
                    ]
                ),

                pl.col(
                    "_zb_event_month"
                ),

            )
            .alias(
                "first_credit_zb_month"
            ),


            # ---------------------------------------------
            # Administrative / other termination
            # ---------------------------------------------

            first_month_when(

                pl.col(
                    "zero_balance_code"
                )
                .is_in(
                    [
                        "15",
                        "16",
                        "96",
                    ]
                ),

                pl.col(
                    "_zb_event_month"
                ),

            )
            .alias(
                "first_admin_termination_month"
            ),


            # ---------------------------------------------
            # Last observed performance month
            # ---------------------------------------------

            pl.col(
                "reporting_period_num"
            )
            .max()
            .alias(
                "last_observed_month"
            ),

        )
        .collect()
    )


    # =====================================================
    # JOIN ZB01 CANDIDATES
    # =====================================================

    loan_candidates = (
        loan_candidates
        .join(
            zb01_loan,
            on="loan_id",
            how="left",
        )
    )


    # =====================================================
    # FIRST DEFAULT EVIDENCE MONTH
    #
    # IMPORTANT:
    # This is only an AUDIT candidate.
    # We are NOT locking the final definition yet.
    # =====================================================

    loan_candidates = (
        loan_candidates
        .with_columns(

            pl.min_horizontal(
                [
                    pl.col(
                        "first_d90_month"
                    ),
                    pl.col(
                        "first_ra_month"
                    ),
                    pl.col(
                        "first_credit_zb_month"
                    ),
                ]
            )
            .alias(
                "first_default_evidence_month"
            )

        )
    )


    # =====================================================
    # DEFAULT VS PREPAYMENT RELATION
    # =====================================================

    loan_candidates = (
        loan_candidates
        .with_columns(

            pl.when(

                pl.col(
                    "first_default_evidence_month"
                )
                .is_not_null()

                &

                pl.col(
                    "first_prepay_month"
                )
                .is_not_null()

                &

                (
                    pl.col(
                        "first_default_evidence_month"
                    )
                    <
                    pl.col(
                        "first_prepay_month"
                    )
                )

            )
            .then(
                pl.lit(
                    "DEFAULT_BEFORE_PREPAY"
                )
            )

            .when(

                pl.col(
                    "first_default_evidence_month"
                )
                .is_not_null()

                &

                pl.col(
                    "first_prepay_month"
                )
                .is_not_null()

                &

                (
                    pl.col(
                        "first_default_evidence_month"
                    )
                    ==
                    pl.col(
                        "first_prepay_month"
                    )
                )

            )
            .then(
                pl.lit(
                    "DEFAULT_AND_PREPAY_SAME_MONTH"
                )
            )

            .when(

                pl.col(
                    "first_default_evidence_month"
                )
                .is_not_null()

                &

                pl.col(
                    "first_prepay_month"
                )
                .is_not_null()

                &

                (
                    pl.col(
                        "first_prepay_month"
                    )
                    <
                    pl.col(
                        "first_default_evidence_month"
                    )
                )

            )
            .then(
                pl.lit(
                    "PREPAY_BEFORE_DEFAULT"
                )
            )

            .otherwise(
                pl.lit(
                    "NO_DEFAULT_PREPAY_CONFLICT"
                )
            )
            .alias(
                "default_prepay_relation"
            )

        )
    )


    # =====================================================
    # EVENT CANDIDATE COUNTS
    # =====================================================

    d90_loans = bool_count(
        loan_candidates,
        pl.col(
            "first_d90_month"
        )
        .is_not_null(),
    )


    ra_loans = bool_count(
        loan_candidates,
        pl.col(
            "first_ra_month"
        )
        .is_not_null(),
    )


    credit_zb_loans = bool_count(
        loan_candidates,
        pl.col(
            "first_credit_zb_month"
        )
        .is_not_null(),
    )


    any_default_evidence = bool_count(
        loan_candidates,
        pl.col(
            "first_default_evidence_month"
        )
        .is_not_null(),
    )


    prepay_loans = bool_count(
        loan_candidates,
        pl.col(
            "first_prepay_month"
        )
        .is_not_null(),
    )


    maturity_loans = bool_count(
        loan_candidates,
        pl.col(
            "first_maturity_month"
        )
        .is_not_null(),
    )


    ambiguous_zb01_loans = bool_count(
        loan_candidates,
        pl.col(
            "first_zb01_ambiguous_month"
        )
        .is_not_null(),
    )


    admin_termination_loans = bool_count(
        loan_candidates,
        pl.col(
            "first_admin_termination_month"
        )
        .is_not_null(),
    )


    no_candidate_event = bool_count(

        loan_candidates,

        pl.col(
            "first_default_evidence_month"
        )
        .is_null()

        &

        pl.col(
            "first_prepay_month"
        )
        .is_null()

        &

        pl.col(
            "first_maturity_month"
        )
        .is_null()

        &

        pl.col(
            "first_zb01_ambiguous_month"
        )
        .is_null()

        &

        pl.col(
            "first_admin_termination_month"
        )
        .is_null(),

    )


    # =====================================================
    # DEFAULT EVIDENCE OVERLAP
    # =====================================================

    d90_and_ra = bool_count(

        loan_candidates,

        pl.col(
            "first_d90_month"
        )
        .is_not_null()

        &

        pl.col(
            "first_ra_month"
        )
        .is_not_null(),

    )


    d90_and_credit_zb = bool_count(

        loan_candidates,

        pl.col(
            "first_d90_month"
        )
        .is_not_null()

        &

        pl.col(
            "first_credit_zb_month"
        )
        .is_not_null(),

    )


    ra_and_credit_zb = bool_count(

        loan_candidates,

        pl.col(
            "first_ra_month"
        )
        .is_not_null()

        &

        pl.col(
            "first_credit_zb_month"
        )
        .is_not_null(),

    )


    d90_ra_same_month = bool_count(

        loan_candidates,

        pl.col(
            "first_d90_month"
        )
        .is_not_null()

        &

        (
            pl.col(
                "first_d90_month"
            )
            ==
            pl.col(
                "first_ra_month"
            )
        ),

    )


    d90_credit_same_month = bool_count(

        loan_candidates,

        pl.col(
            "first_d90_month"
        )
        .is_not_null()

        &

        (
            pl.col(
                "first_d90_month"
            )
            ==
            pl.col(
                "first_credit_zb_month"
            )
        ),

    )


    ra_credit_same_month = bool_count(

        loan_candidates,

        pl.col(
            "first_ra_month"
        )
        .is_not_null()

        &

        (
            pl.col(
                "first_ra_month"
            )
            ==
            pl.col(
                "first_credit_zb_month"
            )
        ),

    )


    # =====================================================
    # DEFAULT / PREPAYMENT CONFLICT
    # =====================================================

    default_and_prepay = bool_count(

        loan_candidates,

        pl.col(
            "first_default_evidence_month"
        )
        .is_not_null()

        &

        pl.col(
            "first_prepay_month"
        )
        .is_not_null(),

    )


    default_before_prepay = bool_count(

        loan_candidates,

        pl.col(
            "default_prepay_relation"
        )
        == "DEFAULT_BEFORE_PREPAY",

    )


    default_prepay_same_month = bool_count(

        loan_candidates,

        pl.col(
            "default_prepay_relation"
        )
        == "DEFAULT_AND_PREPAY_SAME_MONTH",

    )


    prepay_before_default = bool_count(

        loan_candidates,

        pl.col(
            "default_prepay_relation"
        )
        == "PREPAY_BEFORE_DEFAULT",

    )


    # =====================================================
    # OUTPUT RECORDS
    # =====================================================

    candidate_summary = {

        "year":
            year,

        "orig_loans":
            int(
                orig_loans
            ),

        "perf_loans":
            int(
                perf_loans
            ),

        "orig_without_perf":
            int(
                orig_loans
                - perf_loans
            ),

        "d90_loans":
            d90_loans,

        "ra_loans":
            ra_loans,

        "credit_zb_02_03_09_loans":
            credit_zb_loans,

        "any_default_evidence_loans":
            any_default_evidence,

        "prepay_candidate_loans":
            prepay_loans,

        "maturity_candidate_loans":
            maturity_loans,

        "zb01_ambiguous_loans":
            ambiguous_zb01_loans,

        "admin_termination_15_16_96_loans":
            admin_termination_loans,

        "no_candidate_event_loans":
            no_candidate_event,

        "zb_rows":
            int(
                zb_date_audit[
                    "zb_rows"
                ][0]
            ),

        "zb_effective_date_missing":
            int(
                zb_date_audit[
                    "zb_effective_date_missing"
                ][0]
            ),

        "zb_reporting_month_mismatch":
            int(
                zb_date_audit[
                    "zb_reporting_month_mismatch"
                ][0]
            ),

    }


    conflict_summary = {

        "year":
            year,

        "d90_and_ra":
            d90_and_ra,

        "d90_and_credit_zb":
            d90_and_credit_zb,

        "ra_and_credit_zb":
            ra_and_credit_zb,

        "d90_ra_same_month":
            d90_ra_same_month,

        "d90_credit_same_month":
            d90_credit_same_month,

        "ra_credit_same_month":
            ra_credit_same_month,

        "default_and_prepay_both":
            default_and_prepay,

        "default_before_prepay":
            default_before_prepay,

        "default_and_prepay_same_month":
            default_prepay_same_month,

        "prepay_before_default":
            prepay_before_default,

    }


    # =====================================================
    # CONFLICT LOANS
    # =====================================================

    conflict_loans = (
        loan_candidates

        .filter(
            pl.col(
                "default_prepay_relation"
            )
            !=
            "NO_DEFAULT_PREPAY_CONFLICT"
        )

        .with_columns(
            pl.lit(
                year
            )
            .alias(
                "vintage_year"
            )
        )

        .select(
            [
                "vintage_year",
                "loan_id",
                "first_d90_month",
                "first_ra_month",
                "first_credit_zb_month",
                "first_default_evidence_month",
                "first_prepay_month",
                "first_maturity_month",
                "first_admin_termination_month",
                "last_observed_month",
                "default_prepay_relation",
            ]
        )

        .sort(
            [
                "default_prepay_relation",
                "loan_id",
            ]
        )
    )


    # =====================================================
    # TERMINAL OUTPUT
    # =====================================================

    print(
        f"Origination loans:                "
        f"{orig_loans:,}"
    )

    print(
        f"Performance loans:                "
        f"{perf_loans:,}"
    )

    print(
        f"First 90+ DPD candidates:         "
        f"{d90_loans:,}"
    )

    print(
        f"RA candidates:                    "
        f"{ra_loans:,}"
    )

    print(
        f"ZB 02/03/09 candidates:           "
        f"{credit_zb_loans:,}"
    )

    print(
        f"Any default evidence:             "
        f"{any_default_evidence:,}"
    )

    print(
        f"Prepayment candidates:            "
        f"{prepay_loans:,}"
    )

    print(
        f"Maturity candidates:              "
        f"{maturity_loans:,}"
    )

    print(
        f"Ambiguous ZB01:                   "
        f"{ambiguous_zb01_loans:,}"
    )

    print(
        f"Admin terminations 15/16/96:      "
        f"{admin_termination_loans:,}"
    )

    print(
        f"Default + Prepayment both:        "
        f"{default_and_prepay:,}"
    )

    print(
        f"  Default before prepay:          "
        f"{default_before_prepay:,}"
    )

    print(
        f"  Same month:                     "
        f"{default_prepay_same_month:,}"
    )

    print(
        f"  Prepay before default:          "
        f"{prepay_before_default:,}"
    )


    return (
        candidate_summary,
        conflict_summary,
        zero_balance_distribution,
        zb01_classification,
        conflict_loans,
    )


# =========================================================
# MARKDOWN REPORT
# =========================================================

def write_report(
    candidate_df: pl.DataFrame,
    conflict_df: pl.DataFrame,
    zb01_df: pl.DataFrame,
):

    lines = []

    lines.append(
        "# Freddie Mac Event Conflict Audit"
    )

    lines.append("")

    lines.append(
        "This report is an audit only. "
        "No final Default, Prepayment, or Censoring "
        "definition has been applied yet."
    )

    lines.append("")

    lines.append(
        "## Event candidates by vintage"
    )

    lines.append("")

    lines.append(
        "| Year | 90+ DPD | RA | ZB 02/03/09 | Any default evidence | Prepay candidate | Maturity | Ambiguous 01 | Admin 15/16/96 |"
    )

    lines.append(
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|"
    )


    for row in candidate_df.iter_rows(
        named=True
    ):

        lines.append(

            f"| {row['year']} "
            f"| {row['d90_loans']:,} "
            f"| {row['ra_loans']:,} "
            f"| {row['credit_zb_02_03_09_loans']:,} "
            f"| {row['any_default_evidence_loans']:,} "
            f"| {row['prepay_candidate_loans']:,} "
            f"| {row['maturity_candidate_loans']:,} "
            f"| {row['zb01_ambiguous_loans']:,} "
            f"| {row['admin_termination_15_16_96_loans']:,} |"

        )


    lines.append("")

    lines.append(
        "## Default / Prepayment conflicts"
    )

    lines.append("")

    lines.append(
        "| Year | Both exist | Default before prepay | Same month | Prepay before default |"
    )

    lines.append(
        "|---:|---:|---:|---:|---:|"
    )


    for row in conflict_df.iter_rows(
        named=True
    ):

        lines.append(

            f"| {row['year']} "
            f"| {row['default_and_prepay_both']:,} "
            f"| {row['default_before_prepay']:,} "
            f"| {row['default_and_prepay_same_month']:,} "
            f"| {row['prepay_before_default']:,} |"

        )


    lines.append("")

    lines.append(
        "## Zero Balance Code 01 classification"
    )

    lines.append("")

    lines.append(
        "| Year | Classification | Rows | Loans |"
    )

    lines.append(
        "|---:|:---|---:|---:|"
    )


    for row in zb01_df.iter_rows(
        named=True
    ):

        lines.append(

            f"| {row['year']} "
            f"| {row['zb01_classification']} "
            f"| {row['rows']:,} "
            f"| {row['loans']:,} |"

        )


    lines.append("")

    lines.append(
        "## Interpretation rule"
    )

    lines.append("")

    lines.append(
        "- 90+ DPD, RA, and Zero Balance 02/03/09 "
        "are audited as potential default evidence."
    )

    lines.append(
        "- Zero Balance 01 is separated into "
        "prepayment, maturity, or ambiguous cases."
    )

    lines.append(
        "- Zero Balance 15/16/96 are audited separately "
        "and are not automatically treated as borrower default."
    )

    lines.append(
        "- Same-month Default/Prepayment conflicts must be "
        "reviewed before final event precedence is locked."
    )


    REPORT_FILE.write_text(
        "\n".join(
            lines
        ),
        encoding="utf-8",
    )


# =========================================================
# MAIN
# =========================================================

def main():

    ensure_directories()

    TABLES_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    REPORTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


    print(
        "\n"
        + "=" * 80
    )

    print(
        "FREDDIE MAC EVENT CONFLICT AUDIT"
    )

    print(
        "2016–2026"
    )

    print(
        "=" * 80
    )


    candidate_records = []
    conflict_records = []

    zb_tables = []
    zb01_tables = []
    conflict_loan_tables = []


    # =====================================================
    # RUN ALL VINTAGES
    # =====================================================

    for year in STUDY_YEARS:

        (
            candidate_summary,
            conflict_summary,
            zero_balance_distribution,
            zb01_classification,
            conflict_loans,
        ) = audit_year(
            year
        )


        candidate_records.append(
            candidate_summary
        )

        conflict_records.append(
            conflict_summary
        )


        if zero_balance_distribution.height > 0:

            zb_tables.append(
                zero_balance_distribution
            )


        if zb01_classification.height > 0:

            zb01_tables.append(
                zb01_classification
            )


        if conflict_loans.height > 0:

            conflict_loan_tables.append(
                conflict_loans
            )


    # =====================================================
    # BUILD OUTPUT DATAFRAMES
    # =====================================================

    candidate_df = (
        pl.DataFrame(
            candidate_records
        )
        .sort(
            "year"
        )
    )


    conflict_df = (
        pl.DataFrame(
            conflict_records
        )
        .sort(
            "year"
        )
    )


    if zb_tables:

        zero_balance_df = (
            pl.concat(
                zb_tables,
                how="vertical",
            )
            .sort(
                [
                    "year",
                    "zero_balance_code",
                ]
            )
        )

    else:

        zero_balance_df = pl.DataFrame()


    if zb01_tables:

        zb01_df = (
            pl.concat(
                zb01_tables,
                how="vertical",
            )
            .sort(
                [
                    "year",
                    "zb01_classification",
                ]
            )
        )

    else:

        zb01_df = pl.DataFrame()


    if conflict_loan_tables:

        conflict_loans_df = (
            pl.concat(
                conflict_loan_tables,
                how="vertical",
            )
            .sort(
                [
                    "vintage_year",
                    "default_prepay_relation",
                    "loan_id",
                ]
            )
        )

    else:

        conflict_loans_df = (
            pl.DataFrame(
                {
                    "vintage_year": [],
                    "loan_id": [],
                    "first_d90_month": [],
                    "first_ra_month": [],
                    "first_credit_zb_month": [],
                    "first_default_evidence_month": [],
                    "first_prepay_month": [],
                    "first_maturity_month": [],
                    "first_admin_termination_month": [],
                    "last_observed_month": [],
                    "default_prepay_relation": [],
                }
            )
        )


    # =====================================================
    # SAVE OUTPUTS
    # =====================================================

    candidate_df.write_csv(
        CANDIDATE_SUMMARY_FILE
    )

    conflict_df.write_csv(
        CONFLICT_SUMMARY_FILE
    )


    if zero_balance_df.width > 0:

        zero_balance_df.write_csv(
            ZERO_BALANCE_FILE
        )


    if zb01_df.width > 0:

        zb01_df.write_csv(
            ZB01_FILE
        )


    conflict_loans_df.write_csv(
        CONFLICT_LOANS_FILE
    )


    write_report(
        candidate_df,
        conflict_df,
        zb01_df,
    )


    # =====================================================
    # TOTAL SUMMARY
    # =====================================================

    print(
        "\n"
        + "=" * 80
    )

    print(
        "EVENT AUDIT TOTALS"
    )

    print(
        "=" * 80
    )


    total_default_evidence = (
        candidate_df[
            "any_default_evidence_loans"
        ]
        .sum()
    )

    total_prepay = (
        candidate_df[
            "prepay_candidate_loans"
        ]
        .sum()
    )

    total_maturity = (
        candidate_df[
            "maturity_candidate_loans"
        ]
        .sum()
    )

    total_ambiguous = (
        candidate_df[
            "zb01_ambiguous_loans"
        ]
        .sum()
    )

    total_conflicts = (
        conflict_df[
            "default_and_prepay_both"
        ]
        .sum()
    )

    total_same_month = (
        conflict_df[
            "default_and_prepay_same_month"
        ]
        .sum()
    )


    print(
        f"Any default evidence loans:       "
        f"{total_default_evidence:,}"
    )

    print(
        f"Prepayment candidates:            "
        f"{total_prepay:,}"
    )

    print(
        f"Maturity candidates:              "
        f"{total_maturity:,}"
    )

    print(
        f"Ambiguous ZB01:                   "
        f"{total_ambiguous:,}"
    )

    print(
        f"Default + Prepayment both:        "
        f"{total_conflicts:,}"
    )

    print(
        f"Same-month Default/Prepay:        "
        f"{total_same_month:,}"
    )


    print(
        "\nFILES CREATED:"
    )

    print(
        f"  {CANDIDATE_SUMMARY_FILE}"
    )

    print(
        f"  {CONFLICT_SUMMARY_FILE}"
    )

    print(
        f"  {ZERO_BALANCE_FILE}"
    )

    print(
        f"  {ZB01_FILE}"
    )

    print(
        f"  {CONFLICT_LOANS_FILE}"
    )

    print(
        f"  {REPORT_FILE}"
    )


    print(
        "\n"
        + "=" * 80
    )

    print(
        "✓ EVENT CONFLICT AUDIT HOÀN THÀNH"
    )

    print(
        "=" * 80
    )


if __name__ == "__main__":
    main()