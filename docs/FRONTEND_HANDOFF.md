# Frontend Handoff

## A. Backend Status

Backend status: **READY FOR FRONTEND INTEGRATION**

Branch: `backend-huy`

The backend was at `63d134e` at the start of Phase E. The final handoff
commit is the current `HEAD` after this document and the smoke check are
committed.

Published production release: `20260929T085632Z_89d04db`

`results/current.json` is the canonical release resolver. Frontend code must
never hardcode a historical production run path. The resolver verifies that
the selected run is a published production release and verifies its artifacts.

## B. Architecture

```text
Published Production
        |
        v
Dashboard Results Layer
        |
        v
Query Layer
        |
        v
FrontendService
        |
        v
Frontend
```

Frontend integration should use the service/query contract. The frontend
must not refit models, calculate PD/CIF, redefine DEFAULT or PREPAYMENT, read
estimator objects, implement statistical business logic, or infer zero from
NULL values.

## C. Initialize the Backend

Run from the repository root with the project `.venv` selected:

```python
from src.query import FrontendService

service = FrontendService(".")
```

The `"."` argument is the repository root. The canonical data files and
`results/current.json` must be available relative to that directory.

## D. Public Frontend Functions

All methods return `QueryResponse` with `status`, typed `data`, and
`provenance`. `data` is a Polars `DataFrame`; use `response.as_dict()` when a
plain frontend-safe dictionary is required.

### `get_portfolio_summary()`

Purpose: return the published analytical portfolio counts and release
metadata.

Parameters: none.

Fields: `total_loans`, `default_count`, `prepayment_count`, `censor_count`,
`delayed_entry_count`, `data_version`, `performance_cutoff`, `run_id`,
`code_commit`, `specification_version`.

Use: portfolio KPI cards and release metadata. A valid published release
returns `OK`; provenance identifies the production run. Numeric fields are
canonical counts, not frontend-calculated values.

### `get_pd_results()`

Purpose: return published DEFAULT cumulative incidence at fixed horizons.

Parameters: none.

Fields: `horizon_months`, `horizon_role`, `default_cif`, `pd`, `loan_count`,
`n_at_risk`, `default_count`, `prepayment_count`, `follow_up_eligible`,
`follow_up_status`, `data_version`, `model_version`, `run_id`, `code_commit`.

Use: PD cards and horizon charts. `pd` is the already-published DEFAULT CIF.
The current release includes 12, 24, 36, and supplementary 60 months.
Unavailable values remain NULL; do not replace them with zero.

### `get_survival_results()`

Purpose: return published survival and competing-risk curves.

Parameters: none.

Fields: `model`, `model_version`, `endpoint`, `curve_type`, `group_name`,
`group_value`, `analysis_time`, `survival_probability`,
`cumulative_incidence`, `ci_lower`, `ci_upper`, `n_at_risk`, `n_events`,
`n_censored`, `data_version`, `run_id`, `code_commit`.

Use: KM survival and Aalen-Johansen DEFAULT/PREPAYMENT curve visualizations.
KM rows use `survival_probability`; CIF rows use
`cumulative_incidence`. The other curve value is NULL by design.

### `get_risk_driver_results()`

Purpose: return published risk-driver coefficient tables.

Parameters: none.

Fields: `model`, `model_version`, `endpoint`, `predictor`, `coefficient`,
`standard_error`, `hazard_ratio`, `subdistribution_hazard_ratio`, `ci_lower`,
`ci_upper`, `p_value`, `data_version`, `run_id`, `code_commit`.

Use: risk-driver tables or coefficient charts for Baseline Cox, TV-Cox, and
Fine-Gray DEFAULT. A statistic that does not apply to a model is NULL; it is
not substituted or recalculated.

### `get_vintage_results()`

Purpose: return published vintage-by-horizon results.

Parameters: none.

Fields: `vintage_year`, `horizon_months`, `horizon_role`, `default_cif`,
`prepayment_cif`, `pd`, `loan_count`, `n_at_risk`, `default_count`,
`prepayment_count`, `latest_origination_date`, `performance_cutoff`,
`follow_up_eligible`, `follow_up_status`, `data_version`, `model_version`,
`run_id`, `code_commit`.

Use: vintage comparison tables and charts. Ineligible fixed horizons keep
their result fields NULL and identify the reason with
`follow_up_status = INSUFFICIENT_FOLLOW_UP`.

