"""Editorial section blocks shared by the analytical dashboard pages."""

from __future__ import annotations

import streamlit as st

NAVY = "#293A32"
RED = "#AD6254"
BLUE = "#637E69"
GREEN = "#64816A"
TINT_NAVY = "#E9E8DE"
TINT_RED = "#F5E9E4"
TINT_BLUE = "#EAF0E7"
TINT_GREEN = "#EAF0E7"
TINT_GRAY = "#F0EEE6"


def inject_page_blocks_css() -> None:
    st.html(
        """
        <style>
        .research-section{position:relative;display:block;margin:32px 0 16px;padding:0 0 0 2px;}
        .research-section-number{display:none;}
        .research-section:before{content:"✦  MORTGAGE RISK / ANALYSIS";display:block;color:#A78A47;
            font:700 .68rem 'Lora',Georgia,serif;letter-spacing:.12em;margin-bottom:7px;}
        .research-section-title{color:#293A32;font-family:'Lora',Georgia,serif;font-size:1.75rem;
            font-weight:700;line-height:1.22;}
        .research-section-subtitle{color:#777D75;font-size:1rem;margin-top:5px;line-height:1.5;}
        .research-callout{box-sizing:border-box;padding:15px 18px;margin:0 0 14px;border:1px solid #DCD7C8;
            border-left:5px solid #B99B53;border-radius:4px;background:#F6F3E9;color:#303A34;
            font-size:.98rem;line-height:1.65;}
        .research-stat-card{position:relative;box-sizing:border-box;height:100%;min-height:172px;padding:21px 20px 17px;
            border-radius:4px;border:1px solid #DCD7C8;background:#FFFEFA;
            box-shadow:5px 5px 0 rgba(89,82,60,.15);}
        .research-stat-icon{position:absolute;right:16px;top:16px;display:grid;place-items:center;width:36px;height:36px;
            background:var(--card-tint);color:var(--card-color);font:600 1.05rem 'Lora',Georgia,serif;}
        .research-stat-label{max-width:calc(100% - 48px);color:#8B877C;font-size:.69rem;font-weight:700;
            letter-spacing:.105em;text-transform:uppercase;line-height:1.4;}
        .research-stat-value{color:#293A32;font-family:'Lora',Georgia,serif;font-size:2rem;
            font-weight:700;line-height:1.2;margin-top:13px;overflow-wrap:anywhere;}
        .research-stat-note{color:#777D75;font-size:.88rem;line-height:1.45;margin-top:5px;}
        .research-stat-foot{display:flex;align-items:center;gap:8px;border-top:1px solid #EEEADF;margin-top:13px;padding-top:10px;
            color:#777D75;font-size:.77rem;line-height:1.35;}
        .research-stat-foot:before{content:"";width:7px;height:7px;flex:0 0 7px;border-radius:50%;background:var(--card-color);}
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
    key = label.casefold()
    icon = "↗" if any(x in key for x in ("rate", "ltv", "dti", "fico", "lãi suất")) else (
        "◷" if any(x in key for x in ("thời gian", "tháng", "kỳ hạn", "tuổi")) else (
            "▤" if any(x in key for x in ("dư nợ", "upb", "khoản vay", "số khoản")) else "•"
        )
    )
    footnote = note or "Hồ sơ khoản vay đã chuẩn hóa"
    st.markdown(
        f'<div class="research-stat-card" style="--card-color:{color};--card-tint:{tint}">'
        f'<div class="research-stat-icon">{icon}</div>'
        f'<div class="research-stat-label">{label}</div>'
        f'<div class="research-stat-value">{value}</div>'
        f'<div class="research-stat-note">{note}</div>'
        f'<div class="research-stat-foot">{footnote}</div></div>',
        unsafe_allow_html=True,
    )
