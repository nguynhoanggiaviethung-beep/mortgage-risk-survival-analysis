"""Deterministic fixtures dedicated to Step 5A tests."""

from __future__ import annotations

from datetime import date

import numpy as np
import polars as pl

from src.survival.model_input import LOAN_LEVEL_DTYPES
from src.survival.time_varying_input import TIME_VARYING_INPUT_DTYPES


FITTER_SEED = 20260928


def _add_months(value: date, months: int) -> date:
    index = value.year * 12 + value.month - 1 + months
    return date(index // 12, index % 12 + 1, 1)


def build_interval_source_fixture() -> tuple[pl.DataFrame, pl.DataFrame]:
    """Return a small source pair for exact interval-construction tests."""
    specifications = [
        ("L_DEFAULT", "DEFAULT", 1, 0, 3, 202001, 202004),
        ("L_PREPAY", "PREPAYMENT", 2, 2, 4, 202003, 202005),
        ("L_CENSOR_GAP", "CENSOR", 0, 0, 3, 202001, 202004),
        ("L_AFTER_LAST", "DEFAULT", 1, 0, 3, 202001, 202004),
    ]
    loans = []
    for index, (
        loan_id,
        event_type,
        event_code,
        entry,
        exit_time,
        first_observed,
        event_month,
    ) in enumerate(specifications):
        is_default = int(event_type == "DEFAULT")
        is_prepayment = int(event_type == "PREPAYMENT")
        loans.append({
            "loan_id": loan_id,
            "vintage_year": 2020,
            "entry_time_month": entry,
            "exit_time_month": exit_time,
            "duration_months": exit_time,
            "event_type": event_type,
            "event_code": event_code,
            "survival_eligible": True,
            "default_event": is_default,
            "prepayment_event": is_prepayment,
            "competing_event_code": event_code,
            "fico": 690 + 10 * index,
            "original_ltv": 70.0 + index,
            "original_dti": 30.0 + index,
            "original_interest_rate": 3.0 + 0.1 * index,
            "original_loan_term": 360,
            "core_covariates_complete_flag": True,
            "km_default_event": is_default,
            "km_prepayment_event": is_prepayment,
            "cr_event_code": event_code,
            "first_observed_month": first_observed,
            "event_month": event_month,
            "operational_origination_date": date(2020, 1, 1),
        })
    loan_schema = {
        **LOAN_LEVEL_DTYPES,
        "first_observed_month": pl.Int32,
        "event_month": pl.Int32,
        "operational_origination_date": pl.Date,
    }
    loan_level = pl.DataFrame(loans, schema=loan_schema)

    monthly_rows = []
    performance = {
        "L_DEFAULT": [
            (date(2020, 1, 1), 200_000.0, 3.00, "00"),
            (date(2020, 2, 1), 198_000.0, 3.00, "01"),
            (date(2020, 3, 1), 196_000.0, 3.00, "03"),
            # Same-month terminal values must never enter the intervals.
            (date(2020, 4, 1), 0.0, 9.00, "88"),
        ],
        "L_PREPAY": [
            (date(2020, 3, 1), 180_000.0, 3.10, "00"),
            (date(2020, 4, 1), 177_000.0, 3.10, "XX"),
            (date(2020, 5, 1), 0.0, 3.10, "RA"),
        ],
        "L_CENSOR_GAP": [
            (date(2020, 1, 1), 160_000.0, 3.20, "00"),
            (date(2020, 3, 1), 158_000.0, 3.20, "02"),
            (date(2020, 4, 1), 157_000.0, 3.20, "00"),
        ],
        "L_AFTER_LAST": [
            (date(2020, 1, 1), 140_000.0, 3.30, "RA"),
            (date(2020, 2, 1), 138_000.0, 3.30, "00"),
        ],
    }
    for loan_id, observations in performance.items():
        for month, upb, rate, status in observations:
            monthly_rows.append({
                "loan_id": loan_id,
                "performance_month": month,
                "reporting_period_num": month.year * 100 + month.month,
                "current_actual_upb": upb,
                "current_interest_rate": rate,
                "current_delinquency_status": status,
            })
    performance_frame = pl.DataFrame(
        monthly_rows,
        schema={
            "loan_id": pl.String,
            "performance_month": pl.Date,
            "reporting_period_num": pl.Int32,
            "current_actual_upb": pl.Float64,
            "current_interest_rate": pl.Float64,
            "current_delinquency_status": pl.String,
        },
    )
    return performance_frame, loan_level


def build_fitter_fixture(
    seed: int = FITTER_SEED,
    n_loans: int = 420,
) -> pl.DataFrame:
    """Return a full-rank interval fixture with events and no separation."""
    rng = np.random.default_rng(seed)
    event_labels = np.array(["DEFAULT", "PREPAYMENT", "CENSOR"])
    statuses = np.array(["00", "01", "02", "03", "XX", "RA"])
    status_probabilities = np.array([0.40, 0.12, 0.12, 0.16, 0.10, 0.10])
    origin = date(2020, 1, 1)
    rows = []

    for loan_number in range(n_loans):
        loan_id = f"TV{loan_number:04d}"
        event_type = str(event_labels[loan_number % len(event_labels)])
        entry = 1 if loan_number % 5 == 0 else 0
        interval_lengths = [1, 2, 1, 1] if loan_number % 13 == 0 else [1, 1, 1, 1]
        starts = [entry]
        for length in interval_lengths[:-1]:
            starts.append(starts[-1] + length)

        fico = int(rng.integers(560, 821))
        original_ltv = float(rng.uniform(45.0, 110.0))
        original_dti = float(rng.uniform(8.0, 58.0))
        original_rate = float(rng.uniform(2.0, 7.5))
        original_term = int(rng.choice([180, 240, 300, 360]))
        original_upb = float(rng.uniform(90_000.0, 700_000.0))

        for interval_number, (start, length) in enumerate(
            zip(starts, interval_lengths, strict=True)
        ):
            stop = start + length
            terminal = interval_number == len(interval_lengths) - 1
            status = str(rng.choice(statuses, p=status_probabilities))
            indicators = {
                "lag_dq_1m": int(status == "01"),
                "lag_dq_2m": int(status == "02"),
                "lag_dq_3plus": int(status == "03"),
                "lag_dq_xx": int(status == "XX"),
                "lag_dq_ra": int(status == "RA"),
            }
            month = _add_months(origin, start)
            rows.append({
                "loan_id": loan_id,
                "vintage_year": 2020,
                "covariate_month": month,
                "source_reporting_period_num": month.year * 100 + month.month,
                "start_time_month": start,
                "stop_time_month": stop,
                "interval_length_months": length,
                "gap_interval_flag": length > 1,
                "terminal_interval_flag": terminal,
                "default_event": int(terminal and event_type == "DEFAULT"),
                "event_type": event_type,
                "fico": fico,
                "original_ltv": original_ltv,
                "original_dti": original_dti,
                "original_interest_rate": original_rate,
                "original_loan_term": original_term,
                "lag_current_actual_upb": max(
                    1_000.0,
                    original_upb * (1.0 - 0.018 * interval_number)
                    + float(rng.normal(0.0, 500.0)),
                ),
                "lag_current_interest_rate": original_rate
                + float(rng.normal(0.0, 0.12)),
                **indicators,
            })

    return pl.DataFrame(rows, schema=TIME_VARYING_INPUT_DTYPES)
