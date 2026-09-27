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
) -> pl.LazyFrame:
    """
    Build exactly one first event per loan with Performance data.

    EVENT TYPES
    -----------
    1 = DEFAULT
        Primary:
            first delinquency_num >= 3

        Fallback:
            first RA
            first Zero Balance 02 / 03 / 09

    2 = PREPAYMENT
        Zero Balance 01 while remaining legal maturity > 0.

        If remaining maturity is unavailable, compare
        Zero Balance Effective Month with maturity_month.

    0 = CENSOR
        Maturity
        Administrative termination 15 / 16 / 96
        Right censoring at last observed month

    EVENT TIMING
    ------------
    - Among known events, the earliest event month wins.
    - If Default and Prepayment occur in the same month:
        DEFAULT wins and same_month_default_prepay_flag = True.
    - last_observed_month is used only when no known event exists.
      It must NOT override a known Zero Balance Effective Date merely
      because that effective date is later than the last reporting month.
    """

    # =====================================================
    # ORIGINATION INFORMATION NEEDED FOR ZB01 FALLBACK
    # =====================================================

    orig_info = orig.select(
        [
            "loan_id",
            "vintage_year",
            "first_payment_month",
            "maturity_month",
        ]
    )

    # =====================================================
    # JOIN PERFORMANCE WITH ORIGINATION
    # =====================================================

    monthly = (
        perf
        .join(
            orig_info,
            on="loan_id",
            how="left",
            suffix="_orig",
        )
        .with_columns(
            # Official Zero Balance Effective Date first.
            # If unavailable, fall back to Monthly Reporting Period.
            pl.coalesce(
                [
                    pl.col("zero_balance_effective_date")
                    .cast(pl.Int32, strict=False),
                    pl.col("reporting_period_num"),
                ]
            ).alias("_zb_event_month")
        )
        .with_columns(
            # ZB 01 = prepaid OR matured.
            (
                (pl.col("zero_balance_code") == "01")
                &
                (
                    (pl.col("remaining_months_maturity") > 0)
                    |
                    (
                        pl.col("remaining_months_maturity").is_null()
                        & pl.col("zero_balance_effective_month").is_not_null()
                        & pl.col("maturity_month").is_not_null()
                        & (
                            pl.col("zero_balance_effective_month")
                            < pl.col("maturity_month")
                        )
                    )
                )
            ).alias("_is_prepay_candidate"),

            (
                (pl.col("zero_balance_code") == "01")
                &
                (
                    (pl.col("remaining_months_maturity") <= 0)
                    |
                    (
                        pl.col("remaining_months_maturity").is_null()
                        & pl.col("zero_balance_effective_month").is_not_null()
                        & pl.col("maturity_month").is_not_null()
                        & (
                            pl.col("zero_balance_effective_month")
                            >= pl.col("maturity_month")
                        )
                    )
                )
            ).alias("_is_maturity_candidate"),
        )
    )

    # =====================================================
    # FIRST CANDIDATE MONTH PER LOAN
    # =====================================================

    candidates = (
        monthly
        .group_by("loan_id")
        .agg(
            # Loan information
            pl.col("vintage_year").first().alias("vintage_year"),
            pl.col("first_payment_month").first().alias("first_payment_month"),
            pl.col("maturity_month").first().alias("maturity_month"),

            # Primary default
            _first_month_when(
                pl.col("delinquency_num") >= 3,
                pl.col("reporting_period_num"),
            ).alias("first_d90_month"),

            # Default fallback: REO Acquisition
            _first_month_when(
                pl.col("is_ra"),
                pl.col("reporting_period_num"),
            ).alias("first_ra_month"),

            # Credit-related Zero Balance codes
            _first_month_when(
                pl.col("zero_balance_code") == "02",
                pl.col("_zb_event_month"),
            ).alias("first_zb02_month"),

            _first_month_when(
                pl.col("zero_balance_code") == "03",
                pl.col("_zb_event_month"),
            ).alias("first_zb03_month"),

            _first_month_when(
                pl.col("zero_balance_code") == "09",
                pl.col("_zb_event_month"),
            ).alias("first_zb09_month"),

            # Prepayment / maturity
            _first_month_when(
                pl.col("_is_prepay_candidate"),
                pl.col("_zb_event_month"),
            ).alias("first_prepay_month"),

            _first_month_when(
                pl.col("_is_maturity_candidate"),
                pl.col("_zb_event_month"),
            ).alias("first_maturity_month"),

            # Administrative termination
            _first_month_when(
                pl.col("zero_balance_code") == "15",
                pl.col("_zb_event_month"),
            ).alias("first_zb15_month"),

            _first_month_when(
                pl.col("zero_balance_code") == "16",
                pl.col("_zb_event_month"),
            ).alias("first_zb16_month"),

            _first_month_when(
                pl.col("zero_balance_code") == "96",
                pl.col("_zb_event_month"),
            ).alias("first_zb96_month"),

            # Last observed monthly record
            pl.col("reporting_period_num")
            .max()
            .alias("last_observed_month"),
        )
    )

    # =====================================================
    # DEFAULT / ADMIN CANDIDATE MONTHS
    # =====================================================

    candidates = candidates.with_columns(
        pl.min_horizontal(
            [
                pl.col("first_d90_month"),
                pl.col("first_ra_month"),
                pl.col("first_zb02_month"),
                pl.col("first_zb03_month"),
                pl.col("first_zb09_month"),
            ]
        ).alias("first_default_month"),

        pl.min_horizontal(
            [
                pl.col("first_zb15_month"),
                pl.col("first_zb16_month"),
                pl.col("first_zb96_month"),
            ]
        ).alias("first_admin_termination_month"),
    )

    # =====================================================
    # DEFAULT SOURCE
    #
    # Priority only resolves evidence occurring in the same
    # earliest month:
    # D90 > RA > ZB02 > ZB03 > ZB09
    # =====================================================

    candidates = candidates.with_columns(
        pl.when(pl.col("first_default_month").is_null())
        .then(None)
        .when(pl.col("first_default_month") == pl.col("first_d90_month"))
        .then(pl.lit("D90"))
        .when(pl.col("first_default_month") == pl.col("first_ra_month"))
        .then(pl.lit("RA"))
        .when(pl.col("first_default_month") == pl.col("first_zb02_month"))
        .then(pl.lit("ZB02"))
        .when(pl.col("first_default_month") == pl.col("first_zb03_month"))
        .then(pl.lit("ZB03"))
        .otherwise(pl.lit("ZB09"))
        .alias("default_source")
    )

    # =====================================================
    # ADMIN SOURCE
    # =====================================================

    candidates = candidates.with_columns(
        pl.when(pl.col("first_admin_termination_month").is_null())
        .then(None)
        .when(
            pl.col("first_admin_termination_month")
            == pl.col("first_zb15_month")
        )
        .then(pl.lit("ZB15_WHOLE_LOAN_SALE"))
        .when(
            pl.col("first_admin_termination_month")
            == pl.col("first_zb16_month")
        )
        .then(pl.lit("ZB16_REPERFORMING_SECURITIZATION"))
        .otherwise(pl.lit("ZB96_DEFECT"))
        .alias("admin_source")
    )

    # =====================================================
    # SAME-MONTH DEFAULT / PREPAYMENT CONFLICT
    # =====================================================

    candidates = candidates.with_columns(
        (
            pl.col("first_default_month").is_not_null()
            & pl.col("first_prepay_month").is_not_null()
            & (
                pl.col("first_default_month")
                == pl.col("first_prepay_month")
            )
        ).alias("same_month_default_prepay_flag")
    )

    # =====================================================
    # FINAL EVENT MONTH
    #
    # IMPORTANT FIX:
    # First choose among KNOWN events only.
    #
    # Only when there is no known event do we use
    # last_observed_month for right censoring.
    #
    # This prevents a valid Zero Balance Effective Date in a
    # later calendar month from being incorrectly overwritten
    # by the previous last reporting month.
    # =====================================================

    candidates = (
        candidates
        .with_columns(
            pl.min_horizontal(
                [
                    pl.col("first_default_month"),
                    pl.col("first_prepay_month"),
                    pl.col("first_maturity_month"),
                    pl.col("first_admin_termination_month"),
                ]
            ).alias("_first_known_event_month")
        )
        .with_columns(
            pl.coalesce(
                [
                    pl.col("_first_known_event_month"),
                    pl.col("last_observed_month"),
                ]
            ).alias("event_month")
        )
    )

    # =====================================================
    # FINAL EVENT TYPE
    #
    # Earliest known month wins.
    # Same-month precedence:
    # DEFAULT > PREPAYMENT > MATURITY > ADMIN > RIGHT CENSOR
    # =====================================================

    result = candidates.with_columns(
        pl.when(
            pl.col("first_default_month").is_not_null()
            & (pl.col("event_month") == pl.col("first_default_month"))
        )
        .then(pl.lit("DEFAULT"))
        .when(
            pl.col("first_prepay_month").is_not_null()
            & (pl.col("event_month") == pl.col("first_prepay_month"))
        )
        .then(pl.lit("PREPAYMENT"))
        .otherwise(pl.lit("CENSOR"))
        .alias("event_type"),

        pl.when(
            pl.col("first_default_month").is_not_null()
            & (pl.col("event_month") == pl.col("first_default_month"))
        )
        .then(pl.lit(EVENT_DEFAULT))
        .when(
            pl.col("first_prepay_month").is_not_null()
            & (pl.col("event_month") == pl.col("first_prepay_month"))
        )
        .then(pl.lit(EVENT_PREPAYMENT))
        .otherwise(pl.lit(EVENT_CENSOR))
        .cast(pl.Int8)
        .alias("event_code"),
    )

    # =====================================================
    # EVENT SOURCE / CENSOR REASON
    # =====================================================

    result = result.with_columns(
        pl.when(pl.col("event_type") == "DEFAULT")
        .then(pl.col("default_source"))
        .when(pl.col("event_type") == "PREPAYMENT")
        .then(pl.lit("ZB01_PREPAYMENT"))
        .when(
            pl.col("first_maturity_month").is_not_null()
            & (pl.col("event_month") == pl.col("first_maturity_month"))
        )
        .then(pl.lit("MATURITY"))
        .when(
            pl.col("first_admin_termination_month").is_not_null()
            & (
                pl.col("event_month")
                == pl.col("first_admin_termination_month")
            )
        )
        .then(pl.col("admin_source"))
        .otherwise(pl.lit("RIGHT_CENSOR"))
        .alias("event_source")
    )

    # =====================================================
    # RAW ZERO BALANCE CODE AT FINAL EVENT
    # =====================================================

    result = result.with_columns(
        pl.when(pl.col("event_source").str.starts_with("ZB01"))
        .then(pl.lit("01"))
        .when(pl.col("event_source") == "ZB02")
        .then(pl.lit("02"))
        .when(pl.col("event_source") == "ZB03")
        .then(pl.lit("03"))
        .when(pl.col("event_source") == "ZB09")
        .then(pl.lit("09"))
        .when(pl.col("event_source") == "ZB15_WHOLE_LOAN_SALE")
        .then(pl.lit("15"))
        .when(
            pl.col("event_source")
            == "ZB16_REPERFORMING_SECURITIZATION"
        )
        .then(pl.lit("16"))
        .when(pl.col("event_source") == "ZB96_DEFECT")
        .then(pl.lit("96"))
        .otherwise(None)
        .alias("raw_zero_balance_code")
    )

    # =====================================================
    # FINAL FLAGS + EVENT DATE
    # =====================================================

    result = result.with_columns(
        (pl.col("event_type") == "DEFAULT").alias("default_flag"),
        (pl.col("event_type") == "PREPAYMENT").alias("prepayment_flag"),
        (pl.col("event_type") == "CENSOR").alias("censor_flag"),
        _month_number_to_date("event_month").alias("event_date"),
    )

    # =====================================================
    # OUTPUT
    # =====================================================

    return (
        result
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
                "default_flag",
                "prepayment_flag",
                "censor_flag",
                "same_month_default_prepay_flag",
                "raw_zero_balance_code",

                # Audit columns
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
                "last_observed_month",
            ]
        )
        .sort("loan_id")
    )


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

    event_map = build_event_mapping(
        orig,
        perf,
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

    if perf_loans != event_rows:
        raise RuntimeError(
            f"{year}: Event rows "
            f"không bằng số Performance loans."
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
