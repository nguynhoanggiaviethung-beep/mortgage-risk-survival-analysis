import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from src.results import (
    DATA_VERSION,
    MODEL_VERSION_REGISTRY,
    ResultManifestError,
    RunEnvironment,
    RunStatus,
    build_data_version,
    create_run_manifest,
    load_run_manifest,
    register_artifact,
    transition_run,
    validate_run_manifest,
    write_run_manifest,
)


COMMIT = "03d4933d6fa8d9733737189f546407a60f71d76b"
RUN_DATE = datetime(2026, 9, 28, 14, 0, 0, tzinfo=timezone.utc)


class TestResultManifest(unittest.TestCase):
    def test_locked_versions_and_deterministic_identity(self):
        self.assertEqual(
            build_data_version(),
            "freddie_sample_2016_2026_cutoff_202603_v1",
        )
        self.assertEqual(DATA_VERSION, build_data_version())
        self.assertEqual(
            MODEL_VERSION_REGISTRY,
            {
                "kaplan_meier": "km_v1",
                "cox_ph": "cox_ph_v1",
                "time_varying_cox": "tv_cox_v1",
                "cause_specific_default": "cause_specific_default_v1",
                "cause_specific_prepayment": "cause_specific_prepayment_v1",
                "aalen_johansen": "aalen_johansen_v1",
                "fine_gray_default": "fine_gray_default_v1",
                "pd_horizons": "pd_horizons_v1",
                "vintage_analysis": "vintage_analysis_v1",
            },
        )
        manifest = create_run_manifest(
            environment=RunEnvironment.MOCK,
            code_commit=COMMIT,
            run_date_utc=RUN_DATE,
            runtime_versions={"python": "test"},
        )
        self.assertEqual(manifest.run_id, "20260928T140000Z_03d4933")
        self.assertEqual(manifest.run_date_utc, "2026-09-28T14:00:00Z")
        self.assertEqual(manifest.run_status, RunStatus.CREATED)
        self.assertEqual(manifest.specification_version, "1.0.0")
        self.assertEqual(manifest.cohort_start_year, 2016)
        self.assertEqual(manifest.cohort_end_year, 2026)
        self.assertEqual(manifest.performance_cutoff, "202603")

    def test_naive_datetime_and_invalid_model_mapping_are_rejected(self):
        with self.assertRaisesRegex(ResultManifestError, "timezone-aware"):
            create_run_manifest(
                environment="MOCK",
                code_commit=COMMIT,
                run_date_utc=datetime(2026, 9, 28, 14, 0, 0),
            )
        valid = create_run_manifest(
            environment="MOCK",
            code_commit=COMMIT,
            run_date_utc=RUN_DATE,
            runtime_versions={"python": "test"},
        )
        with self.assertRaisesRegex(ResultManifestError, "model_versions"):
            validate_run_manifest(
                replace(valid, model_versions={"kaplan_meier": "wrong"})
            )

    def test_manifest_round_trip_and_caller_not_mutated(self):
        manifest = create_run_manifest(
            environment="MOCK",
            code_commit=COMMIT,
            run_date_utc=RUN_DATE,
            runtime_versions={"python": "test"},
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = root / "models" / "result.bin"
            artifact.parent.mkdir()
            artifact.write_bytes(b"canonical-result")
            registered = register_artifact(
                manifest,
                run_root=root,
                logical_name="test_result",
                relative_path="models/result.bin",
                artifact_type="MODEL_RESULT",
                producer="unit_test",
                row_count=1,
            )
            self.assertEqual(manifest.artifacts, ())
            self.assertEqual(len(registered.artifacts), 1)

            output = root / "manifest.json"
            write_run_manifest(registered, output)
            self.assertEqual(load_run_manifest(output), registered)

    def test_relative_paths_required_and_traversal_rejected(self):
        manifest = create_run_manifest(
            environment="MOCK",
            code_commit=COMMIT,
            run_date_utc=RUN_DATE,
            runtime_versions={"python": "test"},
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outside = root.parent / "outside.bin"
            for relative in ("../outside.bin", str(outside.resolve()), "a\\b.bin"):
                with self.subTest(relative=relative):
                    with self.assertRaises(ResultManifestError):
                        register_artifact(
                            manifest,
                            run_root=root,
                            logical_name="unsafe",
                            relative_path=relative,
                            artifact_type="MODEL_RESULT",
                            producer="unit_test",
                        )

    def test_legal_and_illegal_status_transitions(self):
        created = create_run_manifest(
            environment="PRODUCTION",
            code_commit=COMMIT,
            run_date_utc=RUN_DATE,
            runtime_versions={"python": "test"},
        )
        running = transition_run(created, RunStatus.RUNNING)
        failed = transition_run(running, RunStatus.FAILED)
        self.assertEqual(failed.run_status, RunStatus.FAILED)
        with self.assertRaisesRegex(ResultManifestError, "Illegal"):
            transition_run(created, RunStatus.PUBLISHED)
        with self.assertRaisesRegex(ResultManifestError, "Illegal"):
            transition_run(failed, RunStatus.RUNNING)


if __name__ == "__main__":
    unittest.main()

