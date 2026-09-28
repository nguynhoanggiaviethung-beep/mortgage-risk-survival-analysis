import tempfile
import unittest
from pathlib import Path

import numpy as np
import polars as pl

from scripts.build_mock_fine_gray_results import (
    build_fine_gray_fixture,
    build_mock_fine_gray_results,
)
from src.competing_risks.cause_specific import (
    fit_cause_specific_model,
    validate_cause_specific_input,
)
from src.competing_risks.fine_gray import (
    FINE_GRAY_DIAGNOSTIC_COLUMNS,
    FINE_GRAY_DIAGNOSTIC_DTYPES,
    FINE_GRAY_RESULT_COLUMNS,
    FINE_GRAY_RESULT_DTYPES,
    FineGrayModelError,
    fit_fine_gray_default,
    validate_fine_gray_diagnostics,
    validate_fine_gray_input,
    validate_fine_gray_results,
    write_fine_gray_results,
)
from src.data.model_dataset import CORE_COLUMNS
from src.r_runtime import run_rscript_process
from src.survival.ph_test import resolve_rscript_path


ROOT = Path(__file__).resolve().parent.parent
MOCK_RESULTS = ROOT / "results/mock/fine_gray_default_results.parquet"
MOCK_DIAGNOSTICS = ROOT / "results/mock/fine_gray_default_diagnostics.parquet"

DIRECT_R_REFERENCE = r'''
suppressPackageStartupMessages(library(survival))
d <- utils::read.csv(file("stdin"), stringsAsFactors=FALSE, check.names=FALSE)
d$cause <- factor(d$cr_event_code, levels=c(0L, 1L, 2L),
                  labels=c("CENSOR", "DEFAULT", "PREPAYMENT"))
d$cluster_id <- d$loan_id
fg <- survival::finegray(
  survival::Surv(entry_time_month, exit_time_month, cause) ~
    fico + original_ltv + original_dti + original_interest_rate +
    original_loan_term + cluster_id,
  data=d, etype="DEFAULT", id=loan_id, timefix=TRUE
)
fit <- survival::coxph(
  survival::Surv(fgstart, fgstop, fgstatus) ~
    fico + original_ltv + original_dti + original_interest_rate +
    original_loan_term,
  data=fg, weights=fgwt, cluster=cluster_id, robust=TRUE, ties="efron",
  singular.ok=FALSE
)
beta <- stats::coef(fit)
robust_se <- sqrt(diag(fit$var))
naive_se <- sqrt(diag(fit$naive.var))
z <- beta / robust_se
p <- 2 * stats::pnorm(abs(z), lower.tail=FALSE)
critical <- stats::qnorm(0.975)
for (i in seq_along(beta)) {
  values <- c(beta[[i]], robust_se[[i]], naive_se[[i]], exp(beta[[i]]),
              exp(beta[[i]] - critical * robust_se[[i]]),
              exp(beta[[i]] + critical * robust_se[[i]]), z[[i]], p[[i]])
  cat("REF\t", names(beta)[[i]], "\t",
      paste(sprintf("%.17g", values), collapse="\t"), "\n", sep="")
}
'''


