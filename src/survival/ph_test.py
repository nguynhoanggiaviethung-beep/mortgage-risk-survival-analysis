"""Proportional-hazards diagnostics for the locked Step 3 Cox model.

``lifelines==0.30.3`` cannot compute residuals for a model fitted with an
entry column. This module therefore delegates only Step 4 diagnostics to R's
``survival`` package, using counting-process ``Surv(start, stop, event)``.
The R model specification exactly mirrors Step 3 and is numerically compared
with the supplied fitted lifelines model before PH results are accepted.

``FLAGGED`` means statistical evidence of possible non-proportionality for a
specific test and time transform. It does not invalidate the model, imply
causality, or prescribe remediation.

GLOBAL statistics are emitted directly by ``survival::cox.zph(global=TRUE)``.
The project does not combine variable statistics or p-values to create them.
"""

from __future__ import annotations

from dataclasses import dataclass
from os import PathLike
from pathlib import Path
import os
import shutil
from subprocess import CompletedProcess
from typing import TypeAlias

import numpy as np
import polars as pl

from src.data.model_dataset import CORE_COLUMNS
from src.r_runtime import child_environment as _child_environment
from src.r_runtime import run_rscript_process
from src.survival.cox_model import CoxFitResult, validate_cox_input


FrameLike: TypeAlias = pl.DataFrame | pl.LazyFrame
PathSource: TypeAlias = str | PathLike[str]

ALPHA = 0.05
TIME_TRANSFORMS = ("rank", "km")
TEST_METHOD = "survival::cox.zph"

PH_DIAGNOSTIC_DTYPES: dict[str, pl.DataType] = {
    "model_type": pl.String,
    "endpoint": pl.String,
    "variable": pl.String,
    "time_transform": pl.String,
    "test_statistic": pl.Float64,
    "degrees_of_freedom": pl.Int32,
    "p_value": pl.Float64,
    "alpha": pl.Float64,
    "ph_status": pl.String,
    "test_method": pl.String,
}

PH_GLOBAL_DIAGNOSTIC_DTYPES: dict[str, pl.DataType] = {
    "model_type": pl.String,
    "endpoint": pl.String,
    "time_transform": pl.String,
    "test_statistic": pl.Float64,
    "degrees_of_freedom": pl.Int32,
    "p_value": pl.Float64,
    "alpha": pl.Float64,
    "ph_status": pl.String,
    "test_method": pl.String,
}

ENGINE_COMPARISON_DTYPES: dict[str, pl.DataType] = {
    "variable": pl.String,
    "lifelines_coefficient": pl.Float64,
    "r_coefficient": pl.Float64,
    "coefficient_difference": pl.Float64,
    "lifelines_hazard_ratio": pl.Float64,
    "r_hazard_ratio": pl.Float64,
    "hazard_ratio_difference": pl.Float64,
}

SCALED_SCHOENFELD_DTYPES: dict[str, pl.DataType] = {
    "time_transform": pl.String,
    "event_row": pl.UInt32,
    "analysis_time": pl.Float64,
    "transformed_time": pl.Float64,
    "variable": pl.String,
    "scaled_schoenfeld_residual": pl.Float64,
}

PH_DIAGNOSTIC_COLUMNS = list(PH_DIAGNOSTIC_DTYPES)
PH_GLOBAL_DIAGNOSTIC_COLUMNS = list(PH_GLOBAL_DIAGNOSTIC_DTYPES)


class PHTestError(ValueError):
    """Raised when PH input, execution, or output violates the contract."""


class PHConfigurationError(PHTestError):
    """Raised when a usable R/survival environment is unavailable."""


@dataclass(frozen=True)
class PHTestResult:
    """Structured Step 4 result, including non-persisted audit evidence."""

    variable_diagnostics: pl.DataFrame
    global_diagnostics: pl.DataFrame
    engine_comparison: pl.DataFrame
    scaled_schoenfeld: pl.DataFrame
    r_version: str
    survival_version: str


R_PROBE = r'''
if (!requireNamespace("survival", quietly = TRUE)) {
  cat("PHERROR\tsurvival package is not available\n")
  quit(status = 42L)
}
cat("PHMETA\tR_VERSION\t", R.version.string, "\n", sep = "")
cat("PHMETA\tSURVIVAL_VERSION\t",
    as.character(utils::packageVersion("survival")), "\n", sep = "")
'''


