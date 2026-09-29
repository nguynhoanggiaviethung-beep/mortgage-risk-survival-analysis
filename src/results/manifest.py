"""Validated manifests for versioned analytical result runs.

This module records and publishes analytical artifacts; it does not fit models
or infer analytical methodology. A published pointer can reference only a
validated production run. Mock manifests are supported for compatibility
testing but can never become the current production run.
"""

from __future__ import annotations

import json
import platform
import re
import subprocess
from collections.abc import Mapping
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from importlib.metadata import PackageNotFoundError, version
from os import PathLike
from pathlib import Path
from typing import Any, Callable, TypeAlias

from src.results.integrity import (
    ArtifactIntegrityError,
    resolve_artifact_path,
    sha256_file,
)
from src.results.writers import atomic_write_json


PathSource: TypeAlias = str | PathLike[str]

SPECIFICATION_VERSION = "1.1.0"
COHORT_START_YEAR = 2016
COHORT_END_YEAR = 2026
PERFORMANCE_CUTOFF = "202603"
DATA_BUILD_VERSION = "v2"
DATA_VERSION = "freddie_sample_2016_2026_cutoff_202603_v2"

MODEL_VERSION_REGISTRY: dict[str, str] = {
    "kaplan_meier": "km_v1",
    "cox_ph": "cox_ph_v1",
    "time_varying_cox": "tv_cox_v3",
    "cause_specific_default": "cause_specific_default_v1",
    "cause_specific_prepayment": "cause_specific_prepayment_v1",
    "aalen_johansen": "aalen_johansen_v1",
    "fine_gray_default": "fine_gray_default_v1",
    "pd_horizons": "pd_horizons_v1",
    "vintage_analysis": "vintage_analysis_v1",
}

_RUN_ID_PATTERN = re.compile(r"^\d{8}T\d{6}Z_[0-9a-f]{7,40}$")
_SHA_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_COMMIT_PATTERN = re.compile(r"^[0-9a-fA-F]{7,40}$")


class ResultManifestError(ValueError):
    """Raised when a result manifest or state transition is invalid."""


