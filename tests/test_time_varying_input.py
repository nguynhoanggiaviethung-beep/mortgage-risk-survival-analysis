import unittest

import polars as pl

from src.survival.time_varying_input import (
    TIME_VARYING_INPUT_COLUMNS,
    TIME_VARYING_INPUT_DTYPES,
    TimeVaryingInputError,
    build_time_varying_cox_input,
    validate_time_varying_cox_input,
    validate_time_varying_performance_source,
)
from tests.time_varying_fixtures import build_interval_source_fixture


class TestTimeVaryingInput(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.performance, cls.loan_level = build_interval_source_fixture()
        cls.intervals = build_time_varying_cox_input(
            cls.performance,
            cls.loan_level,
        ).collect()

    def test_canonical_schema_and_interval_counts(self):
        self.assertEqual(self.intervals.columns, TIME_VARYING_INPUT_COLUMNS)
        self.assertEqual(
            self.intervals.schema,
            pl.Schema(TIME_VARYING_INPUT_DTYPES),
        )
        counts = dict(
            self.intervals.group_by("loan_id").len().iter_rows()
        )
        self.assertEqual(
            counts,
            {
                "L_DEFAULT": 3,
                "L_PREPAY": 2,
                "L_CENSOR_GAP": 2,
                "L_AFTER_LAST": 2,
            },
        )

    def test_exact_start_stop_intervals_and_delayed_entry(self):
        actual = {
            loan_id: list(zip(group["start_time_month"], group["stop_time_month"]))
            for loan_id, group in self.intervals.partition_by(
                "loan_id", as_dict=True
            ).items()
        }
        # Polars uses tuple keys when as_dict=True.
        normalized = {
            key[0] if isinstance(key, tuple) else key: value
            for key, value in actual.items()
        }
        self.assertEqual(normalized["L_DEFAULT"], [(0, 1), (1, 2), (2, 3)])
        self.assertEqual(normalized["L_PREPAY"], [(2, 3), (3, 4)])
        self.assertEqual(normalized["L_CENSOR_GAP"], [(0, 2), (2, 3)])
        self.assertEqual(normalized["L_AFTER_LAST"], [(0, 1), (1, 3)])

    def test_default_only_on_terminal_default_interval(self):
        counts = {
            row["loan_id"]: row["default_event"]
            for row in self.intervals.group_by("loan_id")
            .agg(pl.col("default_event").sum())
            .to_dicts()
        }
        self.assertEqual(
            counts,
            {
                "L_DEFAULT": 1,
                "L_PREPAY": 0,
                "L_CENSOR_GAP": 0,
                "L_AFTER_LAST": 1,
            },
        )
        self.assertTrue(
            self.intervals.filter(pl.col("default_event") == 1)[
                "terminal_interval_flag"
            ].all()
        )

    def test_same_month_terminal_values_are_not_predictors(self):
        default = self.intervals.filter(pl.col("loan_id") == "L_DEFAULT")
        self.assertEqual(default["covariate_month"].max().month, 3)
        terminal = default.filter(pl.col("terminal_interval_flag")).row(
            0, named=True
        )
        self.assertEqual(terminal["lag_current_actual_upb"], 196_000.0)
        self.assertEqual(terminal["lag_current_interest_rate"], 3.0)
        self.assertEqual(terminal["lag_dq_3plus"], 1)

    def test_actual_observation_gaps_create_no_artificial_rows(self):
        gaps = self.intervals.filter(pl.col("gap_interval_flag"))
        self.assertEqual(gaps.height, 2)
        lengths = dict(gaps.select("loan_id", "interval_length_months").iter_rows())
        self.assertEqual(lengths, {"L_CENSOR_GAP": 2, "L_AFTER_LAST": 2})

    def test_delinquency_encoding_and_current_reference(self):
        indicators = [
            "lag_dq_1m",
            "lag_dq_2m",
            "lag_dq_3plus",
            "lag_dq_xx",
            "lag_dq_ra",
        ]
        self.assertTrue(
            (
                self.intervals.select(pl.sum_horizontal(indicators)).to_series()
                <= 1
            ).all()
        )
        current = self.intervals.filter(
            (pl.col("loan_id") == "L_DEFAULT")
            & (pl.col("start_time_month") == 0)
        )
        self.assertEqual(current.select(pl.sum_horizontal(indicators)).item(), 0)

        expected = [
            ("L_DEFAULT", 1, "lag_dq_1m"),
            ("L_CENSOR_GAP", 2, "lag_dq_2m"),
            ("L_DEFAULT", 2, "lag_dq_3plus"),
            ("L_PREPAY", 3, "lag_dq_xx"),
            ("L_AFTER_LAST", 0, "lag_dq_ra"),
        ]
        for loan_id, start, indicator in expected:
            with self.subTest(indicator=indicator):
                value = self.intervals.filter(
                    (pl.col("loan_id") == loan_id)
                    & (pl.col("start_time_month") == start)
                )[indicator].item()
                self.assertEqual(value, 1)

    def test_all_three_plus_boundaries_map_to_the_same_indicator(self):
        for status in ("03", "04", "88"):
            with self.subTest(status=status):
                changed = self.performance.with_columns(
                    pl.when(
                        (pl.col("loan_id") == "L_DEFAULT")
                        & (pl.col("reporting_period_num") == 202003)
                    )
                    .then(pl.lit(status))
                    .otherwise(pl.col("current_delinquency_status"))
                    .alias("current_delinquency_status")
                )
                intervals = build_time_varying_cox_input(
                    changed,
                    self.loan_level,
                ).collect()
                value = intervals.filter(
                    (pl.col("loan_id") == "L_DEFAULT")
                    & (pl.col("start_time_month") == 2)
                )["lag_dq_3plus"].item()
                self.assertEqual(value, 1)

    def test_source_and_result_are_not_mutated(self):
        performance_before = self.performance.clone()
        loan_before = self.loan_level.clone()
        build_time_varying_cox_input(self.performance, self.loan_level).collect()
        self.assertTrue(self.performance.equals(performance_before))
        self.assertTrue(self.loan_level.equals(loan_before))

    def test_invalid_monthly_source_is_rejected_without_imputation(self):
        duplicate = pl.concat([self.performance, self.performance.head(1)])
        with self.assertRaisesRegex(TimeVaryingInputError, "duplicate"):
            validate_time_varying_performance_source(duplicate)

        missing = self.performance.with_columns(
            pl.when(pl.arange(0, pl.len()) == 0)
            .then(None)
            .otherwise(pl.col("current_actual_upb"))
            .alias("current_actual_upb")
        )
        with self.assertRaisesRegex(TimeVaryingInputError, "missing or non-finite"):
            validate_time_varying_performance_source(missing)

        invalid_status = self.performance.with_columns(
            pl.when(pl.arange(0, pl.len()) == 0)
            .then(pl.lit("89"))
            .otherwise(pl.col("current_delinquency_status"))
            .alias("current_delinquency_status")
        )
        with self.assertRaisesRegex(TimeVaryingInputError, "unsupported"):
            validate_time_varying_performance_source(invalid_status)

    def test_duplicate_overlap_and_invalid_event_are_rejected(self):
        duplicate = pl.concat([self.intervals, self.intervals.head(1)])
        with self.assertRaisesRegex(TimeVaryingInputError, "duplicate interval"):
            validate_time_varying_cox_input(duplicate)

        overlap = self.intervals.with_columns(
            pl.when(
                (pl.col("loan_id") == "L_DEFAULT")
                & (pl.col("start_time_month") == 1)
            )
            .then(pl.lit(0, dtype=pl.Int32))
            .otherwise(pl.col("start_time_month"))
            .alias("start_time_month")
        ).with_columns(
            (
                pl.col("stop_time_month") - pl.col("start_time_month")
            ).alias("interval_length_months")
        ).with_columns(
            (pl.col("interval_length_months") > 1).alias("gap_interval_flag")
        )
        with self.assertRaisesRegex(TimeVaryingInputError, "contiguous"):
            validate_time_varying_cox_input(overlap)

        invalid_event = self.intervals.with_columns(
            pl.when(
                (pl.col("loan_id") == "L_PREPAY")
                & pl.col("terminal_interval_flag")
            )
            .then(pl.lit(1, dtype=pl.Int8))
            .otherwise(pl.col("default_event"))
            .alias("default_event")
        )
        with self.assertRaisesRegex(TimeVaryingInputError, "terminal event"):
            validate_time_varying_cox_input(invalid_event)


if __name__ == "__main__":
    unittest.main()
