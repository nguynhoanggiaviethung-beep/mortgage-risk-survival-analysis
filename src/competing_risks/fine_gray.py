"""Fine-Gray DEFAULT subdistribution-hazard model with delayed entry.

The estimator delegates expansion and fitting to the installed R
``survival`` package.  It consumes canonical one-row-per-loan event and time
fields, preserves the absolute entry/exit time axis, and reports inference
from the loan-clustered robust sandwich variance.
"""

from __future__ import annotations

from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import TypeAlias

import numpy as np
import polars as pl

from src.data.model_dataset import CORE_COLUMNS
from src.r_runtime import run_rscript_process
from src.survival.ph_test import inspect_r_environment, resolve_rscript_path


FrameLike: TypeAlias = pl.DataFrame | pl.LazyFrame
PathSource: TypeAlias = str | PathLike[str]

FINE_GRAY_INPUT_DTYPES: dict[str, pl.DataType] = {
    "loan_id": pl.String,
    "entry_time_month": pl.Int32,
    "exit_time_month": pl.Int32,
    "event_type": pl.String,
    "cr_event_code": pl.Int8,
    "fico": pl.Int16,
    "original_ltv": pl.Float64,
    "original_dti": pl.Float64,
    "original_interest_rate": pl.Float64,
    "original_loan_term": pl.Int16,
}
FINE_GRAY_INPUT_COLUMNS = list(FINE_GRAY_INPUT_DTYPES)

FINE_GRAY_RESULT_DTYPES: dict[str, pl.DataType] = {
    "model_type": pl.String,
    "endpoint": pl.String,
    "variable": pl.String,
    "coefficient": pl.Float64,
    "subdistribution_hazard_ratio": pl.Float64,
    "standard_error": pl.Float64,
    "ci_lower": pl.Float64,
    "ci_upper": pl.Float64,
    "p_value": pl.Float64,
    "z_statistic": pl.Float64,
}
FINE_GRAY_RESULT_COLUMNS = list(FINE_GRAY_RESULT_DTYPES)

FINE_GRAY_DIAGNOSTIC_DTYPES: dict[str, pl.DataType] = {
    "model_type": pl.String,
    "endpoint": pl.String,
    "n_input_loans": pl.UInt32,
    "n_expanded_rows": pl.UInt32,
    "n_default": pl.UInt32,
    "n_prepayment": pl.UInt32,
    "n_censored": pl.UInt32,
    "n_predictors": pl.UInt32,
    "n_delayed_entry": pl.UInt32,
    "variance_type": pl.String,
    "r_version": pl.String,
    "survival_version": pl.String,
    "convergence_status": pl.String,
    "convergence_warning": pl.String,
}
FINE_GRAY_DIAGNOSTIC_COLUMNS = list(FINE_GRAY_DIAGNOSTIC_DTYPES)


class FineGrayModelError(ValueError):
    """Raised when Fine-Gray input, execution, or output is invalid."""


@dataclass(frozen=True)
class FineGrayExpansionAudit:
    """Engine-reported structural checks for the expanded risk sets."""

    n_competing_extended: int
    delayed_entry_preserved: bool
    intervals_valid: bool
    weights_valid: bool
    status_valid: bool
    cluster_mapping_valid: bool
    ordinary_censoring_preserved: bool


@dataclass(frozen=True)
class FineGrayFitResult:
    """Normalized Fine-Gray estimates plus non-persisted expansion audit."""

    coefficients: pl.DataFrame
    diagnostics: pl.DataFrame
    expansion_audit: FineGrayExpansionAudit