class RunStatus(str, Enum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    VALIDATED = "VALIDATED"
    FAILED = "FAILED"
    PUBLISHED = "PUBLISHED"


class RunEnvironment(str, Enum):
    MOCK = "MOCK"
    PRODUCTION = "PRODUCTION"


_LEGAL_TRANSITIONS: dict[RunStatus, frozenset[RunStatus]] = {
    RunStatus.CREATED: frozenset({RunStatus.RUNNING, RunStatus.FAILED}),
    RunStatus.RUNNING: frozenset({RunStatus.VALIDATED, RunStatus.FAILED}),
    RunStatus.VALIDATED: frozenset({RunStatus.PUBLISHED}),
    RunStatus.FAILED: frozenset(),
    RunStatus.PUBLISHED: frozenset(),
}


@dataclass(frozen=True)
class ArtifactRecord:
    logical_name: str
    relative_path: str
    artifact_type: str
    producer: str
    row_count: int | None
    sha256: str
    status: str


@dataclass(frozen=True)
class RunManifest:
    run_id: str
    run_date_utc: str
    run_status: RunStatus
    environment: RunEnvironment
    data_version: str
    specification_version: str
    code_commit: str
    cohort_start_year: int
    cohort_end_year: int
    performance_cutoff: str
    model_versions: dict[str, str]
    runtime_versions: dict[str, str]
    artifacts: tuple[ArtifactRecord, ...]


def build_data_version(
    cohort_start_year: int = COHORT_START_YEAR,
    cohort_end_year: int = COHORT_END_YEAR,
    performance_cutoff: str = PERFORMANCE_CUTOFF,
    build_version: str = DATA_BUILD_VERSION,
) -> str:
    """Build the locked readable, deterministic analytical data identifier."""
    if not re.fullmatch(r"\d{6}", str(performance_cutoff)):
        raise ResultManifestError("performance_cutoff must have YYYYMM format.")
    if not re.fullmatch(r"v[1-9]\d*", str(build_version)):
        raise ResultManifestError("build_version must have form v<positive integer>.")
    if cohort_start_year > cohort_end_year:
        raise ResultManifestError("cohort_start_year cannot exceed cohort_end_year.")
    return (
        f"freddie_sample_{cohort_start_year}_{cohort_end_year}_"
        f"cutoff_{performance_cutoff}_{build_version}"
    )


def _utc_iso(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ResultManifestError("run_date_utc must be timezone-aware.")
    utc = value.astimezone(timezone.utc)
    return utc.isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse_utc(value: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ResultManifestError("run_date_utc must be ISO 8601 UTC ending in Z.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ResultManifestError("run_date_utc is not valid ISO 8601.") from exc
    if parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ResultManifestError("run_date_utc must be UTC.")
    return parsed


def create_run_id(run_date_utc: datetime, code_commit: str) -> str:
    """Create ``UTC timestamp + short commit`` run identity."""
    if not _COMMIT_PATTERN.fullmatch(code_commit):
        raise ResultManifestError("code_commit must be a 7-40 character Git SHA.")
    utc = run_date_utc.astimezone(timezone.utc)
    if run_date_utc.tzinfo is None or run_date_utc.utcoffset() is None:
        raise ResultManifestError("run_date_utc must be timezone-aware.")
    return f"{utc.strftime('%Y%m%dT%H%M%SZ')}_{code_commit[:7].lower()}"


def current_git_commit(repository_root: PathSource = ".") -> str:
    """Return the actual Git commit for the repository."""
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(repository_root),
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ResultManifestError("Unable to resolve the current Git commit.") from exc


def collect_runtime_versions() -> dict[str, str]:
    """Collect stable runtime identifiers used by existing analytical code."""
    versions = {"python": platform.python_version()}
    for package in ("lifelines", "numpy", "pandas", "polars", "pyarrow"):
        try:
            versions[package] = version(package)
        except PackageNotFoundError:
            continue
    return versions


def create_run_manifest(
    *,
    environment: RunEnvironment | str,
    code_commit: str | None = None,
    repository_root: PathSource = ".",
    run_date_utc: datetime | None = None,
    data_version: str = DATA_VERSION,
    specification_version: str = SPECIFICATION_VERSION,
    model_versions: Mapping[str, str] | None = None,
    runtime_versions: Mapping[str, str] | None = None,
) -> RunManifest:
    """Create a validated immutable manifest in ``CREATED`` state."""
    date = run_date_utc or datetime.now(timezone.utc)
    commit = code_commit or current_git_commit(repository_root)
    manifest = RunManifest(
        run_id=create_run_id(date, commit),
        run_date_utc=_utc_iso(date),
        run_status=RunStatus.CREATED,
        environment=RunEnvironment(environment),
        data_version=data_version,
        specification_version=specification_version,
        code_commit=commit.lower(),
        cohort_start_year=COHORT_START_YEAR,
        cohort_end_year=COHORT_END_YEAR,
        performance_cutoff=PERFORMANCE_CUTOFF,
        model_versions=dict(
            MODEL_VERSION_REGISTRY if model_versions is None else model_versions
        ),
        runtime_versions=dict(
            collect_runtime_versions()
            if runtime_versions is None
            else runtime_versions
        ),
        artifacts=(),
    )
    return validate_run_manifest(manifest)


def _artifact_from_mapping(value: Mapping[str, Any]) -> ArtifactRecord:
    try:
        return ArtifactRecord(**dict(value))
    except TypeError as exc:
        raise ResultManifestError(f"Invalid artifact record: {exc}") from exc


def _manifest_from_mapping(value: Mapping[str, Any]) -> RunManifest:
    required = {field.name for field in RunManifest.__dataclass_fields__.values()}
    if set(value) != required:
        raise ResultManifestError(
            "Manifest fields do not match the canonical contract: "
            f"expected {sorted(required)}."
        )
    try:
        return RunManifest(
            run_id=value["run_id"],
            run_date_utc=value["run_date_utc"],
            run_status=RunStatus(value["run_status"]),
            environment=RunEnvironment(value["environment"]),
            data_version=value["data_version"],
            specification_version=value["specification_version"],
            code_commit=value["code_commit"],
            cohort_start_year=value["cohort_start_year"],
            cohort_end_year=value["cohort_end_year"],
            performance_cutoff=value["performance_cutoff"],
            model_versions=dict(value["model_versions"]),
            runtime_versions=dict(value["runtime_versions"]),
            artifacts=tuple(
                _artifact_from_mapping(item) for item in value["artifacts"]
            ),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ResultManifestError(f"Invalid manifest value: {exc}") from exc


def validate_run_manifest(
    manifest: RunManifest | Mapping[str, Any],
) -> RunManifest:
    """Validate the complete typed manifest contract without filesystem I/O."""
    item = manifest if isinstance(manifest, RunManifest) else _manifest_from_mapping(manifest)

    if not isinstance(item.run_status, RunStatus):
        raise ResultManifestError("run_status is not canonical.")
    if not isinstance(item.environment, RunEnvironment):
        raise ResultManifestError("environment is not canonical.")
    if not _RUN_ID_PATTERN.fullmatch(item.run_id):
        raise ResultManifestError("run_id does not match the canonical format.")
    run_date = _parse_utc(item.run_date_utc)
    expected_prefix = run_date.strftime("%Y%m%dT%H%M%SZ")
    if not item.run_id.startswith(f"{expected_prefix}_"):
        raise ResultManifestError("run_id timestamp does not match run_date_utc.")
    if not _COMMIT_PATTERN.fullmatch(item.code_commit):
        raise ResultManifestError("code_commit is not a valid Git SHA.")
    if not item.code_commit.lower().startswith(item.run_id.rsplit("_", 1)[1]):
        raise ResultManifestError("run_id commit does not match code_commit.")
    if item.specification_version != SPECIFICATION_VERSION:
        raise ResultManifestError("Unsupported specification_version.")
    expected_data_version = build_data_version(
        item.cohort_start_year,
        item.cohort_end_year,
        item.performance_cutoff,
    )
    if item.data_version != expected_data_version:
        raise ResultManifestError("data_version does not match the locked data build.")
    if item.model_versions != MODEL_VERSION_REGISTRY:
        raise ResultManifestError("model_versions does not match the canonical registry.")
    if not item.runtime_versions or any(
        not isinstance(key, str) or not key or not isinstance(value, str) or not value
        for key, value in item.runtime_versions.items()
    ):
        raise ResultManifestError("runtime_versions must be a non-empty string mapping.")

    logical_names: set[str] = set()
    relative_paths: set[str] = set()
    for artifact in item.artifacts:
        if not all(
            isinstance(value, str) and value
            for value in (
                artifact.logical_name,
                artifact.relative_path,
                artifact.artifact_type,
                artifact.producer,
                artifact.status,
            )
        ):
            raise ResultManifestError("Artifact string fields must be non-empty.")
        try:
            resolve_artifact_path(Path.cwd(), artifact.relative_path)
        except ArtifactIntegrityError as exc:
            raise ResultManifestError(str(exc)) from exc
        if artifact.row_count is not None and (
            not isinstance(artifact.row_count, int)
            or isinstance(artifact.row_count, bool)
            or artifact.row_count < 0
        ):
            raise ResultManifestError("Artifact row_count must be non-negative.")
        if not _SHA_PATTERN.fullmatch(artifact.sha256):
            raise ResultManifestError("Artifact sha256 must be lowercase SHA-256.")
        if artifact.logical_name in logical_names:
            raise ResultManifestError("Artifact logical_name values must be unique.")
        if artifact.relative_path in relative_paths:
            raise ResultManifestError("Artifact relative_path values must be unique.")
        logical_names.add(artifact.logical_name)
        relative_paths.add(artifact.relative_path)
    return item


def manifest_to_dict(manifest: RunManifest) -> dict[str, Any]:
    """Return a JSON-compatible representation without mutating the manifest."""
    item = validate_run_manifest(manifest)
    payload = asdict(item)
    payload["run_status"] = item.run_status.value
    payload["environment"] = item.environment.value
    payload["artifacts"] = [asdict(record) for record in item.artifacts]
    return payload


def write_run_manifest(manifest: RunManifest, path: PathSource) -> Path:
    """Validate and atomically persist a run manifest."""
    return atomic_write_json(path, manifest_to_dict(manifest))


def load_run_manifest(path: PathSource) -> RunManifest:
    """Load and validate a persisted run manifest."""
    source = Path(path)
    if not source.is_file():
        raise ResultManifestError(f"Run manifest does not exist: {source}.")
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ResultManifestError(f"Unable to load run manifest: {source}.") from exc
    if not isinstance(payload, dict):
        raise ResultManifestError("Run manifest JSON must be an object.")
    return validate_run_manifest(payload)


def register_artifact(
    manifest: RunManifest,
    *,
    run_root: PathSource,
    logical_name: str,
    relative_path: str,
    artifact_type: str,
    producer: str,
    row_count: int | None = None,
    status: str = "VERIFIED",
) -> RunManifest:
    """Return a new manifest with an existing contained artifact registered."""
    item = validate_run_manifest(manifest)
    if item.run_status not in {RunStatus.CREATED, RunStatus.RUNNING}:
        raise ResultManifestError("Artifacts can only be registered before validation.")
    try:
        artifact_path = resolve_artifact_path(run_root, relative_path)
        digest = sha256_file(artifact_path)
    except ArtifactIntegrityError as exc:
        raise ResultManifestError(str(exc)) from exc
    record = ArtifactRecord(
        logical_name=logical_name,
        relative_path=relative_path,
        artifact_type=artifact_type,
        producer=producer,
        row_count=row_count,
        sha256=digest,
        status=status,
    )
    return validate_run_manifest(replace(item, artifacts=(*item.artifacts, record)))


def verify_artifacts(manifest: RunManifest, *, run_root: PathSource) -> RunManifest:
    """Verify every registered artifact exists and matches its byte checksum."""
    item = validate_run_manifest(manifest)
    if not item.artifacts:
        raise ResultManifestError("A run must register at least one artifact.")
    for artifact in item.artifacts:
        try:
            path = resolve_artifact_path(run_root, artifact.relative_path)
            actual = sha256_file(path)
        except ArtifactIntegrityError as exc:
            raise ResultManifestError(str(exc)) from exc
        if actual != artifact.sha256:
            raise ResultManifestError(
                f"Artifact checksum mismatch: {artifact.logical_name}."
            )
    return item


def transition_run(manifest: RunManifest, status: RunStatus | str) -> RunManifest:
    """Return a new manifest after enforcing the canonical state machine."""
    item = validate_run_manifest(manifest)
    target = RunStatus(status)
    if target not in _LEGAL_TRANSITIONS[item.run_status]:
        raise ResultManifestError(
            f"Illegal run status transition: {item.run_status.value} -> {target.value}."
        )
    return replace(item, run_status=target)


def mark_run_validated(
    manifest: RunManifest,
    *,
    run_root: PathSource,
) -> RunManifest:
    """Verify all artifacts and transition a running run to ``VALIDATED``."""
    item = verify_artifacts(manifest, run_root=run_root)
    return transition_run(item, RunStatus.VALIDATED)


def publish_run(
    manifest: RunManifest,
    *,
    run_root: PathSource,
    current_path: PathSource,
    repository_root: PathSource,
    published_at_utc: datetime | None = None,
    pointer_writer: Callable[[PathSource, Mapping[str, Any]], Path] = atomic_write_json,
) -> RunManifest:
    """Publish and verify a run, rolling back both files on reported failure."""
    item = verify_artifacts(manifest, run_root=run_root)
    if item.environment is not RunEnvironment.PRODUCTION:
        raise ResultManifestError("Only a PRODUCTION run may be published.")
    if item.run_status is not RunStatus.VALIDATED:
        raise ResultManifestError("Only a VALIDATED run may be published.")

    root = Path(repository_root).resolve()
    run_directory = Path(run_root).resolve()
    pointer_path = Path(current_path).resolve()
    try:
        run_directory.relative_to(root)
        pointer_path.relative_to(root)
    except ValueError as exc:
        raise ResultManifestError(
            "Run root and current pointer must remain inside the repository."
        ) from exc

    published = transition_run(item, RunStatus.PUBLISHED)
    manifest_path = run_directory / "manifest.json"
    publication_time = published_at_utc or datetime.now(timezone.utc)
    pointer = {
        "run_id": published.run_id,
        "manifest_relative_path": manifest_path.relative_to(root).as_posix(),
        "published_at_utc": _utc_iso(publication_time),
    }
    previous_pointer: dict[str, Any] | None = None
    if pointer_path.exists():
        previous = load_current_run(pointer_path, repository_root=root)
        previous_pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
        if previous.run_id == published.run_id:
            raise ResultManifestError("Run is already current production.")

    write_run_manifest(published, manifest_path)
    try:
        pointer_writer(pointer_path, pointer)
        loaded = load_current_run(pointer_path, repository_root=root)
        if loaded.run_id != published.run_id:
            raise ResultManifestError(
                "Publication verification did not resolve the intended run."
            )
        return loaded
    except Exception as publication_error:
        rollback_errors: list[str] = []
        try:
            write_run_manifest(item, manifest_path)
        except Exception as exc:  # pragma: no cover - catastrophic filesystem failure
            rollback_errors.append(f"manifest rollback failed: {exc}")
        try:
            if previous_pointer is None:
                pointer_path.unlink(missing_ok=True)
            else:
                atomic_write_json(pointer_path, previous_pointer)
        except Exception as exc:  # pragma: no cover - catastrophic filesystem failure
            rollback_errors.append(f"pointer rollback failed: {exc}")
        if rollback_errors:
            raise ResultManifestError(
                "Publication failed and rollback was incomplete: "
                + "; ".join(rollback_errors)
            ) from publication_error
        raise ResultManifestError(
            f"Publication failed and was rolled back: {publication_error}"
        ) from publication_error


def load_current_run(
    current_path: PathSource,
    *,
    repository_root: PathSource,
) -> RunManifest:
    """Resolve current.json and return its validated published production run."""
    pointer_path = Path(current_path)
    if not pointer_path.is_file():
        raise ResultManifestError("No published production run is available.")
    try:
        pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ResultManifestError("Current production pointer is invalid.") from exc
    expected = {"run_id", "manifest_relative_path", "published_at_utc"}
    if not isinstance(pointer, dict) or set(pointer) != expected:
        raise ResultManifestError("Current production pointer has invalid fields.")
    _parse_utc(pointer["published_at_utc"])
    try:
        manifest_path = resolve_artifact_path(
            repository_root, pointer["manifest_relative_path"]
        )
    except ArtifactIntegrityError as exc:
        raise ResultManifestError(str(exc)) from exc
    manifest = load_run_manifest(manifest_path)
    if manifest.run_id != pointer["run_id"]:
        raise ResultManifestError("Current pointer run_id does not match manifest.")
    if (
        manifest.environment is not RunEnvironment.PRODUCTION
        or manifest.run_status is not RunStatus.PUBLISHED
    ):
        raise ResultManifestError(
            "Current pointer does not reference a published production run."
        )
    verify_artifacts(manifest, run_root=manifest_path.parent)
    return manifest
