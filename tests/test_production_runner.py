import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from src.production.runner import (
    ProductionRunnerError,
    create_unique_run,
    validate_built_release,
)
from src.production.validation import ProductionValidationError
from src.results.manifest import (
    RunStatus,
    create_run_manifest,
    load_run_manifest,
    transition_run,
    write_run_manifest,
)


COMMIT = "0aa04e768c382260da82b2ae9e21bc08ba8ece43"


class TestProductionRunner(unittest.TestCase):
    def test_unique_run_directory_is_never_reused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixed = create_run_manifest(
                environment="PRODUCTION",
                code_commit=COMMIT,
                run_date_utc=datetime(2026, 9, 29, tzinfo=timezone.utc),
                runtime_versions={"python": "test"},
            )
            with patch("src.production.runner.create_run_manifest", return_value=fixed):
                _, paths = create_unique_run(root, runtime_versions={"python": "test"})
                self.assertTrue(paths.run_root.is_dir())
                with self.assertRaisesRegex(ProductionRunnerError, "already exists"):
                    create_unique_run(root, runtime_versions={"python": "test"})

    def test_semantic_failure_blocks_validated_and_marks_run_failed(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            created = create_run_manifest(
                environment="PRODUCTION",
                code_commit=COMMIT,
                run_date_utc=datetime(2026, 9, 29, 1, tzinfo=timezone.utc),
                runtime_versions={"python": "test"},
            )
            running = transition_run(created, RunStatus.RUNNING)
            run_root = repository / "results/production" / created.run_id
            run_root.mkdir(parents=True)
            write_run_manifest(running, run_root / "manifest.json")
            with self.assertRaises(ProductionValidationError):
                validate_built_release(run_root)
            self.assertEqual(
                load_run_manifest(run_root / "manifest.json").run_status,
                RunStatus.FAILED,
            )


if __name__ == "__main__":
    unittest.main()
