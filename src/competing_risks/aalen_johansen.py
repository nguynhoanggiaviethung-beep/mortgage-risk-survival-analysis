"""Aalen-Johansen cumulative incidence with delayed entry.

The estimator is R ``survival::survfit`` on a multi-state counting-process
``Surv(entry_time_month, exit_time_month, factor(cause))`` object. This engine
handles exact tied monthly event times without lifelines' random jitter.
"""

from __future__ import annotations

from os import PathLike
from pathlib import Path
from typing import TypeAlias

import numpy as np
import polars as pl

from src.r_runtime import run_rscript_process
from src.survival.ph_test import inspect_r_environment, resolve_rscript_path


FrameLike: TypeAlias = pl.DataFrame | pl.LazyFrame
PathSource: TypeAlias = str | PathLike[str]

AJ_INPUT_DTYPES: dict[str, pl.DataType] = {
    "loan_id": pl.String,
    "vintage_year": pl.Int16,
    "entry_time_month": pl.Int32,
    "exit_time_month": pl.Int32,
    "duration_months": pl.Int32,
    "cr_event_code": pl.Int8,
    "event_type": pl.String,
}
AJ_RESULT_DTYPES: dict[str, pl.DataType] = {
    "model_type": pl.String,
    "endpoint": pl.String,
    "group_name": pl.String,
    "group_value": pl.String,
    "analysis_time": pl.Int32,
    "cumulative_incidence": pl.Float64,
    "ci_lower": pl.Float64,
    "ci_upper": pl.Float64,
    "n_at_risk": pl.UInt32,
}
AJ_RESULT_COLUMNS = list(AJ_RESULT_DTYPES)
ENDPOINTS = ("DEFAULT", "PREPAYMENT")


class AalenJohansenError(ValueError):
    """Raised when AJ input, engine execution, or output is invalid."""


R_AJ_WORKFLOW = r'''
suppressPackageStartupMessages(library(survival))

d <- utils::read.csv(file("stdin"), stringsAsFactors=FALSE,
                     check.names=FALSE)
required <- c("loan_id", "entry_time_month", "exit_time_month",
              "cr_event_code")
if (!identical(names(d), required)) {
  stop("AJ input columns or order do not match the locked contract.")
}
if (anyDuplicated(d$loan_id)) stop("AJ input contains duplicate loan IDs.")
if (any(!d$cr_event_code %in% c(0L, 1L, 2L))) {
  stop("AJ input contains an unknown cause code.")
}

d$status <- factor(
  d$cr_event_code,
  levels=c(0L, 1L, 2L),
  labels=c("censor", "default", "prepayment")
)
y <- survival::Surv(d$entry_time_month, d$exit_time_month, d$status)
if (!identical(attr(y, "type"), "mcounting")) {
  stop("R survival did not construct a multi-state counting-process Surv.")
}
fit <- survival::survfit(
  y ~ 1,
  data=d,
  id=loan_id,
  conf.type="log-log",
  conf.int=CONFIDENCE_LEVEL
)
expected_states <- c("(s0)", "default", "prepayment")
if (!inherits(fit, "survfitms") || !identical(fit$states, expected_states)) {
  stop("Unexpected Aalen-Johansen states returned by survival::survfit.")
}
if (is.null(fit$lower) || is.null(fit$upper)) {
  stop("Aalen-Johansen confidence intervals were not returned.")
}

emit_number <- function(x) sprintf("%.17g", x)
cat("AJMETA\tR_VERSION\t", R.version.string, "\n", sep="")
cat("AJMETA\tSURVIVAL_VERSION\t",
    as.character(utils::packageVersion("survival")), "\n", sep="")
for (i in seq_along(fit$time)) {
  for (state_index in 2:3) {
    endpoint <- if (state_index == 2) "DEFAULT" else "PREPAYMENT"
    cat("AJROW\t", endpoint, "\t", emit_number(fit$time[[i]]), "\t",
        emit_number(fit$pstate[i, state_index]), "\t",
        emit_number(fit$lower[i, state_index]), "\t",
        emit_number(fit$upper[i, state_index]), "\t",
        as.integer(fit$n.risk[i, 1]), "\n", sep="")
  }
}
'''


def _as_lazy(frame: FrameLike) -> pl.LazyFrame:
    if isinstance(frame, pl.DataFrame):
        return frame.lazy()
    if isinstance(frame, pl.LazyFrame):
        return frame
    raise TypeError("Expected a Polars DataFrame or LazyFrame.")


