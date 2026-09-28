import tempfile
import unittest
from pathlib import Path

import numpy as np
import polars as pl

from scripts.build_mock_cause_specific_results import (
    build_cause_specific_fixture,
    build_mock_cause_specific_results,
)
from src.competing_risks.cause_specific import (
    CAUSE_SPECIFIC_DIAGNOSTIC_COLUMNS,
    CAUSE_SPECIFIC_DIAGNOSTIC_DTYPES,
    CAUSE_SPECIFIC_RESULT_COLUMNS,
    CAUSE_SPECIFIC_RESULT_DTYPES,
    CauseSpecificModelError,
    fit_cause_specific_model,
    fit_paired_cause_specific_models,
    validate_cause_specific_diagnostics,
    validate_cause_specific_input,
    validate_cause_specific_results,
    write_cause_specific_artifacts,
)
from src.data.model_dataset import CORE_COLUMNS
from src.survival.cox_model import fit_cox_model


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RESULTS = ROOT / "results/mock/cause_specific_default_results.parquet"
DEFAULT_DIAGNOSTICS = ROOT / "results/mock/cause_specific_default_diagnostics.parquet"
PREPAYMENT_RESULTS = ROOT / "results/mock/cause_specific_prepayment_results.parquet"
PREPAYMENT_DIAGNOSTICS = ROOT / "results/mock/cause_specific_prepayment_diagnostics.parquet"


