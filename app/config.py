"""
Theme dùng chung cho toàn bộ dashboard.

Bảng màu và font được chọn để đồng bộ với
`Project_Specification_Mortgage_Survival_Analysis.docx`:
- Màu shading header bảng trong docx: #D9EAF7 (light blue) -> dùng làm
  ACCENT / nền header, nền KPI card.
- Font docx: "Aptos" / "Aptos Display" -> trình duyệt không có font này,
  nên dùng fallback stack gần nhất (Segoe UI / Calibri / system sans-serif)
  để giữ cảm giác "Office document" nhất quán.
- Bảng "LOCKED / CONFIRMED / PENDING VALIDATION" trong docx dùng màu
  semantic (xanh lá = locked/ổn, cam = pending, đỏ = vi phạm) -> tái dùng
  cho status pill và cảnh báo trong dashboard.
"""

APP_TITLE = "Hệ thống phân tích rủi ro tín dụng khoản vay thế chấp"
APP_SUBTITLE = "Mortgage Default & Prepayment – Survival Analysis Dashboard"

# ---- Màu chính (đồng bộ với docx) -----------------------------------------
PRIMARY = "#1F4E79"        # xanh navy đậm — tiêu đề, heading, đường viền nhấn
PRIMARY_DARK = "#163A56"   # header bar / sidebar
ACCENT = "#D9EAF7"         # xanh nhạt — đúng màu shade header bảng trong docx
ACCENT_STRONG = "#BBDAF0"  # dùng cho hover / active tab

TEXT_MAIN = "#1A1A1A"
TEXT_MUTED = "#5B6570"

SUCCESS = "#2E7D32"    # LOCKED / CONFIRMED / risk thấp
WARNING = "#B7791F"    # PENDING VALIDATION / cảnh báo
DANGER = "#B3261E"     # vi phạm rule / risk cao

CHART_SEQUENCE = [PRIMARY, "#4C86B5", "#7FB3D5", SUCCESS, WARNING, DANGER]

FONT_STACK = "'Aptos','Aptos Display','Segoe UI','Calibri',sans-serif"

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