R_PH_WORKFLOW = r'''
suppressPackageStartupMessages(library(survival))

d <- utils::read.csv(file("stdin"), stringsAsFactors = FALSE,
                     check.names = FALSE)
predictors <- c("fico", "original_ltv", "original_dti",
                "original_interest_rate", "original_loan_term")
required <- c("entry_time_month", "exit_time_month", "default_event",
              predictors)
if (!identical(names(d), required)) {
  stop("R PH input columns or order do not match the locked contract.")
}

fit <- survival::coxph(
  survival::Surv(entry_time_month, exit_time_month, default_event) ~
    fico + original_ltv + original_dti + original_interest_rate +
    original_loan_term,
  data = d,
  ties = "efron",
  robust = FALSE,
  x = TRUE,
  y = TRUE,
  model = TRUE
)

if (!identical(names(stats::coef(fit)), predictors)) {
  stop("R Cox coefficients do not match the locked five predictors.")
}
if (any(!is.finite(stats::coef(fit)))) {
  stop("R Cox fit produced non-finite coefficients.")
}

emit_number <- function(x) sprintf("%.17g", x)
for (variable in predictors) {
  coefficient <- unname(stats::coef(fit)[[variable]])
  cat("PHCOEF\t", variable, "\t", emit_number(coefficient), "\t",
      emit_number(exp(coefficient)), "\n", sep = "")
}

for (transform_name in c("rank", "km")) {
  diagnostic <- survival::cox.zph(
    fit,
    transform = transform_name,
    global = TRUE
  )
  test_table <- diagnostic$table
  if (!identical(colnames(test_table), c("chisq", "df", "p"))) {
    stop("Unexpected cox.zph table columns.")
  }
  if (!identical(rownames(test_table), c(predictors, "GLOBAL"))) {
    stop("Unexpected cox.zph table rows.")
  }

  for (variable in predictors) {
    values <- test_table[variable, ]
    cat("PHTEST\t", transform_name, "\t", variable, "\t",
        emit_number(values[["chisq"]]), "\t",
        as.integer(values[["df"]]), "\t",
        emit_number(values[["p"]]), "\n", sep = "")
  }
  global_values <- test_table["GLOBAL", ]
  cat("PHGLOBAL\t", transform_name, "\t",
      emit_number(global_values[["chisq"]]), "\t",
      as.integer(global_values[["df"]]), "\t",
      emit_number(global_values[["p"]]), "\n", sep = "")

  residuals <- diagnostic$y
  event_times <- diagnostic$time
  transformed_times <- diagnostic$x
  if (!identical(colnames(residuals), predictors)) {
    stop("Unexpected scaled Schoenfeld residual columns.")
  }
  if (nrow(residuals) != length(event_times) ||
      nrow(residuals) != length(transformed_times) ||
      any(!is.finite(residuals))) {
    stop("Invalid scaled Schoenfeld residual output.")
  }
  for (row_index in seq_len(nrow(residuals))) {
    for (variable in predictors) {
      cat("PHRESID\t", transform_name, "\t", row_index, "\t",
          emit_number(event_times[[row_index]]), "\t",
          emit_number(transformed_times[[row_index]]), "\t", variable,
          "\t", emit_number(residuals[row_index, variable]), "\n",
          sep = "")
    }
  }
}
'''


def resolve_rscript_path() -> Path:
    """Resolve Rscript from RSCRIPT_PATH and then PATH, never the registry."""
    configured = os.environ.get("RSCRIPT_PATH")
    candidate = configured if configured else shutil.which("Rscript")
    if not candidate:
        raise PHConfigurationError(
            "Rscript was not found. Configure RSCRIPT_PATH or add Rscript "
            "to PATH; Step 4 will not install R automatically."
        )
    path = Path(candidate)
    if not path.is_file():
        raise PHConfigurationError(
            f"Resolved Rscript path is not a file: {path}."
        )
    return path.resolve()


def _run_rscript(
    rscript: Path,
    expression: str,
    standard_input: str | None = None,
) -> CompletedProcess[str]:
    process = run_rscript_process(rscript, expression, standard_input)
    if process.returncode != 0:
        detail = process.stderr.strip() or process.stdout.strip()
        raise PHConfigurationError(
            f"Rscript failed with exit code {process.returncode}: {detail}"
        )
    if process.stderr.strip():
        raise PHTestError(
            f"Rscript completed with warnings/errors on stderr: "
            f"{process.stderr.strip()}"
        )
    return process


