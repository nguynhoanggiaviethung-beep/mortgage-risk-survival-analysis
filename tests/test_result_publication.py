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
    mark_run_validated,
    publish_run,
    register_artifact,
    transition_run,
    write_run_manifest,
)
from src.results.writers import atomic_write_json


COMMIT = "03d4933d6fa8d9733737189f546407a60f71d76b"


class TestResultPublication(unittest.TestCase):
    def _validated_run(
        self,
        repository_root: Path,
        second: int,
        environment: str = "PRODUCTION",
    ):
        date = datetime(2026, 9, 28, 14, 0, second, tzinfo=timezone.utc)
        created = create_run_manifest(
            environment=environment,
            code_commit=COMMIT,
            run_date_utc=date,
            runtime_versions={"python": "test"},
        )
        run_root = repository_root / "results" / "production" / created.run_id
        artifact = run_root / "models" / "result.bin"
        artifact.parent.mkdir(parents=True)
        artifact.write_bytes(f"result-{second}".encode())
        registered = register_artifact(
            created,
            run_root=run_root,
            logical_name="result",
            relative_path="models/result.bin",
            artifact_type="MODEL_RESULT",
            producer="unit_test",
            row_count=1,
        )
        running = transition_run(registered, RunStatus.RUNNING)
        return mark_run_validated(running, run_root=run_root), run_root

    def test_validated_production_run_publishes_and_loads(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            manifest, run_root = self._validated_run(repository, 1)
            current = repository / "results" / "current.json"
            published = publish_run(
                manifest,
                run_root=run_root,
                current_path=current,
                repository_root=repository,
                published_at_utc=datetime(
                    2026, 9, 28, 15, 0, 0, tzinfo=timezone.utc
                ),
            )
            self.assertEqual(published.run_status, RunStatus.PUBLISHED)
            pointer = json.loads(current.read_text(encoding="utf-8"))
            self.assertEqual(pointer["run_id"], published.run_id)
            self.assertEqual(
                pointer["manifest_relative_path"],
                f"results/production/{published.run_id}/manifest.json",
            )
            self.assertEqual(load_current_run(current, repository_root=repository), published)

    def test_created_running_failed_and_mock_runs_cannot_publish(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            validated, run_root = self._validated_run(repository, 2)
            current = repository / "results" / "current.json"
            created = create_run_manifest(
                environment="PRODUCTION",
                code_commit=COMMIT,
                run_date_utc=datetime(2026, 9, 28, 14, 1, 0, tzinfo=timezone.utc),
                runtime_versions={"python": "test"},
            )
            for invalid in (
                created,
                transition_run(created, "RUNNING"),
                transition_run(created, "FAILED"),
            ):
                with self.subTest(status=invalid.run_status):
                    with self.assertRaises(ResultManifestError):
                        publish_run(
                            invalid,
                            run_root=run_root,
                            current_path=current,
                            repository_root=repository,
                        )

            mock, mock_root = self._validated_run(repository, 3, environment="MOCK")
            with self.assertRaisesRegex(ResultManifestError, "PRODUCTION"):
                publish_run(
                    mock,
                    run_root=mock_root,
                    current_path=current,
                    repository_root=repository,
                )
            self.assertEqual(validated.run_status, RunStatus.VALIDATED)

    def test_failed_publication_leaves_previous_pointer_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            current = repository / "results" / "current.json"
            first, first_root = self._validated_run(repository, 4)
            publish_run(
                first,
                run_root=first_root,
                current_path=current,
                repository_root=repository,
            )
            previous = current.read_bytes()

            second, second_root = self._validated_run(repository, 5)
            (second_root / "models" / "result.bin").write_bytes(b"corrupt")
            with self.assertRaisesRegex(ResultManifestError, "checksum mismatch"):
                publish_run(
                    second,
                    run_root=second_root,
                    current_path=current,
                    repository_root=repository,
                )
            self.assertEqual(current.read_bytes(), previous)

    def test_loader_rejects_missing_or_non_published_current_run(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            current = repository / "results" / "current.json"
            with self.assertRaisesRegex(ResultManifestError, "No published"):
                load_current_run(current, repository_root=repository)

            validated, run_root = self._validated_run(repository, 6)
            manifest_path = run_root / "manifest.json"
            write_run_manifest(validated, manifest_path)
            atomic_write_json(
                current,
                {
                    "run_id": validated.run_id,
                    "manifest_relative_path": manifest_path.relative_to(repository).as_posix(),
                    "published_at_utc": "2026-09-28T15:00:00Z",
                },
            )
            with self.assertRaisesRegex(ResultManifestError, "published production"):
                load_current_run(current, repository_root=repository)


if __name__ == "__main__":
    unittest.main()

