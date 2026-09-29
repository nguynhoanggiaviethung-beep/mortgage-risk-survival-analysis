"""Artifact integrity and path-containment helpers."""

from __future__ import annotations

import hashlib
from os import PathLike
from pathlib import Path, PurePosixPath
from typing import TypeAlias


PathSource: TypeAlias = str | PathLike[str]


class ArtifactIntegrityError(ValueError):
    """Raised when an artifact path or checksum is unsafe or invalid."""


def sha256_file(path: PathSource, chunk_size: int = 1024 * 1024) -> str:
    """Return the lowercase SHA-256 digest of the actual file bytes."""
    source = Path(path)
    if not source.is_file():
        raise ArtifactIntegrityError(f"Artifact does not exist: {source}.")
    digest = hashlib.sha256()
    with source.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_artifact_path(run_root: PathSource, relative_path: str) -> Path:
    """Resolve a repository-style artifact path strictly within ``run_root``."""
    if not isinstance(relative_path, str) or not relative_path.strip():
        raise ArtifactIntegrityError("Artifact relative_path must be non-empty.")
    if "\\" in relative_path:
        raise ArtifactIntegrityError(
            "Artifact relative_path must use repository-style '/' separators."
        )

    relative = PurePosixPath(relative_path)
    if relative.is_absolute():
        raise ArtifactIntegrityError("Absolute artifact paths are not allowed.")
    if any(part in {"", ".", ".."} for part in relative.parts):
        raise ArtifactIntegrityError("Artifact path traversal is not allowed.")

    root = Path(run_root).resolve()
    candidate = root.joinpath(*relative.parts).resolve(strict=False)
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ArtifactIntegrityError(
            "Artifact path escapes the declared run root."
        ) from exc
    return candidate