R_FINE_GRAY_WORKFLOW = r'''
suppressPackageStartupMessages(library(survival))

d <- utils::read.csv(file("stdin"), stringsAsFactors=FALSE,
                     check.names=FALSE)
required <- c(
  "loan_id", "entry_time_month", "exit_time_month", "event_type",
  "cr_event_code", "fico", "original_ltv", "original_dti",
  "original_interest_rate", "original_loan_term"
)
if (!identical(names(d), required)) {
  stop("Fine-Gray input columns or order do not match the locked contract.")
}
if (anyDuplicated(d$loan_id)) stop("Fine-Gray input contains duplicate loan IDs.")

d$factor_cause <- factor(
  d$cr_event_code,
  levels=c(0L, 1L, 2L),
  labels=c("CENSOR", "DEFAULT", "PREPAYMENT")
)
d$cluster_id <- d$loan_id
y <- survival::Surv(
  d$entry_time_month,
  d$exit_time_month,
  d$factor_cause
)
if (!identical(attr(y, "type"), "mcounting")) {
  stop("R survival did not construct a multi-state counting-process Surv.")
}

warning_messages <- character()
capture_warning <- function(w) {
  warning_messages <<- c(warning_messages, conditionMessage(w))
  invokeRestart("muffleWarning")
}
fg <- withCallingHandlers(
  survival::finegray(
    y ~ fico + original_ltv + original_dti + original_interest_rate +
      original_loan_term + cluster_id,
    data=d,
    etype="DEFAULT",
    id=loan_id,
    prefix="fg",
    count="fgcount",
    timefix=TRUE
  ),
  warning=capture_warning
)
expected_fg <- c(
  "fico", "original_ltv", "original_dti", "original_interest_rate",
  "original_loan_term", "cluster_id", "fgstart", "fgstop", "fgstatus",
  "fgwt", "fgcount"
)
if (!identical(names(fg), expected_fg)) {
  stop("survival::finegray returned an unexpected expanded schema.")
}

source_index <- match(fg$cluster_id, d$loan_id)
cluster_mapping_valid <- all(!is.na(source_index)) &&
  all(d$loan_id %in% fg$cluster_id)
if (!cluster_mapping_valid) stop("Fine-Gray cluster mapping is invalid.")
intervals_valid <- all(is.finite(fg$fgstart)) &&
  all(is.finite(fg$fgstop)) && all(fg$fgstop > fg$fgstart)
weights_valid <- all(is.finite(fg$fgwt)) && all(fg$fgwt >= 0)
status_valid <- all(fg$fgstatus %in% c(0L, 1L))
delayed_entry_preserved <- all(
  fg$fgstart >= d$entry_time_month[source_index]
)
ordinary_censoring_preserved <- all(
  fg$fgstop[d$cr_event_code[source_index] == 0L] <=
    d$exit_time_month[source_index[d$cr_event_code[source_index] == 0L]]
)
competing_extended <- unique(fg$cluster_id[
  d$cr_event_code[source_index] == 2L &
    fg$fgstop > d$exit_time_month[source_index]
])
if (!intervals_valid) stop("Fine-Gray expansion returned invalid intervals.")
if (!weights_valid) stop("Fine-Gray expansion returned invalid weights.")
if (!status_valid) stop("Fine-Gray expansion returned invalid target status.")
if (!delayed_entry_preserved) stop("Fine-Gray expansion lost delayed entry.")
if (!ordinary_censoring_preserved) {
  stop("Fine-Gray expansion extended ordinary censoring observations.")
}

fit <- withCallingHandlers(
  survival::coxph(
    survival::Surv(fgstart, fgstop, fgstatus) ~
      fico + original_ltv + original_dti + original_interest_rate +
      original_loan_term,
    data=fg,
    weights=fgwt,
    cluster=cluster_id,
    robust=TRUE,
    ties="efron",
    singular.ok=FALSE
  ),
  warning=capture_warning
)
if (is.null(fit$naive.var)) {
  stop("coxph did not retain a naive variance alongside robust variance.")
}
if (!identical(names(stats::coef(fit)), required[6:10])) {
  stop("coxph coefficient order does not match the locked predictors.")
}

beta <- stats::coef(fit)
robust_se <- sqrt(diag(fit$var))
names(robust_se) <- names(beta)
if (any(!is.finite(beta)) || any(!is.finite(robust_se)) ||
    any(robust_se <= 0)) {
  stop("coxph returned invalid robust inference.")
}
z <- beta / robust_se
p <- 2 * stats::pnorm(abs(z), lower.tail=FALSE)
critical <- stats::qnorm(1 - CONFIDENCE_ALPHA / 2)
ci_lower <- exp(beta - critical * robust_se)
ci_upper <- exp(beta + critical * robust_se)

emit_number <- function(x) sprintf("%.17g", x)
emit_bool <- function(x) if (isTRUE(x)) "TRUE" else "FALSE"
clean_warning <- function(x) gsub("[\\t\\r\\n]+", " ", x)
warning_text <- paste(unique(vapply(
  warning_messages, clean_warning, character(1)
)), collapse=" | ")

cat("FGMETA\tR_VERSION\t", R.version.string, "\n", sep="")
cat("FGMETA\tSURVIVAL_VERSION\t",
    as.character(utils::packageVersion("survival")), "\n", sep="")
cat("FGMETA\tN_EXPANDED_ROWS\t", nrow(fg), "\n", sep="")
cat("FGMETA\tN_COMPETING_EXTENDED\t", length(competing_extended), "\n", sep="")
cat("FGMETA\tDELAYED_ENTRY_PRESERVED\t",
    emit_bool(delayed_entry_preserved), "\n", sep="")
cat("FGMETA\tINTERVALS_VALID\t", emit_bool(intervals_valid), "\n", sep="")
cat("FGMETA\tWEIGHTS_VALID\t", emit_bool(weights_valid), "\n", sep="")
cat("FGMETA\tSTATUS_VALID\t", emit_bool(status_valid), "\n", sep="")
cat("FGMETA\tCLUSTER_MAPPING_VALID\t",
    emit_bool(cluster_mapping_valid), "\n", sep="")
cat("FGMETA\tORDINARY_CENSORING_PRESERVED\t",
    emit_bool(ordinary_censoring_preserved), "\n", sep="")
cat("FGMETA\tCONVERGENCE_WARNING\t", warning_text, "\n", sep="")
for (variable in names(beta)) {
  cat(
    "FGROW\t", variable, "\t", emit_number(beta[[variable]]), "\t",
    emit_number(exp(beta[[variable]])), "\t",
    emit_number(robust_se[[variable]]), "\t",
    emit_number(ci_lower[[variable]]), "\t",
    emit_number(ci_upper[[variable]]), "\t",
    emit_number(p[[variable]]), "\t", emit_number(z[[variable]]), "\n",
    sep=""
  )
}
'''


