from __future__ import annotations

from pathlib import Path

import polars as pl

from src.config import MODEL_DIR


# =========================================================
# EVENT LABELS
# =========================================================

EVENT_CENSOR = 0
EVENT_DEFAULT = 1
EVENT_PREPAYMENT = 2

ALLOWED_EVENT_SOURCES_AFTER_LAST_REPORT = [
    "ZB01_PREPAYMENT",
    "ZB02",
    "ZB03",
    "ZB09",
    "ZB15_WHOLE_LOAN_SALE",
    "ZB16_REPERFORMING_SECURITIZATION",
    "ZB96_DEFECT",
    "MATURITY",
]


# =========================================================
# HELPERS
# =========================================================

def _first_month_when(
    condition: pl.Expr,
    month_column: pl.Expr,
) -> pl.Expr:
    """Return the earliest YYYYMM value satisfying condition."""
    return (
        pl.when(condition)
        .then(month_column)
        .otherwise(None)
        .min()
    )


def _month_number_to_date(column: str) -> pl.Expr:
    """Convert integer YYYYMM into Date on the first day of month."""
    return (
        pl.col(column)
        .cast(pl.String)
        .str.strptime(
            pl.Date,
            "%Y%m",
            strict=False,
        )
    )


# =========================================================
# BUILD EVENT MAPPING FROM LAZYFRAMES
# =========================================================

