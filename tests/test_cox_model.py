import tempfile
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch

import numpy as np
import polars as pl
from lifelines import CoxPHFitter
from lifelines.exceptions import ConvergenceWarning

from scripts.build_mock_cox_results import SEED, build_fixture
from src.data.model_dataset import CORE_COLUMNS
from src.survival.cox_model import (
    COX_DIAGNOSTIC_COLUMNS,
    COX_DIAGNOSTIC_DTYPES,
    COX_RESULT_COLUMNS,
    COX_RESULT_DTYPES,
    CoxModelError,
    fit_cox_model,
    validate_cox_diagnostics,
    validate_cox_input,
    validate_cox_results,
    write_cox_artifacts,
)


ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "mock_cox_input.parquet"
MOCK_RESULTS = ROOT / "results" / "mock" / "cox_results.parquet"
MOCK_DIAGNOSTICS = ROOT / "results" / "mock" / "cox_diagnostics.parquet"


class TestCoxModel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.input = pl.read_parquet(FIXTURE)
        cls.result = fit_cox_model(cls.input)

    def test_fixture_contract_and_seed_regeneration(self):
        self.assertEqual(SEED, 20260928)
        self.assertTrue(self.input.equals(build_fixture()))
        self.assertEqual(self.input.height, 240)
        counts = {
            row["event_type"]: row["len"]
            for row in self.input.group_by("event_type").len().to_dicts()
        }
        self.assertEqual(counts, {"DEFAULT": 72, "PREPAYMENT": 84, "CENSOR": 84})
        self.assertFalse(self.input.null_count().to_numpy().any())
        self.assertTrue((self.input["entry_time_month"] < self.input["exit_time_month"]).all())
        self.assertGreater((self.input["entry_time_month"] > 0).sum(), 0)
        self.assertLess(self.input["exit_time_month"].n_unique(), self.input.height)
        self.assertTrue(all(self.input[name].n_unique() > 1 for name in CORE_COLUMNS))
        self.assertEqual(
            np.linalg.matrix_rank(self.input.select(CORE_COLUMNS).to_numpy()),
            len(CORE_COLUMNS),
        )

    def test_fit_returns_model_coefficients_and_diagnostics(self):
        self.assertIsInstance(self.result.model, CoxPHFitter)
        self.assertEqual(self.result.model.entry_col, "entry_time_month")
        self.assertEqual(self.result.coefficients.columns, COX_RESULT_COLUMNS)
        self.assertEqual(self.result.coefficients.schema, pl.Schema(COX_RESULT_DTYPES))
        self.assertEqual(self.result.diagnostics.columns, COX_DIAGNOSTIC_COLUMNS)
        self.assertEqual(
            self.result.diagnostics.schema,
            pl.Schema(COX_DIAGNOSTIC_DTYPES),
        )

    def test_locked_predictors_and_original_unit_coefficients(self):
        coefficients = self.result.coefficients
        self.assertEqual(coefficients["variable"].to_list(), CORE_COLUMNS)
        for row in coefficients.to_dicts():
            self.assertAlmostEqual(
                row["hazard_ratio"],
                np.exp(row["coefficient"]),
                places=12,
            )
        self.assertEqual(list(self.result.model.params_.index), CORE_COLUMNS)

    def test_confidence_limits_are_hazard_ratio_limits(self):
        expected = np.exp(
            self.result.model.confidence_intervals_.loc[CORE_COLUMNS].to_numpy()
        )
        np.testing.assert_allclose(
            self.result.coefficients.select("ci_lower", "ci_upper").to_numpy(),
            expected,
            rtol=1e-12,
            atol=0.0,
        )

    def test_diagnostics_counts_and_clean_convergence(self):
        row = self.result.diagnostics.row(0, named=True)
        self.assertEqual(row["n_observations"], 240)
        self.assertEqual(row["n_events"], 72)
        self.assertEqual(row["n_censored"], 168)
        self.assertEqual(row["n_predictors"], 5)
        self.assertEqual(row["delayed_entry_count"], 48)
        self.assertEqual(row["convergence_status"], "PASS")
        self.assertEqual(row["convergence_warning"], "")
        self.assertTrue(np.isfinite(row["log_likelihood"]))
        self.assertTrue(np.isfinite(row["partial_aic"]))
        self.assertTrue(np.isfinite(row["concordance_index"]))

    def test_prepayment_is_censored_for_default_endpoint(self):
        prepayment = self.input.filter(pl.col("event_type") == "PREPAYMENT")
        self.assertTrue((prepayment["default_event"] == 0).all())
        self.assertEqual(self.result.diagnostics["n_censored"].item(), 84 + 84)

    def test_convergence_warning_is_reported_without_fake_pass(self):
        original_fit = CoxPHFitter.fit

        def fit_with_warning(estimator, *args, **kwargs):
            warnings.warn("synthetic convergence warning", ConvergenceWarning)
            return original_fit(estimator, *args, **kwargs)

        with patch.object(CoxPHFitter, "fit", new=fit_with_warning):
            warned = fit_cox_model(self.input)
        diagnostic = warned.diagnostics.row(0, named=True)
        self.assertEqual(diagnostic["convergence_status"], "WARNING")
        self.assertIn("synthetic convergence warning", diagnostic["convergence_warning"])

    def test_missing_nonfinite_duplicate_and_invalid_time_rejected(self):
        with self.assertRaisesRegex(CoxModelError, "missing required columns"):
            validate_cox_input(self.input.drop("fico"))
        with self.assertRaisesRegex(CoxModelError, "duplicate loan_id"):
            validate_cox_input(pl.concat([self.input, self.input.head(1)]))
        with self.assertRaisesRegex(CoxModelError, "missing or non-finite"):
            validate_cox_input(
                self.input.with_columns(
                    pl.when(pl.arange(0, pl.len()) == 0)
                    .then(float("nan"))
                    .otherwise(pl.col("original_ltv"))
                    .alias("original_ltv")
                )
            )
        with self.assertRaisesRegex(CoxModelError, "entry/exit/duration"):
            validate_cox_input(
                self.input.with_columns(
                    pl.col("entry_time_month").alias("exit_time_month")
                )
            )

    def test_invalid_event_and_confidence_level_rejected(self):
        default_loan = self.input.filter(
            pl.col("event_type") == "DEFAULT"
        )["loan_id"][0]
        invalid_event = self.input.with_columns(
            pl.when(pl.col("loan_id") == default_loan)
            .then(pl.lit(0, dtype=pl.Int8))
            .otherwise(pl.col("default_event"))
            .alias("default_event")
        )
        with self.assertRaisesRegex(CoxModelError, "event"):
            validate_cox_input(invalid_event)
        for value in (0, 1, -0.1, 1.1, True, "0.95"):
            with self.subTest(value=value):
                with self.assertRaises(CoxModelError):
                    fit_cox_model(self.input, confidence_level=value)

    def test_input_is_not_mutated(self):
        before = self.input.clone()
        fit_cox_model(self.input)
        self.assertTrue(self.input.equals(before))

    def test_checked_in_artifacts_match_regeneration(self):
        saved_results = validate_cox_results(pl.read_parquet(MOCK_RESULTS))
        saved_diagnostics = validate_cox_diagnostics(
            pl.read_parquet(MOCK_DIAGNOSTICS)
        )
        self.assertTrue(saved_results.equals(self.result.coefficients))
        self.assertTrue(saved_diagnostics.equals(self.result.diagnostics))

    def test_writer_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            coefficients = Path(directory) / "nested" / "coefficients.parquet"
            diagnostics = Path(directory) / "nested" / "diagnostics.parquet"
            outputs = write_cox_artifacts(
                self.result,
                coefficients,
                diagnostics,
            )
            self.assertEqual(outputs, (coefficients, diagnostics))
            self.assertTrue(
                pl.read_parquet(coefficients).equals(self.result.coefficients)
            )
            self.assertTrue(
                pl.read_parquet(diagnostics).equals(self.result.diagnostics)
            )


if __name__ == "__main__":
    unittest.main()
