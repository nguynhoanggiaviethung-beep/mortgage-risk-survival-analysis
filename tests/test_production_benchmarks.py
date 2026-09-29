import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import polars as pl

from src.production.benchmarks import (
    _base_metrics,
    build_tv_cox_benchmark_preflight,
    deterministic_nested_loan_sample,
    deterministic_tv_cox_loan_sample,
    select_complete_performance_histories,
    run_tv_cox_benchmark,
)
from scripts.run_resource_benchmark import print_console_safe_path
from tests.time_varying_fixtures import build_fitter_fixture


class TestProductionBenchmarks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rows = []
        for index in range(40):
            event = "DEFAULT" if index in {3, 29} else (
                "PREPAYMENT" if index % 3 == 0 else "CENSOR"
            )
            rows.append({
                "loan_id": f"L{index:03d}",
                "event_type": event,
                "entry_time_month": index % 4,
            })
        cls.loans = pl.DataFrame(rows)

    def test_samples_are_deterministic_nested_and_event_preserving(self):
        small = deterministic_nested_loan_sample(self.loans, 10)
        repeated = deterministic_nested_loan_sample(self.loans, 10)
        large = deterministic_nested_loan_sample(self.loans, 25)
        self.assertTrue(small.equals(repeated))
        self.assertEqual(
            small["loan_id"].to_list(), large["loan_id"].head(10).to_list()
        )
        self.assertEqual(
            set(small["event_type"]), {"DEFAULT", "PREPAYMENT", "CENSOR"}
        )

    def test_fine_gray_sampler_regression_is_unchanged(self):
        sample = deterministic_nested_loan_sample(self.loans, 10)
        self.assertEqual(sample["loan_id"].to_list(), [
            "L035", "L003", "L036", "L004", "L033",
            "L022", "L010", "L018", "L019", "L017",
        ])

    def test_tv_samples_include_all_defaults_and_are_exact_nested_prefixes(self):
        original = self.loans.clone()
        small = deterministic_tv_cox_loan_sample(self.loans, 10)
        repeated = deterministic_tv_cox_loan_sample(self.loans, 10)
        medium = deterministic_tv_cox_loan_sample(self.loans, 25)
        large = deterministic_tv_cox_loan_sample(self.loans, 35)

        self.assertTrue(small.equals(repeated))
        self.assertEqual(small.height, 10)
        self.assertEqual(medium.height, 25)
        self.assertEqual(large.height, 35)
        self.assertEqual(
            set(self.loans.filter(pl.col("event_type") == "DEFAULT")["loan_id"]),
            set(small.filter(pl.col("event_type") == "DEFAULT")["loan_id"]),
        )
        self.assertEqual(
            small["loan_id"].to_list(), medium["loan_id"].head(10).to_list()
        )
        self.assertEqual(
            medium["loan_id"].to_list(), large["loan_id"].head(25).to_list()
        )
        self.assertTrue(
            {"PREPAYMENT", "CENSOR"}.issubset(set(small["event_type"]))
        )
        self.assertTrue(self.loans.equals(original))

    def test_tv_selection_retains_complete_histories(self):
        performance = pl.DataFrame({
            "loan_id": ["L000", "L000", "L001", "L001", "L001", "L002"],
            "month": [1, 2, 1, 2, 3, 1],
        })
        selected = self.loans.filter(pl.col("loan_id").is_in(["L000", "L001"]))
        result = select_complete_performance_histories(performance, selected).collect()
        self.assertEqual(result.height, 5)
        self.assertEqual(result.group_by("loan_id").len().sort("loan_id")["len"].to_list(), [2, 3])

    def test_benchmark_metadata_is_explicitly_not_production(self):
        sample = deterministic_nested_loan_sample(self.loans, 10)
        metrics = _base_metrics("TEST_RESOURCE", 10, sample)
        self.assertFalse(metrics["is_production_result"])
        self.assertEqual(metrics["peak_rss_bytes"], None)
        self.assertEqual(metrics["actual_loans"], 10)

    def test_tv_identifiability_preflight_reports_exact_support(self):
        intervals = build_fitter_fixture(n_loans=60)
        result = build_tv_cox_benchmark_preflight(intervals)

        self.assertEqual(result["status"], "COMPLETED")
        self.assertTrue(all(
            item["all_finite"]
            for item in result["predictor_finite_support"].values()
        ))
        self.assertEqual(result["interval_integrity"]["status"], "PASS")
        self.assertEqual(result["terminal_default_event_count"], 20)
        self.assertEqual(result["initial_information_matrix_dimension"], 8)
        self.assertTrue(result["initial_information_matrix_all_finite"])
        self.assertIn(
            "positive_count_default_terminal_intervals",
            result["binary_delinquency_support"]["lag_dq_3plus"],
        )

    def test_unicode_output_path_is_safe_for_cp1252_console(self):
        buffer = io.BytesIO()
        stream = io.TextIOWrapper(buffer, encoding="cp1252", errors="strict")
        print_console_safe_path(Path("E:/GÓI_PHẦN_MỀM/báo-cáo.json"), stream=stream)
        stream.flush()
        rendered = buffer.getvalue().decode("cp1252")
        self.assertIn(r"\u1ea6", rendered)
        self.assertIn("báo-cáo.json", rendered)

    def test_tv_failure_persists_completed_metrics_and_exact_exception(self):
        performance = pl.DataFrame({
            "loan_id": self.loans["loan_id"],
            "unused": list(range(self.loans.height)),
        })
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "failed.json"
            intervals = pl.DataFrame({"placeholder": [1, 2, 3]})
            with patch(
                "src.production.benchmarks.build_time_varying_cox_input",
                return_value=intervals.lazy(),
            ), patch(
                "src.production.benchmarks.validate_time_varying_cox_input",
                return_value=intervals,
            ), patch(
                "src.production.benchmarks.fit_time_varying_cox_model",
                side_effect=RuntimeError("diagnostic failure"),
            ), patch(
                "src.production.benchmarks.build_tv_cox_benchmark_preflight",
                return_value={"status": "COMPLETED"},
            ):
                with self.assertRaisesRegex(RuntimeError, "diagnostic failure"):
                    run_tv_cox_benchmark(
                        self.loans,
                        performance,
                        requested_loans=10,
                        output_path=output,
                    )
            report = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(report["status"], "FAILED")
        self.assertEqual(report["failure_stage"], "MODEL_FIT")
        self.assertEqual(report["exception_type"], "RuntimeError")
        self.assertEqual(report["exception_message"], "diagnostic failure")
        self.assertEqual(report["actual_loans"], 10)
        self.assertEqual(report["source_monthly_rows"], 10)
        self.assertEqual(report["constructed_interval_rows"], 3)
        self.assertIsNotNone(report["input_build_runtime_seconds"])
        self.assertEqual(report["input_validation_status"], "PASS")
        self.assertEqual(
            report["identifiability_preflight"], {"status": "COMPLETED"}
        )
        self.assertEqual(report["convergence_status"], "FAILED")
        self.assertIsNotNone(report["fit_runtime_seconds"])
        self.assertFalse(report["is_production_result"])


if __name__ == "__main__":
    unittest.main()