def _as_lazy(frame: FrameLike) -> pl.LazyFrame:
    if isinstance(frame, pl.DataFrame):
        return frame.lazy()
    if isinstance(frame, pl.LazyFrame):
        return frame
    raise TypeError("Expected a Polars DataFrame or LazyFrame.")


def validate_fine_gray_input(frame: FrameLike) -> pl.DataFrame:
    """Validate canonical complete-case input without repairing or dropping rows."""
    source = _as_lazy(frame)
    schema = source.collect_schema()
    missing = [name for name in FINE_GRAY_INPUT_DTYPES if name not in schema]
    if missing:
        raise FineGrayModelError(
            f"Fine-Gray input is missing required columns: {missing}."
        )
    mismatches = {
        name: {"expected": str(dtype), "actual": str(schema[name])}
        for name, dtype in FINE_GRAY_INPUT_DTYPES.items()
        if schema[name] != dtype
    }
    if mismatches:
        raise FineGrayModelError(
            f"Fine-Gray input has incompatible column types: {mismatches}."
        )

    expected_code = (
        pl.when(pl.col("event_type") == "DEFAULT")
        .then(pl.lit(1, dtype=pl.Int8))
        .when(pl.col("event_type") == "PREPAYMENT")
        .then(pl.lit(2, dtype=pl.Int8))
        .when(pl.col("event_type") == "CENSOR")
        .then(pl.lit(0, dtype=pl.Int8))
        .otherwise(None)
    )
    valid_event = (
        pl.col("event_type").is_in(["DEFAULT", "PREPAYMENT", "CENSOR"])
        & pl.col("cr_event_code").is_in([0, 1, 2])
        & (pl.col("cr_event_code") == expected_code)
    ).fill_null(False)
    valid_time = (
        pl.col("entry_time_month").is_not_null()
        & pl.col("exit_time_month").is_not_null()
        & pl.col("entry_time_month").cast(pl.Float64).is_finite()
        & pl.col("exit_time_month").cast(pl.Float64).is_finite()
        & (pl.col("entry_time_month") >= 0)
        & (pl.col("exit_time_month") > pl.col("entry_time_month"))
    ).fill_null(False)
    complete_predictors = pl.all_horizontal([
        pl.col(name).is_not_null()
        & pl.col(name).cast(pl.Float64).is_finite().fill_null(False)
        for name in CORE_COLUMNS
    ])
    stats = source.select(
        pl.len().alias("rows"),
        pl.col("loan_id").n_unique().alias("unique_loans"),
        pl.col("loan_id").null_count().alias("missing_loan_id"),
        (~valid_event).sum().alias("invalid_event"),
        (~valid_time).sum().alias("invalid_time"),
        (~complete_predictors).sum().alias("incomplete_predictors"),
        (pl.col("event_type") == "DEFAULT").sum().alias("n_default"),
        (pl.col("event_type") == "PREPAYMENT").sum().alias("n_prepayment"),
    ).collect().to_dicts()[0]

    if stats["rows"] == 0:
        raise FineGrayModelError("Fine-Gray input is empty.")
    if stats["missing_loan_id"]:
        raise FineGrayModelError("Fine-Gray input contains null loan_id values.")
    if stats["rows"] != stats["unique_loans"]:
        raise FineGrayModelError("Fine-Gray input contains duplicate loan_id values.")
    if stats["invalid_event"]:
        raise FineGrayModelError(
            f"Fine-Gray input has {stats['invalid_event']} invalid or inconsistent "
            "event row(s)."
        )
    if stats["invalid_time"]:
        raise FineGrayModelError(
            f"Fine-Gray input has {stats['invalid_time']} invalid entry/exit row(s)."
        )
    if stats["incomplete_predictors"]:
        raise FineGrayModelError(
            f"Fine-Gray input has {stats['incomplete_predictors']} row(s) with "
            "missing or non-finite predictors."
        )
    if stats["n_default"] == 0:
        raise FineGrayModelError("Fine-Gray input must contain DEFAULT events.")
    if stats["n_prepayment"] == 0:
        raise FineGrayModelError(
            "Fine-Gray input must contain PREPAYMENT competing events."
        )
    return source.select(FINE_GRAY_INPUT_COLUMNS).collect()


