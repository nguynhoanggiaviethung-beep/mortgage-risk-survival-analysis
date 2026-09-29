"""Explicit production orchestration and benchmark support."""

from src.production.contracts import (
    ANALYTICAL_ARTIFACTS,
    COMPLETE_RELEASE_ARTIFACTS,
    INPUT_CONTRACTS,
)
from src.production.preflight import (
    PreflightError,
    classify_worktree,
    fingerprint_inputs,
    preflight_r_runtime,
)

__all__ = [
    "ANALYTICAL_ARTIFACTS",
    "COMPLETE_RELEASE_ARTIFACTS",
    "INPUT_CONTRACTS",
    "PreflightError",
    "classify_worktree",
    "fingerprint_inputs",
    "preflight_r_runtime",
]
