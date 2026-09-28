import unittest
from datetime import datetime, timezone
from pathlib import Path

import polars as pl

from src.results import create_run_manifest, register_artifact, verify_artifacts


ROOT = Path(__file__).resolve().parent.parent
COMMIT = "03d4933d6fa8d9733737189f546407a60f71d76b"

MOCK_ARTIFACTS = (
    ("km_results", "results/mock/km_results.parquet", "MODEL_RESULT", "kaplan_meier"),
    ("cox_results", "results/mock/cox_results.parquet", "MODEL_RESULT", "cox_ph"),
    ("cox_diagnostics", "results/mock/cox_diagnostics.parquet", "DIAGNOSTIC", "cox_ph"),
    ("ph_diagnostics", "results/mock/ph_diagnostics.csv", "DIAGNOSTIC", "cox_ph"),
    ("ph_global_diagnostics", "results/mock/ph_global_diagnostics.csv", "DIAGNOSTIC", "cox_ph"),
    ("time_varying_cox_results", "results/mock/time_varying_cox_results.parquet", "MODEL_RESULT", "time_varying_cox"),
    ("time_varying_cox_diagnostics", "results/mock/time_varying_cox_diagnostics.parquet", "DIAGNOSTIC", "time_varying_cox"),
)


class TestResultArtifactCompatibility(unittest.TestCase):
    def test_existing_mock_artifacts_register_without_regeneration(self):
        before = {relative: (ROOT / relative).read_bytes() for _, relative, _, _ in MOCK_ARTIFACTS}
        manifest = create_run_manifest(
            environment="MOCK",
            code_commit=COMMIT,
            run_date_utc=datetime(2026, 9, 28, 14, 0, 0, tzinfo=timezone.utc),
            runtime_versions={"python": "test"},
        )
        registered = manifest
        for logical_name, relative_path, artifact_type, producer in MOCK_ARTIFACTS:
            path = ROOT / relative_path
            row_count = (
                pl.read_parquet(path).height
                if path.suffix == ".parquet"
                else pl.read_csv(path).height
            )
            registered = register_artifact(
                registered,
                run_root=ROOT,
                logical_name=logical_name,
                relative_path=relative_path,
                artifact_type=artifact_type,
                producer=producer,
                row_count=row_count,
            )
        verify_artifacts(registered, run_root=ROOT)
        self.assertEqual(len(registered.artifacts), len(MOCK_ARTIFACTS))
        self.assertEqual(
            before,
            {relative: (ROOT / relative).read_bytes() for _, relative, _, _ in MOCK_ARTIFACTS},
        )


if __name__ == "__main__":
    unittest.main()
