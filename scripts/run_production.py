"""Explicit two-stage production CLI: preflight/build/validate/publish."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.production.preflight import production_preflight
from src.production.runner import (
    build_complete_release,
    publish_validated_release,
    validate_built_release,
)

def _run_root(run_id: str) -> Path:
    return PROJECT_ROOT / "results" / "production" / run_id


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="mode", required=True)

    preflight = subparsers.add_parser("preflight")
    preflight.add_argument("--group", choices=("python", "complete"), default="complete")
    preflight.add_argument("--rscript", type=Path)

    build = subparsers.add_parser("build")
    build.add_argument("--rscript", type=Path, required=True)
    build.add_argument("--confirm-full-production", action="store_true")

    validate = subparsers.add_parser("validate")
    validate.add_argument("--run-id", required=True)

    publish = subparsers.add_parser("publish")
    publish.add_argument("--run-id", required=True)
    publish.add_argument("--confirm-publish", action="store_true")

    args = parser.parse_args()
    if args.mode == "preflight":
        roles = (
            ("analysis_loans", "complete_cases")
            if args.group == "python"
            else ("analysis_loans", "complete_cases", "performance")
        )
        result = production_preflight(
            PROJECT_ROOT,
            input_roles=roles,
            require_r=args.group == "complete",
            rscript=args.rscript,
        )
        print(json.dumps(result, indent=2, default=str))
    elif args.mode == "build":
        if not args.confirm_full_production:
            parser.error("build requires --confirm-full-production")
        paths = build_complete_release(PROJECT_ROOT, rscript=args.rscript)
        print(paths.run_root)
    elif args.mode == "validate":
        print(validate_built_release(_run_root(args.run_id)).run_status.value)
    else:
        if not args.confirm_publish:
            parser.error("publish requires --confirm-publish")
        print(
            publish_validated_release(
                _run_root(args.run_id), PROJECT_ROOT
            ).run_status.value
        )


if __name__ == "__main__":
    main()
