from pathlib import Path
import sys


# =========================================================
# ADD PROJECT ROOT TO PYTHON PATH
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
    ensure_directories,
)

from src.process_sample import (
    process_sample_year,
)


# =========================================================
# MAIN
# =========================================================

def main():

    # -----------------------------------------------------
    # Kiểm tra input
    # -----------------------------------------------------

    if len(sys.argv) != 2:

        print("\nCách dùng:")

        print(
            "python scripts/process_year.py 2016"
        )

        print(
            "\nCác năm nghiên cứu:"
        )

        print(
            STUDY_YEARS
        )

        sys.exit(1)


    # -----------------------------------------------------
    # Kiểm tra năm có phải integer
    # -----------------------------------------------------

    try:

        year = int(
            sys.argv[1]
        )

    except ValueError:

        print(
            "\n❌ Năm không hợp lệ."
        )

        print(
            "Ví dụ đúng:"
        )

        print(
            "python scripts/process_year.py 2016"
        )

        sys.exit(1)


    # -----------------------------------------------------
    # Kiểm tra phạm vi nghiên cứu
    # -----------------------------------------------------

    if year not in STUDY_YEARS:

        print(
            f"\n❌ {year} nằm ngoài "
            f"phạm vi nghiên cứu."
        )

        print(
            "Các năm hợp lệ:"
        )

        print(
            STUDY_YEARS
        )

        sys.exit(1)


    # -----------------------------------------------------
    # Đảm bảo folder tồn tại
    # -----------------------------------------------------

    ensure_directories()


    # -----------------------------------------------------
    # Chạy pipeline
    # -----------------------------------------------------

    print(
        "\n"
        + "=" * 70
    )

    print(
        f"FREDDIE MAC SAMPLE PIPELINE - {year}"
    )

    print(
        "=" * 70
    )


    try:

        process_sample_year(
            year
        )

    except Exception as error:

        print(
            "\n"
            + "=" * 70
        )

        print(
            f"❌ XỬ LÝ {year} THẤT BẠI"
        )

        print(
            "=" * 70
        )

        print(
            f"\nLỗi: {error}"
        )

        sys.exit(1)


    print(
        "\n"
        + "=" * 70
    )

    print(
        f"✓ XỬ LÝ {year} THÀNH CÔNG"
    )

    print(
        "=" * 70
    )


# =========================================================
# ENTRY POINT
# =========================================================

if __name__ == "__main__":
    main()