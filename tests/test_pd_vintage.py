import tempfile
import unittest
from datetime import date
from pathlib import Path

import numpy as np
import polars as pl

from scripts.build_mock_pd_vintage_results import (
    build_mock_pd_vintage_results,
    build_pd_vintage_fixture,
)
from src.competing_risks.aalen_johansen import AJ_RESULT_DTYPES
from src.competing_risks.pd_vintage import (
    ALLOWED_HORIZONS,
    INSUFFICIENT_FOLLOW_UP,
    OVERALL_PD_COLUMNS,
    OVERALL_PD_DTYPES,
    PERFORMANCE_CUTOFF_DATE,
    PRIMARY_HORIZONS,
    SUPPLEMENTARY_HORIZONS,
    VINTAGE_CIF_COLUMNS,
    VINTAGE_CIF_DTYPES,
    VINTAGE_HORIZON_COLUMNS,
    VINTAGE_HORIZON_DTYPES,
    PDVintageError,
    add_calendar_months,
    build_vintage_horizons,
    evaluate_cif_step,
    fit_pd_vintage_analysis,
    validate_overall_pd_results,
    validate_pd_vintage_input,
    validate_vintage_cif_results,
    validate_vintage_horizon_results,
    vintage_horizon_is_eligible,
    write_pd_vintage_results,
)
from src.survival.kaplan_meier import fit_kaplan_meier


ROOT = Path(__file__).resolve().parent.parent
MOCK_OVERALL = ROOT / "results/mock/overall_pd_horizons.parquet"
MOCK_VINTAGE_CIF = ROOT / "results/mock/vintage_cif_results.parquet"
MOCK_VINTAGE_HORIZONS = ROOT / "results/mock/vintage_horizon_results.parquet"


def _step_curve_fixture() -> pl.DataFrame:
    rows = []
    for analysis_time, default, prepayment, risk in (
        (6, 0.05, 0.02, 10),
        (12, 0.10, 0.04, 9),
        (30, 0.20, 0.08, 6),
        (36, 0.25, 0.10, 5),
    ):
        for endpoint, value in (
            ("DEFAULT", default),
            ("PREPAYMENT", prepayment),
        ):
            rows.append({
                "model_type": "AALEN_JOHANSEN",
                "endpoint": endpoint,
                "group_name": "portfolio",
                "group_value": "all",
                "analysis_time": analysis_time,
                "cumulative_incidence": value,
                "ci_lower": max(0.0, value - 0.01),
                "ci_upper": min(1.0, value + 0.01),
                "n_at_risk": risk,
            })
    return pl.DataFrame(rows, schema=AJ_RESULT_DTYPES)