def _parse_r_output(
    stdout: str,
) -> tuple[list[dict[str, object]], dict[str, str]]:
    rows: list[dict[str, object]] = []
    metadata: dict[str, str] = {}
    for line in stdout.splitlines():
        fields = line.split("\t")
        if len(fields) == 3 and fields[0] == "FGMETA":
            metadata[fields[1]] = fields[2]
        elif len(fields) == 9 and fields[0] == "FGROW":
            try:
                values = [float(value) for value in fields[2:]]
            except ValueError as exc:
                raise FineGrayModelError(
                    "R Fine-Gray output contains a non-numeric estimate."
                ) from exc
            rows.append({
                "model_type": "FINE_GRAY",
                "endpoint": "DEFAULT",
                "variable": fields[1],
                "coefficient": values[0],
                "subdistribution_hazard_ratio": values[1],
                "standard_error": values[2],
                "ci_lower": values[3],
                "ci_upper": values[4],
                "p_value": values[5],
                "z_statistic": values[6],
            })
    required_metadata = {
        "R_VERSION",
        "SURVIVAL_VERSION",
        "N_EXPANDED_ROWS",
        "N_COMPETING_EXTENDED",
        "DELAYED_ENTRY_PRESERVED",
        "INTERVALS_VALID",
        "WEIGHTS_VALID",
        "STATUS_VALID",
        "CLUSTER_MAPPING_VALID",
        "ORDINARY_CENSORING_PRESERVED",
        "CONVERGENCE_WARNING",
    }
    if set(metadata) != required_metadata or len(rows) != len(CORE_COLUMNS):
        raise FineGrayModelError(
            "R Fine-Gray output does not match the locked result protocol."
        )
    return rows, metadata