def build_event_mapping(
    orig: pl.LazyFrame,
    perf: pl.LazyFrame,
    exclude_missing_effective_date: bool = False,
) -> pl.LazyFrame:
    """
    D90/RA là default evidence; ZBC 02/03/09 là fallback default,
    ZBC 01 là prepayment, còn 15/16/96 là censoring termination.
    Nếu default và prepayment cùng tháng, default được ưu tiên và gắn cờ.
    event_month là tháng kết thúc quan sát, kể cả censor.
    Đầu vào: orig_clean_YYYY và perf_clean_YYYY hiện có.
    """
    cutoff = 202603
    known_codes = ["01", "02", "03", "09", "15", "16", "96"]

    # Chỉ đọc những cột cần dùng.
    monthly = perf.select(
        "loan_id",
        "reporting_period_num",
        "delinquency_num",
        "is_ra",
        "zero_balance_code",
        "zero_balance_effective_date",
    ).with_columns(
        pl.col("zero_balance_code")
        .cast(pl.String)
        .str.strip_chars()
        .replace("", None)
        .alias("_code"),
        pl.col("zero_balance_effective_date")
        .cast(pl.String)
        .str.strip_chars()
        .replace("", None)
        .str.strptime(pl.Date, "%Y%m", strict=False)
        .alias("_effective_date"),
        pl.col("reporting_period_num")
        .cast(pl.String)
        .str.strptime(pl.Date, "%Y%m", strict=False)
        .alias("_report_date"),
    )

    # Không âm thầm bỏ tháng báo cáo bị thiếu/sai định dạng.
    bad_dates = (
        monthly.filter(pl.col("_report_date").is_null())
        .select("loan_id", "reporting_period_num")
        .limit(5)
        .collect()
    )
    if bad_dates.height:
        raise ValueError(f"Tháng báo cáo thiếu hoặc sai:\n{bad_dates}")

    monthly = monthly.filter(
        pl.col("reporting_period_num") <= cutoff
    )

    # Mã chưa có trong đặc tả phải được kiểm tra, không tự gán censor.
    unknown = (
        monthly.filter(
            pl.col("_code").is_not_null()
            & ~pl.col("_code").is_in(known_codes)
        )
        .select("loan_id", "_code")
        .limit(5)
        .collect()
    )
    if unknown.height:
        raise ValueError(f"Zero Balance Code chưa có mapping:\n{unknown}")

    # Lấy đầy đủ các bản ghi thiếu/sai ngày để audit.
    missing_dates = (
        monthly.filter(
            pl.col("_code").is_not_null()
            & pl.col("_effective_date").is_null()
        )
        .select(
            "loan_id",
            "reporting_period_num",
            "_code",
            "zero_balance_effective_date",
        )
        .collect()
    )

    if missing_dates.height:
        if not exclude_missing_effective_date:
            raise ValueError(
                "Có mã kết thúc nhưng thiếu/sai ngày hiệu lực:\n"
                f"{missing_dates.head(5)}"
            )

        # Loại toàn bộ lịch sử của khoản bị lỗi khỏi mẫu event.
        # Không chỉ bỏ dòng lỗi rồi gán khoản đó thành right-censor.
        excluded_ids = missing_dates.select("loan_id").unique()

        print(
            f"Tách {excluded_ids.height:,} khoản thiếu/sai "
            "ngày hiệu lực khỏi mẫu; cần kiểm tra riêng.",
            flush=True,
        )

        monthly = monthly.join(
            excluded_ids.lazy(),
            on="loan_id",
            how="anti",
        )

    monthly = monthly.with_columns(
        (
            pl.col("_effective_date").dt.year() * 100
            + pl.col("_effective_date").dt.month()
        ).cast(pl.Int32).alias("_effective_month")
    )

    # Thông tin theo dõi: chỉ khoản có performance trước cutoff.
    followup = monthly.group_by("loan_id").agg(
        pl.col("reporting_period_num").min().alias("first_observed_month"),
        pl.col("reporting_period_num").max().alias("last_observed_month"),
    )
    raw_zbc = (
        monthly.filter(pl.col("_code").is_not_null())
        .sort(["loan_id", "_effective_month"])
        .group_by("loan_id", maintain_order=True)
        .agg(pl.col("_code").first().alias("raw_zero_balance_code"))
    )

    # ZBC 01/02/03/09/15/16/96 dùng ngày hiệu lực chính thức.
    zb_candidates = (
        monthly.filter(
            pl.col("_code").is_not_null()
            & (pl.col("_effective_month") <= cutoff)
        )
        .with_columns(
            pl.when(pl.col("_code").is_in(["02", "03", "09"]))
            .then(pl.lit("DEFAULT"))
            .when(pl.col("_code") == "01")
            .then(pl.lit("PREPAYMENT"))
            .otherwise(pl.lit("CENSOR"))
            .alias("_type"),
            pl.when(pl.col("_code") == "01")
            .then(pl.lit("ZB01_PREPAYMENT"))
            .when(pl.col("_code") == "15")
            .then(pl.lit("ZB15_WHOLE_LOAN_SALE"))
            .when(pl.col("_code") == "16")
            .then(pl.lit("ZB16_REPERFORMING_SECURITIZATION"))
            .when(pl.col("_code") == "96")
            .then(pl.lit("ZB96_DEFECT"))
            .otherwise(pl.concat_str([pl.lit("ZB"), pl.col("_code")]))
            .alias("_source"),
            pl.col("_code").alias("_raw_code"),
            (pl.col("_effective_month") != pl.col("reporting_period_num"))
            .alias("_date_mismatch"),
        )
        .select(
            "loan_id",
            pl.col("_effective_month").alias("_month"),
            "_type",
            "_source",
            "_raw_code",
            "_date_mismatch",
        )
    )

    # First 90+ DPD and RA month provide observed default timing.
    default_candidates = pl.concat(
        [
            monthly.filter(pl.col("delinquency_num") >= 3).select(
                "loan_id",
                pl.col("reporting_period_num").alias("_month"),
                pl.lit("DEFAULT").alias("_type"),
                pl.lit("D90").alias("_source"),
                pl.lit(None, dtype=pl.String).alias("_raw_code"),
                pl.lit(False).alias("_date_mismatch"),
            ),
            monthly.filter(pl.col("is_ra").fill_null(False)).select(
                "loan_id",
                pl.col("reporting_period_num").alias("_month"),
                pl.lit("DEFAULT").alias("_type"),
                pl.lit("RA").alias("_source"),
                pl.lit(None, dtype=pl.String).alias("_raw_code"),
                pl.lit(False).alias("_date_mismatch"),
            ),
        ],
        how="vertical",
    )
    candidates = pl.concat([zb_candidates, default_candidates], how="vertical")

    # Earliest event wins; within one month DEFAULT > PREPAYMENT > CENSOR.
    selected = (
        candidates.with_columns(
            pl.when(pl.col("_type") == "DEFAULT")
            .then(pl.lit(0))
            .when(pl.col("_type") == "PREPAYMENT")
            .then(pl.lit(1))
            .otherwise(pl.lit(2))
            .alias("_priority")
        )
        .sort(["loan_id", "_month", "_priority"])
        .group_by("loan_id", maintain_order=True)
        .agg(
            pl.col("_month").first().alias("_selected_month"),
            pl.col("_type").first().alias("_selected_type"),
            pl.col("_source").first().alias("event_source"),
            pl.col("_raw_code").first().alias("_selected_raw_code"),
            pl.col("_date_mismatch").first().alias("effective_reporting_month_mismatch"),
            (
                (pl.col("_month") == pl.col("_month").first())
                & (pl.col("_type") == "DEFAULT")
            ).any().alias("_has_default_at_first_month"),
            (
                (pl.col("_month") == pl.col("_month").first())
                & (pl.col("_type") == "PREPAYMENT")
            ).any().alias("_has_prepay_at_first_month"),
        )
    )

    result = (
        followup.join(selected, on="loan_id", how="left")
        .join(raw_zbc, on="loan_id", how="left")
        .join(
            orig.select(
                "loan_id",
                "vintage_year",
                "first_payment_month",
                "maturity_month",
            ),
            on="loan_id",
            how="left",
            validate="m:1",
        )
        .with_columns(
            pl.coalesce("_selected_month", "last_observed_month")
            .alias("event_month"),
            pl.coalesce("_selected_raw_code", "raw_zero_balance_code")
            .alias("raw_zero_balance_code"),
            pl.col("_selected_type").fill_null("CENSOR")
            .alias("event_type"),
            pl.col("effective_reporting_month_mismatch")
            .fill_null(False),
        )
        .with_columns(
            pl.when(pl.col("event_type") == "DEFAULT")
            .then(pl.lit(EVENT_DEFAULT))
            .when(pl.col("event_type") == "PREPAYMENT")
            .then(pl.lit(EVENT_PREPAYMENT))
            .otherwise(pl.lit(EVENT_CENSOR))
            .cast(pl.Int8)
            .alias("event_code"),

            pl.col("event_source").fill_null("RIGHT_CENSOR"),

            _month_number_to_date("event_month").alias("event_date"),
            (pl.col("event_type") == "DEFAULT").alias("default_flag"),
            (pl.col("event_type") == "PREPAYMENT").alias("prepayment_flag"),
            (pl.col("event_type") == "CENSOR").alias("censor_flag"),
            (
                pl.col("_has_default_at_first_month").fill_null(False)
                & pl.col("_has_prepay_at_first_month").fill_null(False)
            ).alias("same_month_default_prepay_flag"),
        )
        .with_columns(
            (pl.col("event_month") < pl.col("first_observed_month"))
            .alias("event_before_entry_flag"),
            (pl.col("event_month") > pl.col("last_observed_month"))
            .alias("event_after_last_report_flag"),
        )
        .drop(
            "_selected_month", "_selected_type", "_selected_raw_code",
            "_has_default_at_first_month",
            "_has_prepay_at_first_month",
        )
        .sort("loan_id")
    )

    return result

