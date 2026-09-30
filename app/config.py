"""Display labels, colors, and typography for the dashboard UI."""

APP_TITLE = "Phân tích rủi ro khoản vay thế chấp"
APP_SUBTITLE = "Mortgage Default & Prepayment · Survival Analysis"

# ---- Bảng màu tài chính ấm: xanh rêu, giấy ngà, vàng đồng -------------------
PRIMARY = "#526F5B"          # xanh rêu cho các yếu tố điều hướng / phân tích
PRIMARY_DARK = "#293A32"     # xanh rừng cho tiêu đề và sidebar
ACCENT = "#E8E1CD"           # nền vàng ngà
ACCENT_STRONG = "#B99B53"    # vàng đồng

TEXT_MAIN = "#303A34"
TEXT_MUTED = "#7B8178"

SUCCESS = "#64816A"
WARNING = "#B08C45"
DANGER = "#AD6254"

CHART_SEQUENCE = [PRIMARY_DARK, PRIMARY, ACCENT_STRONG, "#83977E", WARNING, DANGER]

FONT_STACK = "'Lora',Georgia,serif"
DISPLAY_FONT_STACK = "'Lora',Georgia,serif"

# ---- Nhãn hiển thị dùng chung ----------------------------------------------
HORIZON_OPTIONS = [12, 24, 36, 60]

EVENT_LABELS = {
    "DEFAULT": "Default",
    "VOLUNTARY_PREPAYMENT": "Voluntary Prepayment (ZBC 01)",
    "CENSORED": "Censored",
}

MODEL_TYPE_OPTIONS = [
    "Kaplan-Meier",
    "Cox PH",
    "Time-varying Cox",
    "Cause-specific Hazard",
    "Aalen-Johansen / CIF",
    "Fine-Gray",
]

PAGE_ICONS = {
    "overview": ":material/dashboard:",
    "portfolio_risk": ":material/account_balance:",
    "risk_drivers": ":material/monitoring:",
    "loan_explorer": ":material/manage_search:",
    "model_insights": ":material/fact_check:",
}
