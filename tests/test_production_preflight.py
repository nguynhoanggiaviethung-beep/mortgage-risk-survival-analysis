import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.production.contracts import INPUT_CONTRACTS
from src.production.preflight import (
    PreflightError,
    classify_worktree,
    fingerprint_inputs,
    preflight_r_runtime,
    write_input_provenance,
)


ROOT = Path(__file__).resolve().parent.parent


class TestProductionPreflight(unittest.TestCase):
    def _repository(self, root: Path) -> None:
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
        (root / "src").mkdir()
        (root / "reports").mkdir()
        (root / "src/model.py").write_text("VALUE = 1\n", encoding="utf-8")
        (root / "reports/local.txt").write_text("old\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=root, check=True)
        subprocess.run(["git", "commit", "-qm", "initial"], cwd=root, check=True)

    def test_worktree_classifies_critical_and_local_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._repository(root)
            (root / "src/model.py").write_text("VALUE = 2\n", encoding="utf-8")
            (root / "reports/local.txt").write_text("new\n", encoding="utf-8")
            result = classify_worktree(root)
            self.assertFalse(result["eligible"])
            self.assertEqual(
                [item["path"] for item in result["critical_changes"]],
                ["src/model.py"],
            )
            self.assertEqual(
                [item["path"] for item in result["noncritical_changes"]],
                ["reports/local.txt"],
            )

    def test_current_inputs_match_versioned_fingerprints(self):
        result = fingerprint_inputs(ROOT)
        self.assertEqual(result["overall_status"], "PASS")
        self.assertEqual(
            {item["role"] for item in result["inputs"]}, set(INPUT_CONTRACTS)
        )

    def test_input_provenance_is_machine_readable(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "provenance.json"
            payload = {"data_version": "test", "inputs": [], "overall_status": "PASS"}
            write_input_provenance(payload, path)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), payload)

    @patch("src.production.preflight.run_rscript_process")
    def test_r_preflight_accepts_only_exact_runtime(self, run):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "Rscript.exe"
            executable.write_bytes(b"")
            run.return_value.returncode = 0
            run.return_value.stderr = ""
            run.return_value.stdout = (
                "R_VERSION\t4.6.1\nSURVIVAL_VERSION\t3.8-6\n"
                "COXPH\tTRUE\nSURVFIT\tTRUE\nFINEGRAY\tTRUE\n"
            )
            result = preflight_r_runtime(executable)
            self.assertEqual(result["r_version"], "4.6.1")
            self.assertEqual(result["survival_version"], "3.8-6")
            self.assertEqual(result["rscript_path"], str(executable.resolve()))

            run.return_value.stdout = run.return_value.stdout.replace("3.8-6", "3.9-0")
            with self.assertRaisesRegex(PreflightError, "differs from approved"):
                preflight_r_runtime(executable)


if __name__ == "__main__":
    unittest.main()
