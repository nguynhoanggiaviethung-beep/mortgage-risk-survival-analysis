import tempfile
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch

import numpy as np
import polars as pl
from lifelines import CoxTimeVaryingFitter
from lifelines.exceptions import ConvergenceWarning

from scripts.build_mock_time_varying_cox_results import (
    build_mock_time_varying_cox_results,
)
from src.survival.time_varying_cox_model import (
    TIME_VARYING_COX_DIAGNOSTIC_COLUMNS,
    TIME_VARYING_COX_DIAGNOSTIC_DTYPES,
    TIME_VARYING_COX_RESULT_COLUMNS,
    TIME_VARYING_COX_RESULT_DTYPES,
    TimeVaryingCoxModelError,
    fit_time_varying_cox_model,
    validate_time_varying_cox_diagnostics,
    validate_time_varying_cox_results,
    write_time_varying_cox_artifacts,
)
from src.survival.time_varying_input import (
    STEP5A_PREDICTORS,
    validate_time_varying_cox_input,
)
from tests.time_varying_fixtures import FITTER_SEED, build_fitter_fixture


ROOT = Path(__file__).resolve().parent.parent
MOCK_RESULTS = ROOT / "results" / "mock" / "time_varying_cox_results.parquet"
MOCK_DIAGNOSTICS = (
    ROOT / "results" / "mock" / "time_varying_cox_diagnostics.parquet"
)


