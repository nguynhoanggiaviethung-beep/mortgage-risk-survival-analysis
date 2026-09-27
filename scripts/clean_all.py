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

    ensure_directories()

    print(
        "\n"
        + "=" * 80
    )

    print(
        "FREDDIE MAC CLEANING PIPELINE"
    )

    print(
        "2016–2026"
    )

    print(
        "=" * 80
    )


    successful = []
    failed = []


    # =====================================================
    # CLEAN EACH VINTAGE
    # =====================================================

    for year in STUDY_YEARS:

        try:

            result = clean_sample_year(
                year,
                force=False,
            )

            successful.append(
                {
                    "year":
                        year,

                    "status":
                        result["status"],

                    "orig_rows":
                        result["orig_rows"],

                    "perf_rows":
                        result["perf_rows"],

                    "fico_missing":
                        result[
                            "fico_not_available"
                        ],

                    "dti_missing":
                        result[
                            "dti_not_available"
                        ],

                    "ltv_missing":
                        result[
                            "ltv_not_available"
                        ],

                    "cltv_missing":
                        result[
                            "cltv_not_available"
                        ],

                    "xx_rows":
                        result[
                            "xx_rows"
                        ],

                    "ra_rows":
                        result[
                            "ra_rows"
                        ],

                    "eltv_missing":
                        result[
                            "estimated_ltv_not_available"
                        ],
                }
            )

        except Exception as error:

            failed.append(
                {
                    "year":
                        year,

                    "error":
                        str(error),
                }
            )

            print(
                "\n"
                + "=" * 80
            )

            print(
                f"❌ CLEANING {year} FAILED"
            )

            print(
                "=" * 80
            )

            print(
                error
            )


    # =====================================================
    # SUMMARY
    # =====================================================

    print(
        "\n"
        + "=" * 80
    )

    print(
        "CLEANING SUMMARY"
    )

    print(
        "=" * 80
    )


    print(
        "\nSuccessful:"
    )

    if successful:

        for item in successful:

            print(
                f"  ✓ {item['year']}"
                f" | Orig: {item['orig_rows']:,}"
                f" | Perf: {item['perf_rows']:,}"
                f" | XX: {item['xx_rows']:,}"
                f" | RA: {item['ra_rows']:,}"
            )

    else:

        print(
            "  None"
        )


    print(
        "\nFailed:"
    )

    if failed:

        for item in failed:

            print(
                f"  ❌ {item['year']}"
            )

            print(
                f"     {item['error']}"
            )

    else:

        print(
            "  None"
        )


    # =====================================================
    # TOTALS
    # =====================================================

    if successful:

        total_orig = sum(
            item["orig_rows"]
            for item in successful
        )

        total_perf = sum(
            item["perf_rows"]
            for item in successful
        )

        total_fico_missing = sum(
            item["fico_missing"]
            for item in successful
        )

        total_dti_missing = sum(
            item["dti_missing"]
            for item in successful
        )

        total_ltv_missing = sum(
            item["ltv_missing"]
            for item in successful
        )

        total_cltv_missing = sum(
            item["cltv_missing"]
            for item in successful
        )

        total_xx = sum(
            item["xx_rows"]
            for item in successful
        )

        total_ra = sum(
            item["ra_rows"]
            for item in successful
        )

        total_eltv_missing = sum(
            item["eltv_missing"]
            for item in successful
        )


        print(
            "\n"
            + "=" * 80
        )

        print(
            "CLEAN DATA TOTALS"
        )

        print(
            "=" * 80
        )

        print(
            f"Origination rows:        "
            f"{total_orig:,}"
        )

        print(
            f"Performance rows:        "
            f"{total_perf:,}"
        )

        print(
            f"FICO Not Available:      "
            f"{total_fico_missing:,}"
        )

        print(
            f"DTI Not Available:       "
            f"{total_dti_missing:,}"
        )

        print(
            f"LTV Not Available:       "
            f"{total_ltv_missing:,}"
        )

        print(
            f"CLTV Not Available:      "
            f"{total_cltv_missing:,}"
        )

        print(
            f"XX rows:                 "
            f"{total_xx:,}"
        )

        print(
            f"RA rows:                 "
            f"{total_ra:,}"
        )

        print(
            f"Estimated LTV NA:        "
            f"{total_eltv_missing:,}"
        )


    # =====================================================
    # FINAL STATUS
    # =====================================================

    print(
        "\n"
        + "=" * 80
    )

    if failed:

        print(
            "⚠ CLEANING PIPELINE HOÀN THÀNH "
            "NHƯNG CÓ VINTAGE BỊ LỖI"
        )

    else:

        print(
            "✓ CLEANING PIPELINE HOÀN THÀNH"
        )

    print(
        "=" * 80
    )


    if failed:

        sys.exit(1)


if __name__ == "__main__":
    main()