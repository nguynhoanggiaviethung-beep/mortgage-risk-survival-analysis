# Safe Repository Cleanup Manifest

## Scope and safety boundary

This manifest records the inventory and cleanup decisions for the existing
Mortgage Default & Prepayment Survival Analysis project. The cleanup does not
change event definitions, censoring, the survival clock, missing-value rules,
cleaning rules, sample years, covariates, schemas, or model-ready dataset logic.

Baseline inventory before cleanup:

- Project files (excluding Git internals): 176
- Project size: approximately 789.705 MB
- Python source files: 27
- Parquet files: 78
- ZIP files: 11
- CSV files: 23
- Python bytecode cache files: 26
- Git metadata: not present in this directory; `git status` and `git ls-files`
  therefore cannot be evaluated without a separate, explicit repository
  initialization decision.

Baseline validation:

- `python -m unittest tests.test_event_definition -v`: 8/8 PASS
- Key-module compilation: PASS
- Full `src`, `scripts`, and `tests` compilation: PASS
- Full raw/clean validator: 8 PASS, 3 PASS_WITH_WARNING, 0 FAIL
- Model rows: 505,694
- Complete core cases: 500,681
- Event mapping rows: 512,490
- Survival eligible: 505,694
- Excluded before first payment: 6,796

## Classification

| Path or family | Action | Reason |
|---|---|---|
| `src/config.py`, `src/schemas.py`, `src/process_sample.py`, `src/clean_data.py`, `src/validate.py` | KEEP | Authoritative ingestion, schema, cleaning, and validation code. |
| `src/data/event_definition.py` | KEEP | Validated and locked event methodology. |
| `src/data/survival_duration.py` | KEEP | Validated and locked survival-duration methodology. |
| `src/data/model_dataset.py` | KEEP | Validated model-ready dataset logic. |
| `src/__init__.py`, `src/data/__init__.py`, `tests/__init__.py` | KEEP | Empty by design; package and test discovery markers, not redundant copies. |
| `scripts/*.py` | KEEP | Reproducible pipeline runners, validators, audits, and edge-case inspection tools. No obsolete duplicate script was found. |
| `tests/test_event_definition.py` | KEEP | Eight regression tests protecting locked event behavior. |
| `README.md` | KEEP | Repository entry point; populate because the pre-cleanup file is empty. |
| `requirements.txt` | KEEP | Dependency declaration; populate conservatively because the pre-cleanup file is empty. |
| `.gitignore` | KEEP | Already covers Python caches, environments, IDE files, raw/processed/model data, Parquet, ZIP, temp files, logs, figures, and local archive. |
| `reports/raw_validation.md`, `reports/clean_validation.md`, `reports/event_conflict_audit.md`, `reports/loan_age_duration_audit.md` | KEEP | Small methodology and validation evidence. |
| `outputs/tables/final_data_validation.csv`, `outputs/tables/event_mapping_summary_2016_2026.csv`, `outputs/tables/survival_duration_summary_2016_2026.csv`, `outputs/tables/model_dataset_summary_2016_2026.csv` | KEEP | Compact authoritative validation summaries. |
| Other small `outputs/tables/*.csv` audit summaries | KEEP | Reproducibility and audit evidence; preserved because they encode unique checks. |
| `outputs/tables/event_conflict_loans.csv`, `negative_duration_cases.csv`, `nonpositive_duration_summary.csv`, `unmodified_age_mismatch_distribution.csv`, `unmodified_age_mismatch_loans.csv` | NEEDS_REVIEW | Regenerable investigation outputs, but useful for audit. Leave in place; archive only after human review. |
| `outputs/tables/data_audit_2016_2026.parquet` | GITIGNORE_ONLY | Generated Parquet audit artifact; keep locally and exclude from Git. |
| `data/raw/*` and `*.zip` | GITIGNORE_ONLY | Immutable Freddie Mac source archives; never delete or commit during cleanup. |
| `data/processed/*` and `*.parquet` | GITIGNORE_ONLY | Generated ingestion results; keep locally for reproducibility and validation. |
| `data/model/*` and `*.parquet` | GITIGNORE_ONLY | Generated clean/event/survival/model datasets; keep locally and out of Git. |
| `data/_temp/2025/*.txt`, `data/_temp/2026/*.txt` | GITIGNORE_ONLY | Extracted local data can be regenerated, but local data deletion is outside safe automatic cleanup. Preserve it. |
| `archive/` | GITIGNORE_ONLY | Local holding area for future human-reviewed archival decisions. |
| `outputs/logs/`, generated figure image patterns | GITIGNORE_ONLY | Runtime and generated presentation artifacts. |
| `scripts/__pycache__/`, `src/__pycache__/`, `src/data/__pycache__/`, `tests/__pycache__/` | SAFE_DELETE | Disposable Python bytecode cache; regenerated automatically. |
| `src/data/test/` | SAFE_DELETE | Confirmed empty accidental directory; authoritative tests remain under root `tests/`. |
| Empty `archive/`, `outputs/figures/`, `outputs/logs/` directories | KEEP | Expected project structure and future output locations. |
| Missing `.git/` metadata | NEEDS_REVIEW | The folder is not currently a Git worktree. Do not initialize, stage, untrack, or push without an explicit human decision. |

## Duplicate and temporary-file findings

- No exact duplicate non-binary files under 5 MB were found, apart from several
  legitimate zero-byte package markers and the initially empty README and
  requirements files.
- No editor backup files, `*.bak`, `*.tmp`, `*.tmp.parquet`, or swap files were
  found.
- The only automatic deletions approved by this manifest are Python bytecode
  caches and the confirmed empty accidental test directory.

## External reference documents

The July 2026 file-layout workbook was inspected as a reference and contains
the origination and monthly-performance field layouts. It is outside this
repository and is not a cleanup target. The July 2026 user-guide PDF is also
outside the repository and must not be moved, edited, or deleted by this task.

## Cleanup execution and post-cleanup validation

Executed changes:

- Removed the four confirmed Python `__pycache__/` directories. Baseline cache
  files were removed, validation regenerated bytecode, and the regenerated
  caches were removed again after validation.
- Removed the confirmed empty accidental `src/data/test/` directory.
- Populated `README.md` with the data policy, pipeline commands, locked
  methodology, validated totals, test commands, and repository map.
- Populated `requirements.txt` with the current pipeline dependency and the
  planned modeling/reporting dependencies.
- Left `.gitignore` unchanged because it already satisfies the required intent.
- Archived no files and deleted no data, source, tests, audit outputs, reports,
  ZIP archives, or Parquet datasets.

Post-cleanup results:

- Event unit tests: 8/8 PASS.
- Key-module and full-project Python compilation: PASS.
- Full raw/clean validator: 8 PASS, 3 PASS_WITH_WARNING, 0 FAIL.
- Model rows: 505,694; complete core cases: 500,681 (99.01%).
- Missing FICO/LTV/DTI/rate/term: 121 / 1 / 4,891 / 0 / 0.
- Model events: 16,556 DEFAULT; 206,393 PREPAYMENT; 282,745 CENSOR.
- Event-map totals: 512,490 loans; 16,556 DEFAULT; 206,836 PREPAYMENT;
  289,098 CENSOR; 34 same-month conflicts.
- Survival totals: 512,490 loans; 505,694 eligible; 6,796 excluded before
  First Payment Month.
- All validated values are unchanged from baseline.

## Manual review

- Decide whether this project should be initialized as a new Git repository or
  whether missing `.git` metadata should be restored from another location.
- Decide whether investigation-only CSVs should later move to
  `archive/cleanup_review/`; they remain untouched in this cleanup.