class TestPDVintageAnalytics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.input = build_pd_vintage_fixture()
        cls.result = fit_pd_vintage_analysis(cls.input)

    def test_fixture_has_all_vintages_events_delays_ties_and_partial_vintage(self):
        self.assertTrue(self.input.equals(build_pd_vintage_fixture()))
        self.assertEqual(
            self.input["vintage_year"].unique().sort().to_list(),
            list(range(2016, 2027)),
        )
        self.assertEqual(self.input.height, 66)
        self.assertEqual(
            set(self.input["event_type"]), {"DEFAULT", "PREPAYMENT", "CENSOR"}
        )
        self.assertTrue((self.input["entry_time_month"] > 0).any())
        self.assertLess(self.input["exit_time_month"].n_unique(), self.input.height)
        partial = self.input.filter(pl.col("vintage_year") == 2026)
        self.assertEqual(partial["exit_time_month"].max(), 2)

    def test_exact_schemas_and_locked_horizon_roles(self):
        self.assertEqual(self.result.overall_pd_horizons.columns, OVERALL_PD_COLUMNS)
        self.assertEqual(
            self.result.overall_pd_horizons.schema, pl.Schema(OVERALL_PD_DTYPES)
        )
        self.assertEqual(self.result.vintage_cif.columns, VINTAGE_CIF_COLUMNS)
        self.assertEqual(
            self.result.vintage_cif.schema, pl.Schema(VINTAGE_CIF_DTYPES)
        )
        self.assertEqual(
            self.result.vintage_horizons.columns, VINTAGE_HORIZON_COLUMNS
        )
        self.assertEqual(
            self.result.vintage_horizons.schema,
            pl.Schema(VINTAGE_HORIZON_DTYPES),
        )
        self.assertEqual(PRIMARY_HORIZONS, (12, 24, 36))
        self.assertEqual(SUPPLEMENTARY_HORIZONS, (60,))
        self.assertEqual(ALLOWED_HORIZONS, (12, 24, 36, 60))
        roles = dict(
            self.result.overall_pd_horizons.select(
                "horizon_months", "horizon_role"
            ).iter_rows()
        )
        self.assertEqual(
            roles, {12: "PRIMARY", 24: "PRIMARY", 36: "PRIMARY", 60: "SUPPLEMENTARY"}
        )

    def test_pd_is_default_cif_and_prepayment_is_not_default_pd(self):
        overall = self.result.overall_pd_horizons
        np.testing.assert_array_equal(overall["pd"], overall["default_cif"])
        eligible_vintage = self.result.vintage_horizons.filter(
            pl.col("follow_up_status") == "ELIGIBLE"
        )
        np.testing.assert_array_equal(
            eligible_vintage["pd"], eligible_vintage["default_cif"]
        )
        with_competing = eligible_vintage.filter(pl.col("prepayment_cif") > 0)
        self.assertGreater(with_competing.height, 0)
        self.assertTrue(
            (
                with_competing["pd"]
                != with_competing["default_cif"]
                + with_competing["prepayment_cif"]
            ).all()
        )

    def test_competing_risk_pd_is_not_naive_one_minus_km(self):
        km_input = self.input.select(
            "loan_id",
            "vintage_year",
            "entry_time_month",
            "exit_time_month",
            "duration_months",
            (pl.col("event_type") == "DEFAULT")
            .cast(pl.Int8).alias("km_default_event"),
            "event_type",
        )
        km = fit_kaplan_meier(km_input)
        pd_36 = self.result.overall_pd_horizons.filter(
            pl.col("horizon_months") == 36
        )["pd"].item()
        naive_36 = km.filter(pl.col("analysis_time") <= 36).sort(
            "analysis_time"
        )["event_probability"][-1]
        self.assertNotAlmostEqual(pd_36, naive_36, places=12)

    def test_right_continuous_step_exact_no_interpolation_and_no_extrapolation(self):
        curve = _step_curve_fixture()
        exact = evaluate_cif_step(
            curve,
            endpoint="DEFAULT",
            horizon_months=12,
            group_name="portfolio",
            group_value="all",
        )
        between = evaluate_cif_step(
            curve,
            endpoint="DEFAULT",
            horizon_months=24,
            group_name="portfolio",
            group_value="all",
        )
        unsupported = evaluate_cif_step(
            curve,
            endpoint="DEFAULT",
            horizon_months=60,
            group_name="portfolio",
            group_value="all",
        )
        self.assertEqual(exact, 0.10)
        self.assertEqual(between, 0.10)
        self.assertIsNone(unsupported)

    def test_calendar_month_boundaries_and_end_of_month(self):
        self.assertEqual(add_calendar_months(date(2024, 1, 31), 1), date(2024, 2, 29))
        self.assertEqual(add_calendar_months(date(2025, 1, 31), 1), date(2025, 2, 28))
        self.assertTrue(vintage_horizon_is_eligible(date(2025, 3, 31), 12))
        self.assertFalse(vintage_horizon_is_eligible(date(2025, 4, 30), 12))
        self.assertEqual(PERFORMANCE_CUTOFF_DATE, date(2026, 3, 31))

    def test_latest_origin_controls_eligibility_without_redefining_vintage(self):
        changed = self.input.with_columns(
            pl.when(
                (pl.col("vintage_year") == 2024)
                & (pl.col("loan_id") == "V2024_6")
            )
            .then(pl.lit(date(2025, 4, 30)))
            .otherwise(pl.col("operational_origination_date"))
            .alias("operational_origination_date")
        )
        horizons = build_vintage_horizons(changed, self.result.vintage_cif)
        row = horizons.filter(
            (pl.col("vintage_year") == 2024)
            & (pl.col("horizon_months") == 12)
        ).row(0, named=True)
        self.assertEqual(row["vintage_year"], 2024)
        self.assertEqual(row["latest_origination_date"], date(2025, 4, 30))
        self.assertFalse(row["follow_up_eligible"])
        self.assertEqual(row["follow_up_status"], INSUFFICIENT_FOLLOW_UP)
        self.assertIsNone(row["pd"])

    def test_ineligible_rows_remain_na_and_partial_curve_remains_observed(self):
        matrix = self.result.vintage_horizons
        self.assertEqual(matrix.height, 11 * 4)
        ineligible = matrix.filter(~pl.col("follow_up_eligible"))
        self.assertTrue(ineligible["default_cif"].is_null().all())
        self.assertTrue(ineligible["prepayment_cif"].is_null().all())
        self.assertTrue(ineligible["pd"].is_null().all())
        young_rows = matrix.filter(pl.col("vintage_year") == 2026)
        self.assertEqual(young_rows.height, 4)
        self.assertTrue(young_rows["pd"].is_null().all())
        young_curve = self.result.vintage_cif.filter(
            pl.col("vintage_year") == 2026
        )
        self.assertGreater(young_curve.height, 0)
        self.assertEqual(young_curve["analysis_time"].max(), 2)

    def test_no_arbitrary_minimum_risk_threshold(self):
        eligible = self.result.vintage_horizons.filter(
            pl.col("follow_up_status") == "ELIGIBLE"
        )
        self.assertTrue((eligible["loan_count"] < 30).all())
        self.assertTrue(eligible["pd"].is_not_null().all())

    def test_repeated_execution_is_deterministic_and_input_not_mutated(self):
        before = self.input.clone()
        repeated = fit_pd_vintage_analysis(self.input)
        self.assertTrue(self.input.equals(before))
        self.assertTrue(
            repeated.overall_pd_horizons.equals(self.result.overall_pd_horizons)
        )
        self.assertTrue(repeated.vintage_cif.equals(self.result.vintage_cif))
        self.assertTrue(
            repeated.vintage_horizons.equals(self.result.vintage_horizons)
        )

    def test_validation_rejects_invalid_inputs_horizons_and_outputs(self):
        cases = (
            (pl.concat([self.input, self.input.head(1)]), "duplicate"),
            (
                self.input.with_columns(
                    pl.lit(None).cast(pl.Date).alias("operational_origination_date")
                ),
                "origination",
            ),
            (
                self.input.with_columns(
                    pl.lit(2015, dtype=pl.Int16).alias("vintage_year")
                ),
                "outside 2016-2026",
            ),
            (
                self.input.with_columns(
                    pl.col("entry_time_month").alias("exit_time_month")
                ),
                "canonical AJ input",
            ),
        )
        for frame, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(PDVintageError, message):
                    validate_pd_vintage_input(frame)
        with self.assertRaisesRegex(PDVintageError, "missing required"):
            validate_pd_vintage_input(self.input.drop("operational_origination_date"))
        for invalid in ((48,), (12, 12), (), (True,)):
            with self.subTest(horizons=invalid):
                with self.assertRaises(PDVintageError):
                    fit_pd_vintage_analysis(self.input, invalid)
        broken = self.result.vintage_horizons.with_columns(
            pl.when(pl.col("follow_up_status") == "ELIGIBLE")
            .then(pl.col("pd") + 0.01)
            .otherwise(pl.col("pd"))
            .alias("pd")
        )
        with self.assertRaisesRegex(PDVintageError, "PD must equal"):
            validate_vintage_horizon_results(broken)

    def test_validators_writer_and_mock_artifacts_are_byte_deterministic(self):
        validate_overall_pd_results(self.result.overall_pd_horizons)
        validate_vintage_cif_results(self.result.vintage_cif)
        validate_vintage_horizon_results(self.result.vintage_horizons)
        expected = (MOCK_OVERALL, MOCK_VINTAGE_CIF, MOCK_VINTAGE_HORIZONS)
        for path in expected:
            self.assertTrue(path.is_file(), path)
        validate_overall_pd_results(pl.read_parquet(MOCK_OVERALL))
        validate_vintage_cif_results(pl.read_parquet(MOCK_VINTAGE_CIF))
        validate_vintage_horizon_results(pl.read_parquet(MOCK_VINTAGE_HORIZONS))
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            first_paths = tuple(Path(first) / path.name for path in expected)
            second_paths = tuple(Path(second) / path.name for path in expected)
            build_mock_pd_vintage_results(*first_paths)
            build_mock_pd_vintage_results(*second_paths)
            for saved, one, two in zip(expected, first_paths, second_paths, strict=True):
                self.assertEqual(saved.read_bytes(), one.read_bytes())
                self.assertEqual(one.read_bytes(), two.read_bytes())
        with tempfile.TemporaryDirectory() as directory:
            paths = write_pd_vintage_results(
                self.result,
                Path(directory) / "nested/overall.parquet",
                Path(directory) / "nested/curves.parquet",
                Path(directory) / "nested/horizons.parquet",
            )
            self.assertTrue(pl.read_parquet(paths[0]).equals(self.result.overall_pd_horizons))
            self.assertTrue(pl.read_parquet(paths[1]).equals(self.result.vintage_cif))
            self.assertTrue(pl.read_parquet(paths[2]).equals(self.result.vintage_horizons))


if __name__ == "__main__":
    unittest.main()
