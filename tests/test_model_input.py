import unittest
from pathlib import Path

import polars as pl

from src.survival.model_input import (
    COMPETING_RISK_INPUT_COLUMNS,
    COX_INPUT_COLUMNS,
    ModelInputError,
    SURVIVAL_INPUT_COLUMNS,
    build_loan_level_input,
    load_loan_month_source,
    to_competing_risk_input,
    to_cox_input,
    to_survival_input,
    validate_loan_level_input,
    validate_loan_month_source,
)


FIXTURE = Path(__file__).parent / "fixtures" / "mock_loan_month.parquet"


class TestModelInput(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.monthly = pl.read_parquet(FIXTURE)
        cls.loan_level = build_loan_level_input(cls.monthly).collect()

    def test_mock_covers_required_cases(self):
        events = dict(
            self.loan_level.select("loan_id", "event_type").iter_rows()
        )
        self.assertEqual(events["L_DEFAULT"], "DEFAULT")
        self.assertEqual(events["L_PREPAY"], "PREPAYMENT")
        self.assertEqual(events["L_CENSOR"], "CENSOR")
        self.assertEqual(events["L_ADMIN"], "CENSOR")

        delayed = self.loan_level.filter(
            pl.col("loan_id") == "L_PREPAY"
        ).row(0, named=True)
        self.assertEqual(delayed["entry_time_month"], 1)
        self.assertEqual(delayed["exit_time_month"], 3)

    def test_model_input_is_one_row_per_loan(self):
        self.assertEqual(self.loan_level.height, 5)
        self.assertEqual(self.loan_level["loan_id"].n_unique(), 5)
        self.assertEqual(
            set(self.loan_level["loan_id"]),
            set(self.monthly["loan_id"]),
        )

    def test_missing_predictor_is_not_imputed(self):
        loan = self.loan_level.filter(
            pl.col("loan_id") == "L_MISSING_DTI"
        ).row(0, named=True)
        self.assertIsNone(loan["original_dti"])
        self.assertFalse(loan["core_covariates_complete_flag"])

    def test_views_preserve_delayed_entry(self):
        views = (
            (to_survival_input(self.loan_level), SURVIVAL_INPUT_COLUMNS),
            (to_cox_input(self.loan_level), COX_INPUT_COLUMNS),
            (
                to_competing_risk_input(self.loan_level),
                COMPETING_RISK_INPUT_COLUMNS,
            ),
        )
        for view, expected_columns in views:
            self.assertIn("entry_time_month", view.collect_schema())
            self.assertIn("exit_time_month", view.collect_schema())
            self.assertEqual(view.collect_schema().names(), expected_columns)

    def test_cox_is_complete_case_but_other_views_keep_missing_predictor(self):
        survival = to_survival_input(self.loan_level).collect()
        competing = to_competing_risk_input(self.loan_level).collect()
        cox = to_cox_input(self.loan_level).collect()

        self.assertEqual(survival.height, 5)
        self.assertEqual(competing.height, 5)
        self.assertEqual(cox.height, 4)
        self.assertNotIn("L_MISSING_DTI", cox["loan_id"].to_list())

    def test_missing_required_monthly_column_rejected(self):
        with self.assertRaisesRegex(ModelInputError, "missing required columns"):
            validate_loan_month_source(self.monthly.drop("zero_balance_code"))

    def test_duplicate_loan_month_key_rejected(self):
        duplicate = pl.concat([self.monthly, self.monthly.head(1)])
        with self.assertRaisesRegex(ModelInputError, "duplicate"):
            validate_loan_month_source(duplicate)

    def test_inconsistent_static_field_rejected(self):
        changed = self.monthly.with_columns(
            pl.when(
                (pl.col("loan_id") == "L_DEFAULT")
                & (pl.col("reporting_period_num") == 202002)
            )
            .then(pl.lit(999, dtype=pl.Int16))
            .otherwise(pl.col("fico"))
            .alias("fico")
        )
        with self.assertRaisesRegex(ModelInputError, "vary within a loan"):
            validate_loan_month_source(changed)

    def test_duplicate_loan_level_id_rejected(self):
        duplicate = pl.concat([self.loan_level, self.loan_level.head(1)])
        with self.assertRaisesRegex(ModelInputError, "duplicate loan_id"):
            validate_loan_level_input(duplicate)

    def test_invalid_event_mapping_rejected(self):
        invalid = self.loan_level.with_columns(
            pl.when(pl.col("loan_id") == "L_DEFAULT")
            .then(pl.lit(0, dtype=pl.Int8))
            .otherwise(pl.col("event_code"))
            .alias("event_code")
        )
        with self.assertRaisesRegex(ModelInputError, "event label/code"):
            validate_loan_level_input(invalid)

    def test_invalid_time_order_rejected(self):
        invalid = self.loan_level.with_columns(
            pl.when(pl.col("loan_id") == "L_DEFAULT")
            .then(pl.col("entry_time_month"))
            .otherwise(pl.col("exit_time_month"))
            .alias("exit_time_month")
        )
        with self.assertRaisesRegex(ModelInputError, "entry/exit/duration"):
            validate_loan_level_input(invalid)

    def test_loader_preserves_source_ids(self):
        loaded = load_loan_month_source(FIXTURE).collect()
        self.assertEqual(
            set(loaded["loan_id"].unique()),
            set(self.monthly["loan_id"].unique()),
        )


if __name__ == "__main__":
    unittest.main()
