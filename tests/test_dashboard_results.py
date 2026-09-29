import unittest
from unittest.mock import patch

import polars as pl

from src.results.dashboard import (
    DIAGNOSTIC_SCHEMA,
    PD_SCHEMA,
    PORTFOLIO_SCHEMA,
    RISK_DRIVER_SCHEMA,
    SURVIVAL_SCHEMA,
    VINTAGE_SCHEMA,
    model_diagnostics,
    pd_results,
    portfolio_summary,
    resolve_dashboard_release,
    risk_driver_results,
    survival_results,
    vintage_results,
)


class TestDashboardResults(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.release = resolve_dashboard_release(".")

    def test_current_release_is_published(self):
        self.assertEqual(self.release.manifest.run_id, "20260929T085632Z_89d04db")
        self.assertEqual(self.release.manifest.run_status.value, "PUBLISHED")
        self.assertEqual(self.release.manifest.environment.value, "PRODUCTION")

    def test_portfolio_summary_content_and_schema(self):
        result = portfolio_summary(self.release)
        self.assertEqual(result.schema, PORTFOLIO_SCHEMA)
        self.assertEqual(result.row(0, named=True)["total_loans"], 504405)
        self.assertEqual(result.row(0, named=True)["default_count"], 204)
        self.assertEqual(result.row(0, named=True)["prepayment_count"], 212269)
        self.assertEqual(result.row(0, named=True)["censor_count"], 291932)
        self.assertEqual(result.row(0, named=True)["delayed_entry_count"], 34347)

    def test_pd_results_schema_content_and_horizons(self):
        result = pd_results(self.release)
        self.assertEqual(result.schema, PD_SCHEMA)
        self.assertEqual(result["horizon_months"].to_list(), [12, 24, 36, 60])
        self.assertTrue((result["pd"] == result["default_cif"]).all())
        self.assertTrue((result["follow_up_eligible"]).all())

    def test_survival_results_contains_only_curves(self):
        result = survival_results(self.release)
        self.assertEqual(result.schema, SURVIVAL_SCHEMA)
        self.assertEqual(set(result["model"].unique()), {"KAPLAN_MEIER", "AALEN_JOHANSEN"})
        self.assertEqual(
            set(result["curve_type"].unique()),
            {"SURVIVAL", "DEFAULT_CIF", "PREPAYMENT_CIF"},
        )
        self.assertEqual(result.filter(pl.col("curve_type") == "SURVIVAL")["cumulative_incidence"].null_count(), result.filter(pl.col("curve_type") == "SURVIVAL").height)

    def test_risk_driver_results_uses_three_primary_models(self):
        result = risk_driver_results(self.release)
        self.assertEqual(result.schema, RISK_DRIVER_SCHEMA)
        self.assertEqual(set(result["model"].unique()), {"BASELINE_COX", "TV_COX", "FINE_GRAY_DEFAULT"})
        self.assertEqual(result.height, 18)
        self.assertEqual(result.filter(pl.col("model") == "FINE_GRAY_DEFAULT")["hazard_ratio"].null_count(), 5)

    def test_vintage_ineligible_horizons_are_null_and_flagged(self):
        result = vintage_results(self.release)
        self.assertEqual(result.schema, VINTAGE_SCHEMA)
        ineligible = result.filter(~pl.col("follow_up_eligible"))
        self.assertGreater(ineligible.height, 0)
        self.assertTrue((ineligible["follow_up_status"] == "INSUFFICIENT_FOLLOW_UP").all())
        for name in ("default_cif", "prepayment_cif", "pd"):
            self.assertEqual(ineligible[name].null_count(), ineligible.height)

    def test_model_diagnostics_preserves_flagged_findings(self):
        result = model_diagnostics(self.release)
        self.assertEqual(result.schema, DIAGNOSTIC_SCHEMA)
        self.assertTrue(
            (
                result.filter(
                    (pl.col("diagnostic_type") == "ph")
                    & (pl.col("predictor") == "original_ltv")
                )["status"]
                == "FLAGGED"
            ).all()
        )
        self.assertTrue(
            (
                result.filter(pl.col("diagnostic_type") == "ph_global")["status"]
                == "FLAGGED"
            ).all()
        )

    def test_transformations_are_deterministic(self):
        builders = (portfolio_summary, pd_results, survival_results, risk_driver_results, vintage_results, model_diagnostics)
        for builder in builders:
            with self.subTest(builder=builder.__name__):
                self.assertTrue(builder(self.release).equals(builder(self.release)))

    def test_no_nan_or_infinity_leaks(self):
        builders = (portfolio_summary, pd_results, survival_results, risk_driver_results, vintage_results, model_diagnostics)
        for builder in builders:
            result = builder(self.release)
            for name, dtype in result.schema.items():
                if dtype == pl.Float64:
                    self.assertEqual(result.filter(pl.col(name).is_nan() | pl.col(name).is_infinite()).height, 0)

    def test_typed_nulls_are_preserved(self):
        survival = survival_results(self.release)
        risk = risk_driver_results(self.release)
        self.assertEqual(survival.schema["cumulative_incidence"], pl.Float64)
        self.assertEqual(risk.schema["hazard_ratio"], pl.Float64)
        self.assertGreater(survival["cumulative_incidence"].null_count(), 0)
        self.assertGreater(risk["hazard_ratio"].null_count(), 0)

    def test_provenance_and_model_versions_are_retained(self):
        for result in (pd_results(self.release), survival_results(self.release), risk_driver_results(self.release), vintage_results(self.release), model_diagnostics(self.release)):
            self.assertEqual(result["data_version"].unique().to_list(), [self.release.manifest.data_version])
            self.assertEqual(result["run_id"].unique().to_list(), [self.release.manifest.run_id])
            self.assertGreater(result["model_version"].n_unique(), 0)

    def test_result_layer_does_not_fit_models(self):
        with patch("src.survival.cox_model.fit_cox_model", side_effect=AssertionError("fit called")):
            for builder in (pd_results, survival_results, risk_driver_results, vintage_results, model_diagnostics):
                builder(self.release)


if __name__ == "__main__":
    unittest.main()