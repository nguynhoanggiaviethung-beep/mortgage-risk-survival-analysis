from pathlib import Path
import shutil
import zipfile

import polars as pl

from src.config import (
    RAW_DIR,
    PROCESSED_DIR,
    TEMP_DIR,
)

from src.schemas import (
    ORIG_SCHEMA,
    PERF_SCHEMA,
    KEEP_ORIG_COLUMNS,
    KEEP_PERF_COLUMNS,
)

from src.validate import (
    validate_year,
)


# =========================================================
# PROCESS ONE SAMPLE VINTAGE
# =========================================================

def process_sample_year(
    year: int,
    force: bool = False,
) -> dict:
    """
    Process one Freddie Mac Sample Dataset vintage.

    Input:
        data/raw/sample_YYYY.zip

    Output:
        data/processed/orig_YYYY.parquet
        data/processed/perf_YYYY.parquet

    Parameters
    ----------
    year:
        Vintage year, e.g. 2016.

    force:
        If True, overwrite existing processed files.

    Returns
    -------
    dict
        Validation statistics returned by validate_year().
    """

    year = int(year)

    # =====================================================
    # 1. PATHS
    # =====================================================

    sample_zip = (
        RAW_DIR
        / f"sample_{year}.zip"
    )

    orig_output = (
        PROCESSED_DIR
        / f"orig_{year}.parquet"
    )

    perf_output = (
        PROCESSED_DIR
        / f"perf_{year}.parquet"
    )

    temp_dir = (
        TEMP_DIR
        / str(year)
    )

    # =====================================================
    # 2. KIỂM TRA INPUT
    # =====================================================

    if not sample_zip.exists():

        raise FileNotFoundError(
            f"Không tìm thấy file nguồn:\n"
            f"{sample_zip}\n\n"
            f"Hãy đặt sample_{year}.zip "
            f"vào thư mục data/raw."
        )

    # =====================================================
    # 3. NẾU OUTPUT ĐÃ TỒN TẠI
    # =====================================================

    if (
        orig_output.exists()
        and perf_output.exists()
        and not force
    ):

        print(
            f"\n✓ {year}: đã có đủ "
            f"Origination và Performance Parquet."
        )

        print(
            "Đang validate output hiện tại..."
        )

        try:

            result = validate_year(
                year,
                show_report=True,
            )

            print(
                f"\n→ {year} hợp lệ, "
                f"không cần xử lý lại."
            )

            return result

        except Exception:

            print(
                "\n⚠ Output hiện tại không "
                "vượt qua validation."
            )

            print(
                "→ Pipeline sẽ xử lý lại "
                "vintage này."
            )

    # =====================================================
    # 4. DỌN OUTPUT CŨ / FILE CHẠY DỞ
    # =====================================================

    orig_output.unlink(
        missing_ok=True
    )

    perf_output.unlink(
        missing_ok=True
    )

    orig_temp_output = (
        PROCESSED_DIR
        / f"orig_{year}.tmp.parquet"
    )

    perf_temp_output = (
        PROCESSED_DIR
        / f"perf_{year}.tmp.parquet"
    )

    orig_temp_output.unlink(
        missing_ok=True
    )

    perf_temp_output.unlink(
        missing_ok=True
    )

    if temp_dir.exists():

        shutil.rmtree(
            temp_dir
        )

    temp_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    # =====================================================
    # 5. BẮT ĐẦU PIPELINE
    # =====================================================

    print(
        "\n"
        + "=" * 70
    )

    print(
        f"PROCESS SAMPLE VINTAGE {year}"
    )

    print(
        "=" * 70
    )

    print(
        "Nguồn:"
    )

    print(
        sample_zip
    )

    try:

        # =================================================
        # 6. ĐỌC CẤU TRÚC ZIP
        # =================================================

        with zipfile.ZipFile(
            sample_zip,
            "r",
        ) as archive:

            members = (
                archive
                .namelist()
            )

            orig_member = next(
                (
                    member
                    for member in members

                    if Path(member).name
                    == f"sample_orig_{year}.txt"
                ),
                None,
            )

            perf_member = next(
                (
                    member
                    for member in members

                    if Path(member).name
                    == f"sample_perf_{year}.txt"
                ),
                None,
            )

            if orig_member is None:

                raise FileNotFoundError(
                    f"Trong sample_{year}.zip "
                    f"không tìm thấy "
                    f"sample_orig_{year}.txt."
                )

            if perf_member is None:

                raise FileNotFoundError(
                    f"Trong sample_{year}.zip "
                    f"không tìm thấy "
                    f"sample_perf_{year}.txt."
                )

            # =============================================
            # TXT TEMP PATHS
            # =============================================

            orig_txt = (
                temp_dir
                / f"sample_orig_{year}.txt"
            )

            perf_txt = (
                temp_dir
                / f"sample_perf_{year}.txt"
            )

            # =============================================
            # HIỂN THỊ DUNG LƯỢNG
            # =============================================

            orig_info = (
                archive
                .getinfo(orig_member)
            )

            perf_info = (
                archive
                .getinfo(perf_member)
            )

            print(
                "\nDung lượng sau khi giải nén:"
            )

            print(
                f"Origination: "
                f"{orig_info.file_size / (1024 ** 2):,.2f} MB"
            )

            print(
                f"Performance: "
                f"{perf_info.file_size / (1024 ** 2):,.2f} MB"
            )

            # =============================================
            # 7. GIẢI NÉN ORIGINATION
            # =============================================

            print(
                "\nĐang giải nén Origination..."
            )

            with archive.open(
                orig_member
            ) as source:

                with orig_txt.open(
                    "wb"
                ) as target:

                    shutil.copyfileobj(
                        source,
                        target,
                        length=1024 * 1024,
                    )

            print(
                "✓ Origination đã giải nén"
            )

            # =============================================
            # 8. GIẢI NÉN PERFORMANCE
            # =============================================

            print(
                "Đang giải nén Performance..."
            )

            with archive.open(
                perf_member
            ) as source:

                with perf_txt.open(
                    "wb"
                ) as target:

                    shutil.copyfileobj(
                        source,
                        target,
                        length=1024 * 1024,
                    )

            print(
                "✓ Performance đã giải nén"
            )

        # =================================================
        # 9. ORIGINATION → PARQUET
        # =================================================

        print(
            "\nĐang xử lý Origination..."
        )

        orig_lazy = (
            pl.scan_csv(
                orig_txt,
                separator="|",
                has_header=False,
                schema=ORIG_SCHEMA,
                low_memory=True,
            )

            .select(
                KEEP_ORIG_COLUMNS
            )

            .with_columns(
                pl.lit(
                    str(year)
                )
                .alias(
                    "vintage_year"
                )
            )
        )

        orig_lazy.sink_parquet(
            orig_temp_output,
            compression="zstd",
        )

        orig_temp_output.replace(
            orig_output
        )

        print(
            "✓ Đã tạo:",
            orig_output.name,
        )

        # =================================================
        # 10. PERFORMANCE → PARQUET
        # =================================================

        print(
            "\nĐang xử lý Performance..."
        )

        perf_lazy = (
            pl.scan_csv(
                perf_txt,
                separator="|",
                has_header=False,
                schema=PERF_SCHEMA,
                low_memory=True,
            )

            .select(
                KEEP_PERF_COLUMNS
            )

            .with_columns(
                pl.lit(
                    str(year)
                )
                .alias(
                    "vintage_year"
                )
            )
        )

        perf_lazy.sink_parquet(
            perf_temp_output,
            compression="zstd",
        )

        perf_temp_output.replace(
            perf_output
        )

        print(
            "✓ Đã tạo:",
            perf_output.name,
        )

        # =================================================
        # 11. VALIDATE
        # =================================================

        print(
            "\nĐang chạy validation..."
        )

        result = validate_year(
            year,
            show_report=True,
        )

        # =================================================
        # 12. XÓA TEMP
        # =================================================

        if temp_dir.exists():

            shutil.rmtree(
                temp_dir
            )

        print(
            f"\n✓ Đã xóa dữ liệu tạm "
            f"của {year}."
        )

        print(
            "\n"
            + "=" * 70
        )

        print(
            f"✓✓✓ SAMPLE {year} "
            f"HOÀN TẤT"
        )

        print(
            "=" * 70
        )

        return result

    # =====================================================
    # 13. NẾU LỖI
    # =====================================================

    except Exception:

        orig_temp_output.unlink(
            missing_ok=True
        )

        perf_temp_output.unlink(
            missing_ok=True
        )

        print(
            "\n"
            + "=" * 70
        )

        print(
            f"❌ SAMPLE {year} "
            f"XỬ LÝ THẤT BẠI"
        )

        print(
            "=" * 70
        )

        print(
            "\nDữ liệu temp được giữ lại tại:"
        )

        print(
            temp_dir
        )

        print(
            "\nKhông xóa temp cho tới khi "
            "xác định nguyên nhân lỗi."
        )

        raise