def inspect_r_environment(rscript: Path | None = None) -> tuple[Path, str, str]:
    """Validate Rscript and the installed survival package without installing."""
    executable = rscript or resolve_rscript_path()
    if not Path(executable).is_file():
        raise PHConfigurationError(f"Rscript path is not a file: {executable}.")
    process = _run_rscript(Path(executable), R_PROBE)
    metadata: dict[str, str] = {}
    for line in process.stdout.splitlines():
        fields = line.split("\t", maxsplit=2)
        if len(fields) == 3 and fields[0] == "PHMETA":
            metadata[fields[1]] = fields[2]
    if set(metadata) != {"R_VERSION", "SURVIVAL_VERSION"}:
        raise PHConfigurationError(
            "R environment probe did not return R and survival versions."
        )
    return Path(executable).resolve(), metadata["R_VERSION"], metadata["SURVIVAL_VERSION"]


def classify_ph_status(p_value: float, alpha: float = ALPHA) -> str:
    """Map a finite p-value to the locked PASS/FLAGGED rule."""
    if not np.isfinite(p_value) or not 0.0 <= p_value <= 1.0:
        raise PHTestError("p_value must be finite and between 0 and 1.")
    if not np.isfinite(alpha) or not 0.0 < alpha < 1.0:
        raise PHTestError("alpha must be finite and strictly between 0 and 1.")
    return "FLAGGED" if p_value < alpha else "PASS"


def validate_ph_test_input(
    cox_result: CoxFitResult,
    frame: FrameLike,
) -> pl.DataFrame:
    """Verify that model and data are the exact locked Step 3 specification."""
    if not isinstance(cox_result, CoxFitResult):
        raise PHTestError("cox_result must be a CoxFitResult from Step 3.")
    data = validate_cox_input(frame)
    model = cox_result.model
    expected_attributes = {
        "entry_col": "entry_time_month",
        "duration_col": "exit_time_month",
        "event_col": "default_event",
    }
    for attribute, expected in expected_attributes.items():
        if getattr(model, attribute, None) != expected:
            raise PHTestError(
                f"Step 3 model {attribute} must be {expected!r}."
            )
    if list(model.params_.index) != CORE_COLUMNS:
        raise PHTestError("Step 3 model does not contain the locked five predictors.")
    if getattr(model, "strata", None):
        raise PHTestError("Step 3 model must not use strata.")
    if float(model.penalizer) != 0.0 or bool(model.robust):
        raise PHTestError("Step 3 model must be unpenalized and non-robust.")

    diagnostic = cox_result.diagnostics.row(0, named=True)
    n_events = int(data["default_event"].sum())
    delayed = int((data["entry_time_month"] > 0).sum())
    expected_counts = {
        "n_observations": data.height,
        "n_events": n_events,
        "n_censored": data.height - n_events,
        "n_predictors": len(CORE_COLUMNS),
        "delayed_entry_count": delayed,
    }
    mismatches = {
        name: {"model": diagnostic[name], "data": expected}
        for name, expected in expected_counts.items()
        if diagnostic[name] != expected
    }
    if mismatches:
        raise PHTestError(
            f"Step 3 fitted model and PH training data do not match: {mismatches}."
        )
    return data


