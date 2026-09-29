import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from src.results import (
    ResultManifestError,
    RunStatus,
    create_run_manifest,
    load_current_run,
    load_run_manifest,
    mark_run_validated,
    publish_run,
    register_artifact,
    transition_run,
    write_run_manifest,
)
from src.results.writers import atomic_write_json


COMMIT = "0aa04e768c382260da82b2ae9e21bc08ba8ece43"


class TestPublicationHardening(unittest.TestCase):
    def _validated(self, repository: Path, second: int):
        created = create_run_manifest(
            environment="PRODUCTION",
            code_commit=COMMIT,
            run_date_utc=datetime(2026, 9, 29, 1, 0, second, tzinfo=timezone.utc),
            runtime_versions={"python": "test"},
        )
        run_root = repository / "results/production" / created.run_id
        artifact = run_root / "models/result.bin"
        artifact.parent.mkdir(parents=True)
        artifact.write_bytes(f"result-{second}".encode())
        registered = register_artifact(
            created,
            run_root=run_root,
            logical_name="result",
            relative_path="models/result.bin",
            artifact_type="MODEL_RESULT",
            producer="test",
            row_count=1,
        )
        running = transition_run(registered, RunStatus.RUNNING)
        validated = mark_run_validated(running, run_root=run_root)
        write_run_manifest(validated, run_root / "manifest.json")
        return validated, run_root

    def test_pointer_serialization_failure_rolls_back_manifest_and_pointer(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            current = repository / "results/current.json"
            first, first_root = self._validated(repository, 1)
            publish_run(
                first,
                run_root=first_root,
                current_path=current,
                repository_root=repository,
            )
            previous = current.read_bytes()
            second, second_root = self._validated(repository, 2)

            def fail_before_write(path, payload):
                raise TypeError("serialization failure")

            with self.assertRaisesRegex(ResultManifestError, "rolled back"):
                publish_run(
                    second,
                    run_root=second_root,
                    current_path=current,
                    repository_root=repository,
                    pointer_writer=fail_before_write,
                )
            self.assertEqual(current.read_bytes(), previous)
            self.assertEqual(load_run_manifest(second_root / "manifest.json").run_status, RunStatus.VALIDATED)
            self.assertEqual(load_current_run(current, repository_root=repository).run_id, first.run_id)

    def test_pointer_replace_or_postwrite_failure_restores_previous_current(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            current = repository / "results/current.json"
            first, first_root = self._validated(repository, 3)
            publish_run(first, run_root=first_root, current_path=current, repository_root=repository)
            previous = current.read_bytes()
            second, second_root = self._validated(repository, 4)

            def write_then_fail(path, payload):
                atomic_write_json(path, payload)
                raise OSError("injected final replace acknowledgement failure")

            with self.assertRaisesRegex(ResultManifestError, "rolled back"):
                publish_run(
                    second,
                    run_root=second_root,
                    current_path=current,
                    repository_root=repository,
                    pointer_writer=write_then_fail,
                )
            self.assertEqual(current.read_bytes(), previous)
            self.assertEqual(load_run_manifest(second_root / "manifest.json").run_status, RunStatus.VALIDATED)
            self.assertEqual(load_current_run(current, repository_root=repository).run_id, first.run_id)

    def test_pointer_final_replace_failure_preserves_previous_current(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            current = repository / "results/current.json"
            first, first_root = self._validated(repository, 6)
            publish_run(first, run_root=first_root, current_path=current, repository_root=repository)
            previous = current.read_bytes()
            second, second_root = self._validated(repository, 7)

            def fail_at_replace(path, payload):
                temporary = Path(path).with_name(".injected-current.tmp")
                temporary.write_text(json.dumps(payload), encoding="utf-8")
                try:
                    raise OSError("injected final replace failure")
                finally:
                    temporary.unlink(missing_ok=True)

            with self.assertRaisesRegex(ResultManifestError, "rolled back"):
                publish_run(
                    second,
                    run_root=second_root,
                    current_path=current,
                    repository_root=repository,
                    pointer_writer=fail_at_replace,
                )
            self.assertEqual(current.read_bytes(), previous)
            self.assertEqual(load_run_manifest(second_root / "manifest.json").run_status, RunStatus.VALIDATED)
            self.assertEqual(load_current_run(current, repository_root=repository).run_id, first.run_id)

    def test_success_returns_reloaded_current_run(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            current = repository / "results/current.json"
            validated, run_root = self._validated(repository, 5)
            published = publish_run(
                validated,
                run_root=run_root,
                current_path=current,
                repository_root=repository,
            )
            self.assertEqual(published, load_current_run(current, repository_root=repository))


if __name__ == "__main__":
    unittest.main()
