from pathlib import Path

import polars as pl

from src.config import MODEL_DIR, PROCESSED_DIR

START_YEAR = 2016
END_YEAR = 2026
CUTOFF = 202603

CORE_COLUMNS = [
    "fico",
    "original_ltv",
    "original_dti",
    "original_interest_rate",
    "original_loan_term",
]

FEATURE_COLUMNS = [
    "loan_id",
    *CORE_COLUMNS,
    "original_cltv",
    "original_upb",
    "occupancy_status",
    "property_type",
    "loan_purpose",
    "property_state",
    "number_borrowers",
    "multiple_borrowers_flag",
    "origination_quarter",
]


def build_model_dataset(
    orig: pl.LazyFrame,
    survival: pl.LazyFrame,
) -> pl.LazyFrame:
    """Một dòng/khoản vay; giữ thời điểm vào và ra khỏi quan sát."""
    population = survival.filter(
        pl.col("survival_eligible").fill_null(False)
        & pl.col("vintage_year").is_between(START_YEAR, END_YEAR)
    )

    result = population.join(
        orig.select(FEATURE_COLUMNS).with_columns(
            pl.lit(True).alias("_orig_matched")
        ),
        on="loan_id",
        how="left",
        validate="1:1",
    ).with_columns(
        pl.all_horizontal([
            pl.col(name).is_not_null()
            & pl.col(name)
            .cast(pl.Float64)
            .is_finite()
            .fill_null(False)
            for name in CORE_COLUMNS
        ]).alias("core_covariates_complete_flag"),

        (pl.col("event_type") == "DEFAULT")
        .cast(pl.Int8)
        .alias("km_default_event"),

        (pl.col("event_type") == "PREPAYMENT")
        .cast(pl.Int8)
        .alias("km_prepayment_event"),

        pl.col("competing_event_code")
        .cast(pl.Int8)
        .alias("cr_event_code"),
    )

    unmatched = (
        result.filter(~pl.col("_orig_matched").fill_null(False))
        .select("loan_id")
        .limit(5)
        .collect()
    )
    if unmatched.height:
        raise ValueError(
            f"Có khoản vay không ghép được với Origination:\n{unmatched}"
        )

    return result.drop("_orig_matched").sort("loan_id")


def validate_model_frame(frame: pl.LazyFrame) -> dict:
    """Kiểm tra khóa, phạm vi, thời gian và mã sự kiện."""
    valid_time = (
        pl.col("entry_time_month").is_not_null()
        & pl.col("exit_time_month").is_not_null()
        & (pl.col("entry_time_month") >= 0)
        & (pl.col("exit_time_month") > pl.col("entry_time_month"))
        & (pl.col("duration_months") == pl.col("exit_time_month"))
    ).fill_null(False)

    valid_scope = (
        pl.col("vintage_year").is_between(START_YEAR, END_YEAR)
        & (pl.col("event_month") <= CUTOFF)
    ).fill_null(False)

    valid_event = (
        (
            (pl.col("event_type") == "DEFAULT")
            & (pl.col("event_code") == 1)
        )
        | (
            (pl.col("event_type") == "PREPAYMENT")
            & (pl.col("event_code") == 2)
        )
        | (
            (pl.col("event_type") == "CENSOR")
            & (pl.col("event_code") == 0)
        )
    ) & (
        pl.col("event_code") == pl.col("competing_event_code")
    )

    stats = frame.select(
        pl.len().alias("rows"),
        pl.col("loan_id").n_unique().alias("unique_loans"),
        pl.col("loan_id").is_null().sum().alias("missing_id"),
        (~valid_time).sum().alias("invalid_time"),
        (~valid_scope).sum().alias("outside_scope"),
        (~valid_event.fill_null(False)).sum().alias("invalid_event"),
        pl.col("core_covariates_complete_flag")
        .sum().alias("complete_case"),
        (pl.col("event_type") == "DEFAULT").sum().alias("default"),
        (pl.col("event_type") == "PREPAYMENT").sum().alias("prepayment"),
        (pl.col("event_type") == "CENSOR").sum().alias("censor"),
    ).collect().to_dicts()[0]

    if (
        stats["rows"] != stats["unique_loans"]
        or stats["missing_id"]
        or stats["invalid_time"]
        or stats["outside_scope"]
        or stats["invalid_event"]
    ):
        raise ValueError(f"Model dataset không đạt kiểm tra:\n{stats}")

    stats["status"] = "PASS"
    return stats


def build_model_dataset_year(
    year: int,
    force: bool = False,
) -> Path:
    year = int(year)
    if not START_YEAR <= year <= END_YEAR:
        raise ValueError(f"Năm {year} nằm ngoài phạm vi nghiên cứu.")

    orig_path = PROCESSED_DIR / "origination.parquet"
    survival_path = MODEL_DIR / f"survival_duration_{year}.parquet"
    output = MODEL_DIR / f"model_dataset_{year}.parquet"
    temporary = MODEL_DIR / f"model_dataset_{year}.tmp.parquet"

    for path in (orig_path, survival_path):
        if not path.exists():
            raise FileNotFoundError(f"Không tìm thấy: {path}")

    if output.exists() and not force:
        return output

    orig = pl.scan_parquet(orig_path).filter(
        pl.col("vintage_year") == year
    )
    survival = pl.scan_parquet(survival_path)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    build_model_dataset(orig, survival).sink_parquet(
        temporary,
        compression="zstd",
    )

    # Chỉ thay file chính khi file tạm đã đạt kiểm tra.
    validate_model_frame(pl.scan_parquet(temporary))
    temporary.replace(output)
    return output


def validate_model_dataset_year(year: int) -> dict:
    year = int(year)
    model = pl.scan_parquet(
        MODEL_DIR / f"model_dataset_{year}.parquet"
    )
    survival = pl.scan_parquet(
        MODEL_DIR / f"survival_duration_{year}.parquet"
    )

    expected = (
        survival.filter(
            pl.col("survival_eligible").fill_null(False)
            & pl.col("vintage_year").is_between(START_YEAR, END_YEAR)
        )
        .select(pl.len())
        .collect()
        .item()
    )

    stats = validate_model_frame(model)
    if stats["rows"] != expected:
        raise ValueError(
            f"{year}: Có {stats['rows']} dòng, kỳ vọng {expected}."
        )

    stats["year"] = year
    print(
        f"{year}: {stats['rows']:,} khoản đủ điều kiện thời gian; "
        f"{stats['complete_case']:,} khoản đủ biến baseline.",
        flush=True,
    )
    return stats