def _parse_r_output(
    output: str,
    cox_result: CoxFitResult,
    alpha: float,
) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    r_coefficients: dict[str, tuple[float, float]] = {}
    variable_rows: list[dict[str, object]] = []
    global_rows: list[dict[str, object]] = []
    residual_rows: list[dict[str, object]] = []

    for line in output.splitlines():
        if not line:
            continue
        fields = line.split("\t")
        record_type = fields[0]
        try:
            if record_type == "PHCOEF" and len(fields) == 4:
                r_coefficients[fields[1]] = (float(fields[2]), float(fields[3]))
            elif record_type == "PHTEST" and len(fields) == 6:
                p_value = float(fields[5])
                variable_rows.append({
                    "model_type": "cox_ph",
                    "endpoint": "default",
                    "variable": fields[2],
                    "time_transform": fields[1],
                    "test_statistic": float(fields[3]),
                    "degrees_of_freedom": int(fields[4]),
                    "p_value": p_value,
                    "alpha": alpha,
                    "ph_status": classify_ph_status(p_value, alpha),
                    "test_method": TEST_METHOD,
                })
            elif record_type == "PHGLOBAL" and len(fields) == 5:
                p_value = float(fields[4])
                global_rows.append({
                    "model_type": "cox_ph",
                    "endpoint": "default",
                    "time_transform": fields[1],
                    "test_statistic": float(fields[2]),
                    "degrees_of_freedom": int(fields[3]),
                    "p_value": p_value,
                    "alpha": alpha,
                    "ph_status": classify_ph_status(p_value, alpha),
                    "test_method": TEST_METHOD,
                })
            elif record_type == "PHRESID" and len(fields) == 7:
                residual_rows.append({
                    "time_transform": fields[1],
                    "event_row": int(fields[2]),
                    "analysis_time": float(fields[3]),
                    "transformed_time": float(fields[4]),
                    "variable": fields[5],
                    "scaled_schoenfeld_residual": float(fields[6]),
                })
            else:
                raise PHTestError(f"Unexpected R output record: {line!r}.")
        except (TypeError, ValueError) as exc:
            raise PHTestError(f"Invalid R output record: {line!r}.") from exc

    if list(r_coefficients) != CORE_COLUMNS:
        raise PHTestError("R Cox output does not contain the five predictors in order.")

    comparison_rows = []
    lifelines_rows = cox_result.coefficients.to_dicts()
    for row in lifelines_rows:
        variable = row["variable"]
        r_coefficient, r_hazard_ratio = r_coefficients[variable]
        values = np.array([
            row["coefficient"],
            row["hazard_ratio"],
            r_coefficient,
            r_hazard_ratio,
        ])
        if not np.isfinite(values).all():
            raise PHTestError("Cross-engine comparison contains non-finite values.")
        if np.signbit(row["coefficient"]) != np.signbit(r_coefficient):
            raise PHTestError(
                f"Cross-engine coefficient sign mismatch for {variable!r}."
            )
        comparison_rows.append({
            "variable": variable,
            "lifelines_coefficient": row["coefficient"],
            "r_coefficient": r_coefficient,
            "coefficient_difference": r_coefficient - row["coefficient"],
            "lifelines_hazard_ratio": row["hazard_ratio"],
            "r_hazard_ratio": r_hazard_ratio,
            "hazard_ratio_difference": r_hazard_ratio - row["hazard_ratio"],
        })

    variable_diagnostics = pl.DataFrame(
        variable_rows,
        schema=PH_DIAGNOSTIC_DTYPES,
    )
    global_diagnostics = pl.DataFrame(
        global_rows,
        schema=PH_GLOBAL_DIAGNOSTIC_DTYPES,
    )
    comparison = pl.DataFrame(
        comparison_rows,
        schema=ENGINE_COMPARISON_DTYPES,
    )
    residuals = pl.DataFrame(
        residual_rows,
        schema=SCALED_SCHOENFELD_DTYPES,
    )
    return variable_diagnostics, global_diagnostics, comparison, residuals


def run_ph_assumption_test(
    cox_result: CoxFitResult,
    frame: FrameLike,
    alpha: float = ALPHA,
) -> PHTestResult:
    """Run rank and KM cox.zph diagnostics on the Step 3 specification."""
    if float(alpha) != ALPHA:
        raise PHTestError(f"Step 4 alpha is locked at {ALPHA}.")
    data = validate_ph_test_input(cox_result, frame)
    rscript, r_version, survival_version = inspect_r_environment()
    r_input = data.select(
        "entry_time_month",
        "exit_time_month",
        "default_event",
        *CORE_COLUMNS,
    ).write_csv()
    process = _run_rscript(rscript, R_PH_WORKFLOW, r_input)
    variable, global_result, comparison, residuals = _parse_r_output(
        process.stdout,
        cox_result,
        ALPHA,
    )
    validate_ph_diagnostics(variable)
    validate_ph_global_diagnostics(global_result)
    expected_residual_rows = (
        int(data["default_event"].sum())
        * len(CORE_COLUMNS)
        * len(TIME_TRANSFORMS)
    )
    if residuals.height != expected_residual_rows:
        raise PHTestError(
            "Scaled Schoenfeld residual row count is inconsistent with events, "
            "predictors, and transforms."
        )
    if not residuals["scaled_schoenfeld_residual"].is_finite().all():
        raise PHTestError("Scaled Schoenfeld residuals contain non-finite values.")
    return PHTestResult(
        variable,
        global_result,
        comparison,
        residuals,
        r_version,
        survival_version,
    )


