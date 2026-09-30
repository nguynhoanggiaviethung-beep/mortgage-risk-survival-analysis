"""KPI card dùng chung cho Trang 1 (Tổng quan) và các trang khác."""

from __future__ import annotations

import streamlit as st

from app.config import DANGER, SUCCESS


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
    st.markdown(
        f"""
        <div class="kpi-card" title="{help_text or ''}">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
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
