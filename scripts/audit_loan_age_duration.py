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
# IMPORT PROJECT CONFIG
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

REPORTS_DIR = PROJECT_ROOT / "reports"

SUMMARY_FILE = (
    TABLES_DIR
    / "loan_age_duration_audit_by_year.csv"
)

REPORT_FILE = (
    REPORTS_DIR
    / "loan_age_duration_audit.md"
)


# =========================================================
# HELPERS
# =========================================================

def yyyymm_month_index(
    column: str,
) -> pl.Expr:
    """
    Convert YYYYMM integer to continuous month index.
    Example:
        202001 -> 2020 * 12 + 1
    """

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


def date_month_index(
    column: str,
) -> pl.Expr:
    """
    Convert Date column to continuous month index.
    """

    return (
        pl.col(column)
        .dt.year()
        * 12
        +
        pl.col(column)
        .dt.month()
    )


# =========================================================
# AUDIT ONE YEAR
# =========================================================

def audit_year(
    year: int,
) -> dict:

    print(
        "\n"
        + "=" * 80
    )

    print(
        f"LOAN AGE / DURATION AUDIT - {year}"
    )

    print(
        "=" * 80
    )


    # =====================================================
    # PATHS
    # =====================================================

    event_path = (
        MODEL_DIR
        / f"event_map_{year}.parquet"
    )

    perf_path = (
        MODEL_DIR
        / f"perf_clean_{year}.parquet"
    )


    if not event_path.exists():

        raise FileNotFoundError(
            f"Không tìm thấy:\n{event_path}"
        )


    if not perf_path.exists():

        raise FileNotFoundError(
            f"Không tìm thấy:\n{perf_path}"
        )


    # =====================================================
    # LOAD EVENT MAP
    # =====================================================

    events = (
        pl.scan_parquet(
            event_path
        )

        .with_columns(

            (
                pl.col("first_payment_month").dt.offset_by("-1mo").dt.year()
                * 12
                + pl.col("first_payment_month").dt.offset_by("-1mo").dt.month()
            )
            .alias(
                "_origin_index"
            ),

            date_month_index("first_payment_month").alias(
                "_first_payment_index"
            ),

            yyyymm_month_index(
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
                    "_origin_index"
                )
            )
            .cast(
                pl.Int32
            )
            .alias(
                "duration_months"
            )

        )
    )


    # =====================================================
    # EVENT-LEVEL DURATION AUDIT
    # =====================================================

    event_summary = (
        events

        .select(

            pl.len()
            .alias(
                "loans"
            ),

            (
                pl.col(
                    "duration_months"
                )
                < 0
            )
            .sum()
            .alias(
                "negative_duration"
            ),

            (
                pl.col(
                    "duration_months"
                )
                == 0
            )
            .sum()
            .alias(
                "zero_duration"
            ),

            (
                pl.col(
                    "duration_months"
                )
                == 1
            )
            .sum()
            .alias(
                "duration_one"
            ),

            pl.col(
                "duration_months"
            )
            .min()
            .alias(
                "min_duration"
            ),

            pl.col(
                "duration_months"
            )
            .max()
            .alias(
                "max_duration"
            ),

            pl.col(
                "duration_months"
            )
            .median()
            .alias(
                "median_duration"
            ),

        )

        .collect()
    )


    # =====================================================
    # DURATION <= 0 BY EVENT TYPE
    # =====================================================

    nonpositive_by_event = (
        events

        .filter(
            pl.col(
                "duration_months"
            )
            <= 0
        )

        .group_by(
            "event_type"
        )

        .len()

        .collect()
    )


    nonpositive_default = 0
    nonpositive_prepay = 0
    nonpositive_censor = 0


    for row in nonpositive_by_event.iter_rows(
        named=True
    ):

        if row["event_type"] == "DEFAULT":

            nonpositive_default = int(
                row["len"]
            )

        elif row["event_type"] == "PREPAYMENT":

            nonpositive_prepay = int(
                row["len"]
            )

        elif row["event_type"] == "CENSOR":

            nonpositive_censor = int(
                row["len"]
            )


    # =====================================================
    # MONTHLY PERFORMANCE CLOCK AUDIT
    #
    # Fixed clock from the operational origination-month proxy.
    # =====================================================

    event_origin = (
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
            event_origin,
            on="loan_id",
            how="inner",
        )

        .with_columns(

            yyyymm_month_index(
                "reporting_period_num"
            )
            .alias(
                "_reporting_index"
            ),

            (pl.col("first_payment_month").dt.offset_by("-1mo")
             .dt.year() * 12
             + pl.col("first_payment_month").dt.offset_by("-1mo").dt.month())
            .alias(
                "_origin_index"
            ),

        )

        .with_columns(

            (
                pl.col(
                    "_reporting_index"
                )
                -
                pl.col(
                    "_origin_index"
                )
            )
            .cast(
                pl.Int32
            )
            .alias(
                "analysis_age_months"
            )

        )
    )


    # =====================================================
    # MONTHLY AGE COUNTS
    # =====================================================

    perf_summary = (
        perf

        .select(

            pl.len()
            .alias(
                "performance_rows"
            ),

            (
                pl.col(
                    "analysis_age_months"
                )
                < 0
            )
            .sum()
            .alias(
                "negative_analysis_age_rows"
            ),

            (
                pl.col(
                    "analysis_age_months"
                )
                == 0
            )
            .sum()
            .alias(
                "age_zero_rows"
            ),

            pl.col(
                "analysis_age_months"
            )
            .min()
            .alias(
                "min_analysis_age"
            ),

            pl.col(
                "analysis_age_months"
            )
            .max()
            .alias(
                "max_analysis_age"
            ),

        )

        .collect()
    )


    # =====================================================
    # COMPARE TO FREDDIE MAC LOAN AGE
    #
    # Only compare rows that have NOT been modified.
    # Modified loan age may use Modification First Payment
    # Date according to Freddie Mac documentation.
    # =====================================================

    unmodified_age_mismatch = (
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
                    "loan_age"
                )
                !=
                pl.col(
                    "analysis_age_months"
                )
            )

        )

        .select(
            pl.len()
            .alias(
                "n"
            )
        )

        .collect()["n"][0]
    )


    modified_rows = (
        perf

        .filter(
            pl.col(
                "modification_flag"
            )
            .is_not_null()
        )

        .select(
            pl.len()
            .alias(
                "n"
            )
        )

        .collect()["n"][0]
    )


    modified_loans = (
        perf

        .filter(
            pl.col(
                "modification_flag"
            )
            .is_not_null()
        )

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
    # EVENT MONTH VS FIRST PAYMENT MONTH
    # =====================================================

    event_before_first_payment = (
        events

        .filter(
            pl.col(
                "_event_index"
            )
            <
            pl.col(
                "_first_payment_index"
            )
        )

        .select(
            pl.len()
            .alias(
                "n"
            )
        )

        .collect()["n"][0]
    )


    event_at_first_payment = (
        events

        .filter(
            pl.col(
                "_event_index"
            )
            ==
            pl.col(
                "_first_payment_index"
            )
        )

        .select(
            pl.len()
            .alias(
                "n"
            )
        )

        .collect()["n"][0]
    )


    # =====================================================
    # EVENT MONTH AFTER LAST REPORT
    # =====================================================

    event_after_last_report = (
        events

        .filter(
            pl.col(
                "event_month"
            )
            >
            pl.col(
                "last_observed_month"
            )
        )

        .select(
            pl.len()
            .alias(
                "n"
            )
        )

        .collect()["n"][0]
    )


    # =====================================================
    # RESULT
    # =====================================================

    result = {

        "year":
            year,

        "loans":
            int(
                event_summary[
                    "loans"
                ][0]
            ),

        "negative_duration":
            int(
                event_summary[
                    "negative_duration"
                ][0]
            ),

        "zero_duration":
            int(
                event_summary[
                    "zero_duration"
                ][0]
            ),

        "duration_one":
            int(
                event_summary[
                    "duration_one"
                ][0]
            ),

        "min_duration":
            int(
                event_summary[
                    "min_duration"
                ][0]
            ),

        "max_duration":
            int(
                event_summary[
                    "max_duration"
                ][0]
            ),

        "median_duration":
            float(
                event_summary[
                    "median_duration"
                ][0]
            ),

        "event_before_first_payment":
            int(
                event_before_first_payment
            ),

        "event_at_first_payment":
            int(
                event_at_first_payment
            ),

        "nonpositive_default":
            int(
                nonpositive_default
            ),

        "nonpositive_prepay":
            int(
                nonpositive_prepay
            ),

        "nonpositive_censor":
            int(
                nonpositive_censor
            ),

        "performance_rows":
            int(
                perf_summary[
                    "performance_rows"
                ][0]
            ),

        "negative_analysis_age_rows":
            int(
                perf_summary[
                    "negative_analysis_age_rows"
                ][0]
            ),

        "age_zero_rows":
            int(
                perf_summary[
                    "age_zero_rows"
                ][0]
            ),

        "min_analysis_age":
            int(
                perf_summary[
                    "min_analysis_age"
                ][0]
            ),

        "max_analysis_age":
            int(
                perf_summary[
                    "max_analysis_age"
                ][0]
            ),

        "unmodified_age_mismatch":
            int(
                unmodified_age_mismatch
            ),

        "modified_rows":
            int(
                modified_rows
            ),

        "modified_loans":
            int(
                modified_loans
            ),

        "event_after_last_report":
            int(
                event_after_last_report
            ),

    }


    # =====================================================
    # PRINT
    # =====================================================

    print(
        f"Loans:                             "
        f"{result['loans']:,}"
    )

    print(
        f"Duration < 0:                      "
        f"{result['negative_duration']:,}"
    )

    print(
        f"Duration = 0:                      "
        f"{result['zero_duration']:,}"
    )

    print(
        f"Duration = 1:                      "
        f"{result['duration_one']:,}"
    )

    print(
        f"Duration min / median / max:       "
        f"{result['min_duration']} / "
        f"{result['median_duration']} / "
        f"{result['max_duration']}"
    )

    print(
        f"Event before first payment:        "
        f"{result['event_before_first_payment']:,}"
    )

    print(
        f"Event at first payment:            "
        f"{result['event_at_first_payment']:,}"
    )

    print(
        f"Non-positive DEFAULT:              "
        f"{result['nonpositive_default']:,}"
    )

    print(
        f"Non-positive PREPAYMENT:           "
        f"{result['nonpositive_prepay']:,}"
    )

    print(
        f"Non-positive CENSOR:               "
        f"{result['nonpositive_censor']:,}"
    )

    print(
        f"Monthly analysis age < 0 rows:     "
        f"{result['negative_analysis_age_rows']:,}"
    )

    print(
        f"Monthly analysis age = 0 rows:     "
        f"{result['age_zero_rows']:,}"
    )

    print(
        f"Unmodified Freddie-age mismatch:   "
        f"{result['unmodified_age_mismatch']:,}"
    )

    print(
        f"Modified loans:                    "
        f"{result['modified_loans']:,}"
    )

    print(
        f"Known event after last report:     "
        f"{result['event_after_last_report']:,}"
    )


    return result


# =========================================================
# MARKDOWN REPORT
# =========================================================

def write_report(
    summary: pl.DataFrame,
):

    lines = []

    lines.append(
        "# Freddie Mac Loan Age / Survival Duration Audit"
    )

    lines.append("")

    lines.append(
        "Primary survival clock uses an operational origination-month proxy "
        "(First Payment Month minus one calendar month) as a fixed origin."
    )

    lines.append("")

    lines.append(
        "`duration_months = event_month - operational_origination_month_proxy` "
        "on a calendar-month scale; the first payment month is month 1."
    )

    lines.append("")

    lines.append(
        "The Freddie Mac Loan Age field is retained for audit "
        "but is not used as the primary survival clock because "
        "its calculation can reset after loan modification."
    )

    lines.append("")

    lines.append(
        "| Year | Loans | Duration <0 | Duration =0 | "
        "Duration =1 | Min | Median | Max | "
        "Event before FP | Unmodified age mismatch | "
        "Modified loans | Event after last report |"
    )

    lines.append(
        "|---:|---:|---:|---:|---:|---:|---:|---:|"
        "---:|---:|---:|---:|"
    )


    for row in summary.iter_rows(
        named=True
    ):

        lines.append(

            f"| {row['year']} "
            f"| {row['loans']:,} "
            f"| {row['negative_duration']:,} "
            f"| {row['zero_duration']:,} "
            f"| {row['duration_one']:,} "
            f"| {row['min_duration']} "
            f"| {row['median_duration']} "
            f"| {row['max_duration']} "
            f"| {row['event_before_first_payment']:,} "
            f"| {row['unmodified_age_mismatch']:,} "
            f"| {row['modified_loans']:,} "
            f"| {row['event_after_last_report']:,} |"

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
        "FREDDIE MAC LOAN AGE / DURATION AUDIT"
    )

    print(
        "2016–2026"
    )

    print(
        "=" * 80
    )


    results = []


    for year in STUDY_YEARS:

        results.append(
            audit_year(
                year
            )
        )


    summary = (
        pl.DataFrame(
            results
        )
        .sort(
            "year"
        )
    )


    summary.write_csv(
        SUMMARY_FILE
    )


    write_report(
        summary
    )


    # =====================================================
    # TOTALS
    # =====================================================

    print(
        "\n"
        + "=" * 80
    )

    print(
        "LOAN AGE / DURATION AUDIT TOTALS"
    )

    print(
        "=" * 80
    )


    print(
        f"Loans:                         "
        f"{summary['loans'].sum():,}"
    )

    print(
        f"Negative duration:             "
        f"{summary['negative_duration'].sum():,}"
    )

    print(
        f"Zero duration:                 "
        f"{summary['zero_duration'].sum():,}"
    )

    print(
        f"Event before first payment:    "
        f"{summary['event_before_first_payment'].sum():,}"
    )

    print(
        f"Non-positive DEFAULT:          "
        f"{summary['nonpositive_default'].sum():,}"
    )

    print(
        f"Non-positive PREPAYMENT:       "
        f"{summary['nonpositive_prepay'].sum():,}"
    )

    print(
        f"Non-positive CENSOR:           "
        f"{summary['nonpositive_censor'].sum():,}"
    )

    print(
        f"Unmodified age mismatch rows:  "
        f"{summary['unmodified_age_mismatch'].sum():,}"
    )

    print(
        f"Modified loans:                "
        f"{summary['modified_loans'].sum():,}"
    )

    print(
        f"Event after last report:       "
        f"{summary['event_after_last_report'].sum():,}"
    )


    print(
        "\nFILES CREATED:"
    )

    print(
        f"  {SUMMARY_FILE}"
    )

    print(
        f"  {REPORT_FILE}"
    )


    print(
        "\n"
        + "=" * 80
    )

    print(
        "✓ LOAN AGE / DURATION AUDIT HOÀN THÀNH"
    )

    print(
        "=" * 80
    )


if __name__ == "__main__":
    main()