def fit_fine_gray_default(
    frame: FrameLike,
    confidence_level: float = 0.95,
    rscript: Path | None = None,
) -> FineGrayFitResult:
    """Fit the locked DEFAULT Fine-Gray model using robust clustered inference."""
    if not isinstance(confidence_level, (int, float)) or isinstance(
        confidence_level, bool
    ):
        raise FineGrayModelError("confidence_level must be numeric.")
    if not 0.0 < float(confidence_level) < 1.0:
        raise FineGrayModelError(
            "confidence_level must be strictly between 0 and 1."
        )
    data = validate_fine_gray_input(frame).sort("loan_id")
    executable = rscript or resolve_rscript_path()
    try:
        inspect_r_environment(Path(executable))
    except Exception as exc:
        raise FineGrayModelError(f"R survival engine is unavailable: {exc}") from exc

    expression = R_FINE_GRAY_WORKFLOW.replace(
        "CONFIDENCE_ALPHA", format(1.0 - float(confidence_level), ".17g")
    )
    process = run_rscript_process(
        Path(executable), expression, data.write_csv()
    )
    if process.returncode != 0:
        detail = process.stderr.strip() or process.stdout.strip()
        raise FineGrayModelError(
            f"R Fine-Gray fit failed with exit code {process.returncode}: {detail}"
        )
    if process.stderr.strip():
        raise FineGrayModelError(
            "R Fine-Gray execution wrote unexpected stderr output: "
            f"{process.stderr.strip()}"
        )
    rows, metadata = _parse_r_output(process.stdout)
    coefficients = pl.DataFrame(rows, schema=FINE_GRAY_RESULT_DTYPES)

    counts = data.group_by("event_type").len()
    event_counts = dict(zip(counts["event_type"], counts["len"], strict=True))
    warning_text = metadata["CONVERGENCE_WARNING"]
    diagnostics = pl.DataFrame([{
        "model_type": "FINE_GRAY",
        "endpoint": "DEFAULT",
        "n_input_loans": data.height,
        "n_expanded_rows": int(metadata["N_EXPANDED_ROWS"]),
        "n_default": event_counts.get("DEFAULT", 0),
        "n_prepayment": event_counts.get("PREPAYMENT", 0),
        "n_censored": event_counts.get("CENSOR", 0),
        "n_predictors": len(CORE_COLUMNS),
        "n_delayed_entry": int((data["entry_time_month"] > 0).sum()),
        "variance_type": "subject_clustered_robust_sandwich",
        "r_version": metadata["R_VERSION"],
        "survival_version": metadata["SURVIVAL_VERSION"],
        "convergence_status": "WARNING" if warning_text else "PASS",
        "convergence_warning": warning_text,
    }], schema=FINE_GRAY_DIAGNOSTIC_DTYPES)
    expansion_audit = FineGrayExpansionAudit(
        n_competing_extended=int(metadata["N_COMPETING_EXTENDED"]),
        delayed_entry_preserved=metadata["DELAYED_ENTRY_PRESERVED"] == "TRUE",
        intervals_valid=metadata["INTERVALS_VALID"] == "TRUE",
        weights_valid=metadata["WEIGHTS_VALID"] == "TRUE",
        status_valid=metadata["STATUS_VALID"] == "TRUE",
        cluster_mapping_valid=metadata["CLUSTER_MAPPING_VALID"] == "TRUE",
        ordinary_censoring_preserved=(
            metadata["ORDINARY_CENSORING_PRESERVED"] == "TRUE"
        ),
    )
    result = FineGrayFitResult(coefficients, diagnostics, expansion_audit)
    validate_fine_gray_results(result.coefficients)
    validate_fine_gray_diagnostics(result.diagnostics)
    return result


def _validate_schema(
    frame: FrameLike,
    expected: dict[str, pl.DataType],
    label: str,
) -> pl.DataFrame:
    source = _as_lazy(frame)
    schema = source.collect_schema()
    if schema.names() != list(expected):
        raise FineGrayModelError(
            f"{label} columns do not match canonical order: {list(expected)}."
        )
    mismatches = {
        name: {"expected": str(dtype), "actual": str(schema[name])}
        for name, dtype in expected.items()
        if schema[name] != dtype
    }
    if mismatches:
        raise FineGrayModelError(f"{label} has incompatible types: {mismatches}.")
    return source.collect()


