"""Inject CSS dùng chung để mọi trang có giao diện thống nhất."""

import streamlit as st

from app.config import (
    ACCENT,
    ACCENT_STRONG,
    DANGER,
    FONT_STACK,
    PRIMARY,
    PRIMARY_DARK,
    SUCCESS,
    TEXT_MAIN,
    TEXT_MUTED,
    WARNING,
)


def inject_global_css() -> None:
    st.markdown(
        f"""
        <style>
        html, body, [class*="css"] {{
            font-family: {FONT_STACK};
            color: {TEXT_MAIN};
        }}

        /* ---- Header bar (đồng bộ màu navy của tiêu đề docx) ---- */
        .app-header {{
            background: linear-gradient(90deg, {PRIMARY_DARK} 0%, {PRIMARY} 100%);
            padding: 1.1rem 1.6rem;
            border-radius: 10px;
            margin-bottom: 1.2rem;
        }}
        .app-header h1 {{
            color: white;
            font-size: 1.35rem;
            font-weight: 700;
            margin: 0;
        }}
        .app-header p {{
            color: #E3EEF7;
            font-size: 0.85rem;
            margin: 0.2rem 0 0 0;
        }}

        /* ---- Section heading, dùng thay cho st.header mặc định ---- */
        .section-title {{
            color: {PRIMARY_DARK};
            font-size: 1.05rem;
            font-weight: 700;
            border-left: 5px solid {PRIMARY};
            padding-left: 0.6rem;
            margin: 1.1rem 0 0.6rem 0;
        }}
        .section-caption {{
            color: {TEXT_MUTED};
            font-size: 0.85rem;
            margin-bottom: 0.8rem;
        }}

        /* ---- KPI card ---- */
        .kpi-card {{
            background: white;
            border: 1px solid {ACCENT_STRONG};
            border-top: 4px solid {PRIMARY};
            border-radius: 10px;
            padding: 0.9rem 1rem;
        }}
        .kpi-label {{
            color: {TEXT_MUTED};
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.03em;
            margin-bottom: 0.2rem;
        }}
        .kpi-value {{
            color: {PRIMARY_DARK};
            font-size: 1.6rem;
            font-weight: 700;
            line-height: 1.15;
        }}
        .kpi-delta {{
            font-size: 0.78rem;
            margin-top: 0.15rem;
        }}

        /* ---- Status pill (LOCKED / PENDING / vi phạm) ---- */
        .status-pill {{
            display: inline-block;
            padding: 0.1rem 0.55rem;
            border-radius: 999px;
            font-size: 0.72rem;
            font-weight: 600;
        }}
        .status-ok {{ background: #E4F3E6; color: {SUCCESS}; }}
        .status-warn {{ background: #FBF0DD; color: {WARNING}; }}
        .status-bad {{ background: #FBE5E3; color: {DANGER}; }}

        /* ---- Bảng: shading header giống đúng docx (#D9EAF7) ---- */
        [data-testid="stDataFrame"] thead tr th {{
            background-color: {ACCENT} !important;
            color: {PRIMARY_DARK} !important;
            font-weight: 700 !important;
        }}

        /* ---- Sidebar ---- */
        section[data-testid="stSidebar"] {{
            background-color: #F5F8FB;
        }}

        /* ---- Card container quanh chart ---- */
        .chart-card {{
            background: white;
            border: 1px solid {ACCENT_STRONG};
            border-radius: 10px;
            padding: 0.8rem 1rem 0.4rem 1rem;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def app_header(title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="app-header">
            <h1>{title}</h1>
            <p>{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_title(title: str, caption: str | None = None) -> None:
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)
    if caption:
        st.markdown(f'<div class="section-caption">{caption}</div>', unsafe_allow_html=True)


def status_pill(text: str, kind: str = "ok") -> str:
    """kind: 'ok' | 'warn' | 'bad' — dùng inline trong markdown."""
    cls = {"ok": "status-ok", "warn": "status-warn", "bad": "status-bad"}.get(kind, "status-ok")
    return f'<span class="status-pill {cls}">{text}</span>'