def validate_aalen_johansen_input(
    frame: FrameLike,
    group_col: str | None = None,
) -> pl.DataFrame:
    """Validate canonical one-row-per-loan competing-risk input."""
    source = _as_lazy(frame)
    schema = source.collect_schema()
    missing = [name for name in AJ_INPUT_DTYPES if name not in schema]
    if missing:
        raise AalenJohansenError(f"AJ input is missing required columns: {missing}.")
    mismatches = {
        name: {"expected": str(dtype), "actual": str(schema[name])}
        for name, dtype in AJ_INPUT_DTYPES.items()
        if schema[name] != dtype
    }
    if mismatches:
        raise AalenJohansenError(f"AJ input has incompatible types: {mismatches}.")
    if group_col is not None and group_col not in schema:
        raise AalenJohansenError(f"Grouping column does not exist: {group_col!r}.")

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
        & pl.col("duration_months").is_not_null()
        & (pl.col("entry_time_month") >= 0)
        & (pl.col("exit_time_month") > pl.col("entry_time_month"))
        & (pl.col("duration_months") == pl.col("exit_time_month"))
    ).fill_null(False)
    expressions: list[pl.Expr] = [
        pl.len().alias("rows"),
        pl.col("loan_id").n_unique().alias("unique_loans"),
        pl.col("loan_id").null_count().alias("missing_loan_id"),
        (~valid_event).sum().alias("invalid_event"),
        (~valid_time).sum().alias("invalid_time"),
        (pl.col("cr_event_code") > 0).sum().alias("events"),
    ]
    if group_col is not None:
        expressions.append(pl.col(group_col).null_count().alias("missing_group"))
    stats = source.select(expressions).collect().to_dicts()[0]
    if stats["rows"] == 0:
        raise AalenJohansenError("AJ input is empty.")
    if stats["missing_loan_id"]:
        raise AalenJohansenError("AJ input contains null loan_id values.")
    if stats["rows"] != stats["unique_loans"]:
        raise AalenJohansenError("AJ input contains duplicate loan_id values.")
    if stats["invalid_event"]:
        raise AalenJohansenError(
            f"AJ input has {stats['invalid_event']} inconsistent event row(s)."
        )
    if stats["invalid_time"]:
        raise AalenJohansenError(
            f"AJ input has {stats['invalid_time']} invalid entry/exit/duration row(s)."
        )
    if stats["events"] == 0:
        raise AalenJohansenError("AJ input must contain at least one research event.")
    if group_col is not None and stats["missing_group"]:
        raise AalenJohansenError(f"Grouping column {group_col!r} contains null values.")
    return source.collect()


def _run_r_aalen_johansen(
    data: pl.DataFrame,
    confidence_level: float,
    rscript: Path,
) -> list[dict[str, object]]:
    expression = R_AJ_WORKFLOW.replace(
        "CONFIDENCE_LEVEL", format(confidence_level, ".17g")
    )
    csv_input = data.select(
        "loan_id", "entry_time_month", "exit_time_month", "cr_event_code"
    ).write_csv()
    process = run_rscript_process(rscript, expression, csv_input)
    if process.returncode != 0:
        detail = process.stderr.strip() or process.stdout.strip()
        raise AalenJohansenError(
            f"R Aalen-Johansen failed with exit code {process.returncode}: {detail}"
        )
    if process.stderr.strip():
        raise AalenJohansenError(
            f"R Aalen-Johansen emitted warnings/errors: {process.stderr.strip()}"
        )

    rows: list[dict[str, object]] = []
    metadata: dict[str, str] = {}
    for line in process.stdout.splitlines():
        fields = line.split("\t")
        if len(fields) == 3 and fields[0] == "AJMETA":
            metadata[fields[1]] = fields[2]
        elif len(fields) == 7 and fields[0] == "AJROW":
            analysis_time_float = float(fields[2])
            if not analysis_time_float.is_integer():
                raise AalenJohansenError("AJ engine returned non-monthly analysis time.")
            rows.append({
                "endpoint": fields[1],
                "analysis_time": int(analysis_time_float),
                "cumulative_incidence": float(fields[3]),
                "ci_lower": float(fields[4]),
                "ci_upper": float(fields[5]),
                "n_at_risk": int(fields[6]),
            })
        elif line:
            raise AalenJohansenError(f"Unexpected R AJ output: {line}")
    if set(metadata) != {"R_VERSION", "SURVIVAL_VERSION"} or not rows:
        raise AalenJohansenError("R AJ output is missing metadata or estimates.")
    return rows


def _fit_one_group(
    data: pl.DataFrame,
    group_name: str,
    group_value: str,
    confidence_level: float,
    rscript: Path,
) -> pl.DataFrame:
    rows = _run_r_aalen_johansen(data, confidence_level, rscript)
    enriched = [
        {
            "model_type": "AALEN_JOHANSEN",
            "endpoint": row["endpoint"],
            "group_name": group_name,
            "group_value": group_value,
            "analysis_time": row["analysis_time"],
            "cumulative_incidence": row["cumulative_incidence"],
            "ci_lower": row["ci_lower"],
            "ci_upper": row["ci_upper"],
            "n_at_risk": row["n_at_risk"],
        }
        for row in rows
    ]
    return pl.DataFrame(enriched, schema=AJ_RESULT_DTYPES)


