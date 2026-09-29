import unittest
from unittest.mock import patch
from pathlib import Path

import polars as pl

from src.query import FrontendService, QueryStatus
from src.query.queries import (
    PROFILE_SCHEMA,
    TIMELINE_SCHEMA,
    get_loan_profile,
    get_loan_timeline,
    get_model_diagnostics,
    get_pd_results,
    get_portfolio_summary,
    get_risk_driver_results,
    get_survival_results,
    get_vintage_results,
)
from src.results.dashboard import (
    model_diagnostics,
    pd_results,
    portfolio_summary,
    risk_driver_results,
    survival_results,
    vintage_results,
)


LOAN_ID = "F16Q10000006"


class TestQueryLayer(unittest.TestCase):
    def test_six_dashboard_queries_have_stable_responses(self):
        for query in (
            get_portfolio_summary,
            get_pd_results,
            get_survival_results,
            get_risk_driver_results,
            get_vintage_results,
            get_model_diagnostics,
        ):
            with self.subTest(query=query.__name__):
                response = query(".")
                self.assertEqual(response.status, QueryStatus.OK)
                self.assertGreater(response.data.height, 0)
                self.assertIn("run_id", response.provenance)

    def test_dashboard_queries_delegate_to_phase_b_builders(self):
        builders = (
            ("portfolio_summary", get_portfolio_summary, portfolio_summary),
            ("pd_results", get_pd_results, pd_results),
            ("survival_results", get_survival_results, survival_results),
            ("risk_driver_results", get_risk_driver_results, risk_driver_results),
            ("vintage_results", get_vintage_results, vintage_results),
            ("model_diagnostics", get_model_diagnostics, model_diagnostics),
        )
        for name, query, builder in builders:
            with self.subTest(query=name), patch(
                f"src.query.queries.{name}", wraps=builder
            ) as mocked:
                query(".")
                mocked.assert_called_once()

    def test_valid_profile_lookup_has_canonical_schema(self):
        response = get_loan_profile(LOAN_ID, ".")
        self.assertEqual(response.status, QueryStatus.OK)
        self.assertEqual(response.data.schema, PROFILE_SCHEMA)
        self.assertEqual(response.data["loan_id"].to_list(), [LOAN_ID])
        self.assertEqual(response.data.height, 1)

    def test_unknown_profile_is_not_found(self):
        response = get_loan_profile("UNKNOWN", ".")
        self.assertEqual(response.status, QueryStatus.NOT_FOUND)
        self.assertEqual(response.data.schema, PROFILE_SCHEMA)
        self.assertEqual(response.data.height, 0)

    def test_valid_timeline_is_sorted_and_canonical(self):
        response = get_loan_timeline(LOAN_ID, ".")
        self.assertEqual(response.status, QueryStatus.OK)
        self.assertEqual(response.data.schema, TIMELINE_SCHEMA)
        self.assertEqual(response.data["loan_id"].unique().to_list(), [LOAN_ID])
        self.assertEqual(
            response.data["performance_month"].to_list(),
            sorted(response.data["performance_month"].to_list()),
        )

    def test_unknown_and_empty_timeline_are_explicit(self):
        unknown = get_loan_timeline("UNKNOWN", ".")
        empty = get_loan_timeline("", ".")
        self.assertEqual(unknown.status, QueryStatus.NOT_FOUND)
        self.assertEqual(empty.status, QueryStatus.EMPTY)
        self.assertEqual(unknown.data.schema, TIMELINE_SCHEMA)
        self.assertEqual(empty.data.schema, TIMELINE_SCHEMA)

    def test_query_results_are_frontend_safe(self):
        responses = [
            get_loan_profile(LOAN_ID, "."),
            get_loan_timeline(LOAN_ID, "."),
            get_pd_results("."),
            get_survival_results("."),
            get_risk_driver_results("."),
            get_vintage_results("."),
            get_model_diagnostics("."),
        ]
        for response in responses:
            for name, dtype in response.data.schema.items():
                if dtype == pl.Float64:
                    self.assertEqual(
                        response.data.filter(
                            pl.col(name).is_nan() | pl.col(name).is_infinite()
                        ).height,
                        0,
                    )
            self.assertTrue(all(value is not None for value in response.provenance.values()))

    def test_repeated_queries_are_deterministic(self):
        for query, args in (
            (get_loan_profile, (LOAN_ID, ".")),
            (get_loan_timeline, (LOAN_ID, ".")),
            (get_pd_results, (".",)),
            (get_survival_results, (".",)),
        ):
            with self.subTest(query=query.__name__):
                first = query(*args)
                second = query(*args)
                self.assertEqual(first.status, second.status)
                self.assertTrue(first.data.equals(second.data))
                self.assertEqual(first.provenance, second.provenance)

    def test_current_published_release_is_used(self):
        response = get_pd_results(".")
        self.assertEqual(response.provenance["run_id"], "20260929T085632Z_89d04db")
        self.assertEqual(response.provenance["source"], "published_production_release")

    def test_timeline_is_lazy_and_loan_scoped(self):
        with patch("src.query.queries.pl.read_parquet", side_effect=AssertionError("eager read")), patch(
            "src.query.queries.pl.scan_parquet", wraps=pl.scan_parquet
        ) as scan:
            response = get_loan_timeline(LOAN_ID, ".")
        self.assertEqual(response.status, QueryStatus.OK)
        scan.assert_called_once_with(Path("data/processed/performance.parquet"))

    def test_query_layer_does_not_fit_models(self):
        with patch("src.survival.cox_model.fit_cox_model", side_effect=AssertionError("fit called")):
            get_pd_results(".")
            get_loan_profile(LOAN_ID, ".")
            get_loan_timeline(LOAN_ID, ".")

    def test_facade_returns_status_data_and_provenance(self):
        response = FrontendService(".").get_loan_profile(LOAN_ID)
        self.assertEqual(set(response.as_dict()), {"status", "data", "provenance"})
        self.assertEqual(response.as_dict()["status"], "OK")
        self.assertEqual(len(response.as_dict()["data"]), 1)


if __name__ == "__main__":
    unittest.main()