"""Small explicit build, validate, and publish orchestration layer."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import polars as pl

from src.competing_risks.aalen_johansen import (
    fit_aalen_johansen,
    write_aalen_johansen_results,
)
from src.competing_risks.cause_specific import (
    fit_paired_cause_specific_models,
    write_cause_specific_artifacts,
)
from src.competing_risks.fine_gray import (
    fit_fine_gray_default,
    write_fine_gray_results,
)
from src.competing_risks.pd_vintage import (
    PDVintageResult,
    build_overall_pd_horizons,
    build_vintage_horizons,
    fit_vintage_cif,
    write_pd_vintage_results,
)
from src.production.contracts import (
    ANALYTICAL_ARTIFACTS,
    ARTIFACT_FILES,
    ARTIFACT_TYPES,
    INPUT_PROVENANCE_ARTIFACT,
    PRODUCERS,
    VALIDATION_REPORT_ARTIFACT,
)
from src.production.preflight import production_preflight, write_input_provenance
from src.production.validation import (
    require_complete_registered_inventory,
    validate_production_release,
)
from src.results.manifest import (
    RunEnvironment,
    RunManifest,
    RunStatus,
    create_run_manifest,
    load_run_manifest,
    mark_run_validated,
    publish_run,
    register_artifact,
    transition_run,
    write_run_manifest,
)
from src.survival.cox_model import fit_cox_model, write_cox_artifacts
from src.survival.kaplan_meier import fit_kaplan_meier, write_km_results
from src.survival.ph_test import run_ph_assumption_test, write_ph_diagnostics
from src.survival.time_varying_cox_model import (
    fit_time_varying_cox_model,
    write_time_varying_cox_artifacts,
)
from src.survival.time_varying_input import build_time_varying_cox_input


class ProductionRunnerError(ValueError):
    """Raised when explicit production orchestration cannot proceed."""


@dataclass(frozen=True)
class ProductionPaths:
    repository_root: Path
    run_root: Path

    @property
    def manifest(self) -> Path:
        return self.run_root / "manifest.json"

    def artifact(self, logical_name: str) -> Path:
        return self.run_root / ARTIFACT_FILES[logical_name]


def create_unique_run(
    repository_root: Path,
    *,
    runtime_versions: dict[str, str],
) -> tuple[RunManifest, ProductionPaths]:
    root = repository_root.resolve()
    manifest = create_run_manifest(
        environment=RunEnvironment.PRODUCTION,
        repository_root=root,
        runtime_versions=runtime_versions,
    )
    run_root = root / "results" / "production" / manifest.run_id
    if run_root.exists():
        raise ProductionRunnerError(f"Run directory already exists: {run_root}.")
    run_root.mkdir(parents=True, exist_ok=False)
    paths = ProductionPaths(root, run_root)
    write_run_manifest(manifest, paths.manifest)
    return manifest, paths


def _register(
    manifest: RunManifest,
    paths: ProductionPaths,
    logical_name: str,
) -> RunManifest:
    path = paths.artifact(logical_name)
    row_count = None
    if path.suffix == ".parquet":
        row_count = pl.scan_parquet(path).select(pl.len()).collect().item()
    elif path.suffix == ".csv":
        row_count = pl.scan_csv(path).select(pl.len()).collect().item()
    updated = register_artifact(
        manifest,
        run_root=paths.run_root,
        logical_name=logical_name,
        relative_path=ARTIFACT_FILES[logical_name],
        artifact_type=ARTIFACT_TYPES[logical_name],
        producer=PRODUCERS[logical_name],
        row_count=row_count,
    )
    write_run_manifest(updated, paths.manifest)
    return updated


def build_complete_release(
    repository_root: Path,
    *,
    rscript: Path,
) -> ProductionPaths:
    """Run every production estimator but deliberately stop in RUNNING state."""
    root = repository_root.resolve()
    preflight = production_preflight(
        root,
        input_roles=("analysis_loans", "complete_cases", "performance"),
        require_r=True,
        rscript=rscript,
    )
    manifest, paths = create_unique_run(
        root, runtime_versions=preflight["runtime_versions"]
    )
    manifest = transition_run(manifest, RunStatus.RUNNING)
    write_run_manifest(manifest, paths.manifest)
    try:
        provenance_path = paths.artifact(INPUT_PROVENANCE_ARTIFACT)
        write_input_provenance(preflight["inputs"], provenance_path)
        manifest = _register(manifest, paths, INPUT_PROVENANCE_ARTIFACT)

        analysis = pl.scan_parquet(
            root / "data/model/analysis_loans_2016_2026.parquet"
        )
        complete = pl.scan_parquet(
            root / "data/model/baseline_complete_cases_2016_2026.parquet"
        )
        performance = pl.scan_parquet(root / "data/processed/performance.parquet")

        km = fit_kaplan_meier(analysis)
        write_km_results(km, paths.artifact("km_results"))
        manifest = _register(manifest, paths, "km_results")

        cox = fit_cox_model(complete)
        write_cox_artifacts(
            cox, paths.artifact("cox_results"), paths.artifact("cox_diagnostics")
        )
        manifest = _register(manifest, paths, "cox_results")
        manifest = _register(manifest, paths, "cox_diagnostics")

        ph = run_ph_assumption_test(cox, complete, rscript=rscript)
        write_ph_diagnostics(
            ph,
            paths.artifact("ph_diagnostics"),
            paths.artifact("ph_global_diagnostics"),
        )
        manifest = _register(manifest, paths, "ph_diagnostics")
        manifest = _register(manifest, paths, "ph_global_diagnostics")

        paired = fit_paired_cause_specific_models(complete)
        for endpoint, result in (
            ("default", paired.default),
            ("prepayment", paired.prepayment),
        ):
            write_cause_specific_artifacts(
                result,
                paths.artifact(f"cause_specific_{endpoint}_results"),
                paths.artifact(f"cause_specific_{endpoint}_diagnostics"),
            )
            manifest = _register(
                manifest, paths, f"cause_specific_{endpoint}_results"
            )
            manifest = _register(
                manifest, paths, f"cause_specific_{endpoint}_diagnostics"
            )

        overall_aj = fit_aalen_johansen(analysis, rscript=rscript)
        write_aalen_johansen_results(
            overall_aj, paths.artifact("aalen_johansen_results")
        )
        manifest = _register(manifest, paths, "aalen_johansen_results")

        overall_pd = build_overall_pd_horizons(analysis, overall_aj)
        vintage_cif = fit_vintage_cif(analysis, rscript=rscript)
        vintage_horizons = build_vintage_horizons(analysis, vintage_cif)
        pd_result = PDVintageResult(overall_pd, vintage_cif, vintage_horizons)
        write_pd_vintage_results(
            pd_result,
            paths.artifact("overall_pd_horizons"),
            paths.artifact("vintage_cif_results"),
            paths.artifact("vintage_horizon_results"),
        )
        for name in (
            "overall_pd_horizons",
            "vintage_cif_results",
            "vintage_horizon_results",
        ):
            manifest = _register(manifest, paths, name)

        fine_gray = fit_fine_gray_default(complete, rscript=rscript)
        write_fine_gray_results(
            fine_gray,
            paths.artifact("fine_gray_default_results"),
            paths.artifact("fine_gray_default_diagnostics"),
        )
        manifest = _register(manifest, paths, "fine_gray_default_results")
        manifest = _register(manifest, paths, "fine_gray_default_diagnostics")

        tv_input = build_time_varying_cox_input(performance, complete)
        tv = fit_time_varying_cox_model(tv_input)
        write_time_varying_cox_artifacts(
            tv,
            paths.artifact("time_varying_cox_results"),
            paths.artifact("time_varying_cox_diagnostics"),
        )
        manifest = _register(manifest, paths, "time_varying_cox_results")
        manifest = _register(manifest, paths, "time_varying_cox_diagnostics")

        if {record.logical_name for record in manifest.artifacts} != {
            *ANALYTICAL_ARTIFACTS,
            INPUT_PROVENANCE_ARTIFACT,
        }:
            raise ProductionRunnerError("Build did not produce the required inventory.")
        return paths
    except Exception:
        failed = transition_run(manifest, RunStatus.FAILED)
        write_run_manifest(failed, paths.manifest)
        raise


def validate_built_release(run_root: Path) -> RunManifest:
    paths = ProductionPaths(run_root.resolve().parents[2], run_root.resolve())
    manifest = load_run_manifest(paths.manifest)
    if manifest.run_status is not RunStatus.RUNNING:
        raise ProductionRunnerError("Only a RUNNING build may be validated.")
    report_path = paths.artifact(VALIDATION_REPORT_ARTIFACT)
    try:
        validate_production_release(
            manifest, run_root=paths.run_root, report_path=report_path
        )
        manifest = _register(manifest, paths, VALIDATION_REPORT_ARTIFACT)
        require_complete_registered_inventory(manifest)
        manifest = mark_run_validated(manifest, run_root=paths.run_root)
        write_run_manifest(manifest, paths.manifest)
        return manifest
    except Exception:
        failed = transition_run(manifest, RunStatus.FAILED)
        write_run_manifest(failed, paths.manifest)
        raise


def publish_validated_release(run_root: Path, repository_root: Path) -> RunManifest:
    root = repository_root.resolve()
    resolved_run = run_root.resolve()
    manifest = load_run_manifest(resolved_run / "manifest.json")
    require_complete_registered_inventory(manifest)
    return publish_run(
        manifest,
        run_root=resolved_run,
        current_path=root / "results/current.json",
        repository_root=root,
    )
