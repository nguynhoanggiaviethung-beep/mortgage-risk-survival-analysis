import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from src.results import (
    ResultManifestError,
    create_run_manifest,
    register_artifact,
    sha256_file,
    transition_run,
    verify_artifacts,
)


COMMIT = "03d4933d6fa8d9733737189f546407a60f71d76b"
RUN_DATE = datetime(2026, 9, 28, 14, 0, 0, tzinfo=timezone.utc)


class TestResultIntegrity(unittest.TestCase):
    def _registered(self, root: Path):
        artifact = root / "models" / "result.bin"
        artifact.parent.mkdir(parents=True)
        artifact.write_bytes(b"result-bytes")
        manifest = create_run_manifest(
            environment="MOCK",
            code_commit=COMMIT,
            run_date_utc=RUN_DATE,
            runtime_versions={"python": "test"},
        )
        return register_artifact(
            manifest,
            run_root=root,
            logical_name="result",
            relative_path="models/result.bin",
            artifact_type="MODEL_RESULT",
            producer="unit_test",
            row_count=1,
        )

    def test_sha256_uses_actual_bytes_and_verifies(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = self._registered(root)
            self.assertEqual(
                manifest.artifacts[0].sha256,
                sha256_file(root / "models" / "result.bin"),
            )
            self.assertIs(verify_artifacts(manifest, run_root=root), manifest)

    def test_missing_and_corrupted_artifacts_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = self._registered(root)
            artifact = root / "models" / "result.bin"
            artifact.unlink()
            with self.assertRaisesRegex(ResultManifestError, "does not exist"):
                verify_artifacts(manifest, run_root=root)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = self._registered(root)
            (root / "models" / "result.bin").write_bytes(b"corrupted")
            with self.assertRaisesRegex(ResultManifestError, "checksum mismatch"):
                verify_artifacts(manifest, run_root=root)

    def test_artifacts_cannot_be_registered_after_validation_stage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = self._registered(root)
            running = transition_run(manifest, "RUNNING")
            # The transition itself does not mutate the original object.
            self.assertEqual(manifest.run_status.value, "CREATED")
            failed = transition_run(running, "FAILED")
            with self.assertRaisesRegex(ResultManifestError, "before validation"):
                register_artifact(
                    failed,
                    run_root=root,
                    logical_name="late",
                    relative_path="models/result.bin",
                    artifact_type="MODEL_RESULT",
                    producer="unit_test",
                )


if __name__ == "__main__":
    unittest.main()

