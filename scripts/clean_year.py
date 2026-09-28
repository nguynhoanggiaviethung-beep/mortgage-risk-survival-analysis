from pathlib import Path
import sys


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
# IMPORT PROJECT MODULES
# =========================================================

from src.config import (
    STUDY_YEARS,
    ensure_directories,
)

from src.clean_data import (
    clean_sample_year,
)


# =========================================================
# MAIN
# =========================================================

def main():

    if len(sys.argv) != 2:

        print(
            "\nCách dùng:"
        )

        print(
            "python scripts/clean_year.py 2016"
        )

        sys.exit(1)


    try:

        year = int(
            sys.argv[1]
        )

    except ValueError:

        print(
            "\n❌ Năm không hợp lệ."
        )

        sys.exit(1)


    if year not in STUDY_YEARS:

        print(
            f"\n❌ {year} nằm ngoài "
            f"phạm vi nghiên cứu."
        )

        print(
            f"Các năm hợp lệ: "
            f"{STUDY_YEARS}"
        )

        sys.exit(1)


    ensure_directories()


    try:

        clean_sample_year(
            year
        )

    except Exception as error:

        print(
            "\n"
            + "=" * 70
        )

        print(
            f"❌ CLEANING {year} THẤT BẠI"
        )

        print(
            "=" * 70
        )

        print(
            f"\nLỗi: {error}"
        )

        sys.exit(1)


if __name__ == "__main__":
    main()