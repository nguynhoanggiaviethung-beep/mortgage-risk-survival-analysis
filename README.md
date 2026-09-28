# Mortgage Default & Prepayment Survival Analysis

This project prepares Freddie Mac Single-Family Loan-Level Dataset (SFLLD)
sample vintages for survival analysis of mortgage default and prepayment. The
current data-preparation pipeline covers 2016-2026; 2026 is a partial vintage.

The prepared data supports the next modeling phase:

- Kaplan-Meier estimates and horizon default probabilities;
- Cox proportional-hazards models and diagnostics;
- cause-specific default and prepayment models;
- competing-risk and cumulative-incidence analysis; and
- vintage comparisons.

## Data policy

Freddie Mac source data and generated Parquet datasets are local artifacts and
are not stored in Git. Place the source archives at:

```text
data/raw/sample_2016.zip
...
data/raw/sample_2026.zip
```

The pipeline writes generated data to:

```text
data/processed/   # parsed origination and monthly-performance data
data/model/       # cleaned, event, survival-duration, and model datasets
data/_temp/       # temporary extracted source files
```

The existing `.gitignore` excludes these data directories, `*.parquet`, and
`*.zip`. Do not edit raw ZIP files or commit them to source control.

## Environment

Create and activate a virtual environment, then install the project
dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Pipeline

Run commands from the project root. The main reproducible sequence is:

```powershell
# 1. Parse available Freddie Mac sample ZIP files
python scripts\process_all.py

# 2. Audit processed files, then clean them
python scripts\check_data.py
python scripts\clean_all.py
python scripts\final_data_validation.py

# 3. Audit and build the locked event mapping
python scripts\audit_event_conflicts.py
python scripts\build_event_maps_all.py

# 4. Audit and build the fixed-origin survival duration
python scripts\audit_loan_age_duration.py
python scripts\build_survival_duration_all.py

# 5. Build model-ready datasets
python scripts\build_model_datasets_all.py
```

Single-year ingestion and cleaning are also available:

```powershell
python scripts\process_year.py 2016
python scripts\clean_year.py 2016
```

Audit and validation scripts under `scripts/` are part of the reproducibility
evidence, not disposable utilities.

## Locked methodology

Repository cleanup and future organization changes must not silently alter the
validated methodology:

- Event codes are `0=CENSOR`, `1=DEFAULT`, and `2=PREPAYMENT`.
- Default primarily begins at the first month with 90+ DPD; documented RA and
  Zero Balance fallbacks remain part of the event logic.
- Same-month default and prepayment is classified as default while retaining
  the conflict flag.
- The survival origin is First Payment Month.
- `duration_months = event_month - first_payment_month + 1`.
- Events before First Payment Month remain available for audit but are excluded
  from the survival risk set; their duration is not clamped.
- Missing core covariates are not imputed. All eligible loans remain in the
  master model dataset, with `core_covariates_complete_flag` identifying the
  complete-case sample.

See the audit reports in `reports/` and the implementation in `src/data/` for
the complete definitions and preserved evidence columns.

## Validated data status

The current local generated datasets validate to:

| Measure | Value |
|---|---:|
| Origination rows | 512,500 |
| Performance rows | 20,097,384 |
| Event-map loans | 512,490 |
| Survival-eligible loans | 505,694 |
| Excluded before First Payment Month | 6,796 |
| Model rows | 505,694 |
| Complete core cases | 500,681 (99.01%) |
| Eligible defaults | 16,556 |
| Eligible prepayments | 206,393 |
| Eligible censors | 282,745 |

The 2026 model dataset contains 6,144 rows, 10 prepayments, 6,134 censors, and
no defaults. This is expected for a partial vintage with short follow-up.

## Tests and validation

Run the event regression suite:

```powershell
python -m unittest tests.test_event_definition -v
```

Compile the three locked data modules:

```powershell
python -m py_compile src\data\event_definition.py
python -m py_compile src\data\survival_duration.py
python -m py_compile src\data\model_dataset.py
```

Run full raw/clean validation when the local datasets are present:

```powershell
python -X utf8 scripts\final_data_validation.py
```

Compact CSV evidence is stored under `outputs/tables/`; human-readable reports
are stored under `reports/`.

## Repository map

```text
src/               reusable ingestion, cleaning, validation, and data logic
scripts/           reproducible runners and audit tools
tests/             unit tests
data/              local source and generated datasets (Git-ignored)
outputs/tables/    compact validation and audit outputs
outputs/figures/   generated figures
outputs/logs/      generated logs
reports/           human-readable validation and cleanup reports
archive/           local review area (Git-ignored)
```

The cleanup decisions and unresolved Git-metadata issue are documented in
`reports/cleanup_manifest.md`.
