"""Editorial section blocks shared by the analytical dashboard pages."""

from __future__ import annotations

import streamlit as st

NAVY = "#1F4E79"
RED = "#C62828"
BLUE = "#1565C0"
GREEN = "#2E7D32"
TINT_NAVY = "#EAF1F8"
TINT_RED = "#FDECEA"
TINT_BLUE = "#E3F0FD"
TINT_GREEN = "#E8F5E9"
TINT_GRAY = "#ECEFF1"


def inject_page_blocks_css() -> None:
    st.html(
        """
        <style>
        .research-section{display:flex;align-items:center;gap:14px;margin:26px 0 13px;
            padding:10px 15px;border-radius:10px;background:#EAF1F8;border-left:7px solid #1F4E79;}
        .research-section-number{display:flex;align-items:center;justify-content:center;flex:0 0 34px;
            width:34px;height:34px;border-radius:50%;color:#fff;background:#1F4E79;font-weight:700;font-size:1rem;}
        .research-section-title{color:#14263A;font-family:'Lora',Georgia,serif;font-size:1.18rem;
            font-weight:700;line-height:1.3;}
        .research-section-subtitle{color:#55606E;font-size:.88rem;margin-top:2px;line-height:1.4;}
        .research-callout{box-sizing:border-box;padding:15px 18px;margin:0 0 14px;border:1px solid #C8D7E5;
            border-left:5px solid #1F4E79;border-radius:9px;background:#F1F5F9;color:#14263A;
            font-size:.98rem;line-height:1.65;}
        .research-stat-card{box-sizing:border-box;height:100%;min-height:116px;padding:14px 16px;border-radius:10px;
            border:1px solid var(--card-color);border-top:5px solid var(--card-color);background:var(--card-tint);}
        .research-stat-label{color:var(--card-color);font-size:.83rem;font-weight:700;line-height:1.35;}
        .research-stat-value{color:var(--card-color);font-family:'Lora',Georgia,serif;font-size:1.7rem;
            font-weight:700;line-height:1.25;margin-top:5px;}
        .research-stat-note{color:#55606E;font-size:.8rem;line-height:1.4;margin-top:5px;}
        </style>
        """
    )


def section_heading(number: int, title: str, subtitle: str = "") -> None:
    suffix = f'<div class="research-section-subtitle">{subtitle}</div>' if subtitle else ""
    st.markdown(
        f'<div class="research-section"><div class="research-section-number">{number:02d}</div>'
        f'<div><div class="research-section-title">{title}</div>{suffix}</div></div>',
        unsafe_allow_html=True,
    )


def callout(message: str) -> None:
    st.markdown(f'<div class="research-callout">{message}</div>', unsafe_allow_html=True)


def stat_card(label: str, value: str, note: str, color: str, tint: str) -> None:
    st.markdown(
        f'<div class="research-stat-card" style="--card-color:{color};--card-tint:{tint}">'
        f'<div class="research-stat-label">{label}</div>'
        f'<div class="research-stat-value">{value}</div>'
        f'<div class="research-stat-note">{note}</div></div>',
        unsafe_allow_html=True,
    )