### `get_model_diagnostics()`

Purpose: return published model convergence and PH diagnostic findings.

Parameters: none.

Fields: `model`, `model_version`, `diagnostic_type`, `endpoint`, `predictor`,
`status`, `test_statistic`, `degrees_of_freedom`, `p_value`, `alpha`,
`convergence_status`, `convergence_warning`, `n_observations`, `n_events`,
`n_censored`, `n_predictors`, `delayed_entry_count`, `data_version`, `run_id`,
`code_commit`.

Use: diagnostics tables and warning indicators. Preserve the reported status;
`FLAGGED` is not `PASS`.

### `get_loan_profile(loan_id)`

Purpose: return one canonical profile row for a loan.

Parameters: `loan_id: str`.

Fields: `loan_id`, `fico`, `original_ltv`, `original_cltv`, `original_dti`,
`original_upb`, `original_interest_rate`, `original_loan_term`,
`loan_purpose`, `occupancy_status`, `property_state`, `property_type`,
`first_payment_month`, `maturity_month`, `operational_origination_date`,
`vintage_year`, `event_type`, `event_code`, `event_source`, `event_date`,
`default_flag`, `prepayment_flag`, `censor_flag`, `entry_time_month`,
`exit_time_month`, `duration_months`, `survival_eligible`.

Use: loan search and profile view. A valid loan returns `OK` and exactly one
row. An unknown loan returns `NOT_FOUND` with an empty typed result. An empty
identifier returns `EMPTY`. Event and survival fields are canonical values;
the frontend must not reclassify them.

### `get_loan_timeline(loan_id)`

Purpose: return the requested loan's monthly performance history.

Parameters: `loan_id: str`.

Fields: `loan_id`, `monthly_reporting_period`, `reporting_month`,
`performance_month`, `loan_age`, `freddie_loan_age`, `current_actual_upb`,
`current_interest_bearing_upb`, `delinquency_status_raw`,
`current_delinquency_status`, `delinquency_num`, `current_interest_rate`,
`remaining_months_maturity`, `modification_flag`, `payment_deferral_flag`,
`borrower_assistance_plan`, `delinquency_due_to_disaster`,
`zero_balance_code`, `zero_balance_effective_date`,
`zero_balance_effective_month`, `estimated_ltv`, `estimated_ltv_raw`, `ddlpi`,
`ddlpi_month`.

Use: monthly loan history charts and tables. The result is already sorted by
`performance_month`. The lookup uses a lazy, loan-scoped Parquet scan and
does not create a frontend copy of the full performance table. Unknown loans
return `NOT_FOUND`; an empty identifier returns `EMPTY`.

## E. Response Contract

```text
QueryResponse
  status
  data
  provenance
```

Supported statuses:

- `OK`: valid request with available data.
- `NOT_FOUND`: requested `loan_id` does not exist.
- `EMPTY`: empty identifier or another defined empty result state.

`QueryResponse.as_dict()` is the frontend-safe serialization path. It returns
`status` as a string, `data` as a list of row dictionaries, and provenance as
a dictionary. `None`/NULL means unavailable or not applicable. NULL must never
automatically become zero.

## F. Dashboard Mapping

| Frontend view | Backend method | Recommended use |
|---|---|---|
| Portfolio overview | `get_portfolio_summary()` | KPI values and release metadata |
| PD cards/chart | `get_pd_results()` | Published horizon PD/CIF values |
| Survival / competing-risk curves | `get_survival_results()` | KM and DEFAULT/PREPAYMENT CIF curves |
| Risk-driver table/chart | `get_risk_driver_results()` | Published model coefficients |
| Vintage analysis | `get_vintage_results()` | Vintage/horizon comparison |
| Model diagnostics | `get_model_diagnostics()` | Status and warning display |
| Loan search/profile | `get_loan_profile(loan_id)` | One-loan profile |
| Loan monthly history | `get_loan_timeline(loan_id)` | Chronological performance history |

This document does not prescribe frontend styling.

## G. Statistical Semantics

The frontend must preserve these backend meanings:

```text
PD(t) = published DEFAULT CIF(t)
```

Do not use `1 - KM` as competing-risk DEFAULT PD.

Canonical event mapping:

