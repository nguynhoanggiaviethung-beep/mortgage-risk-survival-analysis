from __future__ import annotations

import polars as pl

from src.config import (
    orig_parquet_path,
    perf_parquet_path,
)

from src.schemas import (
    KEEP_ORIG_COLUMNS,
    KEEP_PERF_COLUMNS,
)


# =========================================================
# VALIDATE ONE VINTAGE
# =========================================================

def validate_year(
    year: int,
    show_report: bool = True,
) -> dict:
    """
    Validate processed Freddie Mac sample data
    for one vintage year.

    Expected files:
        data/processed/orig_YYYY.parquet
        data/processed/perf_YYYY.parquet

    Validation rules:
        1. Performance loan missing from Origination:
           FAIL.

        2. Origination loan missing from Performance:
           WARNING, but validation can PASS.

        3. If a loan missing Performance also has an
           invalid first_payment_date:
           FAIL.

    Returns
    -------
    dict
        Validation statistics.

    Raises
    ------
    FileNotFoundError
        If processed files do not exist.

    RuntimeError
        If a critical validation rule fails.
    """

    year = int(year)

    orig_file = orig_parquet_path(year)
    perf_file = perf_parquet_path(year)


    # =====================================================
    # 1. FILE EXISTENCE
    # =====================================================

    if not orig_file.exists():

        raise FileNotFoundError(
            f"Không tìm thấy Origination Parquet:\n"
            f"{orig_file}"
        )


    if not perf_file.exists():

        raise FileNotFoundError(
            f"Không tìm thấy Performance Parquet:\n"
            f"{perf_file}"
        )


    # =====================================================
    # 2. LAZY LOAD
    # =====================================================

    orig = pl.scan_parquet(
        orig_file
    )

    perf = pl.scan_parquet(
        perf_file
    )


    # =====================================================
    # 3. SCHEMA CHECK
    # =====================================================

    orig_columns = (
        orig
        .collect_schema()
        .names()
    )

    perf_columns = (
        perf
        .collect_schema()
        .names()
    )


    required_orig = (
        KEEP_ORIG_COLUMNS
        + ["vintage_year"]
    )

    required_perf = (
        KEEP_PERF_COLUMNS
        + ["vintage_year"]
    )


    missing_orig_columns = [
        column
        for column in required_orig
        if column not in orig_columns
    ]


    missing_perf_columns = [
        column
        for column in required_perf
        if column not in perf_columns
    ]


    if missing_orig_columns:

        raise RuntimeError(
            f"{year}: Origination thiếu cột:\n"
            f"{missing_orig_columns}"
        )


    if missing_perf_columns:

        raise RuntimeError(
            f"{year}: Performance thiếu cột:\n"
            f"{missing_perf_columns}"
        )


    # =====================================================
    # 4. ROWS / UNIQUE LOANS
    # =====================================================

    orig_stats = (
        orig
        .select(
            pl.len().alias(
                "rows"
            ),

            pl.col(
                "loan_id"
            )
            .n_unique()
            .alias(
                "unique_loans"
            ),
        )
        .collect()
    )


    perf_stats = (
        perf
        .select(
            pl.len().alias(
                "rows"
            ),

            pl.col(
                "loan_id"
            )
            .n_unique()
            .alias(
                "unique_loans"
            ),
        )
        .collect()
    )


    orig_rows = (
        orig_stats["rows"][0]
    )

    orig_unique_loans = (
        orig_stats["unique_loans"][0]
    )

    perf_rows = (
        perf_stats["rows"][0]
    )

    perf_unique_loans = (
        perf_stats["unique_loans"][0]
    )


    # =====================================================
    # 5. ORIGINATION LOAN ID MUST BE UNIQUE
    # =====================================================

    if orig_rows != orig_unique_loans:

        raise RuntimeError(
            f"{year}: Origination có Loan ID trùng.\n"
            f"Rows = {orig_rows:,}\n"
            f"Unique loans = {orig_unique_loans:,}"
        )


    # =====================================================
    # 6. TIME RANGE
    # =====================================================

    time_stats = (
        perf
        .select(

            pl.col(
                "monthly_reporting_period"
            )
            .min()
            .alias(
                "first_period"
            ),

            pl.col(
                "monthly_reporting_period"
            )
            .max()
            .alias(
                "last_period"
            ),

            pl.col(
                "loan_age"
            )
            .cast(
                pl.Int64,
                strict=False,
            )
            .min()
            .alias(
                "min_loan_age"
            ),

            pl.col(
                "loan_age"
            )
            .cast(
                pl.Int64,
                strict=False,
            )
            .max()
            .alias(
                "max_loan_age"
            ),
        )
        .collect()
    )


    first_period = (
        time_stats["first_period"][0]
    )

    last_period = (
        time_stats["last_period"][0]
    )

    min_loan_age = (
        time_stats["min_loan_age"][0]
    )

    max_loan_age = (
        time_stats["max_loan_age"][0]
    )


    if last_period is None:

        raise RuntimeError(
            f"{year}: Performance không có "
            f"monthly_reporting_period hợp lệ."
        )


    try:

        performance_cutoff_num = int(
            last_period
        )

    except (TypeError, ValueError):

        raise RuntimeError(
            f"{year}: Không đọc được "
            f"Performance cutoff: {last_period}"
        )


    # =====================================================
    # 7. LOAN ID CHECK
    # =====================================================

    orig_ids = (
        orig
        .select(
            "loan_id"
        )
        .unique()
    )


    perf_ids = (
        perf
        .select(
            "loan_id"
        )
        .unique()
    )


    # -----------------------------------------------------
    # Performance loan không có Origination
    # Đây là lỗi nghiêm trọng -> FAIL
    # -----------------------------------------------------

    perf_missing_in_orig = (
        perf_ids
        .join(
            orig_ids,
            on="loan_id",
            how="anti",
        )
        .select(
            pl.len().alias(
                "count"
            )
        )
        .collect()["count"][0]
    )


    if perf_missing_in_orig != 0:

        raise RuntimeError(
            f"{year}: Có "
            f"{perf_missing_in_orig:,} "
            f"Performance Loan ID "
            f"không tồn tại trong Origination."
        )


    # -----------------------------------------------------
    # Origination loan không có Performance
    # -----------------------------------------------------

    missing_orig_loans = (
        orig
        .join(
            perf_ids,
            on="loan_id",
            how="anti",
        )
        .select(
            "loan_id",
            "first_payment_date",
        )
        .with_columns(
            pl.col(
                "first_payment_date"
            )
            .cast(
                pl.Int64,
                strict=False,
            )
            .alias(
                "first_payment_period_num"
            )
        )
        .collect()
    )


    orig_missing_in_perf = (
        missing_orig_loans.height
    )


    missing_before_cutoff = 0
    missing_at_or_after_cutoff = 0
    missing_invalid_first_payment = 0


    if orig_missing_in_perf > 0:

        # ---------------------------------------------
        # First Payment Date không hợp lệ
        # ---------------------------------------------

        missing_invalid_first_payment = (
            missing_orig_loans
            .filter(
                pl.col(
                    "first_payment_period_num"
                ).is_null()
            )
            .height
        )


        if missing_invalid_first_payment > 0:

            raise RuntimeError(
                f"{year}: Có "
                f"{missing_invalid_first_payment:,} "
                f"Origination loan không có Performance "
                f"và first_payment_date không hợp lệ."
            )


        # ---------------------------------------------
        # Loan có First Payment Date trước cutoff
        # ---------------------------------------------

        missing_before_cutoff = (
            missing_orig_loans
            .filter(
                pl.col(
                    "first_payment_period_num"
                )
                < performance_cutoff_num
            )
            .height
        )


        # ---------------------------------------------
        # Loan có First Payment Date tại / sau cutoff
        # ---------------------------------------------

        missing_at_or_after_cutoff = (
            missing_orig_loans
            .filter(
                pl.col(
                    "first_payment_period_num"
                )
                >= performance_cutoff_num
            )
            .height
        )


    # =====================================================
    # 8. VINTAGE YEAR CHECK
    # =====================================================

    orig_vintage = (
        orig
        .select(
            pl.col(
                "vintage_year"
            )
            .unique()
        )
        .collect()
        .to_series()
        .to_list()
    )


    perf_vintage = (
        perf
        .select(
            pl.col(
                "vintage_year"
            )
            .unique()
        )
        .collect()
        .to_series()
        .to_list()
    )


    expected_vintage = {
        str(year)
    }


    if set(orig_vintage) != expected_vintage:

        raise RuntimeError(
            f"{year}: vintage_year Origination "
            f"không đúng: {orig_vintage}"
        )


    if set(perf_vintage) != expected_vintage:

        raise RuntimeError(
            f"{year}: vintage_year Performance "
            f"không đúng: {perf_vintage}"
        )


    # =====================================================
    # 9. DELINQUENCY SPECIAL CODES
    # =====================================================

    delinquency_stats = (
        perf
        .select(

            (
                pl.col(
                    "delinquency_status"
                )
                == "RA"
            )
            .sum()
            .alias(
                "RA_rows"
            ),

            (
                pl.col(
                    "delinquency_status"
                )
                == "XX"
            )
            .sum()
            .alias(
                "XX_rows"
            ),
        )
        .collect()
    )


    ra_rows = (
        delinquency_stats[
            "RA_rows"
        ][0]
    )

    xx_rows = (
        delinquency_stats[
            "XX_rows"
        ][0]
    )


    # =====================================================
    # 10. ZERO BALANCE CODE
    # =====================================================

    zero_balance = (
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
        .len()
        .sort(
            "zero_balance_code"
        )
        .collect()
    )


    # =====================================================
    # 11. FILE SIZE
    # =====================================================

    orig_size_mb = (
        orig_file.stat().st_size
        / (1024 ** 2)
    )

    perf_size_mb = (
        perf_file.stat().st_size
        / (1024 ** 2)
    )


    # =====================================================
    # 12. STATUS
    # =====================================================

    if orig_missing_in_perf > 0:

        validation_status = (
            "PASS_WITH_WARNING"
        )

    else:

        validation_status = (
            "PASS"
        )


    # =====================================================
    # 13. RESULT
    # =====================================================

    result = {

        "year":
            year,

        "orig_rows":
            orig_rows,

        "orig_unique_loans":
            orig_unique_loans,

        "perf_rows":
            perf_rows,

        "perf_unique_loans":
            perf_unique_loans,

        "perf_missing_in_orig":
            perf_missing_in_orig,

        "orig_missing_in_perf":
            orig_missing_in_perf,

        "orig_missing_before_cutoff":
            missing_before_cutoff,

        "orig_missing_at_or_after_cutoff":
            missing_at_or_after_cutoff,

        "orig_missing_invalid_first_payment":
            missing_invalid_first_payment,

        "first_period":
            first_period,

        "last_period":
            last_period,

        "min_loan_age":
            min_loan_age,

        "max_loan_age":
            max_loan_age,

        "RA_rows":
            ra_rows,

        "XX_rows":
            xx_rows,

        "orig_size_mb":
            orig_size_mb,

        "perf_size_mb":
            perf_size_mb,

        "status":
            validation_status,
    }


    # =====================================================
    # 14. REPORT
    # =====================================================

    if show_report:

        print(
            "\n"
            + "=" * 70
        )

        print(
            f"VALIDATION REPORT - {year}"
        )

        print(
            "=" * 70
        )


        # -------------------------------------------------
        # Origination
        # -------------------------------------------------

        print(
            "\nORIGINATION"
        )

        print(
            f"Rows:          "
            f"{orig_rows:,}"
        )

        print(
            f"Unique loans:  "
            f"{orig_unique_loans:,}"
        )


        # -------------------------------------------------
        # Performance
        # -------------------------------------------------

        print(
            "\nPERFORMANCE"
        )

        print(
            f"Rows:          "
            f"{perf_rows:,}"
        )

        print(
            f"Unique loans:  "
            f"{perf_unique_loans:,}"
        )


        # -------------------------------------------------
        # Loan ID
        # -------------------------------------------------

        print(
            "\nLOAN ID CHECK"
        )

        print(
            "Performance missing in Origination:",
            perf_missing_in_orig,
        )

        print(
            "Origination missing in Performance:",
            orig_missing_in_perf,
        )


        if orig_missing_in_perf > 0:

            print(
                "  Missing before cutoff:",
                missing_before_cutoff,
            )

            print(
                "  Missing at/after cutoff:",
                missing_at_or_after_cutoff,
            )


        # -------------------------------------------------
        # Warning: trước cutoff
        # -------------------------------------------------

        if missing_before_cutoff > 0:

            warning_before = (
                missing_orig_loans
                .filter(
                    pl.col(
                        "first_payment_period_num"
                    )
                    < performance_cutoff_num
                )
                .select(
                    "loan_id",
                    "first_payment_date",
                )
            )

            print(
                "\n⚠ WARNING:"
            )

            print(
                f"{missing_before_cutoff:,} "
                f"Origination loan không có Performance "
                f"dù first_payment_date nằm trước "
                f"Performance cutoff {last_period}."
            )

            print(
                "Các loan này được giữ trong Origination, "
                "nhưng hiện không có follow-up Performance."
            )

            print(
                "\nCác loan bị ảnh hưởng:"
            )

            print(
                warning_before
            )


        # -------------------------------------------------
        # Warning: tại hoặc sau cutoff
        # -------------------------------------------------

        if missing_at_or_after_cutoff > 0:

            warning_after = (
                missing_orig_loans
                .filter(
                    pl.col(
                        "first_payment_period_num"
                    )
                    >= performance_cutoff_num
                )
                .select(
                    "loan_id",
                    "first_payment_date",
                )
            )

            print(
                "\n⚠ WARNING:"
            )

            print(
                f"{missing_at_or_after_cutoff:,} "
                f"Origination loan chưa có Performance "
                f"vì first_payment_date nằm tại hoặc "
                f"sau Performance cutoff {last_period}."
            )

            print(
                "Các loan này được giữ trong Origination "
                "nhưng chưa có follow-up Performance."
            )

            print(
                "\nCác loan bị ảnh hưởng:"
            )

            print(
                warning_after
            )


        # -------------------------------------------------
        # Time range
        # -------------------------------------------------

        print(
            "\nTIME RANGE"
        )

        print(
            "First period:",
            first_period,
        )

        print(
            "Last period:",
            last_period,
        )

        print(
            "Min loan age:",
            min_loan_age,
        )

        print(
            "Max loan age:",
            max_loan_age,
        )


        # -------------------------------------------------
        # Delinquency
        # -------------------------------------------------

        print(
            "\nDELINQUENCY SPECIAL CODES"
        )

        print(
            "RA rows:",
            ra_rows,
        )

        print(
            "XX rows:",
            xx_rows,
        )


        # -------------------------------------------------
        # Zero Balance
        # -------------------------------------------------

        print(
            "\nZERO BALANCE CODE"
        )

        print(
            zero_balance
        )


        # -------------------------------------------------
        # File size
        # -------------------------------------------------

        print(
            "\nFILE SIZE"
        )

        print(
            f"Origination: "
            f"{orig_size_mb:.2f} MB"
        )

        print(
            f"Performance: "
            f"{perf_size_mb:.2f} MB"
        )


        # -------------------------------------------------
        # Final validation status
        # -------------------------------------------------

        print(
            "\n"
            + "=" * 70
        )


        if validation_status == "PASS_WITH_WARNING":

            print(
                f"✓ VALIDATION {year}: "
                f"PASS WITH WARNING"
            )

        else:

            print(
                f"✓ VALIDATION {year}: PASS"
            )


        print(
            "=" * 70
        )


    return result