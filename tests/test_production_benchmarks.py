import unittest

import polars as pl

from src.production.benchmarks import (
    _base_metrics,
    deterministic_nested_loan_sample,
    select_complete_performance_histories,
)


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


if __name__ == "__main__":
    unittest.main()
