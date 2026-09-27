from pathlib import Path
import sys


# =========================================================
# PROJECT ROOT
# =========================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_ROOT)
    )


# =========================================================
# IMPORT PROJECT MODULES
# =========================================================

from src.config import (
    STUDY_YEARS,
    RAW_DIR,
    ensure_directories,
)

from src.process_sample import (
    process_sample_year,
)


# =========================================================
# MAIN
# =========================================================

def main():

    ensure_directories()

    print("\n" + "=" * 70)
    print("FREDDIE MAC SAMPLE PIPELINE")
    print("PROCESS ALL AVAILABLE VINTAGES")
    print("=" * 70)


    # -----------------------------------------------------
    # TÌM CÁC FILE SAMPLE HIỆN CÓ
    # -----------------------------------------------------

    available_years = []
    missing_years = []


    for year in STUDY_YEARS:

        sample_zip = (
            RAW_DIR
            / f"sample_{year}.zip"
        )

        if sample_zip.exists():
            available_years.append(year)

        else:
            missing_years.append(year)


    # -----------------------------------------------------
    # HIỂN THỊ TRẠNG THÁI
    # -----------------------------------------------------

    print("\nCác vintage có dữ liệu:")

    if available_years:

        for year in available_years:
            print(f"  ✓ {year}")

    else:

        print("  Không có file sample nào.")


    print("\nCác vintage chưa có ZIP:")

    if missing_years:

        for year in missing_years:
            print(f"  - {year}")

    else:

        print("  Không thiếu vintage nào.")


    # -----------------------------------------------------
    # KHÔNG CÓ FILE NÀO
    # -----------------------------------------------------

    if not available_years:

        print(
            "\nKhông có dữ liệu để xử lý."
        )

        return


    # -----------------------------------------------------
    # XỬ LÝ LẦN LƯỢT
    # -----------------------------------------------------

    successful = []
    failed = []


    for year in available_years:

        print("\n" + "=" * 70)
        print(f"BẮT ĐẦU VINTAGE {year}")
        print("=" * 70)

        try:

            result = process_sample_year(
                year
            )

            successful.append(
                result["year"]
            )

        except Exception as error:

            failed.append(
                (
                    year,
                    str(error)
                )
            )

            print(
                f"\n❌ {year}: FAILED"
            )

            print(
                f"Lỗi: {error}"
            )


    # -----------------------------------------------------
    # SUMMARY
    # -----------------------------------------------------

    print("\n" + "=" * 70)
    print("PIPELINE SUMMARY")
    print("=" * 70)


    print("\nSuccessful:")

    if successful:

        for year in successful:
            print(f"  ✓ {year}")

    else:

        print("  None")


    print("\nFailed:")

    if failed:

        for year, error in failed:

            print(
                f"  ❌ {year}"
            )

            print(
                f"     {error}"
            )

    else:

        print("  None")


    print("\nMissing ZIP:")

    if missing_years:

        print(
            "  "
            + ", ".join(
                str(year)
                for year in missing_years
            )
        )

    else:

        print("  None")


    print("\n" + "=" * 70)

    if failed:

        print(
            "⚠ PIPELINE HOÀN THÀNH "
            "NHƯNG CÓ VINTAGE BỊ LỖI"
        )

    else:

        print(
            "✓ PIPELINE HOÀN THÀNH"
        )

    print("=" * 70)


# =========================================================
# ENTRY POINT
# =========================================================

if __name__ == "__main__":
    main()