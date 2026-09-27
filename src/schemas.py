import polars as pl


# =========================================================
# ORIGINATION FILE - 31 CỘT
# =========================================================

ORIG_COLUMNS = [
    "fico",
    "first_payment_date",
    "first_time_homebuyer",
    "maturity_date",
    "msa",
    "mi_percentage",
    "number_units",
    "occupancy_status",
    "original_cltv",
    "original_dti",
    "original_upb",
    "original_ltv",
    "original_interest_rate",
    "channel",
    "prepayment_penalty",
    "amortization_type",
    "property_state",
    "property_type",
    "postal_code",
    "loan_id",
    "loan_purpose",
    "original_loan_term",
    "number_borrowers",
    "seller_name",
    "super_conforming_flag",
    "pre_harp_loan_id",
    "special_eligibility_program",
    "harp_indicator",
    "property_valuation_method",
    "interest_only_indicator",
    "vantagescore_4",
]


# =========================================================
# CÁC CỘT ORIGINATION GIỮ LẠI
# =========================================================

KEEP_ORIG_COLUMNS = [
    "loan_id",
    "fico",
    "first_payment_date",
    "maturity_date",
    "original_cltv",
    "original_dti",
    "original_upb",
    "original_ltv",
    "original_interest_rate",
    "occupancy_status",
    "amortization_type",
    "property_state",
    "property_type",
    "loan_purpose",
    "original_loan_term",
    "number_borrowers",
    "vantagescore_4",
]


# =========================================================
# PERFORMANCE FILE - 35 CỘT
# =========================================================

PERF_COLUMNS = [
    "loan_id",
    "monthly_reporting_period",
    "current_actual_upb",
    "delinquency_status",
    "loan_age",
    "remaining_months_maturity",
    "defect_settlement_date",
    "modification_flag",
    "zero_balance_code",
    "zero_balance_effective_date",
    "current_interest_rate",
    "current_non_interest_bearing_upb",
    "ddlpi",
    "mi_recoveries",
    "net_sales_proceeds",
    "non_mi_recoveries",
    "total_expenses",
    "legal_costs",
    "maintenance_preservation_costs",
    "taxes_insurance",
    "misc_expenses",
    "actual_loss",
    "cumulative_modification_costs",
    "interest_rate_step_indicator",
    "payment_deferral_flag",
    "estimated_ltv",
    "zero_balance_removal_upb",
    "delinquent_accrued_interest",
    "delinquency_due_to_disaster",
    "borrower_assistance_plan",
    "current_period_modification_costs",
    "current_interest_bearing_upb",
    "mi_cancellation_indicator",
    "servicer_name",
    "bankruptcy_cramdown_costs",
]


# =========================================================
# CÁC CỘT PERFORMANCE GIỮ LẠI
# =========================================================

KEEP_PERF_COLUMNS = [
    "loan_id",
    "monthly_reporting_period",
    "current_actual_upb",
    "delinquency_status",
    "loan_age",
    "remaining_months_maturity",
    "modification_flag",
    "zero_balance_code",
    "zero_balance_effective_date",
    "current_interest_rate",
    "ddlpi",
    "payment_deferral_flag",
    "estimated_ltv",
    "delinquency_due_to_disaster",
    "borrower_assistance_plan",
    "current_interest_bearing_upb",
]


# =========================================================
# INGEST SCHEMA
# =========================================================
#
# Ở bước đọc dữ liệu, giữ tất cả dưới dạng String.
# Cleaning và convert numeric sẽ làm ở bước sau.
# =========================================================

ORIG_SCHEMA = {
    column: pl.String
    for column in ORIG_COLUMNS
}

PERF_SCHEMA = {
    column: pl.String
    for column in PERF_COLUMNS
}


# =========================================================
# EXPECTED FIELD COUNTS
# =========================================================

EXPECTED_ORIG_FIELDS = 31
EXPECTED_PERF_FIELDS = 35


# =========================================================
# CONSISTENCY CHECKS
# =========================================================

assert len(ORIG_COLUMNS) == EXPECTED_ORIG_FIELDS, (
    f"ORIG_COLUMNS phải có 31 cột, "
    f"hiện có {len(ORIG_COLUMNS)}."
)

assert len(PERF_COLUMNS) == EXPECTED_PERF_FIELDS, (
    f"PERF_COLUMNS phải có 35 cột, "
    f"hiện có {len(PERF_COLUMNS)}."
)

assert set(KEEP_ORIG_COLUMNS).issubset(
    set(ORIG_COLUMNS)
), "KEEP_ORIG_COLUMNS chứa cột không hợp lệ."

assert set(KEEP_PERF_COLUMNS).issubset(
    set(PERF_COLUMNS)
), "KEEP_PERF_COLUMNS chứa cột không hợp lệ."