def validate_fine_gray_results(frame: FrameLike) -> pl.DataFrame:
    """Validate the five-row DEFAULT SHR coefficient artifact."""
    data = _validate_schema(frame, FINE_GRAY_RESULT_DTYPES, "Fine-Gray results")
    if (
        data.height != len(CORE_COLUMNS)
        or data["variable"].to_list() != CORE_COLUMNS
        or data["model_type"].unique().to_list() != ["FINE_GRAY"]
        or data["endpoint"].unique().to_list() != ["DEFAULT"]
    ):
        raise FineGrayModelError(
            "Fine-Gray results have invalid identity or predictor rows."
        )
    numeric = data.select(
        pl.exclude("model_type", "endpoint", "variable")
    ).to_numpy()
    valid_limits = data.select(
        (pl.col("subdistribution_hazard_ratio") > 0)
        & (pl.col("ci_lower") > 0)
        & (pl.col("ci_lower") <= pl.col("subdistribution_hazard_ratio"))
        & (pl.col("subdistribution_hazard_ratio") <= pl.col("ci_upper"))
        & pl.col("p_value").is_between(0.0, 1.0)
        & (pl.col("standard_error") > 0)
    ).to_series()
    if not np.isfinite(numeric).all() or not valid_limits.all():
        raise FineGrayModelError(
            "Fine-Gray results contain invalid or non-finite estimates."
        )
    return data


def validate_fine_gray_diagnostics(frame: FrameLike) -> pl.DataFrame:
    """Validate one supported Fine-Gray diagnostic row."""
    data = _validate_schema(
        frame, FINE_GRAY_DIAGNOSTIC_DTYPES, "Fine-Gray diagnostics"
    )
    if data.height != 1:
        raise FineGrayModelError(
            "Fine-Gray diagnostics must contain exactly one row."
        )
    row = data.row(0, named=True)
    if row["model_type"] != "FINE_GRAY" or row["endpoint"] != "DEFAULT":
        raise FineGrayModelError("Fine-Gray diagnostic identity is invalid.")
    if (
        row["n_default"] + row["n_prepayment"] + row["n_censored"]
        != row["n_input_loans"]
    ):
        raise FineGrayModelError("Fine-Gray diagnostic counts are inconsistent.")
    if row["n_expanded_rows"] < row["n_input_loans"]:
        raise FineGrayModelError("Fine-Gray expanded-row count is invalid.")
    if row["n_predictors"] != len(CORE_COLUMNS):
        raise FineGrayModelError("Fine-Gray predictor count is inconsistent.")
    if row["n_delayed_entry"] > row["n_input_loans"]:
        raise FineGrayModelError("Fine-Gray delayed-entry count is invalid.")
    if row["variance_type"] != "subject_clustered_robust_sandwich":
        raise FineGrayModelError("Fine-Gray variance type is invalid.")
    if row["convergence_status"] not in {"PASS", "WARNING"}:
        raise FineGrayModelError("Fine-Gray convergence status is invalid.")
    if row["convergence_status"] == "PASS" and row["convergence_warning"]:
        raise FineGrayModelError("PASS diagnostics cannot contain a warning.")
    if not row["r_version"] or not row["survival_version"]:
        raise FineGrayModelError("Fine-Gray runtime versions are missing.")
    return data


def write_fine_gray_results(
    result: FineGrayFitResult,
    coefficients_path: PathSource,
    diagnostics_path: PathSource,
) -> tuple[Path, Path]:
    """Validate and atomically write DEFAULT Fine-Gray artifacts."""
    if not isinstance(result, FineGrayFitResult):
        raise FineGrayModelError("result must be a FineGrayFitResult.")
    coefficients = validate_fine_gray_results(result.coefficients)
    diagnostics = validate_fine_gray_diagnostics(result.diagnostics)
    outputs = (Path(coefficients_path), Path(diagnostics_path))
    temporary_paths: list[Path] = []
    try:
        for output_frame, output in zip(
            (coefficients, diagnostics), outputs, strict=True
        ):
            output.parent.mkdir(parents=True, exist_ok=True)
            temporary = output.with_suffix(".tmp.parquet")
            output_frame.write_parquet(temporary, compression="zstd")
            temporary_paths.append(temporary)
        for temporary, output in zip(temporary_paths, outputs, strict=True):
            temporary.replace(output)
    finally:
        for temporary in temporary_paths:
            temporary.unlink(missing_ok=True)
    return outputs
