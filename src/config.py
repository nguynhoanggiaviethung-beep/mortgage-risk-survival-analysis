from pathlib import Path


# =========================================================
# PROJECT ROOT
# =========================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# =========================================================
# DATA DIRECTORIES
# =========================================================

DATA_DIR = PROJECT_ROOT / "data"

RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
MODEL_DIR = DATA_DIR / "model"
TEMP_DIR = DATA_DIR / "_temp"


# =========================================================
# OUTPUT DIRECTORIES
# =========================================================

OUTPUT_DIR = PROJECT_ROOT / "outputs"

TABLES_DIR = OUTPUT_DIR / "tables"
FIGURES_DIR = OUTPUT_DIR / "figures"
LOGS_DIR = OUTPUT_DIR / "logs"


# =========================================================
# STUDY PERIOD
# =========================================================

START_YEAR = 2016
END_YEAR = 2026

STUDY_YEARS = tuple(
    range(START_YEAR, END_YEAR + 1)
)


# =========================================================
# FILE PATH HELPERS
# =========================================================

def sample_zip_path(year: int) -> Path:
    return RAW_DIR / f"sample_{year}.zip"


def orig_parquet_path(year: int) -> Path:
    return PROCESSED_DIR / f"orig_{year}.parquet"


def perf_parquet_path(year: int) -> Path:
    return PROCESSED_DIR / f"perf_{year}.parquet"


# =========================================================
# CREATE REQUIRED DIRECTORIES
# =========================================================

def ensure_directories() -> None:

    directories = [
    RAW_DIR,
    PROCESSED_DIR,
    MODEL_DIR,
    TEMP_DIR,
    TABLES_DIR,
    FIGURES_DIR,
    LOGS_DIR,
]

    for directory in directories:
        directory.mkdir(
            parents=True,
            exist_ok=True
        )