# =========================================================
# BUILD ONE VINTAGE
# =========================================================

def build_event_mapping_year(
    year: int,
    force: bool = False,
) -> Path:

    year = int(year)

    orig_path = MODEL_DIR / f"orig_clean_{year}.parquet"
    perf_path = MODEL_DIR / f"perf_clean_{year}.parquet"
    output_path = MODEL_DIR / f"event_map_{year}.parquet"
    temp_path = MODEL_DIR / f"event_map_{year}.tmp.parquet"

    if not orig_path.exists():
        raise FileNotFoundError(
            f"Không tìm thấy:\n{orig_path}"
        )

    if not perf_path.exists():
        raise FileNotFoundError(
            f"Không tìm thấy:\n{perf_path}"
        )

    if output_path.exists() and not force:
        print(
            f"✓ event_map_{year}.parquet "
            f"đã tồn tại, bỏ qua."
        )
        return output_path

    temp_path.unlink(missing_ok=True)

    orig = pl.scan_parquet(orig_path)
    perf = pl.scan_parquet(perf_path)

    from src.config import PROJECT_ROOT

    # Lưu các khoản bị tách trước khi xây dựng bảng event.
    report_dir = PROJECT_ROOT / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    missing_date_audit = (
        perf.filter(pl.col("reporting_period_num") <= 202603)
        .with_columns(
            pl.col("zero_balance_code")
            .cast(pl.String)
            .str.strip_chars()
            .replace("", None)
            .alias("_code"),

            pl.col("zero_balance_effective_date")
            .cast(pl.String)
            .str.strip_chars()
            .replace("", None)
            .str.strptime(pl.Date, "%Y%m", strict=False)
            .alias("_effective_date"),
        )
        .filter(
            pl.col("_code").is_not_null()
            & pl.col("_effective_date").is_null()
        )
        .select(
            "loan_id",
            "reporting_period_num",
            "zero_balance_code",
            "zero_balance_effective_date",
        )
        .with_columns(
            pl.lit("MISSING_OR_INVALID_EFFECTIVE_DATE")
            .alias("exclusion_reason")
        )
        .collect()
    )

    missing_date_audit.write_csv(
        report_dir / f"event_missing_date_{year}.csv"
    )

    event_map = build_event_mapping(
        orig,
        perf,
        exclude_missing_effective_date=True,
    )

    event_map.sink_parquet(
        temp_path,
        compression="zstd",
    )

    temp_path.replace(output_path)

    return output_path


