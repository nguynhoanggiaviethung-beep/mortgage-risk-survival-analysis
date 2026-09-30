"""Shared visual language for a calm, human-centered finance dashboard."""

import streamlit as st

from app.config import (
    ACCENT,
    ACCENT_STRONG,
    DANGER,
    DISPLAY_FONT_STACK,
    FONT_STACK,
    PRIMARY,
    PRIMARY_DARK,
    SUCCESS,
    TEXT_MAIN,
    TEXT_MUTED,
    WARNING,
)


def inject_global_css() -> None:
    st.html(
        f"""
        <style>
        @import url("https://fonts.googleapis.com/css2?family=Lora:wght@400;500;600;700&display=swap");
        :root {{
            --ink: {PRIMARY_DARK};
            --teal: {PRIMARY};
            --paper: #F5F8FB;
            --surface: #FFFFFF;
            --line: #DCE5EC;
            --muted: {TEXT_MUTED};
            --gold: #C28A4B;
        }}

        html, body, [class*="css"] {{
            font-family: {FONT_STACK};
            color: {TEXT_MAIN};
        }}
        .stApp {{ background: var(--paper); }}
        [data-testid="stAppViewContainer"] {{ background: var(--paper); }}
        [data-testid="stMainBlockContainer"] {{
            max-width: 1500px;
            padding-top: 2rem;
            padding-bottom: 4rem;
        }}

        /* Plain, dependable report header. Keep Vietnamese glyphs in a common UI font. */
        .app-header {{
            background: #FFFFFF;
            color: var(--ink);
            padding: 1.3rem 1.65rem 1.25rem;
            border: 1px solid #DCE5EC;
            border-left: 5px solid {PRIMARY};
            border-radius: 5px;
            margin: 0 0 1.35rem;
            box-shadow: 0 2px 7px rgba(30, 45, 49, .035);
        }}
        .app-header .eyebrow {{
            color: {PRIMARY};
            font-size: .72rem;
            font-weight: 700;
            letter-spacing: .035em;
            margin: 0 0 .35rem;
        }}
        .app-header h1 {{
            color: var(--ink);
            font-family: {DISPLAY_FONT_STACK};
            font-size: clamp(1.45rem, 2vw, 1.8rem);
            font-weight: 700;
            letter-spacing: 0;
            line-height: 1.3;
            margin: 0;
        }}
        .app-header p {{
            color: var(--muted);
            font-size: .9rem;
            margin: .38rem 0 0;
        }}
        .app-header .header-meta {{
            display: inline-flex;
            align-items: center;
            gap: .5rem;
            margin-top: .8rem;
            padding: .3rem .55rem;
            border: 1px solid #E6E6DF;
            border-radius: 4px;
            background: #F3F7FA;
            color: #465B6A;
            font-size: .74rem;
            letter-spacing: 0;
        }}
        .app-header .header-dot {{
            width: 7px; height: 7px; border-radius: 50%; background: {PRIMARY};
        }}

        /* Page context and section rhythm. */
        [data-testid="stCaptionContainer"] {{ color: var(--muted); }}
        .section-title {{
            display: flex;
            align-items: center;
            gap: .62rem;
            color: var(--ink);
            font-family: {FONT_STACK};
            font-size: 1.13rem;
            font-weight: 700;
            letter-spacing: 0;
            border: 0;
            padding: 0;
            margin: 1.95rem 0 .45rem;
        }}
        .section-title:before {{
            content: "";
            width: 4px; height: 1.35rem;
            border-radius: 4px;
            background: {PRIMARY};
        }}
        .section-caption {{
            color: var(--muted);
            font-size: .88rem;
            line-height: 1.55;
            margin: .15rem 0 .85rem 1rem;
        }}
        h1, h2, h3 {{ color: var(--ink); }}
        h1, h2, h3 {{ font-family: {FONT_STACK}; letter-spacing: 0; }}

        /* KPI cards: calm surfaces, precise numbers, no dashboard glare. */
        .kpi-card {{
            height: 100%;
            min-height: 112px;
            background: var(--surface);
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 1rem 1.12rem;
            box-shadow: 0 4px 12px rgba(38, 52, 60, .035);
            transition: box-shadow .15s ease;
        }}
        .kpi-card:hover {{ box-shadow: 0 5px 14px rgba(38, 52, 60, .065); }}
        .kpi-label {{
            color: var(--muted);
            font-size: .7rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: .095em;
            margin-bottom: .5rem;
        }}
        .kpi-value {{
            color: var(--ink);
            font-family: {FONT_STACK};
            font-size: clamp(1.5rem, 2vw, 1.95rem);
            font-weight: 600;
            letter-spacing: 0;
            line-height: 1.1;
        }}
        .kpi-delta {{ font-size: .78rem; margin-top: .45rem; }}
        [data-testid="stMetric"] {{
            background: var(--surface);
            border: 1px solid var(--line);
            border-radius: 13px;
            padding: .85rem 1rem;
            box-shadow: 0 4px 12px rgba(38, 52, 60, .03);
        }}
        [data-testid="stMetricLabel"] {{ color: var(--muted); font-size: .78rem; }}
        [data-testid="stMetricValue"] {{ color: var(--ink); font-family: {FONT_STACK}; }}

        /* Selection controls feel like one quiet filter panel. */
        [data-testid="stSelectbox"], [data-testid="stMultiSelect"],
        [data-testid="stTextInput"], [data-testid="stNumberInput"] {{
            background: transparent;
        }}
        [data-testid="stSelectbox"] label, [data-testid="stRadio"] label,
        [data-testid="stTextInput"] label {{
            color: var(--ink);
            font-size: .82rem;
            font-weight: 650;
        }}
        [data-baseweb="select"] > div, [data-testid="stTextInput"] input {{
            background: var(--surface);
            border-color: var(--line);
            border-radius: 10px;
        }}
        [data-testid="stRadio"] [role="radiogroup"] {{ gap: .35rem; }}
        [data-testid="stRadio"] label[data-baseweb="radio"] {{
            background: rgba(255,254,251,.7);
            border: 1px solid var(--line);
            border-radius: 999px;
            padding: .32rem .7rem;
        }}

        /* Charts and tables. */
        .chart-card {{
            background: var(--surface);
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: .85rem 1rem .5rem;
            box-shadow: 0 5px 16px rgba(38, 52, 60, .035);
        }}
        [data-testid="stDataFrame"] {{
            background: var(--surface);
            border: 1px solid var(--line);
            border-radius: 13px;
            overflow: hidden;
        }}
        [data-testid="stDataFrame"] thead tr th {{
            background-color: {ACCENT} !important;
            color: var(--ink) !important;
            font-weight: 700 !important;
        }}
        [data-testid="stDataFrame"] tbody tr:hover {{ background: #F1F6FA; }}

        /* Sidebar reads like a compact client brief. */
        section[data-testid="stSidebar"] {{
            background: #F1F5F8;
            border-right: 1px solid #DCE5EC;
        }}
        section[data-testid="stSidebar"] [data-testid="stSidebarContent"] {{
            padding-top: 1.1rem;
        }}
        section[data-testid="stSidebar"] [data-testid="stPageLink"] a {{
            border-radius: 10px;
            margin: .12rem 0;
            transition: background .15s ease;
        }}
        section[data-testid="stSidebar"] [data-testid="stPageLink"] a:hover {{
            background: #E7F0F6;
        }}
        section[data-testid="stSidebar"] [aria-current="page"] {{
            background: #DCEAF4 !important;
            color: var(--ink) !important;
            font-weight: 700;
        }}

        /* Status and system feedback. */
        .status-pill {{
            display: inline-block;
            padding: .22rem .65rem;
            border-radius: 999px;
            font-size: .73rem;
            font-weight: 700;
            letter-spacing: .015em;
        }}
        .status-ok {{ background: #E5EFE8; color: {SUCCESS}; }}
        .status-warn {{ background: #F6EBDD; color: {WARNING}; }}
        .status-bad {{ background: #F5E5E1; color: {DANGER}; }}
        .status-neutral {{ background: #E9EEF3; color: #465B6A; }}
        [data-testid="stAlert"] {{ border-radius: 12px; }}
        [data-testid="stExpander"] {{
            background: rgba(255,254,251,.72);
            border: 1px solid var(--line);
            border-radius: 12px;
        }}
        div.stButton > button, [data-testid="stDownloadButton"] button {{
            border-radius: 9px;
            border-color: var(--line);
            font-weight: 600;
        }}
        div.stButton > button[kind="primary"] {{
            background: {PRIMARY}; border-color: {PRIMARY}; color: white;
        }}
        hr {{ border-color: #DCE5EC; }}

        [data-testid="stVerticalBlockBorderWrapper"] {{
            background: #FFFFFF;
            border-color: #DCE5EC !important;
            border-radius: 8px;
            box-shadow: 0 3px 10px rgba(31,78,121,.045);
        }}

        @media (max-width: 760px) {{
            [data-testid="stMainBlockContainer"] {{ padding: 1rem .9rem 3rem; }}
            .app-header {{ padding: 1.05rem 1rem; border-radius: 5px; }}
            .section-title {{ font-size: 1.14rem; margin-top: 1.55rem; }}
        }}
        </style>
        """
    )


def app_header(title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="app-header">
            <div class="eyebrow">Nghiên cứu tín dụng · Quản trị rủi ro</div>
            <h1>{title}</h1>
            <p>{subtitle}</p>
            <div class="header-meta"><span class="header-dot"></span> Freddie Mac · Vintage 2016–2026 · Dữ liệu đến 31/03/2026</div>
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
    cls = {"ok": "status-ok", "warn": "status-warn", "bad": "status-bad", "neutral": "status-neutral"}.get(kind, "status-ok")
    return f'<span class="status-pill {cls}">{text}</span>'
