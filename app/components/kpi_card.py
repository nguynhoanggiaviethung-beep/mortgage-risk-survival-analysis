"""KPI card dùng chung cho Trang 1 (Tổng quan) và các trang khác."""

from __future__ import annotations

import streamlit as st

from app.config import DANGER, PRIMARY, SUCCESS, WARNING


def _delta_html(delta: str | None, delta_positive_is_good: bool) -> str:
    if not delta:
        return ""
    is_up = delta.strip().startswith("+")
    good = (is_up and delta_positive_is_good) or ((not is_up) and not delta_positive_is_good)
    color = SUCCESS if good else DANGER
    return f'<div class="kpi-delta" style="color:{color};">{delta}</div>'


def kpi_card(
    label: str,
    value: str,
    delta: str | None = None,
    delta_positive_is_good: bool = False,
    help_text: str | None = None,
) -> None:
    """Vẽ 1 thẻ KPI. delta_positive_is_good: với Default Rate, tăng là xấu
    (False); với Total Loans, tăng là tốt (True)."""
    label_key = label.casefold()
    accent = DANGER if ("default" in label_key or "vỡ nợ" in label_key) else (
        PRIMARY if ("prepay" in label_key or "trả trước" in label_key or "zbc" in label_key) else (
            SUCCESS if ("khoản vay" in label_key or "danh mục" in label_key) else WARNING
        )
    )
    if "default" in label_key or "vỡ nợ" in label_key:
        icon, category = "↘", "Cause-specific event"
    elif "prepay" in label_key or "trả trước" in label_key or "zbc" in label_key:
        icon, category = "↗", "Competing event"
    elif "pd" in label_key or "cif" in label_key or "xác suất" in label_key:
        icon, category = "◷", "Ước lượng tích lũy"
    elif "khoản vay" in label_key or "danh mục" in label_key or "loan" in label_key:
        icon, category = "▤", "Freddie Mac · loan-level"
    else:
        icon, category = "⌁", "Chỉ số danh mục"
    footnote = f'<div class="kpi-footnote">{help_text}</div>' if help_text else ""
    st.markdown(
        f"""
        <div class="kpi-card" style="--card-accent:{accent}">
            <div class="kpi-icon">{icon}</div>
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
            {footnote}
            <div class="kpi-source">{category}</div>
            {_delta_html(delta, delta_positive_is_good)}
        </div>
        """,
        unsafe_allow_html=True,
    )
def kpi_row(items: list[dict]) -> None:
    """items: list các dict {label, value, delta?, delta_positive_is_good?, help_text?}."""
    cols = st.columns(len(items))
    for col, item in zip(cols, items):
        with col:
            kpi_card(
                label=item["label"],
                value=item["value"],
                delta=item.get("delta"),
                delta_positive_is_good=item.get("delta_positive_is_good", False),
                help_text=item.get("help_text"),
            )