- DEFAULT: Zero Balance Code `03` / `09`.
- PREPAYMENT: Zero Balance Code `01`.
- CENSOR: `02` / `15` / `16` / `96` and surviving/censored cases under the
  canonical backend rules.

Do not derive DEFAULT from delinquency status. The backend has already derived
event and survival fields.

Known diagnostic findings:

- `original_ltv` PH status: `FLAGGED`.
- Global PH status: `FLAGGED`.

The frontend must not display these findings as `PASS`.

For vintage results, an ineligible horizon retains NULL result values and an
explicit insufficient-follow-up status. Never display that NULL as zero.

## H. Current Verified Portfolio Values

These are verified values from the current published release, not constants
to hardcode into frontend code:

| Value | Current release |
|---|---:|
| Total loans | 504405 |
| DEFAULT | 204 |
| PREPAYMENT | 212269 |
| CENSOR | 291932 |
| Delayed entry | 34347 |
| PD 12M | 0.000009 |
| PD 24M | 0.000103 |
| PD 36M | 0.000267 |
| PD 60M | 0.000480 |

## I. Loan Lookup Example

```python
profile = service.get_loan_profile("F16Q10000006")
timeline = service.get_loan_timeline("F16Q10000006")

assert profile.status.value == "OK"
assert timeline.status.value == "OK"
```

The timeline is already chronological.

```python
unknown = service.get_loan_profile("UNKNOWN_LOAN")
assert unknown.status.value == "NOT_FOUND"
```

## J. Smoke Test

Run this from the repository root in PowerShell. Piping the here-string to
Python avoids PowerShell quoting problems:

```powershell
$code = @'
from src.query import FrontendService

service = FrontendService(".")
checks = [
    ("portfolio", service.get_portfolio_summary()),
    ("pd", service.get_pd_results()),
    ("survival", service.get_survival_results()),
    ("risk_drivers", service.get_risk_driver_results()),
    ("vintage", service.get_vintage_results()),
    ("diagnostics", service.get_model_diagnostics()),
    ("loan_profile", service.get_loan_profile("F16Q10000006")),
    ("loan_timeline", service.get_loan_timeline("F16Q10000006")),
    ("unknown loan", service.get_loan_profile("UNKNOWN_LOAN")),
]
for name, response in checks:
    print(f"{name} -> {response.status.value}")
'@
$code | .\.venv\Scripts\python.exe -
```

Expected statuses:

```text
portfolio -> OK
pd -> OK
survival -> OK
risk_drivers -> OK
vintage -> OK
diagnostics -> OK
loan_profile -> OK
loan_timeline -> OK
unknown loan -> NOT_FOUND
```

The smoke test intentionally does not claim permanent row counts.

## K. Frontend Technology Note

This handoff provides a local Python service/facade, not an HTTP REST API.

- Streamlit or another Python frontend can consume `FrontendService` directly.
- React, Vue, or browser-only JavaScript will still need an HTTP adapter layer.

No HTTP framework or localhost port is provided by this phase. Do not assume
that `localhost:8000` exists.

## L. Files Frontend Should Care About

| Path | Role |
|---|---|
| `src/query/service.py` | Primary `FrontendService` facade |
| `src/query/queries.py` | Query functions and response contract; backend integration surface |
| `src/query/__init__.py` | Public query imports |
| `src/results/dashboard.py` | Backend-internal Phase B result projections |
| `results/current.json` | Canonical published release resolver; backend-internal input |
| `docs/FRONTEND_HANDOFF.md` | This integration guide |

Frontend developers should normally import `src.query.FrontendService` and
should not read production artifact paths directly.

## M. Run Requirements

- Activate or select the project `.venv`.
- Run from the repository root.
- Keep the canonical data files available locally.
- Keep `results/current.json` available and resolving to a valid published
  production release.
- No deployment infrastructure is implied by this handoff.

## N. Known Warnings and Limitations

- PH `original_ltv` is `FLAGGED`.
- Global PH status is `FLAGGED`.
- The current service is a local Python facade, not an HTTP API.
- The large performance source is queried lazily by loan ID.
- A pytest cache permission warning is environmental and non-blocking.
- The current published release uses performance cutoff `202603` and data
  version `freddie_sample_2016_2026_cutoff_202603_v1`.
- Current release provenance is run `20260929T085632Z_89d04db`; resolve it via
  `results/current.json` rather than hardcoding that path.