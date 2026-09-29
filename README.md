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
are not stored in Git. Place all 2016–2026 source archives in `src/data/`;
the parser detects each vintage from the archive name:

```text
src/data/<Freddie Mac archive for each vintage 2016–2026>.zip
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
- The survival origin follows the project outline: Origination Month. The
  Freddie Mac extract used here has First Payment Date but no direct
  origination date, so `operational_origination_date` is an explicit proxy
  defined as First Payment Date minus one calendar month.
- `analysis_time_month = performance_month - operational_origination_date`
  in calendar months; the first payment month is analysis month 1. This is
  numerically equivalent to `performance_month - first_payment_month + 1`
  under the stated proxy, but is described as time since proxy origination.
- Loans whose event occurs before their first observed performance month are
  retained for audit and excluded from the survival risk set; time is not
  clamped.
- Missing core covariates are not imputed. All eligible loans remain in the
  master model dataset, with `core_covariates_complete_flag` identifying the
  complete-case sample.
- The time-varying default Cox model uses prior-month UPB, interest rate, and
  1-/2-month delinquency indicators. The 90+ DPD event-month value is excluded
  to prevent target leakage; a 3+-month delinquency predictor has no variation
  before the first-90+ event and is not fitted. The time-varying fit uses a
  fixed L2 penalizer of 0.1 to stabilize near-separation; it is recorded in
  model diagnostics.

See the audit reports in `reports/` and the implementation in `src/data/` for
the complete definitions and preserved evidence columns.

## Modeling workflow

The modeling layer is kept separate from data preparation. After the data
pipeline has produced the validated combined loan-level and monthly files,
the production runner can fit and version the survival and competing-risk
models. It records a run manifest, input fingerprints, model artifacts, and
diagnostics under `results/production/`; mock artifacts are not production
results.

The modeling runner supports a read-only preflight before a full run:

```powershell
python scripts\run_production.py preflight --group python
python scripts\run_production.py preflight --group complete --rscript "C:\path\to\Rscript.exe"
```

The complete model release requires the configured R runtime and the
`survival` package. Build, validate, and publish are separate explicit steps;
publishing is only for a validated run:

```powershell
python scripts\run_production.py build --rscript "C:\path\to\Rscript.exe" --confirm-full-production
python scripts\run_production.py validate --run-id <run-id>
python scripts\run_production.py publish --run-id <run-id> --confirm-publish
```

Do not publish results until the cohort, time origin, data cutoff, event
mapping, and model inputs match the locked specification. The production
preflight checks that code is committed and records each local input's row
count and SHA-256. Model-specific input validators enforce the schemas and
event/time consistency before estimation. Reconcile counts against a fresh
pipeline validation report before treating a run as a research result.

## Validated data status

The current local generated datasets validate to:

| Measure | Value |
|---|---:|
| Origination rows | 512,500 |
| Performance rows | 20,097,384 |
| Event-map loans | 512,489 |
| Explicit event-date exclusions | 1 |
| Survival-eligible loans | 504,405 |
| Excluded before first observed performance | 8,084 |
| Model rows | 504,405 |
| Complete core cases | 499,393 (99.01%) |
| Eligible defaults | 16,556 |
| Eligible prepayments | 206,175 |
| Eligible censors | 281,674 |

One 2025 loan with a termination code but no valid effective date is excluded
from the event map and recorded in `reports/event_missing_date_2025.csv`.
The 2026 model dataset contains 5,123 eligible rows, 6 prepayments, 5,117
censors, and no defaults. This is expected for a partial vintage with short
follow-up.

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
