"""Shared low-level execution for installed Rscript analytical engines.

Callers retain responsibility for interpreting return codes, stderr, and
domain-specific output. This helper owns only the Windows-safe temporary
script lifecycle and locale-neutral child environment used by current R
consumers.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path


def child_environment() -> dict[str, str]:
    """Copy the process environment without locale overrides for Rscript."""
    environment = os.environ.copy()
    for name in ("LANG", "LC_ALL", "LC_CTYPE"):
        environment.pop(name, None)
    return environment


def run_rscript_process(
    rscript: Path,
    expression: str,
    standard_input: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Execute an R expression through a transient UTF-8 script.

    Windows Rscript 4.6.1 is unstable with literal newlines in a subprocess
    ``-e`` argument. The temporary script is created outside the repository
    and removed on every exit path. Analytical data, when supplied, travels
    through stdin rather than a persisted interchange file.
    """
    script_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".R",
            encoding="utf-8",
            newline="\n",
            delete=False,
        ) as script:
            script.write(expression)
            script_path = Path(script.name)
        return subprocess.run(
            [str(rscript), "--vanilla", str(script_path)],
            input=standard_input if standard_input is not None else "",
            text=True,
            capture_output=True,
            env=child_environment(),
            check=False,
        )
    finally:
        if script_path is not None:
            script_path.unlink(missing_ok=True)