class TestFineGrayDefault(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.input = build_fine_gray_fixture()
        cls.result = fit_fine_gray_default(cls.input)

    def test_fixture_reuses_full_rank_step3_data_with_all_required_outcomes(self):
        self.assertTrue(self.input.equals(build_fine_gray_fixture()))
        counts = dict(
            zip(
                *self.input.group_by("event_type").len().select(
                    "event_type", "len"
                ).to_numpy().T,
                strict=True,
            )
        )
        self.assertEqual(counts, {"DEFAULT": 72, "PREPAYMENT": 84, "CENSOR": 84})
        self.assertEqual((self.input["entry_time_month"] > 0).sum(), 48)
        self.assertLess(self.input["exit_time_month"].n_unique(), self.input.height)
        design = self.input.select(CORE_COLUMNS).to_numpy().astype(float)
        self.assertEqual(np.linalg.matrix_rank(design), len(CORE_COLUMNS))

    def test_default_identity_exact_predictors_and_exact_schemas(self):
        self.assertEqual(self.result.coefficients.columns, FINE_GRAY_RESULT_COLUMNS)
        self.assertEqual(
            self.result.coefficients.schema, pl.Schema(FINE_GRAY_RESULT_DTYPES)
        )
        self.assertEqual(self.result.diagnostics.columns, FINE_GRAY_DIAGNOSTIC_COLUMNS)
        self.assertEqual(
            self.result.diagnostics.schema,
            pl.Schema(FINE_GRAY_DIAGNOSTIC_DTYPES),
        )
        self.assertEqual(
            self.result.coefficients["model_type"].unique().to_list(),
            ["FINE_GRAY"],
        )
        self.assertEqual(
            self.result.coefficients["endpoint"].unique().to_list(), ["DEFAULT"]
        )
        self.assertEqual(self.result.coefficients["variable"].to_list(), CORE_COLUMNS)
        validate_fine_gray_results(self.result.coefficients)
        validate_fine_gray_diagnostics(self.result.diagnostics)

    def test_expansion_preserves_delayed_entry_and_competing_risk_sets(self):
        audit = self.result.expansion_audit
        self.assertTrue(audit.delayed_entry_preserved)
        self.assertTrue(audit.intervals_valid)
        self.assertTrue(audit.weights_valid)
        self.assertTrue(audit.status_valid)
        self.assertTrue(audit.cluster_mapping_valid)
        self.assertTrue(audit.ordinary_censoring_preserved)
        self.assertGreater(audit.n_competing_extended, 0)
        row = self.result.diagnostics.row(0, named=True)
        self.assertEqual(row["n_input_loans"], 240)
        self.assertEqual(row["n_expanded_rows"], 1521)
        self.assertEqual(row["n_default"], 72)
        self.assertEqual(row["n_prepayment"], 84)
        self.assertEqual(row["n_censored"], 84)
        self.assertEqual(row["n_delayed_entry"], 48)
        self.assertEqual(row["n_predictors"], 5)
        self.assertEqual(row["variance_type"], "subject_clustered_robust_sandwich")
        self.assertEqual(row["convergence_status"], "PASS")

    def test_shr_and_robust_confidence_intervals(self):
        coefficients = self.result.coefficients
        np.testing.assert_allclose(
            coefficients["subdistribution_hazard_ratio"],
            np.exp(coefficients["coefficient"]),
            rtol=1e-14,
            atol=0.0,
        )
        critical = 1.959963984540054
        expected = np.exp(
            np.column_stack((
                coefficients["coefficient"] - critical * coefficients["standard_error"],
                coefficients["coefficient"] + critical * coefficients["standard_error"],
            ))
        )
        np.testing.assert_allclose(
            coefficients.select("ci_lower", "ci_upper"),
            expected,
            rtol=1e-13,
            atol=0.0,
        )

    def test_wrapper_matches_direct_r_and_reports_robust_not_naive_se(self):
        process = run_rscript_process(
            resolve_rscript_path(),
            DIRECT_R_REFERENCE,
            self.input.sort("loan_id").write_csv(),
        )
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(process.stderr, "")
        reference = {}
        for line in process.stdout.splitlines():
            fields = line.split("\t")
            if fields[0] == "REF":
                reference[fields[1]] = np.array(fields[2:], dtype=float)
        self.assertEqual(list(reference), CORE_COLUMNS)
        robust = np.array([reference[name][1] for name in CORE_COLUMNS])
        naive = np.array([reference[name][2] for name in CORE_COLUMNS])
        self.assertGreater(np.max(np.abs(robust - naive)), 1e-10)
        actual = self.result.coefficients
        expected = np.array([
            [
                reference[name][0],
                reference[name][3],
                reference[name][1],
                reference[name][4],
                reference[name][5],
                reference[name][7],
                reference[name][6],
            ]
            for name in CORE_COLUMNS
        ])
        np.testing.assert_allclose(
            actual.select(
                "coefficient",
                "subdistribution_hazard_ratio",
                "standard_error",
                "ci_lower",
                "ci_upper",
                "p_value",
                "z_statistic",
            ),
            expected,
            rtol=1e-13,
            atol=1e-15,
        )

    def test_fine_gray_is_not_a_renamed_cause_specific_risk_set(self):
        cause_specific_input = validate_cause_specific_input(
            self.input.with_columns(
                (pl.col("event_type") == "DEFAULT")
                .cast(pl.Int8)
                .alias("default_event"),
                (pl.col("event_type") == "PREPAYMENT")
                .cast(pl.Int8)
                .alias("prepayment_event"),
                pl.lit(2020, dtype=pl.Int16).alias("vintage_year"),
                pl.col("exit_time_month").alias("duration_months"),
            ).select(
                "loan_id",
                "vintage_year",
                "entry_time_month",
                "exit_time_month",
                "duration_months",
                "default_event",
                "prepayment_event",
                "event_type",
                *CORE_COLUMNS,
            )
        )
        cause_specific = fit_cause_specific_model(cause_specific_input, "DEFAULT")
        prepayments = cause_specific_input.filter(
            pl.col("event_type") == "PREPAYMENT"
        )
        self.assertTrue((prepayments["default_event"] == 0).all())
        self.assertEqual(cause_specific.model.event_col, "default_event")
        self.assertGreater(self.result.expansion_audit.n_competing_extended, 0)

    def test_repeated_fit_is_deterministic_and_does_not_mutate_input(self):
        before = self.input.clone()
        repeated = fit_fine_gray_default(self.input)
        self.assertTrue(self.input.equals(before))
        self.assertTrue(repeated.coefficients.equals(self.result.coefficients))
        self.assertTrue(repeated.diagnostics.equals(self.result.diagnostics))
        self.assertEqual(repeated.expansion_audit, self.result.expansion_audit)

    def test_invalid_inputs_fail_loudly_without_dropping_or_imputation(self):
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
                    pl.col("entry_time_month").alias("exit_time_month")
                ),
                "entry/exit",
            ),
            (
                self.input.with_columns(pl.lit(None).cast(pl.Int16).alias("fico")),
                "missing or non-finite",
            ),
            (
                self.input.with_columns(
                    pl.when(pl.arange(0, pl.len()) == 0)
                    .then(float("inf"))
                    .otherwise(pl.col("original_ltv"))
                    .alias("original_ltv")
                ),
                "missing or non-finite",
            ),
            (
                self.input.filter(pl.col("event_type") != "DEFAULT"),
                "DEFAULT",
            ),
            (
                self.input.filter(pl.col("event_type") != "PREPAYMENT"),
                "PREPAYMENT",
            ),
        )
        for frame, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(FineGrayModelError, message):
                    validate_fine_gray_input(frame)
        with self.assertRaisesRegex(FineGrayModelError, "missing required"):
            validate_fine_gray_input(self.input.drop("original_dti"))
        with self.assertRaisesRegex(FineGrayModelError, "incompatible"):
            validate_fine_gray_input(
                self.input.with_columns(pl.col("fico").cast(pl.Int32))
            )

    def test_invalid_confidence_levels_are_rejected(self):
        for value in (0, 1, -0.1, 1.1, True, "0.95"):
            with self.subTest(value=value):
                with self.assertRaises(FineGrayModelError):
                    fit_fine_gray_default(self.input, value)

    def test_writer_and_checked_in_mock_artifacts_are_byte_deterministic(self):
        for path in (MOCK_RESULTS, MOCK_DIAGNOSTICS):
            self.assertTrue(path.is_file(), path)
        validate_fine_gray_results(pl.read_parquet(MOCK_RESULTS))
        validate_fine_gray_diagnostics(pl.read_parquet(MOCK_DIAGNOSTICS))
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            first_paths = (
                Path(first) / MOCK_RESULTS.name,
                Path(first) / MOCK_DIAGNOSTICS.name,
            )
            second_paths = (
                Path(second) / MOCK_RESULTS.name,
                Path(second) / MOCK_DIAGNOSTICS.name,
            )
            build_mock_fine_gray_results(*first_paths)
            build_mock_fine_gray_results(*second_paths)
            for saved, one, two in zip(
                (MOCK_RESULTS, MOCK_DIAGNOSTICS),
                first_paths,
                second_paths,
                strict=True,
            ):
                self.assertEqual(saved.read_bytes(), one.read_bytes())
                self.assertEqual(one.read_bytes(), two.read_bytes())
        with tempfile.TemporaryDirectory() as directory:
            outputs = write_fine_gray_results(
                self.result,
                Path(directory) / "nested/results.parquet",
                Path(directory) / "nested/diagnostics.parquet",
            )
            self.assertTrue(pl.read_parquet(outputs[0]).equals(self.result.coefficients))
            self.assertTrue(pl.read_parquet(outputs[1]).equals(self.result.diagnostics))


if __name__ == "__main__":
    unittest.main()