def fit_aalen_johansen(
    frame: FrameLike,
    group_col: str | None = None,
    confidence_level: float = 0.95,
    rscript: Path | None = None,
) -> pl.DataFrame:
    """Estimate DEFAULT and PREPAYMENT CIFs with delayed entry and exact ties."""
    if not isinstance(confidence_level, (int, float)) or isinstance(
        confidence_level, bool
    ):
        raise AalenJohansenError("confidence_level must be numeric.")
    if not 0.0 < float(confidence_level) < 1.0:
        raise AalenJohansenError(
            "confidence_level must be strictly between 0 and 1."
        )
    data = validate_aalen_johansen_input(frame, group_col=group_col)
    executable = rscript or resolve_rscript_path()
    try:
        inspect_r_environment(Path(executable))
    except Exception as exc:
        raise AalenJohansenError(f"R survival engine is unavailable: {exc}") from exc

    if group_col is None:
        result = _fit_one_group(
            data, "portfolio", "all", float(confidence_level), Path(executable)
        )
    else:
        results = [
            _fit_one_group(
                group,
                group_col,
                str(group[group_col][0]),
                float(confidence_level),
                Path(executable),
            )
            for group in data.sort(group_col).partition_by(
                group_col, maintain_order=True
            )
        ]
        result = pl.concat(results)
    return validate_aalen_johansen_results(
        result.sort(["group_value", "analysis_time", "endpoint"])
    )


def validate_aalen_johansen_results(frame: FrameLike) -> pl.DataFrame:
    """Validate long-format paired CIF estimates and mathematical bounds."""
    source = _as_lazy(frame)
    schema = source.collect_schema()
    if schema.names() != AJ_RESULT_COLUMNS:
        raise AalenJohansenError(
            f"AJ result columns do not match canonical order: {AJ_RESULT_COLUMNS}."
        )
    mismatches = {
        name: {"expected": str(dtype), "actual": str(schema[name])}
        for name, dtype in AJ_RESULT_DTYPES.items()
        if schema[name] != dtype
    }
    if mismatches:
        raise AalenJohansenError(f"AJ result has incompatible types: {mismatches}.")
    data = source.collect()
    if data.height == 0:
        raise AalenJohansenError("AJ result is empty.")
    if data["model_type"].unique().to_list() != ["AALEN_JOHANSEN"]:
        raise AalenJohansenError("AJ model_type is invalid.")
    if set(data["endpoint"].unique()) != set(ENDPOINTS):
        raise AalenJohansenError("AJ result must contain both canonical endpoints.")
    valid = data.select(
        pl.all_horizontal([
            pl.col(name).is_not_null() & pl.col(name).is_finite()
            for name in ("cumulative_incidence", "ci_lower", "ci_upper")
        ]).alias("finite"),
        (
            pl.col("cumulative_incidence").is_between(0.0, 1.0)
            & pl.col("ci_lower").is_between(0.0, 1.0)
            & pl.col("ci_upper").is_between(0.0, 1.0)
            & (pl.col("ci_lower") <= pl.col("cumulative_incidence"))
            & (pl.col("cumulative_incidence") <= pl.col("ci_upper"))
        ).alias("bounded"),
        ((pl.col("analysis_time") >= 0) & (pl.col("n_at_risk") > 0))
        .alias("valid_time_and_risk"),
    ).to_numpy()
    if not valid.all():
        raise AalenJohansenError("AJ result contains invalid estimates or counts.")

    key_columns = ["group_name", "group_value", "analysis_time"]
    paired = data.pivot(
        on="endpoint",
        index=key_columns,
        values="cumulative_incidence",
    )
    if paired.height * 2 != data.height or paired.null_count().to_numpy().any():
        raise AalenJohansenError("AJ result does not contain paired endpoint rows.")
    if ((paired["DEFAULT"] + paired["PREPAYMENT"]) > 1.0 + 1e-12).any():
        raise AalenJohansenError("Paired CIF values exceed one.")
    for group in data.partition_by(["group_name", "group_value"]):
        for endpoint in ENDPOINTS:
            values = (
                group.filter(pl.col("endpoint") == endpoint)
                .sort("analysis_time")["cumulative_incidence"]
                .to_numpy()
            )
            if np.any(np.diff(values) < -1e-12):
                raise AalenJohansenError(f"{endpoint} CIF is not non-decreasing.")
    return data


def write_aalen_johansen_results(frame: FrameLike, path: PathSource) -> Path:
    """Validate and atomically write the AJ result artifact."""
    result = validate_aalen_johansen_results(frame)
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".tmp.parquet")
    try:
        result.write_parquet(temporary, compression="zstd")
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    return output
