import json
import math
import unittest
from pathlib import Path
from unittest.mock import patch

import polars as pl

from src.query import FrontendService, QueryStatus
from src.query.queries import (
    get_loan_profile,
    get_loan_timeline,
    get_model_diagnostics,
    get_pd_results,
    get_portfolio_summary,
    get_risk_driver_results,
    get_survival_results,
    get_vintage_results,
)
from src.results.dashboard import resolve_dashboard_release


REAL_LOAN_ID = "F16Q10000006"


class TestBackendE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.release = resolve_dashboard_release(".")
        cls.service = FrontendService(".")

    def _source(self, logical_name: str) -> pl.DataFrame:
        record = next(
            item
            for item in self.release.manifest.artifacts
            if item.logical_name == logical_name
        )
        path = self.release.run_root / record.relative_path
        return pl.read_csv(path) if path.suffix == ".csv" else pl.read_parquet(path)

    def test_published_release_and_validation_are_current(self):
        self.assertEqual(self.release.manifest.run_id, "20260929T085632Z_89d04db")
        self.assertEqual(self.release.manifest.run_status.value, "PUBLISHED")
        self.assertEqual(self.release.manifest.environment.value, "PRODUCTION")
        report = json.loads(
            (self.release.run_root / "validation/production_validation_report.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(report["overall_status"], "PASS")
        self.assertEqual(report["run_id"], self.release.manifest.run_id)

    def test_portfolio_reconciles_to_provenance(self):
        provenance = json.loads(
            (self.release.run_root / "provenance/input_provenance.json").read_text(
                encoding="utf-8"
            )
        )
        source = next(item for item in provenance["inputs"] if item["role"] == "analysis_loans")
        result = get_portfolio_summary(".")
        row = result.data.row(0, named=True)
        self.assertEqual(row["total_loans"], source["row_count"])
        self.assertEqual(row["default_count"], source["reconciliation"]["DEFAULT"])
        self.assertEqual(row["prepayment_count"], source["reconciliation"]["PREPAYMENT"])
        self.assertEqual(row["censor_count"], source["reconciliation"]["CENSOR"])
        self.assertEqual(row["delayed_entry_count"], source["reconciliation"]["delayed_entry"])
        self.assertEqual(row["data_version"], self.release.manifest.data_version)
        self.assertEqual(row["performance_cutoff"], self.release.manifest.performance_cutoff)
        self.assertEqual(row["run_id"], self.release.manifest.run_id)

    def test_pd_reconciles_without_recalculation(self):
        source = self._source("overall_pd_horizons").sort("horizon_months")
        result = get_pd_results(".")
        self.assertEqual(result.status, QueryStatus.OK)
        columns = [
            "horizon_months", "horizon_role", "default_cif", "pd", "loan_count",
            "n_at_risk", "default_count", "prepayment_count", "follow_up_eligible",
            "follow_up_status",
        ]
        self.assertTrue(
            result.data.select(columns).equals(source.select(columns))
        )
        self.assertTrue((result.data["pd"] == result.data["default_cif"]).all())

    def test_survival_curves_reconcile_to_published_sources(self):
        result = get_survival_results(".").data
        km = self._source("km_results").with_columns(
            pl.lit("KAPLAN_MEIER").alias("model"),
            pl.col("endpoint").str.to_uppercase(),
            pl.lit("SURVIVAL").alias("curve_type"),
            pl.col("survival").alias("survival_probability"),
            pl.lit(None, dtype=pl.Float64).alias("cumulative_incidence"),
        )
        aj = self._source("aalen_johansen_results").with_columns(
            pl.lit("AALEN_JOHANSEN").alias("model"),
            pl.col("endpoint").str.to_uppercase(),
            pl.col("endpoint").str.to_uppercase().map_elements(
                lambda value: f"{value}_CIF", return_dtype=pl.String
            ).alias("curve_type"),
            pl.lit(None, dtype=pl.Float64).alias("survival_probability"),
            pl.col("cumulative_incidence"),
            pl.lit(None, dtype=pl.UInt32).alias("n_events"),
            pl.lit(None, dtype=pl.UInt32).alias("n_censored"),
        )
        for source in (km, aj):
            columns = [
                "model", "endpoint", "curve_type", "group_name", "group_value",
                "analysis_time", "survival_probability", "cumulative_incidence",
                "ci_lower", "ci_upper", "n_at_risk", "n_events", "n_censored",
            ]
            expected = source.select(columns).sort(["model", "endpoint", "analysis_time"])
            actual = result.filter(pl.col("model") == source["model"][0]).select(columns).sort(
                ["model", "endpoint", "analysis_time"]
            )
            self.assertTrue(actual.equals(expected))

    def test_risk_drivers_reconcile_to_published_sources(self):
        result = get_risk_driver_results(".").data
        for logical_name, model in (
            ("cox_results", "BASELINE_COX"),
            ("time_varying_cox_results", "TV_COX"),
            ("fine_gray_default_results", "FINE_GRAY_DEFAULT"),
        ):
            source = self._source(logical_name)
            expected = source.with_columns(
                pl.lit(model).alias("model"),
                pl.col("endpoint").str.to_uppercase(),
                pl.col("variable").alias("predictor"),
            )
            for name in ("hazard_ratio", "subdistribution_hazard_ratio"):
                if name not in expected.columns:
                    expected = expected.with_columns(pl.lit(None, dtype=pl.Float64).alias(name))
            columns = [
                "model", "endpoint", "predictor", "coefficient", "standard_error",
                "hazard_ratio", "subdistribution_hazard_ratio", "ci_lower", "ci_upper", "p_value",
            ]
            actual = result.filter(pl.col("model") == model).select(columns).sort("predictor")
            self.assertTrue(actual.equals(expected.select(columns).sort("predictor")))

    def test_vintage_and_diagnostics_preserve_critical_semantics(self):
        vintage_source = self._source("vintage_horizon_results").sort(["vintage_year", "horizon_months"])
        vintage = get_vintage_results(".").data
        columns = [
            "vintage_year", "horizon_months", "horizon_role", "default_cif",
            "prepayment_cif", "pd", "loan_count", "n_at_risk", "default_count",
            "prepayment_count", "latest_origination_date", "performance_cutoff",
            "follow_up_eligible", "follow_up_status",
        ]
        self.assertTrue(vintage.select(columns).equals(vintage_source.select(columns)))
        ineligible = vintage.filter(~pl.col("follow_up_eligible"))
        self.assertTrue((ineligible["follow_up_status"] == "INSUFFICIENT_FOLLOW_UP").all())
        for name in ("default_cif", "prepayment_cif", "pd"):
            self.assertEqual(ineligible[name].null_count(), ineligible.height)

        diagnostics = get_model_diagnostics(".").data
        ltv = diagnostics.filter(
            (pl.col("diagnostic_type") == "ph") & (pl.col("predictor") == "original_ltv")
        )
        global_ph = diagnostics.filter(pl.col("diagnostic_type") == "ph_global")
        self.assertTrue((ltv["status"] == "FLAGGED").all())
        self.assertTrue((global_ph["status"] == "FLAGGED").all())

    def test_full_service_flow_is_frontend_safe_and_deterministic(self):
        methods = (
            "get_portfolio_summary", "get_pd_results", "get_survival_results",
            "get_risk_driver_results", "get_vintage_results", "get_model_diagnostics",
        )
        for method in methods:
            first = getattr(self.service, method)()
            second = getattr(self.service, method)()
            self.assertEqual(first.status, QueryStatus.OK)
            self.assertTrue(first.data.equals(second.data))
            payload = first.as_dict()
            self.assertEqual(set(payload), {"status", "data", "provenance"})
            self._assert_no_nonfinite(payload)

        profile = self.service.get_loan_profile(REAL_LOAN_ID)
        timeline = self.service.get_loan_timeline(REAL_LOAN_ID)
        unknown = self.service.get_loan_profile("UNKNOWN")
        empty = self.service.get_loan_timeline("")
        self.assertEqual(profile.status, QueryStatus.OK)
        self.assertEqual(profile.data.height, 1)
        self.assertEqual(timeline.status, QueryStatus.OK)
        self.assertEqual(
            timeline.data["performance_month"].to_list(),
            sorted(timeline.data["performance_month"].to_list()),
        )
        self.assertEqual(unknown.status, QueryStatus.NOT_FOUND)
        self.assertEqual(empty.status, QueryStatus.EMPTY)
        self._assert_no_nonfinite(profile.as_dict())
        self._assert_no_nonfinite(timeline.as_dict())

    def test_e2e_does_not_fit_models(self):
        with patch("src.survival.cox_model.fit_cox_model", side_effect=AssertionError("fit called")):
            self.service.get_pd_results()
            self.service.get_model_diagnostics()
            self.service.get_loan_profile(REAL_LOAN_ID)
            self.service.get_loan_timeline(REAL_LOAN_ID)

    def _assert_no_nonfinite(self, value):
        if isinstance(value, dict):
            for item in value.values():
                self._assert_no_nonfinite(item)
        elif isinstance(value, list):
            for item in value:
                self._assert_no_nonfinite(item)
        elif isinstance(value, float):
            self.assertFalse(math.isnan(value) or math.isinf(value))


if __name__ == "__main__":
    unittest.main()