# =========================================================
# VALIDATE ONE EVENT MAP
# =========================================================

def validate_event_mapping_year(year: int) -> dict:

    year = int(year)

    perf_path = MODEL_DIR / f"perf_clean_{year}.parquet"
    event_path = MODEL_DIR / f"event_map_{year}.parquet"

    perf = pl.scan_parquet(perf_path)
    events = pl.scan_parquet(event_path)

    perf_loans = (
        perf
        .select(
            pl.col("loan_id")
            .n_unique()
            .alias("n")
        )
        .collect()["n"][0]
    )

    # Event rows deliberately omit loans with an unusable official
    # zero-balance effective date. Reconcile those explicit exclusions
    # separately instead of treating them as a pipeline failure.
    excluded_loans = (
        perf
        .filter(pl.col("reporting_period_num") <= 202603)
        .with_columns(
            pl.col("zero_balance_code")
            .cast(pl.String)
            .str.strip_chars()
            .replace("", None)
            .alias("_code"),
            pl.col("zero_balance_effective_date")
            .cast(pl.String)
            .str.strip_chars()
            .replace("", None)
            .str.strptime(pl.Date, "%Y%m", strict=False)
            .alias("_effective_date"),
        )
        .filter(pl.col("_code").is_not_null() & pl.col("_effective_date").is_null())
        .select(pl.col("loan_id").n_unique().alias("n"))
        .collect()["n"][0]
    )

    event_rows = (
        events
        .select(
            pl.len().alias("n")
        )
        .collect()["n"][0]
    )

    event_unique_loans = (
        events
        .select(
            pl.col("loan_id")
            .n_unique()
            .alias("n")
        )
        .collect()["n"][0]
    )

    duplicate_event_loans = (
        events
        .group_by("loan_id")
        .len()
        .filter(pl.col("len") > 1)
        .select(pl.len().alias("n"))
        .collect()["n"][0]
    )

    invalid_event_types = (
        events
        .filter(
            ~pl.col("event_type").is_in(
                [
                    "DEFAULT",
                    "PREPAYMENT",
                    "CENSOR",
                ]
            )
        )
        .select(pl.len().alias("n"))
        .collect()["n"][0]
    )

    missing_event_month = (
        events
        .filter(
            pl.col("event_month").is_null()
        )
        .select(pl.len().alias("n"))
        .collect()["n"][0]
    )

    # =====================================================
    # EVENT AFTER LAST REPORT
    #
    # A known ZB/maturity event may validly have an official
    # effective month later than last_observed_month.
    #
    # D90 / RA / RIGHT_CENSOR are NOT allowed to do this.
    # =====================================================

    known_event_after_last_observation = (
        events
        .filter(
            (pl.col("event_month") > pl.col("last_observed_month"))
            & pl.col("event_source").is_in(
                ALLOWED_EVENT_SOURCES_AFTER_LAST_REPORT
            )
        )
        .select(pl.len().alias("n"))
        .collect()["n"][0]
    )

    event_after_last_observation = (
        events
        .filter(
            (pl.col("event_month") > pl.col("last_observed_month"))
            &
            ~pl.col("event_source").is_in(
                ALLOWED_EVENT_SOURCES_AFTER_LAST_REPORT
            )
        )
        .select(pl.len().alias("n"))
        .collect()["n"][0]
    )

    counts = (
        events
        .group_by("event_type")
        .len()
        .collect()
    )

    same_month_conflicts = (
        events
        .filter(
            pl.col("same_month_default_prepay_flag")
        )
        .select(pl.len().alias("n"))
        .collect()["n"][0]
    )

    # =====================================================
    # CRITICAL VALIDATION
    # =====================================================

    if perf_loans != event_rows + excluded_loans:
        raise RuntimeError(
            f"{year}: Event rows + số khoản loại trừ có ngày hiệu lực "
            f"không hợp lệ ({event_rows:,} + {excluded_loans:,}) "
            f"không bằng số Performance loans ({perf_loans:,})."
        )

    if event_rows != event_unique_loans:
        raise RuntimeError(
            f"{year}: Event mapping "
            f"không unique theo Loan ID."
        )

    if duplicate_event_loans != 0:
        raise RuntimeError(
            f"{year}: Có duplicate Loan ID "
            f"trong event mapping."
        )

    if invalid_event_types != 0:
        raise RuntimeError(
            f"{year}: Có event_type không hợp lệ."
        )

    if missing_event_month != 0:
        raise RuntimeError(
            f"{year}: Có event_month bị null."
        )

    if event_after_last_observation != 0:
        raise RuntimeError(
            f"{year}: Có event không hợp lệ xảy ra sau "
            f"last observed month."
        )

    count_dict = {
        row["event_type"]: row["len"]
        for row in counts.iter_rows(named=True)
    }

    result = {
        "year": year,
        "loans": event_rows,
        "excluded_missing_effective_date": excluded_loans,
        "default": count_dict.get("DEFAULT", 0),
        "prepayment": count_dict.get("PREPAYMENT", 0),
        "censor": count_dict.get("CENSOR", 0),
        "same_month_conflicts": same_month_conflicts,
        "known_event_after_last_observation":
            known_event_after_last_observation,
        "status": "PASS",
    }

    print("\n" + "=" * 70)
    print(f"EVENT MAPPING VALIDATION - {year}")
    print("=" * 70)
    print(f"Loans:                             {result['loans']:,}")
    print(
        "Excluded:                          "
        f"{result['excluded_missing_effective_date']:,} "
        "(missing/invalid effective date)"
    )
    print(f"DEFAULT:                           {result['default']:,}")
    print(f"PREPAYMENT:                        {result['prepayment']:,}")
    print(f"CENSOR:                            {result['censor']:,}")
    print(
        "Same-month conflicts:              "
        f"{result['same_month_conflicts']:,}"
    )
    print(
        "Known event after last report:     "
        f"{result['known_event_after_last_observation']:,}"
    )
    print("\n✓ EVENT MAPPING VALIDATION PASS")
    print("=" * 70)

    return result
