from __future__ import annotations

from pathlib import Path

import polars as pl

from src.config import MODEL_DIR


# =========================================================
# STUDY SETTINGS
# =========================================================

PERFORMANCE_CUTOFF = 202603

KNOWN_ZERO_BALANCE_CODES = [
    "01",
    "02",
    "03",
    "09",
    "15",
    "16",
    "96",
]


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
    """Convert integer YYYYMM into Date on first day of month."""

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
    Event mapping theo Project Specification:

    03 / 09 -> DEFAULT
    01      -> PREPAYMENT
    02/15/16/96 -> CENSOR

    D90 và RA KHÔNG tự tạo Default.

    Event month:
    - ZBC event -> Zero Balance Effective Date
    - Không có event -> last observed performance month

    Loan có ZBC nhưng thiếu/sai Zero Balance Effective Date:
    - Không impute
    - Không tự chuyển thành censor
    - Loại toàn bộ loan khỏi event sample nếu
      exclude_missing_effective_date=True
    """

    cutoff = PERFORMANCE_CUTOFF
    known_codes = KNOWN_ZERO_BALANCE_CODES

    # =====================================================
    # SELECT REQUIRED PERFORMANCE FIELDS
    # =====================================================

    monthly = (
        perf.select(
            "loan_id",
            "reporting_period_num",
            "zero_balance_code",
            "zero_balance_effective_date",
        )
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
            .str.strptime(
                pl.Date,
                "%Y%m",
                strict=False,
            )
            .alias("_effective_date"),

            pl.col("reporting_period_num")
            .cast(pl.String)
            .str.strptime(
                pl.Date,
                "%Y%m",
                strict=False,
            )
            .alias("_report_date"),
        )
    )

    # =====================================================
    # REPORTING MONTH VALIDATION
    # =====================================================

    bad_dates = (
        monthly
        .filter(
            pl.col("_report_date").is_null()
        )
        .select(
            "loan_id",
            "reporting_period_num",
        )
        .limit(5)
        .collect()
    )

    if bad_dates.height:
        raise ValueError(
            "Tháng báo cáo thiếu hoặc sai:\n"
            f"{bad_dates}"
        )

    # Chỉ giữ Performance trong cửa sổ nghiên cứu.
    monthly = monthly.filter(
        pl.col("reporting_period_num") <= cutoff
    )

    # =====================================================
    # UNKNOWN ZERO BALANCE CODE
    # =====================================================

    unknown = (
        monthly
        .filter(
            pl.col("_code").is_not_null()
            & ~pl.col("_code").is_in(known_codes)
        )
        .select(
            "loan_id",
            "_code",
        )
        .limit(5)
        .collect()
    )

    if unknown.height:
        raise ValueError(
            "Zero Balance Code chưa có mapping:\n"
            f"{unknown}"
        )

    # =====================================================
    # MISSING / INVALID EFFECTIVE DATE
    # =====================================================

    missing_dates = (
        monthly
        .filter(
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

        # Một loan có event nhưng thiếu ngày hiệu lực thì
        # loại TOÀN BỘ loan khỏi event sample.
        #
        # Không:
        # - tự điền reporting month
        # - tự censor
        # - sửa raw data

        excluded_ids = (
            missing_dates
            .select("loan_id")
            .unique()
        )

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

    # =====================================================
    # EFFECTIVE MONTH
    # =====================================================

    monthly = monthly.with_columns(
        (
            pl.col("_effective_date").dt.year() * 100
            + pl.col("_effective_date").dt.month()
        )
        .cast(pl.Int32)
        .alias("_effective_month")
    )

    # =====================================================
    # FOLLOW-UP INFORMATION
    # =====================================================

    followup = (
        monthly
        .group_by("loan_id")
        .agg(
            pl.col("reporting_period_num")
            .min()
            .alias("first_observed_month"),

            pl.col("reporting_period_num")
            .max()
            .alias("last_observed_month"),
        )
    )

    # =====================================================
    # EVENT CANDIDATES
    # =====================================================

    candidates = (
        monthly
        .filter(
            pl.col("_code").is_not_null()
            & (
                pl.col("_effective_month")
                <= cutoff
            )
        )
        .with_columns(
            pl.when(
                pl.col("_code").is_in(
                    ["03", "09"]
                )
            )
            .then(
                pl.lit("DEFAULT")
            )
            .when(
                pl.col("_code") == "01"
            )
            .then(
                pl.lit("PREPAYMENT")
            )
            .otherwise(
                pl.lit("CENSOR")
            )
            .alias("_type")
        )
    )

    # =====================================================
    # EARLIEST EVENT
    # =====================================================

    earliest = (
        candidates
        .group_by("loan_id")
        .agg(
            pl.col("_effective_month")
            .min()
            .alias("_first_event_month")
        )
    )

    first = (
        candidates
        .join(
            earliest,
            on="loan_id",
            how="inner",
        )
        .filter(
            pl.col("_effective_month")
            == pl.col("_first_event_month")
        )
    )

    # =====================================================
    # SAME-MONTH EVENT CONFLICT
    # =====================================================

    conflicts = (
        first
        .group_by("loan_id")
        .agg(
            pl.col("_code")
            .n_unique()
            .alias("n_codes")
        )
        .filter(
            pl.col("n_codes") > 1
        )
        .limit(5)
        .collect()
    )

    if conflicts.height:
        raise ValueError(
            "Có nhiều mã kết thúc khác nhau tại "
            "tháng sự kiện đầu tiên; cần kiểm tra:\n"
            f"{conflicts}"
        )

    # =====================================================
    # SELECT EVENT
    # =====================================================

    selected = (
        first
        .group_by("loan_id")
        .agg(
            pl.col("_effective_month")
            .first()
            .alias("_selected_month"),

            pl.col("_code")
            .first()
            .alias("raw_zero_balance_code"),

            pl.col("_type")
            .first()
            .alias("_selected_type"),

            (
                pl.col("_effective_month")
                != pl.col("reporting_period_num")
            )
            .any()
            .alias(
                "effective_reporting_month_mismatch"
            ),
        )
    )

    # =====================================================
    # FINAL EVENT TABLE
    # =====================================================

    result = (
        followup
        .join(
            selected,
            on="loan_id",
            how="left",
        )
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

        # -------------------------------------------------
        # EVENT MONTH + EVENT TYPE
        # -------------------------------------------------

        .with_columns(
            pl.coalesce(
                "_selected_month",
                "last_observed_month",
            )
            .alias("event_month"),

            pl.col("_selected_type")
            .fill_null("CENSOR")
            .alias("event_type"),

            pl.col(
                "effective_reporting_month_mismatch"
            )
            .fill_null(False),
        )

        # -------------------------------------------------
        # EVENT CODE + SOURCE + FLAGS
        # -------------------------------------------------

        .with_columns(

            pl.when(
                pl.col("event_type")
                == "DEFAULT"
            )
            .then(
                pl.lit(EVENT_DEFAULT)
            )
            .when(
                pl.col("event_type")
                == "PREPAYMENT"
            )
            .then(
                pl.lit(EVENT_PREPAYMENT)
            )
            .otherwise(
                pl.lit(EVENT_CENSOR)
            )
            .cast(pl.Int8)
            .alias("event_code"),

            pl.when(
                pl.col(
                    "raw_zero_balance_code"
                ).is_null()
            )
            .then(
                pl.lit("RIGHT_CENSOR")
            )
            .when(
                pl.col(
                    "raw_zero_balance_code"
                ) == "01"
            )
            .then(
                pl.lit("ZB01_PREPAYMENT")
            )
            .when(
                pl.col(
                    "raw_zero_balance_code"
                ) == "15"
            )
            .then(
                pl.lit(
                    "ZB15_WHOLE_LOAN_SALE"
                )
            )
            .when(
                pl.col(
                    "raw_zero_balance_code"
                ) == "16"
            )
            .then(
                pl.lit(
                    "ZB16_REPERFORMING_SECURITIZATION"
                )
            )
            .when(
                pl.col(
                    "raw_zero_balance_code"
                ) == "96"
            )
            .then(
                pl.lit("ZB96_DEFECT")
            )
            .otherwise(
                pl.concat_str(
                    [
                        pl.lit("ZB"),
                        pl.col(
                            "raw_zero_balance_code"
                        ),
                    ]
                )
            )
            .alias("event_source"),

            _month_number_to_date(
                "event_month"
            )
            .alias("event_date"),

            (
                pl.col("event_type")
                == "DEFAULT"
            )
            .alias("default_flag"),

            (
                pl.col("event_type")
                == "PREPAYMENT"
            )
            .alias("prepayment_flag"),

            (
                pl.col("event_type")
                == "CENSOR"
            )
            .alias("censor_flag"),

            pl.lit(False)
            .alias(
                "same_month_default_prepay_flag"
            ),
        )

        # -------------------------------------------------
        # FOLLOW-UP AUDIT FLAGS
        # -------------------------------------------------

        .with_columns(
            (
                pl.col("event_month")
                < pl.col(
                    "first_observed_month"
                )
            )
            .alias(
                "event_before_entry_flag"
            ),

            (
                pl.col("event_month")
                > pl.col(
                    "last_observed_month"
                )
            )
            .alias(
                "event_after_last_report_flag"
            ),
        )

        .drop(
            "_selected_month",
            "_selected_type",
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

    orig_path = (
        MODEL_DIR
        / f"orig_clean_{year}.parquet"
    )

    perf_path = (
        MODEL_DIR
        / f"perf_clean_{year}.parquet"
    )

    output_path = (
        MODEL_DIR
        / f"event_map_{year}.parquet"
    )

    temp_path = (
        MODEL_DIR
        / f"event_map_{year}.tmp.parquet"
    )

    # =====================================================
    # INPUT CHECK
    # =====================================================

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

    temp_path.unlink(
        missing_ok=True
    )

    orig = pl.scan_parquet(
        orig_path
    )

    perf = pl.scan_parquet(
        perf_path
    )

    from src.config import PROJECT_ROOT

    # =====================================================
    # AUDIT DIRECTORY
    # =====================================================

    report_dir = (
        PROJECT_ROOT
        / "reports"
    )

    report_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    # =====================================================
    # MISSING EFFECTIVE DATE AUDIT
    # =====================================================

    missing_date_audit = (
        perf
        .filter(
            pl.col("reporting_period_num")
            <= PERFORMANCE_CUTOFF
        )
        .with_columns(
            pl.col(
                "zero_balance_code"
            )
            .cast(pl.String)
            .str.strip_chars()
            .replace("", None)
            .alias("_code"),

            pl.col(
                "zero_balance_effective_date"
            )
            .cast(pl.String)
            .str.strip_chars()
            .replace("", None)
            .str.strptime(
                pl.Date,
                "%Y%m",
                strict=False,
            )
            .alias("_effective_date"),
        )
        .filter(
            pl.col("_code").is_not_null()
            & pl.col(
                "_effective_date"
            ).is_null()
        )
        .select(
            "loan_id",
            "reporting_period_num",
            "zero_balance_code",
            "zero_balance_effective_date",
        )
        .with_columns(
            pl.lit(
                "MISSING_OR_INVALID_EFFECTIVE_DATE"
            )
            .alias(
                "exclusion_reason"
            )
        )
        .collect()
    )

    missing_date_audit.write_csv(
        report_dir
        / f"event_missing_date_{year}.csv"
    )

    # =====================================================
    # BUILD EVENT MAP
    # =====================================================

    event_map = build_event_mapping(
        orig,
        perf,
        exclude_missing_effective_date=True,
    )

    event_map.sink_parquet(
        temp_path,
        compression="zstd",
    )

    temp_path.replace(
        output_path
    )

    return output_path


# =========================================================
# VALIDATE ONE EVENT MAP
# =========================================================

def validate_event_mapping_year(
    year: int,
) -> dict:

    year = int(year)

    perf_path = (
        MODEL_DIR
        / f"perf_clean_{year}.parquet"
    )

    event_path = (
        MODEL_DIR
        / f"event_map_{year}.parquet"
    )

    if not perf_path.exists():
        raise FileNotFoundError(
            f"Không tìm thấy:\n{perf_path}"
        )

    if not event_path.exists():
        raise FileNotFoundError(
            f"Không tìm thấy:\n{event_path}"
        )

    perf = pl.scan_parquet(
        perf_path
    )

    events = pl.scan_parquet(
        event_path
    )

    # =====================================================
    # PERFORMANCE LOANS INSIDE STUDY WINDOW
    # =====================================================

    perf_window = (
        perf
        .filter(
            pl.col("reporting_period_num")
            <= PERFORMANCE_CUTOFF
        )
    )

    perf_loans = (
        perf_window
        .select(
            pl.col("loan_id")
            .n_unique()
            .alias("n")
        )
        .collect()["n"][0]
    )

    # =====================================================
    # COUNT LOANS EXCLUDED FOR MISSING EFFECTIVE DATE
    # =====================================================

    excluded_missing_effective_date_loans = (
        perf_window
        .with_columns(
            pl.col(
                "zero_balance_code"
            )
            .cast(pl.String)
            .str.strip_chars()
            .replace("", None)
            .alias("_code"),

            pl.col(
                "zero_balance_effective_date"
            )
            .cast(pl.String)
            .str.strip_chars()
            .replace("", None)
            .str.strptime(
                pl.Date,
                "%Y%m",
                strict=False,
            )
            .alias("_effective_date"),
        )
        .filter(
            pl.col("_code").is_not_null()
            & pl.col(
                "_effective_date"
            ).is_null()
        )
        .select(
            pl.col("loan_id")
            .n_unique()
            .alias("n")
        )
        .collect()["n"][0]
    )

    expected_event_rows = (
        perf_loans
        - excluded_missing_effective_date_loans
    )

    # =====================================================
    # EVENT ROW COUNTS
    # =====================================================

    event_rows = (
        events
        .select(
            pl.len()
            .alias("n")
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
        .filter(
            pl.col("len") > 1
        )
        .select(
            pl.len()
            .alias("n")
        )
        .collect()["n"][0]
    )

    # =====================================================
    # EVENT TYPE VALIDATION
    # =====================================================

    invalid_event_types = (
        events
        .filter(
            ~pl.col("event_type")
            .is_in(
                [
                    "DEFAULT",
                    "PREPAYMENT",
                    "CENSOR",
                ]
            )
        )
        .select(
            pl.len()
            .alias("n")
        )
        .collect()["n"][0]
    )

    missing_event_month = (
        events
        .filter(
            pl.col(
                "event_month"
            ).is_null()
        )
        .select(
            pl.len()
            .alias("n")
        )
        .collect()["n"][0]
    )

    # =====================================================
    # EVENT AFTER LAST REPORT
    #
    # Known official ZB effective dates may be later than
    # last_observed_month.
    #
    # Unknown/non-official sources are not allowed.
    # =====================================================

    known_event_after_last_observation = (
        events
        .filter(
            (
                pl.col("event_month")
                > pl.col(
                    "last_observed_month"
                )
            )
            & pl.col(
                "event_source"
            ).is_in(
                ALLOWED_EVENT_SOURCES_AFTER_LAST_REPORT
            )
        )
        .select(
            pl.len()
            .alias("n")
        )
        .collect()["n"][0]
    )

    event_after_last_observation = (
        events
        .filter(
            (
                pl.col("event_month")
                > pl.col(
                    "last_observed_month"
                )
            )
            & ~pl.col(
                "event_source"
            ).is_in(
                ALLOWED_EVENT_SOURCES_AFTER_LAST_REPORT
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

    counts = (
        events
        .group_by(
            "event_type"
        )
        .len()
        .collect()
    )

    same_month_conflicts = (
        events
        .filter(
            pl.col(
                "same_month_default_prepay_flag"
            )
        )
        .select(
            pl.len()
            .alias("n")
        )
        .collect()["n"][0]
    )

    # =====================================================
    # CRITICAL VALIDATION
    # =====================================================

    # QUAN TRỌNG:
    #
    # Event map KHÔNG bắt buộc bằng toàn bộ Performance loans.
    #
    # Những loan có ZBC nhưng thiếu/sai
    # zero_balance_effective_date đã được chủ động loại khỏi
    # event sample.
    #
    # expected_event_rows =
    # performance loans
    # - excluded missing effective-date loans

    if event_rows != expected_event_rows:
        raise RuntimeError(
            f"{year}: Event rows không đúng. "
            f"Expected {expected_event_rows:,} "
            f"= {perf_loans:,} Performance loans "
            f"- {excluded_missing_effective_date_loans:,} "
            f"excluded missing-effective-date loans; "
            f"actual event rows = {event_rows:,}."
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
            f"{year}: Có event_type "
            f"không hợp lệ."
        )

    if missing_event_month != 0:
        raise RuntimeError(
            f"{year}: Có event_month "
            f"bị null."
        )

    if event_after_last_observation != 0:
        raise RuntimeError(
            f"{year}: Có event không hợp lệ "
            f"xảy ra sau last observed month."
        )

    # =====================================================
    # RESULT
    # =====================================================

    count_dict = {
        row["event_type"]: row["len"]
        for row in counts.iter_rows(
            named=True
        )
    }

    result = {
        "year": year,

        "performance_loans":
            perf_loans,

        "excluded_missing_effective_date_loans":
            excluded_missing_effective_date_loans,

        "expected_event_rows":
            expected_event_rows,

        "loans":
            event_rows,

        "default":
            count_dict.get(
                "DEFAULT",
                0,
            ),

        "prepayment":
            count_dict.get(
                "PREPAYMENT",
                0,
            ),

        "censor":
            count_dict.get(
                "CENSOR",
                0,
            ),

        "same_month_conflicts":
            same_month_conflicts,

        "known_event_after_last_observation":
            known_event_after_last_observation,

        "status":
            "PASS",
    }

    # =====================================================
    # PRINT VALIDATION REPORT
    # =====================================================

    print(
        "\n"
        + "=" * 70
    )

    print(
        f"EVENT MAPPING VALIDATION - {year}"
    )

    print(
        "=" * 70
    )

    print(
        f"Performance loans:                  "
        f"{result['performance_loans']:,}"
    )

    print(
        f"Excluded missing effective date:    "
        f"{result['excluded_missing_effective_date_loans']:,}"
    )

    print(
        f"Expected event-map rows:             "
        f"{result['expected_event_rows']:,}"
    )

    print(
        f"Event-map loans:                     "
        f"{result['loans']:,}"
    )

    print(
        f"DEFAULT:                             "
        f"{result['default']:,}"
    )

    print(
        f"PREPAYMENT:                          "
        f"{result['prepayment']:,}"
    )

    print(
        f"CENSOR:                              "
        f"{result['censor']:,}"
    )

    print(
        f"Same-month conflicts:                "
        f"{result['same_month_conflicts']:,}"
    )

    print(
        f"Known event after last report:       "
        f"{result['known_event_after_last_observation']:,}"
    )

    print(
        "\n✓ EVENT MAPPING VALIDATION PASS"
    )

    print(
        "=" * 70
    )

    return result