# Backend Architecture

This document records the repository as it exists. It does not authorize a
methodology change. Canonical analytical rules are also summarized in the
root `AGENTS.md`.

## A. Project pipeline

```text
RAW
  -> PROCESSED / STANDARDIZED
  -> MODEL INPUT
  -> MODEL RESULTS
  -> QUERY LAYER          [future; not implemented]
  -> API                  [future; not implemented]
  -> FRONTEND             [outside the current repository]
```

Current code uses top-level modules `src/process_sample.py` and
`src/clean_data.py`; there are no `src/ingestion/` or `src/cleaning/`
packages. Query and HTTP/API packages do not yet exist.

## B. Responsibility map

| Concern | Canonical owner | Inputs | Outputs | Consumers | Must not be recomputed in |
|---|---|---|---|---|---|
| Raw ingestion | `src/process_sample.py`, with layouts from `src/schemas.py` and paths from `src/config.py` | Freddie Mac sample ZIP/TXT | `data/processed/orig_YYYY.parquet`, `perf_YYYY.parquet` | Standardization | Data/model/result/API layers |
| Standardization | `src/clean_data.py` | Parsed yearly Parquet | Clean yearly model files and standardized `origination.parquet`, `performance.parquet` | Canonical data builders | Models, query, API |
| Missing-code conversion | `src/clean_data.py` | Raw Freddie special codes | Typed values, nulls, audit flags; no imputation | Canonical data/model input | Statistical models, query, API |
| Research event mapping | `src/data/event_definition.py` | Standardized origination/performance, ZBC and follow-up | `event_type`, `event_code`, event month/source and audit flags | Survival-time construction | Model modules, results, query, API |
| Analysis-time construction and delayed entry | `src/data/survival_duration.py` | Canonical event map and operational origination fields | `entry_time_month`, `exit_time_month`, `duration_months`, event flags, eligibility | Model-dataset builder and all survival models | Estimators, results, query, API |
| Loan-level model-input construction | `src/data/model_dataset.py`; validation/adapters in `src/survival/model_input.py` | Origination features plus survival duration | One row per eligible loan, canonical event representations and complete-case flag | KM, Cox, TV input, competing risks | Individual estimators |
| Static predictor contract | `CORE_COLUMNS` in `src/data/model_dataset.py` | Standardized origination fields | Ordered five-predictor definition and complete-case flag | Cox, TV-Cox, cause-specific Cox, PH diagnostics | Downstream model/query/API modules |
| KM estimation | `src/survival/kaplan_meier.py` | Validated loan-level KM view | KM result schema/artifact | Future query layer | Query/API/frontend |
| Baseline Cox | `src/survival/cox_model.py` | Complete-case Cox view | Coefficients and model diagnostics | PH diagnostics, future query layer | Query/API/frontend |
| PH diagnostics | `src/survival/ph_test.py` | Step-3 fit and identical training input | Variable/global PH diagnostics | Future query layer | Query/API/frontend |
| Time-varying interval construction | `src/survival/time_varying_input.py` | Canonical loan-level timing/events and monthly performance | Validated start-stop intervals and lagged predictors | TV-Cox | TV estimator, query/API |
| Time-varying Cox | `src/survival/time_varying_cox_model.py` | Validated Step-5A intervals | Coefficients and diagnostics | Future query layer | Query/API/frontend |
| Cause-specific Cox | `src/competing_risks/cause_specific.py` | Canonical event flags/times plus complete-case predictors | DEFAULT and PREPAYMENT coefficients/diagnostics | Future query layer | Query/API/frontend |
| Aalen-Johansen/CIF | `src/competing_risks/aalen_johansen.py` | Canonical `cr_event_code`, event type, entry and exit | DEFAULT/PREPAYMENT CIF, CI and risk-set result | Future PD/query layer | Query/API/frontend |
| Shared R process execution | `src/r_runtime.py` | Installed Rscript, R expression, optional stdin | Captured subprocess result with safe temporary-script cleanup | PH and AJ modules | Individual R-backed models |
| Model/run versioning | `src/results/manifest.py` | Validated artifact metadata and code/data/model versions | Typed run manifest and current pointer | Future runners/query discovery | Estimators and API request handlers |
| Artifact integrity/publication | `src/results/integrity.py`, `src/results/writers.py`, publication functions in `manifest.py` | Persisted files and validated manifest | SHA-256 verification, atomic JSON publication | Future production runners/query loader | Statistical estimation code |
| Future query contracts | Not implemented | Validated versioned model/query artifacts | Eight query datasets | Future API | Model and results layers |
| Future HTTP/API | Not implemented | Query services/contracts | Read-only HTTP responses | Frontend | Data preparation, model fitting, statistical transformation |

`src/data/load_data.py` is an unused pandas/config loader in the current tree;
the active ingestion scripts call `src/process_sample.py`. It is not a second
canonical ingestion owner unless a future task explicitly migrates and tests
the pipeline.

## C. Dependency direction

Allowed direction:

```text
configuration / ingestion / cleaning
    -> canonical data
    -> model-input adapters
    -> statistical models
    -> result persistence/versioning
    -> query [future]
    -> API [future]
```

Current imports are acyclic. Data modules do not import estimators or results.
The results package does not import or fit statistical models. Model packages
do not import future query/API code. Cause-specific Cox reuses the established
Cox result dtype contract; neither package imports the other through its
package initializer.

Scripts are orchestration entry points. They may call owners in dependency
order, but must not become a second home for analytical definitions.

