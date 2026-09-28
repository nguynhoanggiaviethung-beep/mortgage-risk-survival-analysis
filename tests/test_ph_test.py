import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import polars as pl

from src.data.model_dataset import CORE_COLUMNS
from src.survival.cox_model import fit_cox_model
from src.survival.ph_test import (
    ALPHA,
    PH_DIAGNOSTIC_COLUMNS,
    PH_DIAGNOSTIC_DTYPES,
    PH_GLOBAL_DIAGNOSTIC_COLUMNS,
    PH_GLOBAL_DIAGNOSTIC_DTYPES,
    PHConfigurationError,
    PHTestError,
    _child_environment,
    classify_ph_status,
    resolve_rscript_path,
    run_ph_assumption_test,
    validate_ph_diagnostics,
    validate_ph_global_diagnostics,
    validate_ph_test_input,
    write_ph_diagnostics,
)


ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "mock_cox_input.parquet"
VARIABLE_OUTPUT = ROOT / "results" / "mock" / "ph_diagnostics.csv"
GLOBAL_OUTPUT = ROOT / "results" / "mock" / "ph_global_diagnostics.csv"


class TestPHHelpers(unittest.TestCase):
    def test_locked_status_mapping_including_boundary(self):
        self.assertEqual(classify_ph_status(0.049999, ALPHA), "FLAGGED")
        self.assertEqual(classify_ph_status(0.05, ALPHA), "PASS")
        self.assertEqual(classify_ph_status(0.5, ALPHA), "PASS")

    def test_missing_rscript_has_clear_configuration_error(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("src.survival.ph_test.shutil.which", return_value=None):
                with self.assertRaisesRegex(PHConfigurationError, "RSCRIPT_PATH"):
                    resolve_rscript_path()

    def test_invalid_configured_rscript_is_rejected(self):
        with patch.dict(os.environ, {"RSCRIPT_PATH": "missing-rscript"}, clear=True):
            with self.assertRaisesRegex(PHConfigurationError, "not a file"):
                resolve_rscript_path()

    def test_child_environment_removes_only_locale_variables(self):
        additions = {
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "LC_CTYPE": "C.UTF-8",
            "PH_KEEP_ME": "yes",
        }
        with patch.dict(os.environ, additions, clear=False):
            child = _child_environment()
            self.assertNotIn("LANG", child)
            self.assertNotIn("LC_ALL", child)
            self.assertNotIn("LC_CTYPE", child)
            self.assertEqual(child["PH_KEEP_ME"], "yes")
            self.assertEqual(os.environ["LANG"], "C.UTF-8")


@unittest.skipUnless(
    bool(os.environ.get("RSCRIPT_PATH")) or bool(__import__("shutil").which("Rscript")),
    "Rscript is not configured for Step 4 integration tests.",
)
class TestPHIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.input = pl.read_parquet(FIXTURE)
        cls.cox_result = fit_cox_model(cls.input)
        cls.result = run_ph_assumption_test(cls.cox_result, cls.input)

    def test_exact_step3_model_and_input_are_reused(self):
        before = self.input.clone()
        validated = validate_ph_test_input(self.cox_result, self.input)
        self.assertTrue(validated.equals(self.input))
        self.assertTrue(self.input.equals(before))
        self.assertEqual(self.cox_result.model.entry_col, "entry_time_month")
        self.assertEqual(list(self.cox_result.model.params_.index), CORE_COLUMNS)

    def test_variable_diagnostics_contract(self):
        result = self.result.variable_diagnostics
        self.assertEqual(result.columns, PH_DIAGNOSTIC_COLUMNS)
        self.assertEqual(result.schema, pl.Schema(PH_DIAGNOSTIC_DTYPES))
        self.assertEqual(result.height, 10)
        self.assertEqual(set(result["variable"]), set(CORE_COLUMNS))
        self.assertEqual(set(result["time_transform"]), {"rank", "km"})
        self.assertNotIn("GLOBAL", result["variable"].to_list())
        self.assertTrue(result["test_statistic"].is_finite().all())
        self.assertTrue(result["p_value"].is_between(0.0, 1.0).all())
        self.assertEqual(result["alpha"].unique().to_list(), [0.05])

    def test_official_global_results_are_separate(self):
        result = self.result.global_diagnostics
        self.assertEqual(result.columns, PH_GLOBAL_DIAGNOSTIC_COLUMNS)
        self.assertEqual(result.schema, pl.Schema(PH_GLOBAL_DIAGNOSTIC_DTYPES))
        self.assertEqual(result.height, 2)
        self.assertEqual(result["time_transform"].to_list(), ["rank", "km"])
        self.assertEqual(result["degrees_of_freedom"].to_list(), [5, 5])
        self.assertEqual(result["test_method"].unique().to_list(), ["survival::cox.zph"])
        self.assertNotIn("whole_model_status", result.columns)

    def test_mock_expected_statuses(self):
        variable = self.result.variable_diagnostics
        fico = variable.filter(pl.col("variable") == "fico")
        self.assertEqual(fico["ph_status"].to_list(), ["FLAGGED", "FLAGGED"])
        others = variable.filter(pl.col("variable") != "fico")
        self.assertEqual(set(others["ph_status"]), {"PASS"})
        self.assertEqual(set(self.result.global_diagnostics["ph_status"]), {"PASS"})

    def test_cross_engine_comparison_preserves_raw_differences(self):
        comparison = self.result.engine_comparison
        self.assertEqual(comparison["variable"].to_list(), CORE_COLUMNS)
        self.assertTrue(
            comparison.select(pl.exclude("variable")).to_numpy().shape == (5, 6)
        )
        self.assertTrue(
            np.isfinite(comparison.select(pl.exclude("variable")).to_numpy()).all()
        )
        np.testing.assert_array_equal(
            np.signbit(comparison["lifelines_coefficient"].to_numpy()),
            np.signbit(comparison["r_coefficient"].to_numpy()),
        )
        np.testing.assert_array_equal(
            comparison["coefficient_difference"].to_numpy(),
            (
                comparison["r_coefficient"]
                - comparison["lifelines_coefficient"]
            ).to_numpy(),
        )

    def test_scaled_schoenfeld_information_is_retained(self):
        residuals = self.result.scaled_schoenfeld
        self.assertEqual(residuals.height, 72 * 5 * 2)
        self.assertEqual(set(residuals["time_transform"]), {"rank", "km"})
        self.assertEqual(set(residuals["variable"]), set(CORE_COLUMNS))
        self.assertTrue(residuals["scaled_schoenfeld_residual"].is_finite().all())
        counts = residuals.group_by("time_transform", "variable").len()
        self.assertEqual(counts["len"].unique().to_list(), [72])

    def test_mismatched_training_data_is_rejected(self):
        with self.assertRaisesRegex(PHTestError, "do not match"):
            validate_ph_test_input(self.cox_result, self.input.head(239))

    def test_nonlocked_alpha_is_rejected(self):
        with self.assertRaisesRegex(PHTestError, "locked"):
            run_ph_assumption_test(self.cox_result, self.input, alpha=0.01)

    def test_checked_in_csvs_match_regeneration(self):
        saved_variable = pl.read_csv(
            VARIABLE_OUTPUT,
            schema_overrides=PH_DIAGNOSTIC_DTYPES,
        )
        saved_global = pl.read_csv(
            GLOBAL_OUTPUT,
            schema_overrides=PH_GLOBAL_DIAGNOSTIC_DTYPES,
        )
        self.assertTrue(
            validate_ph_diagnostics(saved_variable).equals(
                self.result.variable_diagnostics
            )
        )
        self.assertTrue(
            validate_ph_global_diagnostics(saved_global).equals(
                self.result.global_diagnostics
            )
        )

    def test_writer_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            variable_path = Path(directory) / "nested" / "variable.csv"
            global_path = Path(directory) / "nested" / "global.csv"
            outputs = write_ph_diagnostics(
                self.result,
                variable_path,
                global_path,
            )
            self.assertEqual(outputs, (variable_path, global_path))
            variable = pl.read_csv(
                variable_path,
                schema_overrides=PH_DIAGNOSTIC_DTYPES,
            )
            global_result = pl.read_csv(
                global_path,
                schema_overrides=PH_GLOBAL_DIAGNOSTIC_DTYPES,
            )
            self.assertTrue(variable.equals(self.result.variable_diagnostics))
            self.assertTrue(global_result.equals(self.result.global_diagnostics))


if __name__ == "__main__":
    unittest.main()
