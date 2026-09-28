# Canonical Backend Guardrails

## Project and data

- Project: Mortgage Default & Prepayment: Survival Analysis.
- Dataset: Freddie Mac Single-Family Loan-Level Dataset SAMPLE.
- Canonical analytical cohort: 2016–2026.
- Performance cutoff: `202603` / 31 March 2026.
- Time origin: loan origination using the project's existing operational origination construction.
- Preserve delayed entry in every estimator that supports the analytical data.

## Locked methodology

- Event mapping: ZBC `03`, `09` → DEFAULT; ZBC `01` → PREPAYMENT; ZBC `02`, `15`, `16`, `96` → CENSOR. Blank/no research event is censored subject to locked follow-up rules.
- D90/90+, RA, and XX do not independently create DEFAULT.
- Do not silently impute. Baseline static models use complete cases for required predictors.
- Primary static predictors, exactly: `fico`, `original_ltv`, `original_dti`, `original_interest_rate`, `original_loan_term`.
- Primary horizons: 12, 24, and 36 months. Use 60 months only as supplementary analysis when follow-up is sufficient.
- `PD(t)` is the DEFAULT cumulative incidence function under competing risks. Never represent `1 - KM` as competing-risk PD.
- Any proposed change to cohort, cutoff, event definition, time origin, delayed entry, predictors, PD definition, or missing-data methodology requires explicit approval before implementation.

## Architecture and frontend

`RAW → PROCESSED/STANDARDIZED → MODEL INPUT → MODEL RESULTS → QUERY LAYER → API → FRONTEND`

- Read `docs/BACKEND_ARCHITECTURE.md` before backend changes and obey its dependency direction and schema ownership.
- Reuse canonical owners before creating code: derive once, consume many. Do not duplicate analytical or business logic downstream.
- Add no abstraction without a demonstrated current reuse case.
- The frontend must not recalculate model statistics or reinterpret events.
- Use the `src/results` run/version infrastructure. MOCK runs and artifacts must never be published as PRODUCTION.

## Conflicts, tests, and Git safety

- Current canonical code and specification rules override legacy README logic such as D90/RA default definitions. Report conflicts; do not silently change methodology.
- Run targeted tests after each module. Run the full regression suite at a phase checkpoint, or earlier only when a shared change could affect existing steps.
- Do not commit or push unless explicitly instructed.
- Do not stage or modify unrelated local `config/`, `outputs/`, or `reports/` changes.
