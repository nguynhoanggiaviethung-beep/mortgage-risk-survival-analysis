"""Small atomic writers used by analytical result infrastructure."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from os import PathLike
from pathlib import Path
from typing import Any, TypeAlias
from uuid import uuid4


PathSource: TypeAlias = str | PathLike[str]


def atomic_write_json(path: PathSource, payload: Mapping[str, Any]) -> Path:
    """Write canonical JSON through a same-directory temporary file."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.{uuid4().hex}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(
                payload,
                handle,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    return output

