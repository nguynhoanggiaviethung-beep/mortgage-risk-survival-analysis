import tempfile
import unittest
from pathlib import Path

import polars as pl

from src.survival.kaplan_meier import (
    KM_RESULT_COLUMNS,
    KM_RESULT_DTYPES,
    KaplanMeierInputError,
    fit_kaplan_meier,
    validate_km_input,
    validate_km_results,
    write_km_results,
)
from src.survival.model_input import build_loan_level_input, to_survival_input


ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "mock_loan_month.parquet"
MOCK_RESULT = ROOT / "results" / "mock" / "km_results.parquet"


class TestKaplanMeier(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        monthly = pl.read_parquet(FIXTURE)
        cls.input = to_survival_input(
            build_loan_level_input(monthly)
        ).collect()
        cls.result = fit_kaplan_meier(cls.input)

    def test_exact_mock_curve_and_risk_sets(self):
        self.assertEqual(self.result["analysis_time"].to_list(), [0, 1, 2, 3])
        self.assertEqual(self.result["n_at_risk"].to_list(), [4, 5, 4, 1])
        self.assertEqual(self.result["n_events"].to_list(), [0, 0, 1, 0])
        self.assertEqual(self.result["n_censored"].to_list(), [0, 1, 2, 1])
        for actual, expected in zip(
            self.result["survival"].to_list(),
            [1.0, 1.0, 0.75, 0.75],
            strict=True,
        ):
            self.assertAlmostEqual(actual, expected, places=12)

    def test_lifelines_log_log_confidence_interval_values(self):
        month_two = self.result.filter(pl.col("analysis_time") == 2).row(
            0, named=True
        )
        self.assertAlmostEqual(month_two["ci_lower"], 0.12794692, places=7)
        self.assertAlmostEqual(month_two["ci_upper"], 0.96054864, places=7)

    def test_probability_bounds_and_monotonicity(self):
        survival = self.result["survival"]
        self.assertTrue(((survival >= 0) & (survival <= 1)).all())
        self.assertTrue((survival.diff().drop_nulls() <= 0).all())
        self.assertTrue(
            self.result.select(
                (
                    pl.col("event_probability")
                    - (1.0 - pl.col("survival"))
                ).abs().max()
            ).item()
            <= 1e-12
        )

    def test_default_is_event_and_prepayment_is_censored(self):
        self.assertEqual(self.input["km_default_event"].sum(), 1)
        prepayment = self.input.filter(pl.col("event_type") == "PREPAYMENT")
        self.assertEqual(prepayment["km_default_event"].item(), 0)
        self.assertEqual(self.result["n_events"].sum(), 1)
        self.assertEqual(self.result["n_censored"].sum(), 4)

    def test_output_schema_and_overall_labels(self):
        self.assertEqual(self.result.columns, KM_RESULT_COLUMNS)
        self.assertEqual(self.result.schema, pl.Schema(KM_RESULT_DTYPES))
        self.assertEqual(self.result["group_name"].unique().to_list(), ["portfolio"])
        self.assertEqual(self.result["group_value"].unique().to_list(), ["all"])
        self.assertEqual(self.result["model_type"].unique().to_list(), ["kaplan_meier"])
        self.assertEqual(self.result["endpoint"].unique().to_list(), ["default"])

    def test_grouping_by_existing_non_null_column(self):
        grouped_input = self.input.with_columns(
            pl.when(pl.col("loan_id") == "L_PREPAY")
            .then(pl.lit("delayed"))
            .otherwise(pl.lit("standard"))
            .alias("segment")
        )
        grouped = fit_kaplan_meier(grouped_input, group_col="segment")
        self.assertEqual(set(grouped["group_value"]), {"delayed", "standard"})
        self.assertEqual(grouped["group_name"].unique().to_list(), ["segment"])
        delayed = grouped.filter(pl.col("group_value") == "delayed")
        self.assertEqual(delayed["analysis_time"].min(), 1)
        self.assertEqual(delayed["analysis_time"].max(), 3)

    def test_grouping_by_vintage_year(self):
        grouped = fit_kaplan_meier(self.input, group_col="vintage_year")
        self.assertEqual(grouped["group_name"].unique().to_list(), ["vintage_year"])
        self.assertEqual(grouped["group_value"].unique().to_list(), ["2020"])

    def test_missing_or_null_group_rejected(self):
        with self.assertRaisesRegex(KaplanMeierInputError, "does not exist"):
            fit_kaplan_meier(self.input, group_col="missing_group")
        with self.assertRaisesRegex(KaplanMeierInputError, "contains null"):
            fit_kaplan_meier(
                self.input.with_columns(
                    pl.when(pl.col("loan_id") == "L_DEFAULT")
                    .then(None)
                    .otherwise(pl.col("vintage_year"))
                    .cast(pl.Int16)
                    .alias("vintage_year")
                ),
                group_col="vintage_year",
            )

    def test_invalid_confidence_level_rejected(self):
        for value in (0, 1, -0.1, 1.1, True, "0.95"):
            with self.subTest(value=value):
                with self.assertRaises(KaplanMeierInputError):
                    fit_kaplan_meier(self.input, confidence_level=value)

    def test_duplicate_and_invalid_time_rejected(self):
        duplicate = pl.concat([self.input, self.input.head(1)])
        with self.assertRaisesRegex(KaplanMeierInputError, "duplicate loan_id"):
            validate_km_input(duplicate)

        invalid_time = self.input.with_columns(
            pl.when(pl.col("loan_id") == "L_DEFAULT")
            .then(pl.col("entry_time_month"))
            .otherwise(pl.col("exit_time_month"))
            .alias("exit_time_month")
        )
        with self.assertRaisesRegex(KaplanMeierInputError, "entry/exit/duration"):
            validate_km_input(invalid_time)

    def test_missing_cox_predictor_does_not_affect_km_sample(self):
        self.assertEqual(self.input.height, 5)
        self.assertIn("L_MISSING_DTI", self.input["loan_id"].to_list())
        self.assertEqual(self.result["n_at_risk"].max(), 5)

    def test_input_is_not_mutated(self):
        before = self.input.clone()
        fit_kaplan_meier(self.input)
        self.assertTrue(self.input.equals(before))

    def test_checked_in_mock_result_matches_regeneration(self):
        saved = validate_km_results(pl.read_parquet(MOCK_RESULT))
        self.assertTrue(saved.equals(self.result))

    def test_writer_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "nested" / "km.parquet"
            self.assertEqual(write_km_results(self.result, output), output)
            self.assertTrue(pl.read_parquet(output).equals(self.result))


if __name__ == "__main__":
    unittest.main()