def _validate_result_schema(
    frame: FrameLike,
    expected: dict[str, pl.DataType],
    label: str,
) -> pl.DataFrame:
    source = frame.lazy() if isinstance(frame, pl.DataFrame) else frame
    if not isinstance(source, pl.LazyFrame):
        raise TypeError("Expected a Polars DataFrame or LazyFrame.")
    schema = source.collect_schema()
    if schema.names() != list(expected):
        raise PHTestError(f"{label} columns do not match the canonical order.")
    mismatches = {
        name: {"expected": str(dtype), "actual": str(schema[name])}
        for name, dtype in expected.items()
        if schema[name] != dtype
    }
    if mismatches:
        raise PHTestError(f"{label} has incompatible types: {mismatches}.")
    return source.collect()


def validate_ph_diagnostics(frame: FrameLike) -> pl.DataFrame:
    """Validate the ten-row variable-level cox.zph output contract."""
    data = _validate_result_schema(
        frame,
        PH_DIAGNOSTIC_DTYPES,
        "PH diagnostics",
    )
    expected_keys = {
        (variable, transform)
        for transform in TIME_TRANSFORMS
        for variable in CORE_COLUMNS
    }
    actual_keys = set(zip(
        data["variable"].to_list(),
        data["time_transform"].to_list(),
        strict=True,
    ))
    if data.height != 10 or actual_keys != expected_keys:
        raise PHTestError("PH diagnostics must contain 10 unique variable-transform rows.")
    _validate_diagnostic_values(data, "PH diagnostics")
    return data


def validate_ph_global_diagnostics(frame: FrameLike) -> pl.DataFrame:
    """Validate the two-row official cox.zph GLOBAL output contract."""
    data = _validate_result_schema(
        frame,
        PH_GLOBAL_DIAGNOSTIC_DTYPES,
        "PH global diagnostics",
    )
    if data.height != 2 or set(data["time_transform"]) != set(TIME_TRANSFORMS):
        raise PHTestError("PH global diagnostics must contain rank and km rows.")
    _validate_diagnostic_values(data, "PH global diagnostics")
    return data


def _validate_diagnostic_values(data: pl.DataFrame, label: str) -> None:
    numeric = data.select(
        "test_statistic",
        "degrees_of_freedom",
        "p_value",
        "alpha",
    ).to_numpy()
    if not np.isfinite(numeric).all():
        raise PHTestError(f"{label} contains non-finite values.")
    for row in data.to_dicts():
        if row["degrees_of_freedom"] <= 0:
            raise PHTestError(f"{label} contains invalid degrees of freedom.")
        if not 0.0 <= row["p_value"] <= 1.0:
            raise PHTestError(f"{label} contains an invalid p-value.")
        if row["alpha"] != ALPHA:
            raise PHTestError(f"{label} must use alpha={ALPHA}.")
        if row["ph_status"] != classify_ph_status(row["p_value"], ALPHA):
            raise PHTestError(f"{label} contains an inconsistent PH status.")
        if row["test_method"] != TEST_METHOD:
            raise PHTestError(f"{label} contains an unexpected test method.")


def write_ph_diagnostics(
    result: PHTestResult,
    variable_path: PathSource,
    global_path: PathSource,
) -> tuple[Path, Path]:
    """Atomically write separate variable-level and official GLOBAL CSVs."""
    variable = validate_ph_diagnostics(result.variable_diagnostics)
    global_result = validate_ph_global_diagnostics(result.global_diagnostics)
    outputs = (Path(variable_path), Path(global_path))
    frames = (variable, global_result)
    temporary_paths: list[Path] = []
    try:
        for frame, output in zip(frames, outputs, strict=True):
            output.parent.mkdir(parents=True, exist_ok=True)
            temporary = output.with_suffix(".tmp.csv")
            frame.write_csv(temporary)
            temporary_paths.append(temporary)
        for temporary, output in zip(temporary_paths, outputs, strict=True):
            temporary.replace(output)
    finally:
        for temporary in temporary_paths:
            temporary.unlink(missing_ok=True)
    return outputs
