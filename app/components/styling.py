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
            --moss: {PRIMARY};
            --paper: #F1EFE6;
            --surface: #FFFEFA;
            --line: #DCD7C8;
            --muted: {TEXT_MUTED};
            --gold: {ACCENT_STRONG};
            --surface-soft: #F6F3E9;
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
            background: transparent;
            color: var(--ink);
            padding: .1rem 0 .2rem;
            border: 0;
            margin: 0 0 1.9rem;
            box-shadow: none;
        }}
        .app-header .eyebrow {{
            color: var(--gold);
            font-size: .78rem;
            font-weight: 700;
            letter-spacing: .13em;
            text-transform: uppercase;
            margin: 0 0 .72rem;
        }}
        .app-header .eyebrow:before {{ content:"✦";font-size:1rem;margin-right:.65rem;color:var(--gold); }}
        .app-header h1 {{
            color: var(--ink);
            font-family: {DISPLAY_FONT_STACK};
            font-size: clamp(2.7rem, 4vw, 4rem);
            font-weight: 700;
            letter-spacing: 0;
            line-height: 1.12;
            margin: 0;
        }}
        .app-header p {{
            color: var(--muted);
            font-size: 1.2rem;
            margin: .75rem 0 0;
        }}
        .app-header .header-meta {{
            display: none;
        }}
        .app-header .header-dot {{
            width: 7px; height: 7px; border-radius: 50%; background: {SUCCESS};
        }}

        /* Page context and section rhythm. */
        [data-testid="stCaptionContainer"] {{ color: var(--muted); }}
        .section-title {{
            display: block;
            color: var(--ink);
            font-family: {FONT_STACK};
            font-size: 1.75rem;
            font-weight: 700;
            letter-spacing: 0;
            background: transparent;
            border: 0;
            padding: 0;
            margin: 2rem 0 .45rem;
            box-shadow: none;
            line-height:1.22;
        }}
        .section-title:before {{
            content: "✦  PORTFOLIO / ANALYSIS";
            display:block;
            color: var(--gold);
            font-family: {DISPLAY_FONT_STACK};
            font-size: .68rem;
            letter-spacing:.12em;
            margin:0 0 .48rem;
        }}
        .section-caption {{
            color: var(--muted);
            font-size: .88rem;
            line-height: 1.55;
            margin: .15rem 0 1rem;
        }}
        h1, h2, h3 {{ color: var(--ink); }}
        h1, h2, h3 {{ font-family: {FONT_STACK}; letter-spacing: 0; }}

        /* KPI cards: calm surfaces, precise numbers, no dashboard glare. */
        .kpi-card {{
            position: relative;
            height: 100%;
            min-height: 190px;
            background: var(--surface);
            border: 1px solid var(--line);
            border-radius: 4px;
            padding: 1.2rem 1.25rem 1rem;
            box-shadow: 5px 5px 0 rgba(89, 82, 60, .15);
            transition: box-shadow .15s ease;
        }}
        .kpi-card:hover {{ box-shadow: 7px 7px 0 rgba(89, 82, 60, .18); }}
        .kpi-icon {{
            position:absolute;right:1rem;top:1rem;display:grid;place-items:center;width:2.25rem;height:2.25rem;
            background:color-mix(in srgb, var(--card-accent, var(--gold)) 12%, white);
            color:var(--card-accent, var(--gold));font:600 1.1rem {DISPLAY_FONT_STACK};
        }}
        .kpi-label {{
            color: #8B877C;
            max-width:calc(100% - 3rem);
            font-size: .69rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: .105em;
            line-height:1.4;
            margin-bottom: .78rem;
        }}
        .kpi-value {{
            color: var(--ink);
            font-family: {FONT_STACK};
            font-size: clamp(1.8rem, 2.2vw, 2.35rem);
            font-weight: 700;
            letter-spacing: 0;
            line-height: 1.1;
        }}
        .kpi-footnote {{
            color: var(--muted);
            font-size: .78rem;
            line-height: 1.45;
            margin-top: .5rem;
            display: flex;
            align-items: flex-start;
            gap: .45rem;
        }}
        .kpi-footnote:before {{ content: none; }}
        .kpi-source {{
            display:flex;align-items:center;gap:.5rem;border-top:1px solid #EEEADF;margin-top:.85rem;padding-top:.65rem;
            color:var(--muted);font-size:.78rem;line-height:1.35;
        }}
        .kpi-source:before {{
            content:"";width:7px;height:7px;flex:0 0 7px;border-radius:50%;background:var(--card-accent,var(--gold));
        }}
        .kpi-delta {{ font-size: .78rem; margin-top: .45rem; }}
        [data-testid="stMetric"] {{
            background: var(--surface);
            border: 1px solid var(--line);
            border-radius: 4px;
            padding: .85rem 1rem;
            box-shadow: 4px 4px 0 rgba(89, 82, 60, .10);
            border-top: 3px solid var(--gold);
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
            border-radius: 4px;
        }}
        [data-testid="stRadio"] [role="radiogroup"] {{ gap: .35rem; }}
        [data-testid="stRadio"] label[data-baseweb="radio"] {{
            background: var(--surface-soft);
            border: 1px solid var(--line);
            border-radius: 4px;
            padding: .32rem .7rem;
        }}

        /* Charts and tables. */
        .chart-card {{
            background: var(--surface);
            border: 1px solid var(--line);
            border-radius: 4px;
            padding: .85rem 1rem .5rem;
            box-shadow: 4px 4px 0 rgba(89, 82, 60, .10);
        }}
        [data-testid="stDataFrame"] {{
            background: var(--surface);
            border: 1px solid var(--line);
            border-radius: 4px;
            overflow: hidden;
        }}
        [data-testid="stDataFrame"] thead tr th {{
            background-color: {ACCENT} !important;
            color: var(--ink) !important;
            font-weight: 700 !important;
        }}
        [data-testid="stDataFrame"] tbody tr:hover {{ background: #F1EFE6; }}

        /* Sidebar reads like a compact client brief. */
        section[data-testid="stSidebar"] {{
            background: {PRIMARY_DARK};
            border-right: 1px solid #1D2A24;
            min-width: 20rem;
            max-width: 20rem;
        }}
        section[data-testid="stSidebar"] [data-testid="stSidebarContent"] {{
            padding-top: 1.1rem;
        }}
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] {{
            position: relative;
            padding-top: 9.4rem;
        }}
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"]:before {{
            content: "⌂";
            position: absolute;
            top: 1.15rem;
            left: 1.2rem;
            width: 3.05rem;
            height: 3.05rem;
            display: grid;
            place-items: center;
            background: var(--gold);
            color: #FFFDF6;
            font: 700 2rem Georgia, serif;
            box-shadow: 3px 3px 0 rgba(15,24,19,.32);
        }}
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"]:after {{
            content: "mortgage risk\\A RISK INTELLIGENCE\\A\\A WORKSPACE";
            white-space: pre;
            position: absolute;
            top: 1.1rem;
            left: 5rem;
            color: #F4F0E4;
            font-family: {DISPLAY_FONT_STACK};
            font-size: .92rem;
            font-weight: 700;
            letter-spacing: .015em;
            line-height: 1.65;
        }}
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a {{
            color: #FFFDF6 !important;
            border-radius: 4px;
            margin: .18rem 0;
            padding-top: .42rem;
            padding-bottom: .42rem;
            font-family: {FONT_STACK};
            transition: background .15s ease;
        }}
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a svg {{
            color: #E2C76F !important;
            fill: #E2C76F !important;
        }}
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a svg * {{
            stroke:#E2C76F !important;fill:#E2C76F !important;
        }}
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a span {{ color:#FFFDF6 !important; }}
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a [data-testid="stIconMaterial"] {{
            color:#E2C76F !important;
        }}
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a:hover {{
            background: #35483D;
        }}
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] [aria-current="page"] {{
            background: #3A4D41 !important;
            color: #FFFDF6 !important;
            font-weight: 700;
            border-left: 3px solid var(--gold);
        }}
        section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"],
        section[data-testid="stSidebar"] label {{ color: #FFFDF6; }}
        section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {{ color: #D8D9CE; }}
        section[data-testid="stSidebar"] code {{ color: #293A32 !important;background:#F6F3E9 !important; }}
        section[data-testid="stSidebar"] [data-testid="stExpander"] {{
            background: #314238;
            border: 1px solid #526453;
            color: #F4F0E4;
        }}
        section[data-testid="stSidebar"] [data-testid="stExpander"] summary,
        section[data-testid="stSidebar"] [data-testid="stExpander"] summary span {{ color: #FFFDF6 !important; }}
        section[data-testid="stSidebar"] [data-testid="stExpander"] summary {{ background:#3A4D41 !important; }}
        .sidebar-brand-footer {{
            display:flex;align-items:center;gap:.65rem;margin:1.05rem .15rem .6rem;
            padding:.7rem .6rem;border-top:1px solid #435348;color:#F4F0E4;
        }}
        .sidebar-brand-mark {{
            display:grid;place-items:center;width:2.35rem;height:2.35rem;flex:0 0 2.35rem;
            background:#3E5044;color:var(--gold);font:700 .82rem {DISPLAY_FONT_STACK};
        }}
        .sidebar-brand-copy {{ font-family:{DISPLAY_FONT_STACK};font-weight:700;font-size:.82rem;line-height:1.25; }}
        .sidebar-brand-subtitle {{ display:block;color:#AAB5A9;font-size:.69rem;font-weight:400;margin-top:.18rem; }}
        .sidebar-brand-dot {{ width:.48rem;height:.48rem;margin-left:auto;border-radius:50%;background:#78A58B; }}

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
        .status-neutral {{ background: #F0EEE6; color: #536056; }}
        [data-testid="stAlert"] {{ border-radius: 4px; }}
        [data-testid="stExpander"] {{
            background: var(--surface);
            border: 1px solid var(--line);
            border-radius: 4px;
        }}
        div.stButton > button, [data-testid="stDownloadButton"] button {{
            border-radius: 4px;
            border-color: var(--line);
            font-weight: 600;
        }}
        div.stButton > button[kind="primary"] {{
            background: {PRIMARY}; border-color: {PRIMARY}; color: white;
        }}
        hr {{ border-color: var(--line); }}

        [data-testid="stVerticalBlockBorderWrapper"] {{
            background: var(--surface);
            border-color: var(--line) !important;
            border-radius: 4px;
            box-shadow: 4px 4px 0 rgba(89, 82, 60, .08);
        }}

        @media (max-width: 760px) {{
            [data-testid="stMainBlockContainer"] {{ padding: 1rem .9rem 3rem; }}
            .app-header {{ padding: .1rem 0 .2rem; }}
            .section-title {{ font-size: 1.14rem; margin-top: 1.55rem; }}
            section[data-testid="stSidebar"] {{ min-width:min(21rem, 88vw); max-width:min(21rem, 88vw); }}
        }}
        </style>
        """
    )


def app_header(title: str, subtitle: str, kicker: str = "LOAN BOOK / 01") -> None:
    st.markdown(
        f"""
        <div class="app-header">
            <div class="eyebrow">{kicker}</div>
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
    cls = {"ok": "status-ok", "warn": "status-warn", "bad": "status-bad", "neutral": "status-neutral"}.get(kind, "status-ok")
    return f'<span class="status-pill {cls}">{text}</span>'
