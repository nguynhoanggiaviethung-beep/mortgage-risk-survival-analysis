import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from src.production.contracts import (
    ANALYTICAL_ARTIFACTS,
    COMPLETE_RELEASE_ARTIFACTS,
    INPUT_PROVENANCE_ARTIFACT,
)
from src.production.validation import (
    ProductionValidationError,
    require_complete_registered_inventory,
    validate_production_release,
)
from src.results.manifest import (
    ArtifactRecord,
    create_run_manifest,
    transition_run,
)


COMMIT = "0aa04e768c382260da82b2ae9e21bc08ba8ece43"


class TestProductionValidation(unittest.TestCase):
    def _running(self):
        created = create_run_manifest(
            environment="PRODUCTION",
            code_commit=COMMIT,
            run_date_utc=datetime(2026, 9, 29, tzinfo=timezone.utc),
            runtime_versions={"python": "test"},
        )
        return transition_run(created, "RUNNING")

    def test_incomplete_inventory_fails_and_writes_report(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.json"
            with self.assertRaises(ProductionValidationError):
                validate_production_release(
                    self._running(), run_root=Path(directory), report_path=report
                )
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["overall_status"], "FAIL")
            inventory = next(
                item for item in payload["checks"] if item["name"] == "artifact_inventory"
            )
            self.assertEqual(inventory["status"], "FAIL")

    def test_mock_inventory_cannot_satisfy_production(self):
        manifest = self._running()
        records = tuple(
            ArtifactRecord(
                logical_name=name,
                relative_path=f"results/mock/{name}.parquet",
                artifact_type="MODEL_RESULT",
                producer="test",
                row_count=1,
                sha256="0" * 64,
                status="VERIFIED",
            )
            for name in (*ANALYTICAL_ARTIFACTS, INPUT_PROVENANCE_ARTIFACT)
        )
        object.__setattr__(manifest, "artifacts", records)
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.json"
            with self.assertRaises(ProductionValidationError):
                validate_production_release(
                    manifest, run_root=Path(directory), report_path=report
                )
            checks = json.loads(report.read_text(encoding="utf-8"))["checks"]
            self.assertEqual(
                next(item for item in checks if item["name"] == "no_mock_artifacts")["status"],
                "FAIL",
            )

    def test_complete_inventory_is_exact(self):
        manifest = self._running()
        records = tuple(
            ArtifactRecord(name, f"safe/{name}", "TYPE", "test", None, "0" * 64, "VERIFIED")
            for name in COMPLETE_RELEASE_ARTIFACTS
        )
        object.__setattr__(manifest, "artifacts", records)
        require_complete_registered_inventory(manifest)
        object.__setattr__(manifest, "artifacts", records[:-1])
        with self.assertRaises(ProductionValidationError):
            require_complete_registered_inventory(manifest)


if __name__ == "__main__":
    unittest.main()
