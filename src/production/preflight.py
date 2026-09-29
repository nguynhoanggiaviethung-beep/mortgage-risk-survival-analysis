"""Read-only production preflight, input lineage, and runtime provenance."""

from __future__ import annotations

import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import polars as pl

from src.production.contracts import INPUT_CONTRACTS
from src.results.integrity import sha256_file
from src.results.manifest import (
    DATA_VERSION,
    MODEL_VERSION_REGISTRY,
    collect_runtime_versions,
    current_git_commit,
)
from src.results.writers import atomic_write_json
from src.r_runtime import run_rscript_process


APPROVED_R_VERSION = "4.6.1"
APPROVED_SURVIVAL_VERSION = "3.8-6"

_CRITICAL_EXACT = {
    "AGENTS.md",
    "requirements.txt",
    "docs/BACKEND_ARCHITECTURE.md",
    "docs/research_specification.md",
    "scripts/run_production.py",
}
_CRITICAL_PREFIXES = ("src/",)


class PreflightError(ValueError):
    """Raised when a production preflight invariant fails."""


def _git(repository_root: Path, *arguments: str) -> str:
    try:
        return subprocess.run(
            ["git", *arguments],
            cwd=repository_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise PreflightError(f"Git command failed: git {' '.join(arguments)}") from exc


def is_critical_source(relative_path: str) -> bool:
    """Classify paths that can alter production computation or its contract."""
    normalized = relative_path.replace("\\", "/")
    return normalized in _CRITICAL_EXACT or normalized.startswith(_CRITICAL_PREFIXES)


def classify_worktree(repository_root: Path) -> dict[str, object]:
    """Separate computation-critical changes from local/generated changes."""
    root = repository_root.resolve()
    output = _git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    entries = [entry for entry in output.split("\0") if entry]
    changed: list[dict[str, str]] = []
    index = 0
    while index < len(entries):
        entry = entries[index]
        status, path = entry[:2], entry[3:]
        if status[0] in {"R", "C"} and index + 1 < len(entries):
            index += 1
            path = entries[index]
        normalized = path.replace("\\", "/")
        changed.append({"status": status, "path": normalized})
        index += 1
    critical = [item for item in changed if is_critical_source(item["path"])]
    noncritical = [item for item in changed if item not in critical]
    return {
        "code_commit": current_git_commit(root),
        "critical_changes": critical,
        "noncritical_changes": noncritical,
        "eligible": not critical,
    }


def require_eligible_worktree(repository_root: Path) -> dict[str, object]:
    classification = classify_worktree(repository_root)
    if classification["critical_changes"]:
        paths = [item["path"] for item in classification["critical_changes"]]
        raise PreflightError(f"Critical production source is dirty: {paths}.")
    return classification


def _input_observed(path: Path, role: str) -> dict[str, object]:
    source = pl.scan_parquet(path)
    schema = source.collect_schema()
    expressions = [pl.len().alias("row_count")]
    if "event_type" in schema:
        expressions.extend(
            (pl.col("event_type") == event).sum().alias(event)
            for event in ("DEFAULT", "PREPAYMENT", "CENSOR")
        )
    if "entry_time_month" in schema:
        expressions.append(
            (pl.col("entry_time_month") > 0).sum().alias("delayed_entry")
        )
    observed = source.select(expressions).collect().to_dicts()[0]
    return {
        "path": path,
        "role": role,
        "byte_size": path.stat().st_size,
        "sha256": sha256_file(path),
        **observed,
    }


def fingerprint_inputs(
    repository_root: Path,
    roles: Iterable[str] | None = None,
) -> dict[str, object]:
    """Fingerprint and reconcile only the canonical inputs requested."""
    root = repository_root.resolve()
    selected = tuple(roles or INPUT_CONTRACTS)
    unknown = sorted(set(selected) - set(INPUT_CONTRACTS))
    if unknown:
        raise PreflightError(f"Unknown production input role(s): {unknown}.")
    records: list[dict[str, object]] = []
    for role in selected:
        expected = INPUT_CONTRACTS[role]
        path = root / expected.relative_path
        if not path.is_file():
            raise PreflightError(f"Production input is missing: {expected.relative_path}.")
        observed = _input_observed(path, role)
        comparisons = {
            name: (observed[name], wanted)
            for name, wanted in (
                ("sha256", expected.sha256),
                ("byte_size", expected.byte_size),
                ("row_count", expected.row_count),
            )
            if wanted is not None
        }
        comparisons.update({
            name: (observed.get(name), value)
            for name, value in expected.reconciliation.items()
        })
        mismatches = {
            name: {"observed": actual, "expected": wanted}
            for name, (actual, wanted) in comparisons.items()
            if actual != wanted
        }
        record = {
            "role": role,
            "relative_path": expected.relative_path,
            "purpose": expected.role,
            "data_version": DATA_VERSION,
            "sha256": observed["sha256"],
            "byte_size": observed["byte_size"],
            "row_count": observed["row_count"],
            "reconciliation": {
                name: observed.get(name) for name in expected.reconciliation
            },
            "status": "PASS" if not mismatches else "FAIL",
            "mismatches": mismatches,
        }
        records.append(record)
        if mismatches:
            raise PreflightError(
                f"Production input does not match {DATA_VERSION}: "
                f"{expected.relative_path}: {mismatches}."
            )
    return {
        "data_version": DATA_VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "inputs": records,
        "overall_status": "PASS",
    }


_R_PROBE = r'''
cat("R_VERSION\t", paste(R.version$major, R.version$minor, sep="."), "\n", sep="")
if (!requireNamespace("survival", quietly=TRUE)) stop("survival is unavailable")
cat("SURVIVAL_VERSION\t", packageDescription("survival")[["Version"]], "\n", sep="")
ns <- asNamespace("survival")
for (name in c("coxph", "survfit", "finegray")) {
  cat(toupper(name), "\t", exists(name, envir=ns, inherits=FALSE), "\n", sep="")
}
'''


def _resolve_rscript(explicit: Path | None = None) -> Path:
    candidate = explicit or (
        Path(os.environ["RSCRIPT_PATH"]) if os.environ.get("RSCRIPT_PATH") else None
    )
    if candidate is None:
        discovered = shutil.which("Rscript")
        candidate = Path(discovered) if discovered else None
    if candidate is None or not candidate.is_file():
        raise PreflightError(
            "Rscript is unavailable; set RSCRIPT_PATH or provide an explicit path."
        )
    return candidate.resolve()


def preflight_r_runtime(rscript: Path | None = None) -> dict[str, str]:
    """Verify the exact approved R runtime and estimator functions."""
    executable = _resolve_rscript(rscript)
    process = run_rscript_process(executable, _R_PROBE)
    if process.returncode != 0 or process.stderr.strip():
        detail = process.stderr.strip() or process.stdout.strip()
        raise PreflightError(f"R runtime probe failed: {detail}")
    metadata: dict[str, str] = {}
    for line in process.stdout.splitlines():
        fields = line.split("\t", maxsplit=1)
        if len(fields) == 2:
            metadata[fields[0]] = fields[1]
    required = {"R_VERSION", "SURVIVAL_VERSION", "COXPH", "SURVFIT", "FINEGRAY"}
    if set(metadata) != required:
        raise PreflightError(f"R probe returned unexpected metadata: {metadata}.")
    if metadata["R_VERSION"] != APPROVED_R_VERSION:
        raise PreflightError(
            f"R version {metadata['R_VERSION']} differs from approved "
            f"{APPROVED_R_VERSION}."
        )
    if metadata["SURVIVAL_VERSION"] != APPROVED_SURVIVAL_VERSION:
        raise PreflightError(
            f"survival version {metadata['SURVIVAL_VERSION']} differs from approved "
            f"{APPROVED_SURVIVAL_VERSION}."
        )
    unavailable = [name for name in ("COXPH", "SURVFIT", "FINEGRAY") if metadata[name] != "TRUE"]
    if unavailable:
        raise PreflightError(f"Required survival functions are unavailable: {unavailable}.")
    return {
        "rscript_path": str(executable),
        "r_version": metadata["R_VERSION"],
        "survival_version": metadata["SURVIVAL_VERSION"],
    }


def runtime_provenance(rscript: Path | None = None) -> dict[str, str]:
    versions = collect_runtime_versions()
    r = preflight_r_runtime(rscript)
    return {**versions, **r}


def write_input_provenance(payload: dict[str, object], path: Path) -> Path:
    return atomic_write_json(path, payload)


def production_preflight(
    repository_root: Path,
    *,
    input_roles: Iterable[str],
    require_r: bool,
    rscript: Path | None = None,
) -> dict[str, object]:
    root = repository_root.resolve()
    if DATA_VERSION != "freddie_sample_2016_2026_cutoff_202603_v2":
        raise PreflightError(f"Unexpected production data version: {DATA_VERSION}.")
    if not MODEL_VERSION_REGISTRY:
        raise PreflightError("Model version registry is empty.")
    result: dict[str, object] = {
        "worktree": require_eligible_worktree(root),
        "inputs": fingerprint_inputs(root, input_roles),
        "runtime_versions": collect_runtime_versions(),
    }
    if require_r:
        r = preflight_r_runtime(rscript)
        result["r_runtime"] = r
        result["runtime_versions"] = {**result["runtime_versions"], **r}
    return result
