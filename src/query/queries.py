"""Stable, read-only query functions over canonical and published data."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import polars as pl

from src.production.contracts import INPUT_CONTRACTS
from src.results.dashboard import (
    model_diagnostics,
    pd_results,
    portfolio_summary,
    resolve_dashboard_release,
    risk_driver_results,
    survival_results,
    vintage_results,
)
from src.results.manifest import PathSource


class QueryStatus(str, Enum):
    OK = "OK"
    NOT_FOUND = "NOT_FOUND"
    EMPTY = "EMPTY"


@dataclass(frozen=True)
class QueryResponse:
    status: QueryStatus
    data: pl.DataFrame
    provenance: dict[str, str]

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "data": self.data.to_dicts(),
            "provenance": dict(self.provenance),
        }


PROFILE_SCHEMA = {
    "loan_id": pl.String,
    "fico": pl.Int16,
    "original_ltv": pl.Float64,
    "original_cltv": pl.Float64,
    "original_dti": pl.Float64,
    "original_upb": pl.Float64,
    "original_interest_rate": pl.Float64,
    "original_loan_term": pl.Int16,
    "loan_purpose": pl.String,
    "occupancy_status": pl.String,
    "property_state": pl.String,
    "property_type": pl.String,
    "first_payment_month": pl.Date,
    "maturity_month": pl.Date,
    "operational_origination_date": pl.Date,
    "vintage_year": pl.Int16,
    "event_type": pl.String,
    "event_code": pl.Int8,
    "event_source": pl.String,
    "event_date": pl.Date,
    "default_flag": pl.Boolean,
    "prepayment_flag": pl.Boolean,
    "censor_flag": pl.Boolean,
    "entry_time_month": pl.Int32,
    "exit_time_month": pl.Int32,
    "duration_months": pl.Int32,
    "survival_eligible": pl.Boolean,
}

TIMELINE_SCHEMA = {
    "loan_id": pl.String,
    "monthly_reporting_period": pl.String,
    "reporting_month": pl.Date,
    "performance_month": pl.Date,
    "loan_age": pl.Int16,
    "freddie_loan_age": pl.Int16,
    "current_actual_upb": pl.Float64,
    "current_interest_bearing_upb": pl.Float64,
    "delinquency_status_raw": pl.String,
    "current_delinquency_status": pl.String,
    "delinquency_num": pl.Int16,
    "current_interest_rate": pl.Float64,
    "remaining_months_maturity": pl.Int16,
    "modification_flag": pl.String,
    "payment_deferral_flag": pl.String,
    "borrower_assistance_plan": pl.String,
    "delinquency_due_to_disaster": pl.String,
    "zero_balance_code": pl.String,
    "zero_balance_effective_date": pl.Date,
    "zero_balance_effective_month": pl.Date,
    "estimated_ltv": pl.Float64,
    "estimated_ltv_raw": pl.String,
    "ddlpi": pl.String,
    "ddlpi_month": pl.Date,
}


def _provenance(release, source: str) -> dict[str, str]:
    return {
        "source": source,
        "run_id": release.manifest.run_id,
        "code_commit": release.manifest.code_commit,
        "data_version": release.manifest.data_version,
        "specification_version": release.manifest.specification_version,
    }


def _safe_frame(frame: pl.DataFrame, schema: dict[str, pl.DataType]) -> pl.DataFrame:
    output = frame
    for name, dtype in schema.items():
        if name not in output.columns:
            output = output.with_columns(pl.lit(None, dtype=dtype).alias(name))
        else:
            output = output.with_columns(pl.col(name).cast(dtype).alias(name))
    for name, dtype in schema.items():
        if dtype == pl.Float64 and output.filter(
            pl.col(name).is_nan() | pl.col(name).is_infinite()
        ).height:
            raise ValueError(f"Query result contains non-finite values: {name}")
    return output.select(list(schema))


def _empty(schema: dict[str, pl.DataType]) -> pl.DataFrame:
    return pl.DataFrame(schema=schema)


def _dashboard_response(repository_root: PathSource, builder) -> QueryResponse:
    release = resolve_dashboard_release(repository_root)
    return QueryResponse(
        QueryStatus.OK,
        builder(release),
        _provenance(release, "published_production_release"),
    )


def get_portfolio_summary(repository_root: PathSource = ".") -> QueryResponse:
    return _dashboard_response(repository_root, portfolio_summary)


def get_pd_results(repository_root: PathSource = ".") -> QueryResponse:
    return _dashboard_response(repository_root, pd_results)


def get_survival_results(repository_root: PathSource = ".") -> QueryResponse:
    return _dashboard_response(repository_root, survival_results)


def get_risk_driver_results(repository_root: PathSource = ".") -> QueryResponse:
    return _dashboard_response(repository_root, risk_driver_results)


def get_vintage_results(repository_root: PathSource = ".") -> QueryResponse:
    return _dashboard_response(repository_root, vintage_results)


def get_model_diagnostics(repository_root: PathSource = ".") -> QueryResponse:
    return _dashboard_response(repository_root, model_diagnostics)


def get_loan_profile(
    loan_id: str, repository_root: PathSource = "."
) -> QueryResponse:
    release = resolve_dashboard_release(repository_root)
    if not loan_id:
        return QueryResponse(
            QueryStatus.EMPTY, _empty(PROFILE_SCHEMA), _provenance(release, "analysis_loans")
        )
    path = Path(repository_root) / INPUT_CONTRACTS["analysis_loans"].relative_path
    result = (
        pl.scan_parquet(path)
        .filter(pl.col("loan_id") == loan_id)
        .select(list(PROFILE_SCHEMA))
        .collect()
    )
    if result.height == 0:
        return QueryResponse(
            QueryStatus.NOT_FOUND, _empty(PROFILE_SCHEMA), _provenance(release, "analysis_loans")
        )
    if result.height != 1:
        raise ValueError(f"Canonical loan profile is not unique: {loan_id}")
    return QueryResponse(
        QueryStatus.OK,
        _safe_frame(result, PROFILE_SCHEMA),
        _provenance(release, "analysis_loans"),
    )


def get_loan_timeline(
    loan_id: str, repository_root: PathSource = "."
) -> QueryResponse:
    release = resolve_dashboard_release(repository_root)
    provenance = _provenance(release, "performance")
    if not loan_id:
        return QueryResponse(QueryStatus.EMPTY, _empty(TIMELINE_SCHEMA), provenance)
    path = Path(repository_root) / INPUT_CONTRACTS["performance"].relative_path
    result = (
        pl.scan_parquet(path)
        .filter(pl.col("loan_id") == loan_id)
        .select(list(TIMELINE_SCHEMA))
        .sort("performance_month")
        .collect()
    )
    if result.height == 0:
        return QueryResponse(QueryStatus.NOT_FOUND, _empty(TIMELINE_SCHEMA), provenance)
    return QueryResponse(
        QueryStatus.OK,
        _safe_frame(result, TIMELINE_SCHEMA),
        provenance,
    )


__all__ = [
    "PROFILE_SCHEMA",
    "TIMELINE_SCHEMA",
    "QueryResponse",
    "QueryStatus",
    "get_loan_profile",
    "get_loan_timeline",
    "get_model_diagnostics",
    "get_pd_results",
    "get_portfolio_summary",
    "get_risk_driver_results",
    "get_survival_results",
    "get_vintage_results",
]