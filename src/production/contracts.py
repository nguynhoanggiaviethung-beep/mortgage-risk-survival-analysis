"""Version-specific contracts for the current production data release."""

from __future__ import annotations

from dataclasses import dataclass

from src.results.manifest import DATA_VERSION


@dataclass(frozen=True)
class InputContract:
    relative_path: str
    role: str
    sha256: str
    byte_size: int
    row_count: int
    reconciliation: dict[str, int]


INPUT_CONTRACTS: dict[str, InputContract] = {
    "analysis_loans": InputContract(
        relative_path="data/model/analysis_loans_2016_2026.parquet",
        role="canonical analytical loan-level population",
        sha256="0df2313bd17bc1a2884cf33b65db593543b899c0589ea84f0ce86e702b99bc54",
        byte_size=10_533_726,
        row_count=504_405,
        reconciliation={
            "DEFAULT": 204,
            "PREPAYMENT": 212_269,
            "CENSOR": 291_932,
            "delayed_entry": 34_347,
        },
    ),
    "complete_cases": InputContract(
        relative_path="data/model/baseline_complete_cases_2016_2026.parquet",
        role="canonical complete-case static-model population",
        sha256="c1b7a0cad480c787d58b055576d6e1bc6a94ac9de1eb425481cd8622e1f0dcd7",
        byte_size=10_367_271,
        row_count=499_393,
        reconciliation={
            "DEFAULT": 181,
            "PREPAYMENT": 209_404,
            "CENSOR": 289_808,
            "delayed_entry": 33_757,
        },
    ),
    "performance": InputContract(
        relative_path="data/processed/performance.parquet",
        role="canonical monthly performance source for time-varying Cox",
        sha256="1a5553ec655a09b9a77369ea851051a265d06ab9785fbb1d3de719eae5ce78ee",
        byte_size=206_940_730,
        row_count=20_097_384,
        reconciliation={},
    ),
}

if DATA_VERSION != "freddie_sample_2016_2026_cutoff_202603_v1":
    raise RuntimeError("Production input contracts do not match DATA_VERSION.")


ANALYTICAL_ARTIFACTS: tuple[str, ...] = (
    "km_results",
    "cox_results",
    "cox_diagnostics",
    "ph_diagnostics",
    "ph_global_diagnostics",
    "time_varying_cox_results",
    "time_varying_cox_diagnostics",
    "cause_specific_default_results",
    "cause_specific_default_diagnostics",
    "cause_specific_prepayment_results",
    "cause_specific_prepayment_diagnostics",
    "aalen_johansen_results",
    "fine_gray_default_results",
    "fine_gray_default_diagnostics",
    "overall_pd_horizons",
    "vintage_cif_results",
    "vintage_horizon_results",
)

INPUT_PROVENANCE_ARTIFACT = "input_provenance"
VALIDATION_REPORT_ARTIFACT = "production_validation_report"
COMPLETE_RELEASE_ARTIFACTS = (
    *ANALYTICAL_ARTIFACTS,
    INPUT_PROVENANCE_ARTIFACT,
    VALIDATION_REPORT_ARTIFACT,
)

ARTIFACT_FILES: dict[str, str] = {
    "km_results": "models/km_results.parquet",
    "cox_results": "models/cox_results.parquet",
    "cox_diagnostics": "diagnostics/cox_diagnostics.parquet",
    "ph_diagnostics": "diagnostics/ph_diagnostics.csv",
    "ph_global_diagnostics": "diagnostics/ph_global_diagnostics.csv",
    "time_varying_cox_results": "models/time_varying_cox_results.parquet",
    "time_varying_cox_diagnostics": "diagnostics/time_varying_cox_diagnostics.parquet",
    "cause_specific_default_results": "models/cause_specific_default_results.parquet",
    "cause_specific_default_diagnostics": "diagnostics/cause_specific_default_diagnostics.parquet",
    "cause_specific_prepayment_results": "models/cause_specific_prepayment_results.parquet",
    "cause_specific_prepayment_diagnostics": "diagnostics/cause_specific_prepayment_diagnostics.parquet",
    "aalen_johansen_results": "models/aalen_johansen_results.parquet",
    "fine_gray_default_results": "models/fine_gray_default_results.parquet",
    "fine_gray_default_diagnostics": "diagnostics/fine_gray_default_diagnostics.parquet",
    "overall_pd_horizons": "derived/overall_pd_horizons.parquet",
    "vintage_cif_results": "models/vintage_cif_results.parquet",
    "vintage_horizon_results": "derived/vintage_horizon_results.parquet",
    INPUT_PROVENANCE_ARTIFACT: "provenance/input_provenance.json",
    VALIDATION_REPORT_ARTIFACT: "validation/production_validation_report.json",
}

ARTIFACT_TYPES: dict[str, str] = {
    **{name: "MODEL_RESULT" for name in ANALYTICAL_ARTIFACTS},
    "cox_diagnostics": "DIAGNOSTIC_RESULT",
    "ph_diagnostics": "DIAGNOSTIC_RESULT",
    "ph_global_diagnostics": "DIAGNOSTIC_RESULT",
    "time_varying_cox_diagnostics": "DIAGNOSTIC_RESULT",
    "cause_specific_default_diagnostics": "DIAGNOSTIC_RESULT",
    "cause_specific_prepayment_diagnostics": "DIAGNOSTIC_RESULT",
    "fine_gray_default_diagnostics": "DIAGNOSTIC_RESULT",
    "overall_pd_horizons": "ANALYTICAL_DERIVED_RESULT",
    "vintage_horizon_results": "ANALYTICAL_DERIVED_RESULT",
    INPUT_PROVENANCE_ARTIFACT: "INPUT_PROVENANCE",
    VALIDATION_REPORT_ARTIFACT: "VALIDATION_REPORT",
}

PRODUCERS: dict[str, str] = {
    "km_results": "kaplan_meier",
    "cox_results": "cox_ph",
    "cox_diagnostics": "cox_ph",
    "ph_diagnostics": "cox_ph",
    "ph_global_diagnostics": "cox_ph",
    "time_varying_cox_results": "time_varying_cox",
    "time_varying_cox_diagnostics": "time_varying_cox",
    "cause_specific_default_results": "cause_specific_default",
    "cause_specific_default_diagnostics": "cause_specific_default",
    "cause_specific_prepayment_results": "cause_specific_prepayment",
    "cause_specific_prepayment_diagnostics": "cause_specific_prepayment",
    "aalen_johansen_results": "aalen_johansen",
    "fine_gray_default_results": "fine_gray_default",
    "fine_gray_default_diagnostics": "fine_gray_default",
    "overall_pd_horizons": "pd_horizons",
    "vintage_cif_results": "vintage_analysis",
    "vintage_horizon_results": "vintage_analysis",
    INPUT_PROVENANCE_ARTIFACT: "production_preflight",
    VALIDATION_REPORT_ARTIFACT: "production_validation",
}
