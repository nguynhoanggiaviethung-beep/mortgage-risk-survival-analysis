"""Display labels, colors, and typography for the dashboard UI."""

APP_TITLE = "Phân tích rủi ro khoản vay thế chấp"
APP_SUBTITLE = "Mortgage Default & Prepayment · Survival Analysis"

# ---- Bảng màu xanh navy/xanh nhạt ban đầu ----------------------------------
PRIMARY = "#1F4E79"
PRIMARY_DARK = "#163A56"
ACCENT = "#D9EAF7"
ACCENT_STRONG = "#BBDAF0"

TEXT_MAIN = "#1A1A1A"
TEXT_MUTED = "#5B6570"

SUCCESS = "#2E7D32"
WARNING = "#B7791F"
DANGER = "#B3261E"

CHART_SEQUENCE = [PRIMARY, "#4C86B5", "#7FB3D5", SUCCESS, WARNING, DANGER]

FONT_STACK = "'Lora',Georgia,serif"
DISPLAY_FONT_STACK = "'Lora',Georgia,serif"

# ---- Nhãn hiển thị dùng chung ----------------------------------------------
HORIZON_OPTIONS = [12, 24, 36, 60]

EVENT_LABELS = {
    "DEFAULT": "Default",
    "VOLUNTARY_PREPAYMENT": "Voluntary Prepayment",
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
    "overview": "📊",
    "portfolio_risk": "🧭",
    "risk_drivers": "📈",
    "loan_explorer": "🔍",
    "model_insights": "🧪",
}
