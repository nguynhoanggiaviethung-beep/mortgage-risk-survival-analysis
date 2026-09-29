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
    """Tính tuổi tại thời điểm vào và ra khỏi quan sát."""
    result = (
        event_map
        .with_columns(
            pl.col("first_payment_month")
            .dt.offset_by("-1mo")
            .alias("operational_origination_date")
        )
        .with_columns(
            _date_month_index("operational_origination_date")
            .alias("_origin_index"),
            _yyyymm_month_index("first_observed_month")
            .alias("_entry_index"),

            _yyyymm_month_index("event_month")
            .alias("_exit_index"),
        )
        .with_columns(
            # Time origin is the operational origination month proxy.
            # The first payment month is therefore analysis month 1.
            (pl.col("_entry_index") - pl.col("_origin_index"))
            .cast(pl.Int32)
            .alias("entry_time_month"),

            (pl.col("_exit_index") - pl.col("_origin_index"))
            .cast(pl.Int32)
            .alias("exit_time_month"),
        )
        .with_columns(
            (
                pl.col("exit_time_month")
                - pl.col("entry_time_month")
            ).alias("observed_duration_months"),

            # Giữ giá trị gốc để kiểm tra, kể cả khi âm.
            pl.col("exit_time_month").alias("raw_duration_months"),

            pl.when(
                pl.col("operational_origination_date").is_null()
                | pl.col("entry_time_month").is_null()
                | pl.col("exit_time_month").is_null()
            )
            .then(pl.lit("MISSING_TIME"))

            .when(
                (pl.col("entry_time_month") < 0)
                | (pl.col("exit_time_month") < 0)
            )
            .then(pl.lit("NEGATIVE_AGE"))

            .when(
                pl.col("exit_time_month") < pl.col("entry_time_month")
            )
            .then(pl.lit("EVENT_BEFORE_ENTRY"))

            .when(
                pl.col("exit_time_month") == pl.col("entry_time_month")
            )
            .then(pl.lit("ZERO_OBSERVED_INTERVAL"))

            .when(pl.col("event_month") > 202603)
            .then(pl.lit("AFTER_CUTOFF"))

            .otherwise(pl.lit(None, dtype=pl.String))
            .alias("survival_exclusion_reason"),
        )
        .with_columns(
            pl.col("survival_exclusion_reason")
            .is_null()
            .alias("survival_eligible"),

            (pl.col("event_type") == "DEFAULT")
            .cast(pl.Int8)
            .alias("default_event"),

            (pl.col("event_type") == "PREPAYMENT")
            .cast(pl.Int8)
            .alias("prepayment_event"),

            pl.col("event_code")
            .cast(pl.Int8)
            .alias("competing_event_code"),
        )
        .with_columns(
            pl.when(pl.col("survival_eligible"))
            .then(pl.col("exit_time_month"))
            .otherwise(None)
            .cast(pl.Int32)
            .alias("duration_months"),
        )
        .drop("_origin_index", "_entry_index", "_exit_index")
        .sort("loan_id")
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
def export_loan_age(years):
    """Xuất tuổi theo tháng; giữ dòng bất thường để audit."""
    import json
    from src.config import PROCESSED_DIR, PROJECT_ROOT
    from src.data.event_definition import build_event_mapping_year

    years = sorted(set(int(year) for year in years))
    if not years:
        raise ValueError("Cần chỉ định ít nhất một năm.")

    parts = []

    for year in years:
        # Tạo lại để không dùng event theo định nghĩa cũ.
        build_event_mapping_year(year, force=True)
        survival_path = build_survival_duration_year(year, force=True)

        survival = pl.scan_parquet(survival_path).select(
            "loan_id",
            "vintage_year",
            "first_payment_month",
            "operational_origination_date",
            "entry_time_month",
            "exit_time_month",
            "observed_duration_months",
            "event_month",
            "event_type",
            "event_code",
            "survival_eligible",
            "survival_exclusion_reason",
        )

        monthly = (
            pl.scan_parquet(MODEL_DIR / f"perf_clean_{year}.parquet")
            .select(
                "loan_id",
                "reporting_period_num",
                pl.col("loan_age").alias("freddie_loan_age"),
            )
            .with_columns(
                pl.col("reporting_period_num")
                .cast(pl.String)
                .str.strptime(pl.Date, "%Y%m", strict=True)
                .alias("performance_month")
            )
            .filter(pl.col("reporting_period_num") <= 202603)
            .join(
                survival,
                on="loan_id",
                how="left",
                validate="m:1",
            )
            .sort(["loan_id", "performance_month"])
            .with_columns(
                (
                    _date_month_index("performance_month")
                    - _date_month_index("operational_origination_date")
                )
                .cast(pl.Int32)
                .alias("analysis_time_month"),

                _date_month_index("performance_month")
                .diff()
                .over("loan_id")
                .alias("month_step"),
            )
            .with_columns(
                (pl.col("analysis_time_month") < 0)
                .fill_null(False)
                .alias("negative_age_flag"),

                (pl.col("month_step") > 1)
                .fill_null(False)
                .alias("reporting_gap_flag"),

                (pl.col("month_step") <= 0)
                .fill_null(False)
                .alias("duplicate_or_order_flag"),

                (pl.col("reporting_period_num") > pl.col("event_month"))
                .fill_null(False)
                .alias("after_exit_flag"),

                (
                    pl.col("analysis_time_month").is_null()
                    | pl.col("entry_time_month").is_null()
                    | pl.col("exit_time_month").is_null()
                ).alias("missing_time_flag"),
            )
            .with_columns(
                # Cờ chọn các dòng nằm trong khoảng quan sát hợp lệ.
                (
                    pl.col("survival_eligible").fill_null(False)
                    & ~pl.col("negative_age_flag")
                    & ~pl.col("duplicate_or_order_flag")
                    & ~pl.col("after_exit_flag")
                    & ~pl.col("missing_time_flag")
                ).alias("within_observation_window")
            )
        )
        parts.append(monthly)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    report_dir = PROJECT_ROOT / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    output = PROCESSED_DIR / "loan_age.parquet"
    temporary = PROCESSED_DIR / "loan_age.tmp.parquet"

    pl.concat(parts).sort(
        ["loan_id", "performance_month"]
    ).sink_parquet(temporary, compression="zstd")

    saved = pl.scan_parquet(temporary)

    # Kiểm tra trên chính file vừa xuất.
    checks = saved.select(
        pl.len().alias("rows"),
        pl.col("loan_id").n_unique().alias("loans"),
        pl.col("loan_id").is_null().sum().alias("missing_loan_id"),
        pl.col("negative_age_flag").sum().alias("negative_age_rows"),
        pl.col("reporting_gap_flag").sum().alias("reporting_gap_rows"),
        pl.col("duplicate_or_order_flag").sum().alias("order_error_rows"),
        pl.col("after_exit_flag").sum().alias("after_exit_rows"),
        pl.col("missing_time_flag").sum().alias("missing_time_rows"),
        (
            pl.col("within_observation_window")
            & (pl.col("analysis_time_month") < 0)
        ).sum().alias("eligible_negative_age_rows"),
    ).collect().to_dicts()[0]

    duplicate_keys = (
        saved.group_by(["loan_id", "performance_month"])
        .len()
        .filter(pl.col("len") > 1)
        .select(pl.len())
        .collect()
        .item()
    )

    exclusions = (
        saved.select("loan_id", "survival_exclusion_reason")
        .unique()
        .filter(pl.col("survival_exclusion_reason").is_not_null())
        .group_by("survival_exclusion_reason")
        .len()
        .collect()
        .to_dicts()
    )

    failed = (
        checks["missing_loan_id"] > 0
        or checks["missing_time_rows"] > 0
        or checks["order_error_rows"] > 0
        or duplicate_keys > 0
        or checks["eligible_negative_age_rows"] > 0
    )

    warnings = (
        checks["negative_age_rows"] > 0
        or checks["reporting_gap_rows"] > 0
        or checks["after_exit_rows"] > 0
        or bool(exclusions)
    )

    report = {
        "years": years,
        "cutoff": 202603,
        "time_origin": (
            "operational_origination_date proxy (first payment month - 1 calendar month); "
            "first payment month is analysis month 1"
        ),
        "unit": "calendar months",
        "checks": checks,
        "duplicate_loan_month_keys": duplicate_keys,
        "excluded_loans_by_reason": exclusions,
        "status": (
            "FAIL" if failed
            else "PASS_WITH_WARNING" if warnings
            else "PASS"
        ),
    }

    report_path = report_dir / "loan_age_validation.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(report, ensure_ascii=False, indent=2))

    if failed:
        raise ValueError(
            f"Kiểm tra không đạt. Xem {report_path}. "
            "Chưa thay file loan_age.parquet."
        )

    temporary.replace(output)
    print(f"Đã xuất: {output}")
    print(f"Báo cáo: {report_path}")