class TestTimeVaryingCoxModel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.input = build_fitter_fixture()
        cls.result = fit_time_varying_cox_model(cls.input)

    def test_fitter_fixture_is_deterministic_full_rank_and_well_formed(self):
        self.assertEqual(FITTER_SEED, 20260928)
        self.assertTrue(self.input.equals(build_fitter_fixture()))
        self.assertEqual(self.input["loan_id"].n_unique(), 420)
        self.assertEqual(self.input.height, 1680)
        self.assertEqual(self.input["default_event"].sum(), 140)
        self.assertFalse(self.input.null_count().to_numpy().any())
        self.assertEqual(
            np.linalg.matrix_rank(
                self.input.select(STEP5A_PREDICTORS).to_numpy()
            ),
            len(STEP5A_PREDICTORS),
        )
        validate_time_varying_cox_input(self.input)

    def test_fit_returns_locked_model_and_result_schemas(self):
        self.assertIsInstance(self.result.model, CoxTimeVaryingFitter)
        self.assertFalse(self.result.model.robust)
        self.assertEqual(self.result.model.id_col, "loan_id")
        self.assertEqual(self.result.model.start_col, "start_time_month")
        self.assertEqual(self.result.model.stop_col, "stop_time_month")
        self.assertEqual(list(self.result.model.params_.index), STEP5A_PREDICTORS)
        self.assertEqual(
            self.result.coefficients.columns,
            TIME_VARYING_COX_RESULT_COLUMNS,
        )
        self.assertEqual(
            self.result.coefficients.schema,
            pl.Schema(TIME_VARYING_COX_RESULT_DTYPES),
        )
        self.assertEqual(
            self.result.diagnostics.columns,
            TIME_VARYING_COX_DIAGNOSTIC_COLUMNS,
        )
        self.assertEqual(
            self.result.diagnostics.schema,
            pl.Schema(TIME_VARYING_COX_DIAGNOSTIC_DTYPES),
        )

    def test_coefficients_and_hazard_ratio_confidence_limits(self):
        coefficients = self.result.coefficients
        self.assertEqual(coefficients["variable"].to_list(), STEP5A_PREDICTORS)
        np.testing.assert_allclose(
            coefficients["hazard_ratio"].to_numpy(),
            np.exp(coefficients["coefficient"].to_numpy()),
            rtol=1e-12,
            atol=0.0,
        )
        expected_ci = np.exp(
            self.result.model.confidence_intervals_
            .loc[STEP5A_PREDICTORS]
            .to_numpy()
        )
        np.testing.assert_allclose(
            coefficients.select("ci_lower", "ci_upper").to_numpy(),
            expected_ci,
            rtol=1e-12,
            atol=0.0,
        )

    def test_required_diagnostics(self):
        row = self.result.diagnostics.row(0, named=True)
        self.assertEqual(row["n_intervals"], 1680)
        self.assertEqual(row["n_loans"], 420)
        self.assertEqual(row["n_events"], 140)
        self.assertEqual(row["n_censored_loans"], 280)
        self.assertEqual(row["n_predictors"], len(STEP5A_PREDICTORS))
        self.assertEqual(row["n_delayed_entry_loans"], 84)
        self.assertEqual(row["n_gap_intervals"], 33)
        self.assertEqual(row["max_interval_length_months"], 2)
        self.assertEqual(row["variance_type"], "model_based")
        self.assertEqual(row["convergence_status"], "PASS")
        self.assertEqual(row["convergence_warning"], "")
        self.assertTrue(np.isfinite(row["log_likelihood"]))
        self.assertTrue(np.isfinite(row["partial_aic"]))

    def test_convergence_warning_is_reported(self):
        original_fit = CoxTimeVaryingFitter.fit

        def fit_with_warning(estimator, *args, **kwargs):
            warnings.warn("synthetic time-varying warning", ConvergenceWarning)
            return original_fit(estimator, *args, **kwargs)

        with patch.object(CoxTimeVaryingFitter, "fit", new=fit_with_warning):
            warned = fit_time_varying_cox_model(self.input)
        diagnostic = warned.diagnostics.row(0, named=True)
        self.assertEqual(diagnostic["convergence_status"], "WARNING")
        self.assertIn(
            "synthetic time-varying warning",
            diagnostic["convergence_warning"],
        )

    def test_invalid_input_and_confidence_level_are_rejected(self):
        missing = self.input.drop("lag_dq_ra")
        with self.assertRaisesRegex(TimeVaryingCoxModelError, "missing required"):
            fit_time_varying_cox_model(missing)

        nonfinite = self.input.with_columns(
            pl.when(pl.arange(0, pl.len()) == 0)
            .then(float("nan"))
            .otherwise(pl.col("lag_current_interest_rate"))
            .alias("lag_current_interest_rate")
        )
        with self.assertRaisesRegex(TimeVaryingCoxModelError, "non-finite"):
            fit_time_varying_cox_model(nonfinite)

        for value in (0, 1, -0.1, 1.1, True, "0.95"):
            with self.subTest(value=value):
                with self.assertRaises(TimeVaryingCoxModelError):
                    fit_time_varying_cox_model(
                        self.input,
                        confidence_level=value,
                    )

    def test_input_is_not_mutated(self):
        before = self.input.clone()
        fit_time_varying_cox_model(self.input)
        self.assertTrue(self.input.equals(before))

    def test_result_validators_and_writer_round_trip(self):
        self.assertTrue(
            validate_time_varying_cox_results(
                self.result.coefficients
            ).equals(self.result.coefficients)
        )
        self.assertTrue(
            validate_time_varying_cox_diagnostics(
                self.result.diagnostics
            ).equals(self.result.diagnostics)
        )
        with tempfile.TemporaryDirectory() as directory:
            coefficients = Path(directory) / "nested" / "coefficients.parquet"
            diagnostics = Path(directory) / "nested" / "diagnostics.parquet"
            outputs = write_time_varying_cox_artifacts(
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

    def test_checked_in_artifacts_match_deterministic_regeneration(self):
        saved_results = validate_time_varying_cox_results(
            pl.read_parquet(MOCK_RESULTS)
        )
        saved_diagnostics = validate_time_varying_cox_diagnostics(
            pl.read_parquet(MOCK_DIAGNOSTICS)
        )
        self.assertTrue(saved_results.equals(self.result.coefficients))
        self.assertTrue(saved_diagnostics.equals(self.result.diagnostics))

        with tempfile.TemporaryDirectory() as first_directory, \
                tempfile.TemporaryDirectory() as second_directory:
            first_results = Path(first_directory) / "results.parquet"
            first_diagnostics = Path(first_directory) / "diagnostics.parquet"
            second_results = Path(second_directory) / "results.parquet"
            second_diagnostics = Path(second_directory) / "diagnostics.parquet"

            first_outputs = build_mock_time_varying_cox_results(
                first_results,
                first_diagnostics,
            )
            second_outputs = build_mock_time_varying_cox_results(
                second_results,
                second_diagnostics,
            )

            self.assertEqual(first_outputs, (first_results, first_diagnostics))
            self.assertEqual(second_outputs, (second_results, second_diagnostics))
            self.assertEqual(MOCK_RESULTS.read_bytes(), first_results.read_bytes())
            self.assertEqual(first_results.read_bytes(), second_results.read_bytes())
            self.assertEqual(
                MOCK_DIAGNOSTICS.read_bytes(),
                first_diagnostics.read_bytes(),
            )
            self.assertEqual(
                first_diagnostics.read_bytes(),
                second_diagnostics.read_bytes(),
            )


if __name__ == "__main__":
    unittest.main()
