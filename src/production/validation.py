"""Semantic validation gate for a complete production analytical release."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import polars as pl

from src.competing_risks.aalen_johansen import validate_aalen_johansen_results
from src.competing_risks.cause_specific import (
    validate_cause_specific_diagnostics,
    validate_cause_specific_results,
)
from src.competing_risks.fine_gray import (
    validate_fine_gray_diagnostics,
    validate_fine_gray_results,
)
from src.competing_risks.pd_vintage import (
    validate_overall_pd_results,
    validate_vintage_cif_results,
    validate_vintage_horizon_results,
)
from src.production.contracts import (
    ANALYTICAL_ARTIFACTS,
    ARTIFACT_FILES,
    COMPLETE_RELEASE_ARTIFACTS,
    INPUT_CONTRACTS,
    INPUT_PROVENANCE_ARTIFACT,
    VALIDATION_REPORT_ARTIFACT,
)
from src.results.manifest import RunEnvironment, RunManifest, validate_run_manifest
from src.results.writers import atomic_write_json
from src.survival.cox_model import validate_cox_diagnostics, validate_cox_results
from src.survival.kaplan_meier import validate_km_results
from src.survival.ph_test import (
    PH_DIAGNOSTIC_DTYPES,
    PH_GLOBAL_DIAGNOSTIC_DTYPES,
    validate_ph_diagnostics,
    validate_ph_global_diagnostics,
)
from src.survival.time_varying_cox_model import (
    validate_time_varying_cox_diagnostics,
    validate_time_varying_cox_results,
)


class ProductionValidationError(ValueError):
    """Raised when a production release fails semantic validation."""


def _read_table(path: Path) -> pl.DataFrame:
    if path.suffix == ".csv":
        schema = {
            "ph_diagnostics.csv": PH_DIAGNOSTIC_DTYPES,
            "ph_global_diagnostics.csv": PH_GLOBAL_DIAGNOSTIC_DTYPES,
        }.get(path.name)
        return pl.read_csv(path, schema_overrides=schema)
    return pl.read_parquet(path)


def _validator_map() -> dict[str, Callable[[pl.DataFrame], pl.DataFrame]]:
    return {
        "km_results": validate_km_results,
        "cox_results": validate_cox_results,
        "cox_diagnostics": validate_cox_diagnostics,
        "ph_diagnostics": validate_ph_diagnostics,
        "ph_global_diagnostics": validate_ph_global_diagnostics,
        "time_varying_cox_results": validate_time_varying_cox_results,
        "time_varying_cox_diagnostics": validate_time_varying_cox_diagnostics,
        "cause_specific_default_results": lambda frame: validate_cause_specific_results(frame, "DEFAULT"),
        "cause_specific_default_diagnostics": lambda frame: validate_cause_specific_diagnostics(frame, "DEFAULT"),
        "cause_specific_prepayment_results": lambda frame: validate_cause_specific_results(frame, "PREPAYMENT"),
        "cause_specific_prepayment_diagnostics": lambda frame: validate_cause_specific_diagnostics(frame, "PREPAYMENT"),
        "aalen_johansen_results": validate_aalen_johansen_results,
        "fine_gray_default_results": validate_fine_gray_results,
        "fine_gray_default_diagnostics": validate_fine_gray_diagnostics,
        "overall_pd_horizons": validate_overall_pd_results,
        "vintage_cif_results": validate_vintage_cif_results,
        "vintage_horizon_results": validate_vintage_horizon_results,
    }


def _check_counts(tables: dict[str, pl.DataFrame]) -> None:
    complete = INPUT_CONTRACTS["complete_cases"].reconciliation
    analytical = INPUT_CONTRACTS["analysis_loans"].reconciliation
    expected_complete = INPUT_CONTRACTS["complete_cases"].row_count
    expected_analysis = INPUT_CONTRACTS["analysis_loans"].row_count

    cox = tables["cox_diagnostics"].row(0, named=True)
    if (
        cox["n_observations"] != expected_complete
        or cox["n_events"] != complete["DEFAULT"]
        or cox["delayed_entry_count"] != complete["delayed_entry"]
    ):
        raise ProductionValidationError("Baseline Cox counts do not reconcile.")

    for endpoint in ("default", "prepayment"):
        row = tables[f"cause_specific_{endpoint}_diagnostics"].row(0, named=True)
        event = endpoint.upper()
        if (
            row["n_observations"] != expected_complete
            or row["n_events"] != complete[event]
            or row["delayed_entry_count"] != complete["delayed_entry"]
        ):
            raise ProductionValidationError(
                f"Cause-specific {event} counts do not reconcile."
            )

    fine_gray = tables["fine_gray_default_diagnostics"].row(0, named=True)
    if (
        fine_gray["n_input_loans"] != expected_complete
        or fine_gray["n_default"] != complete["DEFAULT"]
        or fine_gray["n_prepayment"] != complete["PREPAYMENT"]
        or fine_gray["n_censored"] != complete["CENSOR"]
        or fine_gray["n_delayed_entry"] != complete["delayed_entry"]
    ):
        raise ProductionValidationError("Fine-Gray counts do not reconcile.")

    overall = tables["overall_pd_horizons"]
    if (
        overall["loan_count"].unique().to_list() != [expected_analysis]
        or overall["default_count"].unique().to_list() != [analytical["DEFAULT"]]
        or overall["prepayment_count"].unique().to_list()
        != [analytical["PREPAYMENT"]]
    ):
        raise ProductionValidationError("Overall PD counts do not reconcile.")


def _validate_provenance(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProductionValidationError("Input provenance JSON is invalid.") from exc
    if payload.get("overall_status") != "PASS":
        raise ProductionValidationError("Input provenance did not pass.")
    roles = {item.get("role") for item in payload.get("inputs", [])}
    if roles != set(INPUT_CONTRACTS):
        raise ProductionValidationError("Input provenance inventory is incomplete.")
    if any(item.get("status") != "PASS" for item in payload["inputs"]):
        raise ProductionValidationError("Input provenance contains a failed input.")
    return payload


def validate_production_release(
    manifest: RunManifest,
    *,
    run_root: Path,
    report_path: Path,
    validated_at_utc: datetime | None = None,
) -> dict[str, object]:
    """Validate an unpublished release and always write a durable report."""
    item = validate_run_manifest(manifest)
    checks: list[dict[str, object]] = []

    def check(name: str, operation: Callable[[], object]) -> object | None:
        try:
            value = operation()
            checks.append({"name": name, "status": "PASS"})
            return value
        except Exception as exc:
            checks.append({"name": name, "status": "FAIL", "detail": str(exc)})
            return None

    check(
        "production_environment",
        lambda: item.environment is RunEnvironment.PRODUCTION
        or (_ for _ in ()).throw(ProductionValidationError("Run is not PRODUCTION.")),
    )
    registered = {record.logical_name: record for record in item.artifacts}
    expected_before_report = set(COMPLETE_RELEASE_ARTIFACTS) - {
        VALIDATION_REPORT_ARTIFACT
    }
    check(
        "artifact_inventory",
        lambda: set(registered) == expected_before_report
        or (_ for _ in ()).throw(
            ProductionValidationError(
                f"Expected {sorted(expected_before_report)}, observed {sorted(registered)}."
            )
        ),
    )
    check(
        "no_mock_artifacts",
        lambda: all("mock" not in record.relative_path.lower() for record in item.artifacts)
        or (_ for _ in ()).throw(ProductionValidationError("MOCK path in production run.")),
    )

    tables: dict[str, pl.DataFrame] = {}
    for logical_name in ANALYTICAL_ARTIFACTS:
        expected_path = ARTIFACT_FILES[logical_name]
        record = registered.get(logical_name)
        if record is None:
            continue
        check(
            f"path:{logical_name}",
            lambda record=record, expected_path=expected_path: record.relative_path
            == expected_path
            or (_ for _ in ()).throw(
                ProductionValidationError("Artifact path is not canonical.")
            ),
        )
        path = run_root / record.relative_path
        table = check(f"schema_and_semantics:{logical_name}", lambda path=path, logical_name=logical_name: _validator_map()[logical_name](_read_table(path)))
        if isinstance(table, pl.DataFrame):
            tables[logical_name] = table
            check(
                f"row_count:{logical_name}",
                lambda record=record, table=table: record.row_count == table.height
                or (_ for _ in ()).throw(
                    ProductionValidationError("Manifest row count is inconsistent.")
                ),
            )

    provenance_record = registered.get(INPUT_PROVENANCE_ARTIFACT)
    if provenance_record is not None:
        check(
            "input_provenance",
            lambda: _validate_provenance(run_root / provenance_record.relative_path),
        )
    if set(tables) == set(ANALYTICAL_ARTIFACTS):
        check("cross_artifact_count_reconciliation", lambda: _check_counts(tables))

    status = "PASS" if all(entry["status"] == "PASS" for entry in checks) else "FAIL"
    timestamp = validated_at_utc or datetime.now(timezone.utc)
    report = {
        "run_id": item.run_id,
        "code_commit": item.code_commit,
        "data_version": item.data_version,
        "validated_at_utc": timestamp.astimezone(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "checks": checks,
        "overall_status": status,
    }
    atomic_write_json(report_path, report)
    if status != "PASS":
        raise ProductionValidationError(
            f"Production semantic validation failed; see {report_path}."
        )
    return report


def require_complete_registered_inventory(manifest: RunManifest) -> None:
    observed = {record.logical_name for record in manifest.artifacts}
    if observed != set(COMPLETE_RELEASE_ARTIFACTS):
        raise ProductionValidationError(
            f"Complete release inventory required; observed {sorted(observed)}."
        )
