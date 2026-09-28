import tempfile
import unittest
from pathlib import Path

import numpy as np
import polars as pl

from scripts.build_mock_aalen_johansen_results import (
    build_aalen_johansen_fixture,
    build_mock_aalen_johansen_results,
)
from src.competing_risks.aalen_johansen import (
    AJ_RESULT_COLUMNS,
    AJ_RESULT_DTYPES,
    AalenJohansenError,
    fit_aalen_johansen,
    validate_aalen_johansen_input,
    validate_aalen_johansen_results,
    write_aalen_johansen_results,
)
from src.survival.kaplan_meier import fit_kaplan_meier


ROOT = Path(__file__).resolve().parent.parent
MOCK_RESULT = ROOT / "results/mock/aalen_johansen_results.parquet"


def _km_input(data: pl.DataFrame) -> pl.DataFrame:
    return data.select(
        "loan_id",
        "vintage_year",
        "entry_time_month",
        "exit_time_month",
        "duration_months",
        (pl.col("event_type") == "DEFAULT").cast(pl.Int8).alias("km_default_event"),
        "event_type",
    )


class TestAalenJohansen(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.input = build_aalen_johansen_fixture()
        cls.result = fit_aalen_johansen(cls.input)

    def test_result_schema_identity_and_overall_group_convention(self):
        self.assertEqual(self.result.columns, AJ_RESULT_COLUMNS)
        self.assertEqual(self.result.schema, pl.Schema(AJ_RESULT_DTYPES))
        self.assertEqual(self.result["model_type"].unique().to_list(), ["AALEN_JOHANSEN"])
        self.assertEqual(set(self.result["endpoint"]), {"DEFAULT", "PREPAYMENT"})
        self.assertEqual(self.result["group_name"].unique().to_list(), ["portfolio"])
        self.assertEqual(self.result["group_value"].unique().to_list(), ["all"])

    def test_manual_reference_values_delayed_entry_ties_and_censoring(self):
        pivoted = self.result.pivot(
            on="endpoint",
            index=["analysis_time", "n_at_risk"],
            values="cumulative_incidence",
        ).sort("analysis_time")
        self.assertEqual(pivoted["analysis_time"].to_list(), [2, 3, 4])
        # At t=2, AJ6 has entry=2 and is not in the (start, stop] risk set.
        self.assertEqual(pivoted["n_at_risk"].to_list(), [5, 4, 2])
        np.testing.assert_allclose(pivoted["DEFAULT"], [0.20, 0.35, 0.35], atol=1e-15)
        np.testing.assert_allclose(pivoted["PREPAYMENT"], [0.20, 0.20, 0.425], atol=1e-15)
        # The censor at t=3 does not increment either cause; only DEFAULT does.
        self.assertAlmostEqual(pivoted["PREPAYMENT"][1], pivoted["PREPAYMENT"][0], places=15)
        # The censor at t=4 does not increment DEFAULT; only PREPAYMENT does.
        self.assertAlmostEqual(pivoted["DEFAULT"][2], pivoted["DEFAULT"][1], places=15)

    def test_mathematical_bounds_and_monotonicity(self):
        validate_aalen_johansen_results(self.result)
        for endpoint in ("DEFAULT", "PREPAYMENT"):
            values = self.result.filter(pl.col("endpoint") == endpoint).sort("analysis_time")["cumulative_incidence"].to_numpy()
            self.assertTrue(np.all((values >= 0) & (values <= 1)))
            self.assertTrue(np.all(np.diff(values) >= -1e-12))
        paired = self.result.pivot(
            on="endpoint", index="analysis_time", values="cumulative_incidence"
        )
        self.assertTrue(((paired["DEFAULT"] + paired["PREPAYMENT"]) <= 1 + 1e-12).all())

    def test_no_competing_cause_matches_single_event_reference(self):
        no_competing = self.input.filter(pl.col("event_type") != "PREPAYMENT")
        aj = fit_aalen_johansen(no_competing)
        km = fit_kaplan_meier(_km_input(no_competing))
        default_aj = aj.filter(pl.col("endpoint") == "DEFAULT").select(
            "analysis_time", "cumulative_incidence"
        )
        aligned = default_aj.join(
            km.select("analysis_time", "event_probability"),
            on="analysis_time",
            how="inner",
        )
        self.assertEqual(aligned.height, default_aj.height)
        np.testing.assert_allclose(
            aligned["cumulative_incidence"],
            aligned["event_probability"],
            rtol=1e-12,
            atol=1e-12,
        )

    def test_competing_fixture_demonstrates_naive_one_minus_km_is_not_cif(self):
        km = fit_kaplan_meier(_km_input(self.input))
        default_at_four = self.result.filter(
            (pl.col("endpoint") == "DEFAULT") & (pl.col("analysis_time") == 4)
        )["cumulative_incidence"].item()
        naive_at_four = km.filter(pl.col("analysis_time") == 4)["event_probability"].item()
        self.assertAlmostEqual(default_at_four, 0.35, places=15)
        self.assertAlmostEqual(naive_at_four, 0.40, places=15)
        self.assertNotAlmostEqual(default_at_four, naive_at_four, places=12)

    def test_invalid_input_unknown_cause_time_duplicate_and_group_rejected(self):
        cases = (
            (pl.concat([self.input, self.input.head(1)]), "duplicate"),
            (
                self.input.with_columns(
                    pl.when(pl.arange(0, pl.len()) == 0)
                    .then(pl.lit(9, dtype=pl.Int8))
                    .otherwise(pl.col("cr_event_code"))
                    .alias("cr_event_code")
                ),
                "event",
            ),
            (
                self.input.with_columns(
                    pl.when(pl.arange(0, pl.len()) == 0)
                    .then(pl.lit("CENSOR"))
                    .otherwise(pl.col("event_type"))
                    .alias("event_type")
                ),
                "event",
            ),
            (
                self.input.with_columns(
                    pl.col("entry_time_month").alias("exit_time_month")
                ),
                "entry/exit/duration",
            ),
        )
        for frame, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(AalenJohansenError, message):
                    validate_aalen_johansen_input(frame)
        with self.assertRaisesRegex(AalenJohansenError, "Grouping column"):
            validate_aalen_johansen_input(self.input, group_col="missing")

    def test_input_immutability_grouping_and_confidence_validation(self):
        before = self.input.clone()
        grouped = fit_aalen_johansen(self.input, group_col="vintage_year")
        self.assertTrue(self.input.equals(before))
        self.assertEqual(grouped["group_name"].unique().to_list(), ["vintage_year"])
        self.assertEqual(set(grouped["group_value"]), {"2020", "2021"})
        for value in (0, 1, -0.1, 1.1, True, "0.95"):
            with self.subTest(value=value):
                with self.assertRaises(AalenJohansenError):
                    fit_aalen_johansen(self.input, confidence_level=value)

    def test_deterministic_mock_artifact_and_writer(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            first_path = Path(first) / "aj.parquet"
            second_path = Path(second) / "aj.parquet"
            build_mock_aalen_johansen_results(first_path)
            build_mock_aalen_johansen_results(second_path)
            self.assertEqual(MOCK_RESULT.read_bytes(), first_path.read_bytes())
            self.assertEqual(first_path.read_bytes(), second_path.read_bytes())
            self.assertTrue(
                pl.read_parquet(first_path).equals(
                    validate_aalen_johansen_results(self.result)
                )
            )
            third = Path(first) / "nested" / "written.parquet"
            self.assertEqual(write_aalen_johansen_results(self.result, third), third)
            self.assertTrue(pl.read_parquet(third).equals(self.result))


if __name__ == "__main__":
    unittest.main()