class TestCauseSpecificCox(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.input = build_cause_specific_fixture()
        cls.pair = fit_paired_cause_specific_models(cls.input)

    def test_locked_event_coding_risk_sets_delayed_entry_and_ties(self):
        default = self.input.filter(pl.col("event_type") == "DEFAULT")
        prepayment = self.input.filter(pl.col("event_type") == "PREPAYMENT")
        censor = self.input.filter(pl.col("event_type") == "CENSOR")
        self.assertTrue((default["default_event"] == 1).all())
        self.assertTrue((default["prepayment_event"] == 0).all())
        self.assertTrue((prepayment["default_event"] == 0).all())
        self.assertTrue((prepayment["prepayment_event"] == 1).all())
        self.assertTrue((censor["default_event"] == 0).all())
        self.assertTrue((censor["prepayment_event"] == 0).all())
        self.assertEqual((self.input["entry_time_month"] > 0).sum(), 48)
        self.assertLess(self.input["exit_time_month"].n_unique(), self.input.height)
        self.assertEqual(self.pair.default.model.entry_col, "entry_time_month")
        self.assertEqual(self.pair.prepayment.model.entry_col, "entry_time_month")

    def test_result_and_diagnostic_schemas(self):
        for endpoint, result, events in (
            ("DEFAULT", self.pair.default, 72),
            ("PREPAYMENT", self.pair.prepayment, 84),
        ):
            with self.subTest(endpoint=endpoint):
                self.assertEqual(result.coefficients.columns, CAUSE_SPECIFIC_RESULT_COLUMNS)
                self.assertEqual(
                    result.coefficients.schema,
                    pl.Schema(CAUSE_SPECIFIC_RESULT_DTYPES),
                )
                self.assertEqual(
                    result.diagnostics.columns,
                    CAUSE_SPECIFIC_DIAGNOSTIC_COLUMNS,
                )
                self.assertEqual(
                    result.diagnostics.schema,
                    pl.Schema(CAUSE_SPECIFIC_DIAGNOSTIC_DTYPES),
                )
                self.assertEqual(result.coefficients["endpoint"].unique().to_list(), [endpoint])
                self.assertEqual(result.coefficients["variable"].to_list(), CORE_COLUMNS)
                row = result.diagnostics.row(0, named=True)
                self.assertEqual(row["n_observations"], 240)
                self.assertEqual(row["n_events"], events)
                self.assertEqual(row["n_censored"], 240 - events)
                self.assertEqual(row["delayed_entry_count"], 48)
                self.assertEqual(row["convergence_status"], "PASS")
                validate_cause_specific_results(result.coefficients, endpoint)
                validate_cause_specific_diagnostics(result.diagnostics, endpoint)

    def test_hazard_ratios_and_confidence_intervals_are_on_hr_scale(self):
        for result in (self.pair.default, self.pair.prepayment):
            np.testing.assert_allclose(
                result.coefficients["hazard_ratio"].to_numpy(),
                np.exp(result.coefficients["coefficient"].to_numpy()),
                rtol=1e-12,
                atol=0.0,
            )
            expected_ci = np.exp(
                result.model.confidence_intervals_.loc[CORE_COLUMNS].to_numpy()
            )
            np.testing.assert_allclose(
                result.coefficients.select("ci_lower", "ci_upper").to_numpy(),
                expected_ci,
                rtol=1e-12,
                atol=0.0,
            )

    def test_step3_default_is_numerically_equivalent(self):
        step3_input = self.input.drop("prepayment_event")
        step3 = fit_cox_model(step3_input)
        np.testing.assert_allclose(
            self.pair.default.coefficients.select(
                "coefficient",
                "hazard_ratio",
                "standard_error",
                "ci_lower",
                "ci_upper",
                "p_value",
                "z_statistic",
            ).to_numpy(),
            step3.coefficients.select(
                "coefficient",
                "hazard_ratio",
                "standard_error",
                "ci_lower",
                "ci_upper",
                "p_value",
                "z_statistic",
            ).to_numpy(),
            rtol=1e-13,
            atol=1e-14,
        )

    def test_validation_rejects_duplicates_events_flags_time_and_predictors(self):
        cases = (
            (pl.concat([self.input, self.input.head(1)]), "duplicate loan_id"),
            (
                self.input.with_columns(
                    pl.when(pl.arange(0, pl.len()) == 0)
                    .then(pl.lit("UNKNOWN"))
                    .otherwise(pl.col("event_type"))
                    .alias("event_type")
                ),
                "event",
            ),
            (
                self.input.with_columns(
                    pl.when(pl.col("event_type") == "DEFAULT")
                    .then(pl.lit(1, dtype=pl.Int8))
                    .otherwise(pl.col("prepayment_event"))
                    .alias("prepayment_event")
                ),
                "event",
            ),
            (
                self.input.with_columns(
                    pl.col("entry_time_month").alias("exit_time_month")
                ),
                "entry/exit/duration",
            ),
            (self.input.with_columns(pl.lit(None).cast(pl.Int16).alias("fico")), "missing or non-finite"),
            (
                self.input.with_columns(
                    pl.when(pl.arange(0, pl.len()) == 0)
                    .then(float("inf"))
                    .otherwise(pl.col("original_ltv"))
                    .alias("original_ltv")
                ),
                "missing or non-finite",
            ),
        )
        for frame, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(CauseSpecificModelError, message):
                    validate_cause_specific_input(frame)
        with self.assertRaisesRegex(CauseSpecificModelError, "missing required"):
            validate_cause_specific_input(self.input.drop("original_dti"))

    def test_unknown_cause_and_invalid_confidence_level_rejected(self):
        with self.assertRaisesRegex(CauseSpecificModelError, "Unknown cause"):
            fit_cause_specific_model(self.input, "OTHER")
        for value in (0, 1, -0.1, 1.1, True, "0.95"):
            with self.subTest(value=value):
                with self.assertRaises(CauseSpecificModelError):
                    fit_cause_specific_model(self.input, "DEFAULT", value)

    def test_no_imputation_and_input_immutability(self):
        before = self.input.clone()
        fit_paired_cause_specific_models(self.input)
        self.assertTrue(self.input.equals(before))
        incomplete = self.input.with_columns(
            pl.when(pl.arange(0, pl.len()) == 0)
            .then(None)
            .otherwise(pl.col("original_dti"))
            .alias("original_dti")
        )
        with self.assertRaisesRegex(CauseSpecificModelError, "missing"):
            fit_cause_specific_model(incomplete, "DEFAULT")
        self.assertEqual(incomplete.height, self.input.height)

    def test_deterministic_fit_and_writer_round_trip(self):
        repeated = fit_paired_cause_specific_models(build_cause_specific_fixture())
        self.assertTrue(repeated.default.coefficients.equals(self.pair.default.coefficients))
        self.assertTrue(repeated.prepayment.coefficients.equals(self.pair.prepayment.coefficients))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outputs = write_cause_specific_artifacts(
                self.pair.default,
                root / "default_results.parquet",
                root / "default_diagnostics.parquet",
            )
            self.assertTrue(pl.read_parquet(outputs[0]).equals(self.pair.default.coefficients))
            self.assertTrue(pl.read_parquet(outputs[1]).equals(self.pair.default.diagnostics))

    def test_checked_in_mock_artifacts_match_two_regenerations(self):
        expected = (
            DEFAULT_RESULTS,
            DEFAULT_DIAGNOSTICS,
            PREPAYMENT_RESULTS,
            PREPAYMENT_DIAGNOSTICS,
        )
        for path in expected:
            self.assertTrue(path.is_file(), path)
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            first_paths = tuple(Path(first) / path.name for path in expected)
            second_paths = tuple(Path(second) / path.name for path in expected)
            build_mock_cause_specific_results(*first_paths)
            build_mock_cause_specific_results(*second_paths)
            for saved, one, two in zip(expected, first_paths, second_paths, strict=True):
                self.assertEqual(saved.read_bytes(), one.read_bytes())
                self.assertEqual(one.read_bytes(), two.read_bytes())


if __name__ == "__main__":
    unittest.main()
