"""Stable frontend-facing projections of a published production release."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
import polars as pl

from src.results.integrity import resolve_artifact_path
from src.results.manifest import (
    PathSource,
    RunManifest,
    load_current_run,
)


@dataclass(frozen=True)
class DashboardRelease:
    manifest: RunManifest
    run_root: Path


PORTFOLIO_SCHEMA = {
    "total_loans": pl.UInt32,
    "default_count": pl.UInt32,
    "prepayment_count": pl.UInt32,
    "censor_count": pl.UInt32,
    "delayed_entry_count": pl.UInt32,
    "data_version": pl.String,
    "performance_cutoff": pl.String,
    "run_id": pl.String,
    "code_commit": pl.String,
    "specification_version": pl.String,
}

PD_SCHEMA = {
    "horizon_months": pl.Int16,
    "horizon_role": pl.String,
    "default_cif": pl.Float64,
    "pd": pl.Float64,
    "loan_count": pl.UInt32,
    "n_at_risk": pl.UInt32,
    "default_count": pl.UInt32,
    "prepayment_count": pl.UInt32,
    "follow_up_eligible": pl.Boolean,
    "follow_up_status": pl.String,
    "data_version": pl.String,
    "model_version": pl.String,
    "run_id": pl.String,
    "code_commit": pl.String,
}

SURVIVAL_SCHEMA = {
    "model": pl.String,
    "model_version": pl.String,
    "endpoint": pl.String,
    "curve_type": pl.String,
    "group_name": pl.String,
    "group_value": pl.String,
    "analysis_time": pl.Int32,
    "survival_probability": pl.Float64,
    "cumulative_incidence": pl.Float64,
    "ci_lower": pl.Float64,
    "ci_upper": pl.Float64,
    "n_at_risk": pl.UInt32,
    "n_events": pl.UInt32,
    "n_censored": pl.UInt32,
    "data_version": pl.String,
    "run_id": pl.String,
    "code_commit": pl.String,
}

RISK_DRIVER_SCHEMA = {
    "model": pl.String,
    "model_version": pl.String,
    "endpoint": pl.String,
    "predictor": pl.String,
    "coefficient": pl.Float64,
    "standard_error": pl.Float64,
    "hazard_ratio": pl.Float64,
    "subdistribution_hazard_ratio": pl.Float64,
    "ci_lower": pl.Float64,
    "ci_upper": pl.Float64,
    "p_value": pl.Float64,
    "data_version": pl.String,
    "run_id": pl.String,
    "code_commit": pl.String,
}

VINTAGE_SCHEMA = {
    "vintage_year": pl.Int16,
    "horizon_months": pl.Int16,
    "horizon_role": pl.String,
    "default_cif": pl.Float64,
    "prepayment_cif": pl.Float64,
    "pd": pl.Float64,
    "loan_count": pl.UInt32,
    "n_at_risk": pl.UInt32,
    "default_count": pl.UInt32,
    "prepayment_count": pl.UInt32,
    "latest_origination_date": pl.Date,
    "performance_cutoff": pl.Date,
    "follow_up_eligible": pl.Boolean,
    "follow_up_status": pl.String,
    "data_version": pl.String,
    "model_version": pl.String,
    "run_id": pl.String,
    "code_commit": pl.String,
}

DIAGNOSTIC_SCHEMA = {
    "model": pl.String,
    "model_version": pl.String,
    "diagnostic_type": pl.String,
    "endpoint": pl.String,
    "predictor": pl.String,
    "status": pl.String,
    "test_statistic": pl.Float64,
    "degrees_of_freedom": pl.Int64,
    "p_value": pl.Float64,
    "alpha": pl.Float64,
    "convergence_status": pl.String,
    "convergence_warning": pl.String,
    "n_observations": pl.UInt32,
    "n_events": pl.UInt32,
    "n_censored": pl.UInt32,
    "n_predictors": pl.UInt32,
    "delayed_entry_count": pl.UInt32,
    "data_version": pl.String,
    "run_id": pl.String,
    "code_commit": pl.String,
}


def resolve_dashboard_release(repository_root: PathSource = ".") -> DashboardRelease:
    root = Path(repository_root)
    pointer_path = root / "results" / "current.json"
    manifest = load_current_run(pointer_path, repository_root=root)
    pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    manifest_path = resolve_artifact_path(root, pointer["manifest_relative_path"])
    return DashboardRelease(manifest=manifest, run_root=manifest_path.parent)


def _artifact(release: DashboardRelease, logical_name: str) -> Path:
    record = next(
        item for item in release.manifest.artifacts if item.logical_name == logical_name
    )
    return release.run_root / record.relative_path


def _read(release: DashboardRelease, logical_name: str) -> pl.DataFrame:
    path = _artifact(release, logical_name)
    return pl.read_csv(path) if path.suffix == ".csv" else pl.read_parquet(path)


def _attach(frame: pl.DataFrame, release: DashboardRelease, schema: dict[str, pl.DataType]) -> pl.DataFrame:
    output = frame
    for name, dtype in schema.items():
        if name not in output.columns:
            output = output.with_columns(pl.lit(None, dtype=dtype).alias(name))
        else:
            output = output.with_columns(pl.col(name).cast(dtype).alias(name))
    float_columns = [name for name, dtype in schema.items() if dtype == pl.Float64]
    for name in float_columns:
        if output.filter(pl.col(name).is_nan() | pl.col(name).is_infinite()).height:
            raise ValueError(f"Dashboard result contains non-finite values: {name}")
    return output.select(list(schema))


def portfolio_summary(release: DashboardRelease) -> pl.DataFrame:
    provenance = json.loads(
        (_artifact(release, "input_provenance")).read_text(encoding="utf-8")
    )
    analysis = next(item for item in provenance["inputs"] if item["role"] == "analysis_loans")
    counts = analysis["reconciliation"]
    return pl.DataFrame(
        [{
            "total_loans": analysis["row_count"],
            "default_count": counts["DEFAULT"],
            "prepayment_count": counts["PREPAYMENT"],
            "censor_count": counts["CENSOR"],
            "delayed_entry_count": counts["delayed_entry"],
            "data_version": release.manifest.data_version,
            "performance_cutoff": release.manifest.performance_cutoff,
            "run_id": release.manifest.run_id,
            "code_commit": release.manifest.code_commit,
            "specification_version": release.manifest.specification_version,
        }],
        schema=PORTFOLIO_SCHEMA,
    )


def pd_results(release: DashboardRelease) -> pl.DataFrame:
    source = _read(release, "overall_pd_horizons").filter(
        pl.col("horizon_months").is_in([12, 24, 36, 60])
    )
    return _attach(
        source.with_columns(
            pl.lit(release.manifest.data_version).alias("data_version"),
            pl.lit(release.manifest.model_versions["pd_horizons"]).alias("model_version"),
            pl.lit(release.manifest.run_id).alias("run_id"),
            pl.lit(release.manifest.code_commit).alias("code_commit"),
        ),
        release,
        PD_SCHEMA,
    ).sort("horizon_months")


def survival_results(release: DashboardRelease) -> pl.DataFrame:
    km = _read(release, "km_results").select(
        pl.lit("KAPLAN_MEIER").alias("model"),
        pl.lit(release.manifest.model_versions["kaplan_meier"]).alias("model_version"),
        pl.col("endpoint").str.to_uppercase(),
        pl.lit("SURVIVAL").alias("curve_type"),
        "group_name", "group_value", "analysis_time",
        pl.col("survival").alias("survival_probability"),
        pl.lit(None, dtype=pl.Float64).alias("cumulative_incidence"),
        "ci_lower", "ci_upper", "n_at_risk", "n_events", "n_censored",
    )
    aj = _read(release, "aalen_johansen_results").select(
        pl.lit("AALEN_JOHANSEN").alias("model"),
        pl.lit(release.manifest.model_versions["aalen_johansen"]).alias("model_version"),
        "endpoint", pl.col("endpoint").str.to_uppercase().map_elements(
            lambda value: f"{value}_CIF", return_dtype=pl.String
        ).alias("curve_type"),
        "group_name", "group_value", "analysis_time",
        pl.lit(None, dtype=pl.Float64).alias("survival_probability"),
        pl.col("cumulative_incidence"), "ci_lower", "ci_upper", "n_at_risk",
        pl.lit(None, dtype=pl.UInt32).alias("n_events"),
        pl.lit(None, dtype=pl.UInt32).alias("n_censored"),
    )
    return _attach(
        pl.concat([km, aj], how="vertical").with_columns(
            pl.lit(release.manifest.data_version).alias("data_version"),
            pl.lit(release.manifest.run_id).alias("run_id"),
            pl.lit(release.manifest.code_commit).alias("code_commit"),
        ),
        release,
        SURVIVAL_SCHEMA,
    ).sort(["model", "endpoint", "analysis_time"])


def risk_driver_results(release: DashboardRelease) -> pl.DataFrame:
    sources = (
        ("cox_results", "BASELINE_COX", "cox_ph"),
        ("time_varying_cox_results", "TV_COX", "time_varying_cox"),
        ("fine_gray_default_results", "FINE_GRAY_DEFAULT", "fine_gray_default"),
        ("cause_specific_default_results", "CAUSE_SPECIFIC_DEFAULT", "cause_specific_default"),
        ("cause_specific_prepayment_results", "CAUSE_SPECIFIC_PREPAYMENT", "cause_specific_prepayment"),
    )
    frames = []
    for artifact, model, version_key in sources:
        source = _read(release, artifact)
        frames.append(source.select(
            pl.lit(model).alias("model"),
            pl.lit(release.manifest.model_versions[version_key]).alias("model_version"),
            pl.col("endpoint").str.to_uppercase(),
            pl.col("variable").alias("predictor"),
            "coefficient", "standard_error",
            pl.col("hazard_ratio")
            if "hazard_ratio" in source.columns
            else pl.lit(None, dtype=pl.Float64).alias("hazard_ratio"),
            pl.col("subdistribution_hazard_ratio")
            if "subdistribution_hazard_ratio" in source.columns
            else pl.lit(None, dtype=pl.Float64).alias("subdistribution_hazard_ratio"),
            "ci_lower", "ci_upper", "p_value",
        ))
    return _attach(
        pl.concat(frames, how="vertical").with_columns(
            pl.lit(release.manifest.data_version).alias("data_version"),
            pl.lit(release.manifest.run_id).alias("run_id"),
            pl.lit(release.manifest.code_commit).alias("code_commit"),
        ),
        release,
        RISK_DRIVER_SCHEMA,
    ).sort(["model", "predictor"])


def vintage_results(release: DashboardRelease) -> pl.DataFrame:
    source = _read(release, "vintage_horizon_results")
    return _attach(
        source.with_columns(
            pl.lit(release.manifest.data_version).alias("data_version"),
            pl.lit(release.manifest.model_versions["vintage_analysis"]).alias("model_version"),
            pl.lit(release.manifest.run_id).alias("run_id"),
            pl.lit(release.manifest.code_commit).alias("code_commit"),
        ),
        release,
        VINTAGE_SCHEMA,
    ).sort(["vintage_year", "horizon_months"])


def model_diagnostics(release: DashboardRelease) -> pl.DataFrame:
    frames = []
    for artifact, model, version_key in (
        ("cox_diagnostics", "BASELINE_COX", "cox_ph"),
        ("ph_diagnostics", "BASELINE_COX", "cox_ph"),
        ("ph_global_diagnostics", "BASELINE_COX", "cox_ph"),
        ("time_varying_cox_diagnostics", "TV_COX", "time_varying_cox"),
        ("fine_gray_default_diagnostics", "FINE_GRAY_DEFAULT", "fine_gray_default"),
        ("cause_specific_default_diagnostics", "CAUSE_SPECIFIC_DEFAULT", "cause_specific_default"),
        ("cause_specific_prepayment_diagnostics", "CAUSE_SPECIFIC_PREPAYMENT", "cause_specific_prepayment"),
    ):
        source = _read(release, artifact)
        diagnostic_type = artifact.removesuffix("_diagnostics")
        frames.append(source.with_columns(
            pl.lit(model).alias("model"),
            pl.lit(release.manifest.model_versions[version_key]).alias("model_version"),
            pl.lit(diagnostic_type).alias("diagnostic_type"),
            pl.col("endpoint").str.to_uppercase().alias("endpoint")
            if "endpoint" in source.columns
            else pl.lit(None, dtype=pl.String).alias("endpoint"),
            pl.col("variable").alias("predictor")
            if "variable" in source.columns
            else pl.lit(None, dtype=pl.String).alias("predictor"),
            pl.col("ph_status").alias("status")
            if "ph_status" in source.columns
            else pl.col("convergence_status").alias("status")
            if "convergence_status" in source.columns
            else pl.lit(None, dtype=pl.String).alias("status"),
        ))
    return _attach(
        pl.concat(frames, how="diagonal").with_columns(
            pl.lit(release.manifest.data_version).alias("data_version"),
            pl.lit(release.manifest.run_id).alias("run_id"),
            pl.lit(release.manifest.code_commit).alias("code_commit"),
        ),
        release,
        DIAGNOSTIC_SCHEMA,
    ).sort(["model", "diagnostic_type", "predictor"])


__all__ = [
    "DashboardRelease",
    "DIAGNOSTIC_SCHEMA",
    "PD_SCHEMA",
    "PORTFOLIO_SCHEMA",
    "RISK_DRIVER_SCHEMA",
    "SURVIVAL_SCHEMA",
    "VINTAGE_SCHEMA",
    "model_diagnostics",
    "pd_results",
    "portfolio_summary",
    "resolve_dashboard_release",
    "risk_driver_results",
    "survival_results",
    "vintage_results",
]
