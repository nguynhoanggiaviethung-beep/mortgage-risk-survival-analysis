"""Read-only smoke check for the local frontend/backend service contract."""

from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.query import FrontendService, QueryStatus


def _assert_frontend_safe(value: object) -> None:
    if isinstance(value, dict):
        for item in value.values():
            _assert_frontend_safe(item)
    elif isinstance(value, list):
        for item in value:
            _assert_frontend_safe(item)
    elif isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        raise AssertionError("serialized response contains NaN or Inf")


def main() -> int:
    service = FrontendService(".")
    checks = [
        ("portfolio", service.get_portfolio_summary, QueryStatus.OK),
        ("pd", service.get_pd_results, QueryStatus.OK),
        ("survival", service.get_survival_results, QueryStatus.OK),
        ("risk_drivers", service.get_risk_driver_results, QueryStatus.OK),
        ("vintage", service.get_vintage_results, QueryStatus.OK),
        ("diagnostics", service.get_model_diagnostics, QueryStatus.OK),
        ("loan_profile", lambda: service.get_loan_profile("F16Q10000006"), QueryStatus.OK),
        ("loan_timeline", lambda: service.get_loan_timeline("F16Q10000006"), QueryStatus.OK),
        ("unknown loan", lambda: service.get_loan_profile("UNKNOWN_LOAN"), QueryStatus.NOT_FOUND),
    ]
    try:
        for name, query, expected in checks:
            response = query()
            if response.status is not expected:
                raise AssertionError(
                    f"{name}: expected {expected.value}, got {response.status.value}"
                )
            payload = response.as_dict()
            if set(payload) != {"status", "data", "provenance"}:
                raise AssertionError(f"{name}: invalid response keys")
            _assert_frontend_safe(payload)
            print(f"{name} -> {response.status.value}")
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print("PASS: frontend/backend smoke check")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())