## D. Canonical-source rules

- ZBC-to-event research mapping is defined only in
  `src/data/event_definition.py`.
- `src/data/survival_duration.py` owns operational-origin-relative entry/exit
  time and delayed-entry semantics.
- `src/data/model_dataset.py` creates downstream event indicators and cause
  codes from the canonical event type. These are model-input representations,
  not new event definitions.
- Statistical modules may reject inconsistent event labels, flags, codes, or
  times. Such checks are defensive validation, not permission to inspect ZBC
  or delinquency and reclassify an event.
- TV input maps monthly observations onto the already established analysis
  time axis and validates its outer boundaries. It must not replace upstream
  loan entry/exit times.
- Mock/test fixture builders may construct explicit known labels and flags for
  testing. They are not production business-logic owners.

## E. Schema and grain ownership

| Schema | Owner | Producers | Validators | Consumers |
|---|---|---|---|---|
| Canonical loan-level model input, one row/loan | `src/survival/model_input.py`, based on `src/data/model_dataset.py` output | Data/model builders | `validate_loan_level_input` | KM, Cox adapters, TV input, competing-risk adapters/models |
| KM result | `src/survival/kaplan_meier.py` | `fit_kaplan_meier` | `validate_km_results` | KM writer, future query |
| Cox coefficient and diagnostic schemas | `src/survival/cox_model.py` | `fit_cox_model` | Cox result validators | Cox writer, PH, cause-specific dtype reuse, future query |
| TV-Cox result/diagnostics | `src/survival/time_varying_cox_model.py` | TV fitter | TV result validators | TV writer, future query |
| Cause-specific result/diagnostics | `src/competing_risks/cause_specific.py` | Cause-specific fitter | Cause-specific validators | Cause-specific writer, future query |
| AJ long-format result | `src/competing_risks/aalen_johansen.py` | R survival AJ workflow | AJ result validator | AJ writer, future PD/query |
| Run manifest/artifact record | `src/results/manifest.py` | Run infrastructure callers | `validate_run_manifest`, integrity verification | Publication and future query discovery |

Only schema owners may change field meanings. Consumers may select, filter,
join, or validate; they may not redefine upstream event/time semantics.

## F. Model boundaries and validation

Shared invariants repeated defensively at public model boundaries include:

- required schema and exact types;
- non-null/unique loan IDs for one-row-per-loan inputs;
- `entry_time_month >= 0`, `exit_time_month > entry_time_month`, and
  `duration_months == exit_time_month`;
- canonical event labels and consistency with supplied flags/codes;
- finite required predictors and no silent imputation.

These checks are intentionally local because KM, Cox, competing-risk, and
test fixtures expose different subset schemas and domain-specific exceptions.
Forcing them through the full loan-level validator would add coupling and
break current public input contracts.

Model-specific invariants remain with their model:

- KM probability, confidence and risk-count constraints;
- Cox event endpoint, predictor order, convergence and HR-scale intervals;
- PH input identity with the fitted Step-3 model;
- TV interval contiguity, terminal-event placement, gap flags and lagged-field
  completeness;
- cause-specific paired event flags and endpoint-specific censoring;
- AJ cause-code consistency, paired CIF rows, monotonicity, confidence bounds,
  and sum-of-CIF bound.

Do not introduce a generic validator hierarchy unless two current consumers
can share it without weakening errors, schemas, or public APIs.

## G. Result infrastructure

Estimator modules own their typed numerical result validators and Parquet/CSV
writers. `src/results` owns run identity, model/data/specification versions,
artifact registration, byte checksums, legal run-state transitions, and atomic
publication. It does not estimate, refit, or reinterpret a model.

MOCK artifacts may be registered for compatibility testing but cannot be
published or selected through `current.json` as PRODUCTION.

## H. Future Query/API boundaries

- Query builders will consume validated, versioned artifacts and canonical
  lookup data. They may reshape and filter; they must not refit models,
  reclassify events, or calculate a substitute PD.
- `PD(t)` comes from DEFAULT Aalen-Johansen/CIF output.
- API handlers will validate transport parameters and serve query contracts.
  They must not scan raw ZIPs, run estimators, or implement analytical math.
- The frontend displays API contracts and must not recalculate model
  statistics or reinterpret events.

## I. Do not duplicate

- Do not copy ZBC or delinquency event rules into a model/query/API module.
- Do not recalculate entry/exit from dates downstream of canonical model input.
- Do not create local predictor lists; import `CORE_COLUMNS` or the appropriate
  model-owned ordered contract.
- Do not create an alternative complete-case policy.
- Do not duplicate R temporary-script/subprocess handling; use
  `src/r_runtime.py` and keep domain-specific parsing/errors in the caller.
- Do not write a second manifest, checksum, or production-pointer mechanism.
- Reuse an owner before creating a helper. Add no abstraction without a real
  current reuse case.

## J. Architecture decisions

1. Event derivation is upstream and ZBC-based; estimators consume it.
2. Delayed entry and absolute analysis time are upstream model-input semantics.
3. Models consume and defensively validate canonical model inputs.
4. Competing-risk DEFAULT CIF owns analytical `PD(t)`; `1-KM` does not.
5. Results infrastructure persists, validates integrity, and versions; it does
   not estimate.
6. The future query layer transforms validated results but does not model.
7. The future API serves query contracts but does not calculate analytics.
8. Dependency direction remains one-way and no new abstraction is introduced
   without demonstrated reuse.
