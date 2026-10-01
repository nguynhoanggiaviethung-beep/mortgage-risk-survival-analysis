"""
Trang 1 — Tổng quan  (GỘP MỘT FILE: giao diện + xử lý dữ liệu)
Trả lời: "Danh mục khoản vay đang có mức rủi ro như thế nào?"

Giao diện dễ hiểu cho người ít kiến thức tài chính, mã màu nhất quán:
    Xám xanh = tổng quy mô · ĐỎ = vỡ nợ · XANH DƯƠNG = trả trước hạn
    "XANH LÁ = chưa xảy ra vỡ nợ · ĐỎ = vỡ nợ · XANH DƯƠNG = trả trước hạn"

Nguồn dữ liệu (query layer): portfolio_summary, pd_results, survival_results.

Lưu ý: trang này chỉ gọi ds.get_xxx() KHÔNG truyền tham số, sau đó tự lọc
bằng pandas -> không phụ thuộc chữ ký hàm trong data_service.py.
Có bộ lọc NĂM GIẢI NGÂN (2016–2026) và biểu đồ so sánh rủi ro giữa các năm.
Tỷ lệ luôn là số thập phân (0.0071 = 0,71%). Thiếu dữ liệu -> hiện "—", không báo lỗi.
"""
from __future__ import annotations

import math
import re

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.pages.portfolio_risk import _render_intro
from app.components.page_blocks import page_kicker
from app.services import data_service as ds
from app.config import FONT_STACK


# --------------------------------------------------------------------------
# BẢNG MÀU (chỉnh ở đây là đổi toàn trang)
# --------------------------------------------------------------------------
C_NAVY = "#293A32"      # xanh rừng cho tiêu đề / danh mục
C_TOTAL = "#526F5B"     # xanh rêu
C_DEFAULT = "#AD6254"   # đất nung dịu cho default
C_PREPAY = "#637E69"    # xanh sage cho ZBC 01
C_OK = "#64816A"        # trạng thái sống sót
C_WARN = "#B08C45"      # vàng đồng

T_NAVY = "#E9E8DE"
T_TOTAL = "#F0EEE6"
T_DEFAULT = "#F5E9E4"
T_PREPAY = "#EAF0E7"
T_OK = "#EAF0E7"
T_WARN = "#F4EFDF"

DOT_OK = "#9AAA8F"
LINE_GRID = "#E2DED2"

HORIZON_LABEL = {12: "1 năm", 24: "2 năm", 36: "3 năm", 48: "4 năm", 60: "5 năm"}

# Khoảng năm giải ngân (vintage) cho phép chọn
YEAR_MIN = 2016
YEAR_MAX = 2026

# CSS viết liền, không thụt dòng, không dòng trống -> markdown không hiểu nhầm là code
_CSS = (
    "<style>"
    ".po-sec{display:block;margin:34px 0 14px 0;padding:0 0 0 2px;background:transparent!important;}"
    ".po-num{flex:0 0 auto;width:34px;height:34px;border-radius:50%;color:#fff;"
    "font-weight:700;font-size:1.05rem;display:flex;align-items:center;justify-content:center;}"
    ".po-num{display:none;}"
    ".po-sec:before{content:'✦  MORTGAGE RISK / OVERVIEW';display:block;color:#A78A47;"
    "font:700 .68rem 'Lora',Georgia,serif;letter-spacing:.12em;margin-bottom:7px;}"
    ".po-sec-t{font-size:1.75rem;font-weight:700;color:#293A32;line-height:1.22;font-family:'Lora',Georgia,serif;}"
    ".po-sec-s{font-size:1rem;color:#777D75;margin-top:5px;}"
    ".po-summary{border-radius:4px;padding:18px 22px;font-size:1.15rem;line-height:1.75;"
    "color:#303A34;box-shadow:4px 4px 0 rgba(89,82,60,.10);}"
    ".po-card{border-radius:4px;padding:16px 18px;height:100%;box-sizing:border-box;"
    "position:relative;min-height:192px;border:1px solid #DCD7C8;box-shadow:5px 5px 0 rgba(89,82,60,.15);background:#FFFEFA!important;}"
    ".po-card-icon{position:absolute;right:16px;top:16px;display:grid;place-items:center;width:36px;height:36px;"
    "background:#F6F3E9;color:#A78A47;font:600 1.05rem 'Lora',Georgia,serif;}"
    ".po-title{max-width:calc(100% - 48px);color:#8B877C!important;font-size:.7rem;font-weight:700;"
    "text-transform:uppercase;letter-spacing:.105em;margin-bottom:14px;}"
    ".po-big{font-family:'Lora',Georgia,serif;font-size:2.2rem;font-weight:700;line-height:1.2;color:#293A32!important;}"
    ".po-plain{font-size:.94rem;color:#777D75;margin-top:7px;line-height:1.5;}"
    ".po-note{display:flex;align-items:center;gap:8px;font-size:.78rem;color:#777D75;margin-top:14px;"
    "padding-top:10px;border-top:1px solid #EEEADF;line-height:1.4;}"
    ".po-note:before{content:'';width:7px;height:7px;flex:0 0 7px;border-radius:50%;background:#A78A47;}"
    ".po-badge{display:inline-block;padding:3px 12px;border-radius:999px;color:#fff;"
    "font-weight:700;font-size:0.9rem;}"
    ".po-result{border-radius:4px;padding:18px 22px;box-shadow:4px 4px 0 rgba(89,82,60,.10);}"
    ".po-headline{font-size:1.25rem;color:#303A34;line-height:1.7;}"
    ".po-dots{display:flex;flex-wrap:wrap;gap:3px;margin:12px 0 8px 0;}"
    ".po-dot{width:10px;height:10px;border-radius:50%;display:inline-block;}"
    ".po-legend{font-size:0.92rem;color:#3B4652;}"
    ".po-legend .po-dot{margin:0 6px 0 16px;vertical-align:middle;}"
    ".po-legend .po-dot:first-child{margin-left:0;}"
    "</style>"
)


# --------------------------------------------------------------------------
# Hàm phụ (an toàn với None / NaN)
# --------------------------------------------------------------------------
def _ok(x) -> bool:
    if x is None:
        return False
    try:
        return not math.isnan(float(x))
    except (TypeError, ValueError):
        return False


def _pct(p, digits: int = 2) -> str:
    """0.0071 -> '0,71%' (dấu phẩy thập phân kiểu Việt Nam)."""
    if not _ok(p):
        return "—"
    return f"{float(p) * 100:.{digits}f}%".replace(".", ",")


def _num(n) -> str:
    """504405 -> '504.405' (dấu chấm ngăn cách hàng nghìn kiểu Việt Nam)."""
    if not _ok(n):
        return "—"
    return f"{int(round(float(n))):,}".replace(",", ".")


def _per(p, total: int):
    """Tỷ lệ -> số khoản trên `total` khoản (tối thiểu 1 nếu p > 0). None nếu thiếu dữ liệu."""
    if not _ok(p):
        return None
    p = float(p)
    if p <= 0:
        return 0
    return max(1, int(round(p * total)))


def _per_txt(p, total: int) -> str:
    v = _per(p, total)
    return "—" if v is None else str(v)



def _h_label(h) -> str:
    h = int(h)
    return HORIZON_LABEL.get(h, f"{h} tháng")


def _section(num: int, title: str, sub: str, color: str, tint: str) -> str:
    return (
        f'<div class="po-sec">'
        f'<div class="po-num">{num}</div>'
        f'<div><div class="po-sec-t">{title}</div><div class="po-sec-s">{sub}</div></div></div>'
    )


def _card(title: str, big: str, plain: str, note: str, color: str, tint: str) -> str:
    title_key = title.casefold()
    icon = "↘" if "default" in title_key or "vỡ nợ" in title_key else (
        "↗" if "prepay" in title_key or "trả trước" in title_key else (
            "◷" if "sau " in title_key or "pd" in title_key else "▤"
        )
    )
    source = note or (
        "Freddie Mac · loan-level" if "tổng số khoản" in title_key else
        "Ước lượng CIF tích lũy" if "sau " in title_key else
        "Danh mục khoản vay thế chấp"
    )
    note_html = f'<div class="po-note">{source}</div>'
    return (
        f'<div class="po-card" style="background:#FFFEFA;border:1px solid #DCD7C8;'
        f'--card-accent:{color};--card-tint:{tint}">'
        f'<div class="po-card-icon" style="color:{color};background:{tint}">{icon}</div>'
        f'<div class="po-title">{title}</div>'
        f'<div class="po-big">{big}</div>'
        f'<div class="po-plain">{plain}</div>{note_html}</div>'
    )


def _dots_html(p, total: int = 1000, bad_color: str = C_DEFAULT) -> str:
    bad = _per(p, total) or 0
    bad = min(bad, total)
    dots = "".join(
        f'<span class="po-dot" style="background:{bad_color if i < bad else DOT_OK}"></span>'
        for i in range(total)
    )
    return f'<div class="po-dots">{dots}</div>'


def _interp_cif(pd_h: dict, months: int):
    """Tỷ lệ tích lũy tại `months` tháng -> (giá trị, có_phải_mốc_mô_hình_tính_sẵn).
    Mốc không có sẵn được ước tính bằng nội suy tuyến tính giữa hai mốc gần nhất
    (tính từ điểm gốc: tháng 0 = 0%)."""
    if months in pd_h:
        return pd_h[months], True
    pts = [(0, 0.0)] + sorted(pd_h.items())
    for (m0, v0), (m1, v1) in zip(pts, pts[1:]):
        if m0 < months < m1:
            return v0 + (v1 - v0) * (months - m0) / (m1 - m0), False
    return None, False


def _clean_horizons(d) -> dict:
    """Chuẩn hóa dict {horizon: giá trị}: ép kiểu, bỏ NaN/None."""
    out = {}
    for k, v in (d or {}).items():
        try:
            if _ok(v):
                out[int(k)] = float(v)
        except (TypeError, ValueError):
            continue
    return dict(sorted(out.items()))


# --------------------------------------------------------------------------
# Hàm chính
# --------------------------------------------------------------------------
def render_plain_overview(
    loan_count,
    default_rate,
    prepay_rate,
    pd_by_horizon: dict,
    prepay_by_horizon: dict | None = None,
    km_months=None,
    km_survival=None,
    km_ci_low=None,
    km_ci_high=None,
    km_at_risk=None,
    scope_label=None,
    km_note=None,
    extra_section=None,
    risk_by_horizon=None,
) -> None:
    st.markdown(_CSS, unsafe_allow_html=True)

    pd_h = _clean_horizons(pd_by_horizon)
    pp_h = _clean_horizons(prepay_by_horizon)
    risk_by_horizon = risk_by_horizon or {}
    horizons = list(pd_h.keys())

    # ======================================================================
    # ① TÓM TẮT NHANH
    # ======================================================================
    st.markdown(
        _section(1, "Tóm tắt nhanh", "Đọc phần này là nắm được bức tranh chung", C_NAVY, T_NAVY),
        unsafe_allow_html=True,
    )

    who = (
        f"Các khoản vay giải ngân năm <b>{scope_label}</b> gồm"
        if scope_label
        else "Danh mục hiện có"
    )
    parts = [f"{who} <b>{_num(loan_count)}</b> khoản vay thế chấp."]
    if _ok(default_rate):
        parts.append(
            f'Trong <b>36 tháng đầu</b>, cứ 100 khoản vay có khoảng '
            f'<b style="color:{C_DEFAULT}">{_per_txt(default_rate, 100)} khoản</b> '
            f'xảy ra vỡ nợ tích lũy'
        )
        if _ok(prepay_rate):
            parts[-1] += (
                f'; đồng thời khoảng <b style="color:{C_PREPAY}">'
                f'{_per_txt(prepay_rate, 100)} khoản</b> được tất toán trước hạn.'
            )
        else:
            parts[-1] += "."
    elif _ok(prepay_rate):
        parts.append(
            f'Trong <b>36 tháng đầu</b>, cứ 100 khoản vay có khoảng '
            f'<b style="color:{C_PREPAY}">{_per_txt(prepay_rate, 100)} khoản</b> '
            "ghi nhận Zero Balance Code 01."
        )
    st.markdown(
        f'<div class="po-summary" style="background:{T_NAVY};border:1px solid {C_NAVY}55">'
        f'{" ".join(parts)}</div>',
        unsafe_allow_html=True,
    )
    st.write("")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(
            _card(
                "Tổng số khoản vay",
                _num(loan_count),
                "khoản vay thế chấp được đưa vào phân tích",
                "",
                C_TOTAL,
                T_TOTAL,
            ),
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            _card(
                "Xác suất vỡ nợ tích lũy · 36 tháng",
                _pct(default_rate),
                f"Trong 100 khoản vay, khoảng <b>{_per_txt(default_rate, 100)}</b> khoản vỡ nợ trong 36 tháng",
                "CIF tích lũy; ZBC 01 (trả trước/đáo hạn gộp) là sự kiện cạnh tranh",
                C_DEFAULT,
                T_DEFAULT,
            ),
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            _card(
                "Xác suất CIF của ZBC 01 · 36 tháng",
                _pct(prepay_rate),
                f"Trong 100 khoản vay, khoảng <b>{_per_txt(prepay_rate, 100)}</b> kết thúc bằng mã 01 trong 36 tháng",
                "ZBC 01 gộp trả trước và đáo hạn; không thể tách hai trường hợp từ mã này. "
                + _horizon_detail(risk_by_horizon.get(36, {}).get("PREPAYMENT")),
                C_PREPAY,
                T_PREPAY,
            ),
            unsafe_allow_html=True,
        )

    # ======================================================================
    # ② VỠ NỢ TÍCH LŨY THEO THỜI GIAN
    # ======================================================================
    st.markdown(
        _section(
            2,
            "Vỡ nợ tích lũy theo thời gian",
            "Chọn mốc thời gian để xem tỷ lệ khoản vay đã xảy ra vỡ nợ tích lũy đến thời điểm đó.",
            C_DEFAULT,
            T_DEFAULT,
        ),
        unsafe_allow_html=True,
    )

    if horizons:
        # Chỉ cho phép chọn các horizon thực sự được tính
        year_opts = [h // 12 for h in horizons if h % 12 == 0]

        if year_opts:
            chosen_years = st.select_slider(
                "Chọn mốc thời gian",
                options=year_opts,
                value=3 if 3 in year_opts else year_opts[-1],
                format_func=lambda y: f"{y} năm",
                key="plain_overview_years",
            )

            chosen = chosen_years * 12
            p = pd_h.get(chosen)

            if p is not None:
                st.markdown(
                    f'<div class="po-result" style="background:{T_DEFAULT};'
                    f'border:1px solid {C_DEFAULT}55;'
                    f'border-left:8px solid {C_DEFAULT}">'
                    f'<div class="po-headline">'
                    f'Đến <b>{_h_label(chosen)}</b>, cứ <b>1.000</b> khoản vay '
                    f'thì có khoảng '
                    f'<b style="color:{C_DEFAULT}">{_per_txt(p, 1000)} khoản</b> '
                    f'đã xảy ra vỡ nợ ({_pct(p)}).'
                    f'</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            st.write("")
            st.markdown("**So sánh các mốc thời gian**")

            cols = st.columns(len(horizons))

            for col, h in zip(cols, horizons):
                ph = pd_h[h]

                with col:
                    st.markdown(
                        _card(
                            f"Sau {_h_label(h)}",
                            _pct(ph),
                            f"Khoảng <b>{_per_txt(ph, 1000)}</b> / 1.000 khoản vay "
                            f"đã xảy ra vỡ nợ",
                            _horizon_detail(risk_by_horizon.get(h, {}).get("DEFAULT")),
                            C_DEFAULT,
                            T_DEFAULT,
                        ),
                        unsafe_allow_html=True,
                    )
    else:
        st.info("Chưa có dữ liệu vỡ nợ tích lũy theo mốc thời gian.")

    # ======================================================================
    # ③ SO SÁNH VỠ NỢ và TRẢ TRƯỚC HẠN (đỏ vs xanh dương)
    # ======================================================================
    if horizons:
        st.markdown(
            _section(
                3,
                "Vỡ nợ và kết thúc bằng ZBC 01 theo thời gian",
                "ZBC 01 gộp khoản trả trước và khoản đáo hạn; dữ liệu hiện tại không tách riêng hai trường hợp.",
                C_PREPAY,
                T_PREPAY,
            ),
            unsafe_allow_html=True,
        )
        fig = go.Figure()
        default_meta = [risk_by_horizon.get(h, {}).get("DEFAULT", {}) for h in horizons]
        default_ci = _error_arrays([pd_h[h] for h in horizons], default_meta)
        default_custom = _hover_meta(default_meta)
        fig.add_scatter(
            x=[_h_label(h) for h in horizons], y=[pd_h[h] for h in horizons],
            name="Vỡ nợ (CIF)", mode="markers+text", marker=dict(color=C_DEFAULT, size=11),
            text=[_pct(pd_h[h], 1) for h in horizons], textposition="top center",
            error_y=default_ci, customdata=default_custom,
            hovertemplate="Mốc %{x}<br>Xác suất vỡ nợ tích lũy: %{y:.2%}<br>95% CI: %{customdata[0]}<br>Còn trong risk set: %{customdata[1]}<extra></extra>",
        )
        pp_keys = [h for h in horizons if h in pp_h]
        if pp_keys:
            pp_meta = [risk_by_horizon.get(h, {}).get("PREPAYMENT", {}) for h in pp_keys]
            pp_ci = _error_arrays([pp_h[h] for h in pp_keys], pp_meta, C_PREPAY)
            pp_custom = _hover_meta(pp_meta)
            fig.add_scatter(
                x=[_h_label(h) for h in pp_keys], y=[pp_h[h] for h in pp_keys],
                name="ZBC 01 (trả trước/đáo hạn, gộp)", mode="markers+text", marker=dict(color=C_PREPAY, size=11),
                text=[_pct(pp_h[h], 1) for h in pp_keys], textposition="bottom center",
                error_y=pp_ci, customdata=pp_custom,
                hovertemplate="Mốc %{x}<br>Xác suất CIF của ZBC 01: %{y:.2%}<br>95% CI: %{customdata[0]}<br>Còn trong risk set: %{customdata[1]}<extra></extra>",
            )
        fig.update_layout(
            height=400,
            margin=dict(l=10, r=10, t=40, b=10),
            yaxis=dict(
                tickformat=".0%",
                title="Xác suất tích lũy",
                gridcolor=LINE_GRID,
                range=[0, min(1.0, max([*pd_h.values(), *pp_h.values()], default=0.05) * 1.25 or 0.05)],
            ),
            xaxis=dict(title="Mốc theo dõi kể từ khi bắt đầu (tháng)", type="category"),
            legend=dict(orientation="h", y=1.12, x=0),
            plot_bgcolor="white",
            paper_bgcolor="white",
            font=dict(family=FONT_STACK, size=14, color=C_NAVY),
        )
        st.plotly_chart(fig, width="stretch")

    # ======================================================================
    # ④ ĐƯỜNG SỐNG SÓT (màu XANH LÁ = vẫn trả bình thường)
    # ======================================================================
    pairs = []
    if km_months is not None and km_survival is not None:
        for m, s in zip(list(km_months), list(km_survival)):
            if _ok(m) and _ok(s):
                pairs.append((float(m) / 12.0, float(s)))
    if pairs:
        st.markdown(
            _section(
                4,
                "Xác suất chưa ghi nhận vỡ nợ (Kaplan–Meier)",
                "Khoản trả trước được xem như kiểm duyệt; vì vậy 1 − KM có thể cao hơn xác suất vỡ nợ thực tế khi có rủi ro cạnh tranh.",
                C_OK,
                T_OK,
            ),
            unsafe_allow_html=True,
        )
        pairs.sort()
        years = [a for a, _ in pairs]
        surv = [b for _, b in pairs]
        low = max(0.0, min(surv) - 0.02)
        fig2 = go.Figure()
        if km_ci_low is not None and km_ci_high is not None and len(km_ci_low) == len(years):
            fig2.add_scatter(
                x=years + years[::-1],
                y=list(km_ci_high) + list(km_ci_low)[::-1],
                fill="toself", fillcolor="rgba(46,125,50,0.12)",
                line=dict(width=0), showlegend=False, hoverinfo="skip",
            )
        fig2.add_scatter(
            x=years,
            y=surv,
            mode="lines",
            line=dict(color=C_OK, width=3, shape="hv"),
            customdata=list(zip(km_ci_low or [None] * len(years), km_ci_high or [None] * len(years), km_at_risk or [None] * len(years))),
            hovertemplate="Sau %{x:.1f} năm: xác suất chưa ghi nhận vỡ nợ %{y:.1%}<br>Khoảng tin cậy 95%: %{customdata[0]:.1%}–%{customdata[1]:.1%}<br>Số khoản còn trong diện rủi ro: %{customdata[2]:,}<extra></extra>",
        )
        fig2.update_layout(
            height=380,
            margin=dict(l=10, r=10, t=20, b=10),
            xaxis=dict(title="Số năm kể từ mốc khởi tạo nghiên cứu", gridcolor=LINE_GRID),
            yaxis=dict(
                title="Xác suất chưa ghi nhận vỡ nợ",
                tickformat=".0%",
                range=[0, 1.005],
                gridcolor=LINE_GRID,
            ),
            showlegend=False,
            plot_bgcolor="white",
            paper_bgcolor="white",
            font=dict(family=FONT_STACK, size=14, color=C_NAVY),
        )
        st.plotly_chart(fig2, width="stretch")
    elif km_note:
        st.caption(km_note)

    if extra_section is not None:
        extra_section()

    # ======================================================================
    # Giải thích thuật ngữ
    # ======================================================================
    st.write("")
    with st.expander("Giải thích các thuật ngữ chuyên môn"):
        st.markdown(
           "- **PD:** xác suất một khoản vay xảy ra vỡ nợ trong một khoảng thời gian.\n"
            "- **Xác suất vỡ nợ tích lũy:** tỷ lệ vỡ nợ tích lũy đến một mốc thời gian, có xét đến các sự kiện cạnh tranh.\n"
            "- **CIF của ZBC 01:** xác suất tích lũy của kết cục gộp trả trước hoặc đáo hạn. Nguồn Freddie Mac không cho phép tách hai trường hợp chỉ bằng mã này.\n"
            "- **Kaplan–Meier:** ước tính xác suất chưa xảy ra vỡ nợ theo thời gian.\n"
            "- **Origination:** thời điểm bắt đầu khoản vay được đưa vào phân tích."
        )


# ==========================================================================
# XỬ LÝ DỮ LIỆU + HÀM render() ĐƯỢC app.py GỌI
# ==========================================================================
def _pick(df: pd.DataFrame, **conds) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    out = df.copy()

    for col, val in conds.items():
        if col in out.columns:
            out = out[out[col].astype(str) == str(val)]

    return out
def _pick_or_all(df: pd.DataFrame, **conds) -> pd.DataFrame:
    out = _pick(df, **conds)
    return out if not out.empty else df

def _per_horizon(df: pd.DataFrame, value_col: str) -> pd.DataFrame:
    """Return one published estimate per horizon, without averaging CIFs.
    Chịu được horizon dạng số (12) hoặc chữ ('12M')."""
    if df is None or df.empty or "horizon" not in df.columns or value_col not in df.columns:
        return pd.DataFrame()
    tmp = pd.DataFrame({
        "horizon": pd.to_numeric(
            df["horizon"].astype(str).str.extract(r"(\d+)")[0], errors="coerce"
        ),
        value_col: pd.to_numeric(df[value_col], errors="coerce"),
    }).dropna(subset=["horizon"])
    if tmp.empty:
        return pd.DataFrame()
    return tmp.drop_duplicates("horizon", keep="last").sort_values("horizon")


def _horizon_dict(df: pd.DataFrame, value_col: str) -> dict:
    """DataFrame (horizon, value_col) -> {horizon(int): value(float)}, bỏ giá trị NaN."""
    if df.empty:
        return {}
    return {
        int(r["horizon"]): float(r[value_col])
        for _, r in df.iterrows()
        if pd.notna(r[value_col])
    }


def _safe_rate(numerator, denominator):
    try:
        if denominator and pd.notna(numerator) and pd.notna(denominator):
            return float(numerator) / float(denominator)
    except (TypeError, ValueError, ZeroDivisionError):
        pass
    return None


def _horizon_detail(meta):
    if not meta:
        return "Khoảng tin cậy và số còn theo dõi chưa được công bố ở mốc này."
    low, high, n = meta.get("ci_lower"), meta.get("ci_upper"), meta.get("n_at_risk")
    pieces = []
    if pd.notna(low) and pd.notna(high):
        pieces.append(f"95% CI: {float(low):.2%}–{float(high):.2%}")
    if pd.notna(n):
        pieces.append(f"Còn trong risk set: {int(n):,}")
    return " · ".join(pieces) if pieces else "CI / số còn theo dõi không có trong nguồn."


def _error_arrays(values, metadata, color=C_DEFAULT):
    lows, highs = [], []
    for value, meta in zip(values, metadata):
        low, high = meta.get("ci_lower"), meta.get("ci_upper")
        lows.append(max(0.0, float(value) - float(low)) if pd.notna(low) else 0.0)
        highs.append(max(0.0, float(high) - float(value)) if pd.notna(high) else 0.0)
    return dict(type="data", symmetric=False, array=highs, arrayminus=lows,
                visible=any(x > 0 for x in highs + lows), color=color, thickness=1.5)


def _hover_meta(metadata):
    return [[
        f"{float(meta['ci_lower']):.2%}–{float(meta['ci_upper']):.2%}"
        if pd.notna(meta.get("ci_lower")) and pd.notna(meta.get("ci_upper")) else "không có",
        f"{int(meta['n_at_risk']):,}" if pd.notna(meta.get("n_at_risk")) else "không có",
    ] for meta in metadata]


# --------------------------------------------------------------------------
# Bộ lọc năm giải ngân (vintage)
# --------------------------------------------------------------------------
_VINTAGE_COLS = {"vintage", "vintage_year", "origination_year", "orig_year", "orig_yr", "vintage_yr"}
_ALL_LABELS = {"all", "tất cả", "tat ca", "nan", "none", ""}
ALL_YEARS = "Tất cả các năm"


def _vcol(df):
    """Tên cột năm giải ngân trong df (hoặc None)."""
    if df is None or df.empty:
        return None
    for c in df.columns:
        if str(c).strip().lower() in _VINTAGE_COLS:
            return c
    return None


def _vstr(series: pd.Series) -> pd.Series:
    """Chuẩn hóa nhãn vintage thành chuỗi: 2019.0 -> '2019', ' 2019 ' -> '2019'."""
    return series.astype(str).str.strip().str.replace(r"\.0$", "", regex=True)


def _sort_key(label: str):
    m = re.match(r"(\d{4})", label)
    return (int(m.group(1)) if m else 9999, label)


def _available_vintages(*dfs):
    """-> (danh sách nhãn vintage để chọn, cờ 'không có năm nào trong 2016–2026').
    Ưu tiên các năm nằm trong YEAR_MIN..YEAR_MAX; nếu không có năm nào thì
    hiện toàn bộ nhóm đang có trong dữ liệu (trừ 'All')."""
    labels = set()
    for df in dfs:
        vc = _vcol(df)
        if vc is None:
            continue
        for v in _vstr(df[vc]).unique():
            if v.lower() not in _ALL_LABELS:
                labels.add(v)
    in_range = {
        v for v in labels if re.fullmatch(r"\d{4}", v) and YEAR_MIN <= int(v) <= YEAR_MAX
    }
    if in_range:
        return sorted(in_range, key=_sort_key), False
    return sorted(labels, key=_sort_key), bool(labels)


def _only_vintage(df: pd.DataFrame, label: str) -> pd.DataFrame:
    """Lọc NGHIÊM NGẶT theo nhãn vintage (không tự quay về toàn bộ dữ liệu như _pick)."""
    vc = _vcol(df)
    if vc is None:
        return pd.DataFrame()
    return df[_vstr(df[vc]) == label]


def _show_diagnostics(**named_dfs) -> None:
    """Hiện cột / giá trị đang có để dễ biết vì sao chưa lọc được theo năm."""
    for name, df in named_dfs.items():
        if df is None or df.empty:
            st.markdown(f"**{name}**: rỗng")
            continue
        st.markdown(f"**{name}** — các cột: " + ", ".join(f"`{c}`" for c in df.columns))
        vc = _vcol(df)
        if vc is not None:
            vals = sorted(_vstr(df[vc]).unique(), key=_sort_key)[:30]
            st.markdown(f"Giá trị của cột `{vc}`: " + ", ".join(f"`{v}`" for v in vals))
        else:
            st.markdown("Không có cột nào giống `vintage`.")
        if "horizon" in df.columns:
            hs = sorted(_vstr(df["horizon"]).unique())[:20]
            st.markdown("Các mốc `horizon`: " + ", ".join(f"`{h}`" for h in hs))


def _vintage_text(v: str) -> str:
    return f"Năm {v}" if re.fullmatch(r"\d{4}", v) else v


def _render_vintage_compare(vintage_raw: pd.DataFrame, options: list, selected) -> None:
    """So sánh vintage chỉ từ bảng vintage production, không suy diễn từ portfolio PD."""
    if vintage_raw is None or vintage_raw.empty:
        return
    base = vintage_raw.copy().rename(columns={"horizon_months": "horizon", "default_cif": "cif_default", "vintage_year": "vintage"})
    vc = _vcol(base)
    if vc is None or not {"horizon", "cif_default"}.issubset(base.columns):
        st.info("Chưa có bảng CIF theo vintage; trang không dùng dữ liệu toàn danh mục để thay thế.")
        return
    if "follow_up_eligible" in base.columns:
        eligible = base["follow_up_eligible"]
        if not pd.api.types.is_bool_dtype(eligible):
            eligible = eligible.astype(str).str.strip().str.lower().isin({"true", "1", "yes", "y"})
        base = base[eligible]
    tmp = pd.DataFrame({
        "label": _vstr(base[vc]),
        "horizon": pd.to_numeric(base["horizon"].astype(str).str.extract(r"(\d+)")[0], errors="coerce"),
        "cif": pd.to_numeric(base["cif_default"], errors="coerce"),
        "loan_count": pd.to_numeric(base.get("loan_count", pd.Series(index=base.index, dtype=float)), errors="coerce"),
    }).dropna()
    tmp = tmp[tmp["label"].isin(options)]
    if tmp["label"].nunique() < 2:
        return

    st.markdown(
        _section(
            5,
            "Khác biệt về Default CIF giữa các vintage",
            "So sánh các năm đủ seasoning tại cùng một horizon; thiếu cột nghĩa là chưa đủ theo dõi.",
            C_DEFAULT,
            T_DEFAULT,
        ),
        unsafe_allow_html=True,
    )
    hs = sorted(int(h) for h in tmp["horizon"].unique())
    chosen = st.radio(
        "So sánh ở mốc thời gian",
        hs,
        index=hs.index(12) if 12 in hs else 0,
        horizontal=True,
        format_func=lambda h: f"Sau {_h_label(h)}",
        key="vintage_compare_horizon",
    )
    d = tmp[tmp["horizon"] == chosen].drop_duplicates("label", keep="first")
    if d.empty:
        st.info("Chưa có dữ liệu ở mốc thời gian này.")
        return
    d["label"] = pd.Categorical(d["label"], categories=options, ordered=True)
    d = d.sort_values("label")
    labels = [str(x) for x in d["label"]]
    colors = [
        C_DEFAULT if (selected is None or lb == selected) else "#D9C2B8" for lb in labels
    ]
    curves = ds.get_aj_curves(endpoint="DEFAULT", group_name="vintage_year")
    ci_low, ci_high, at_risk = [], [], []
    for label in labels:
        curve = curves[curves["group_value"].astype(str) == str(label)] if not curves.empty else pd.DataFrame()
        if not curve.empty:
            curve = curve[pd.to_numeric(curve["analysis_time"], errors="coerce") <= chosen].sort_values("analysis_time")
        point = curve.iloc[-1] if not curve.empty else None
        ci_low.append(point.get("ci_lower") if point is not None else None)
        ci_high.append(point.get("ci_upper") if point is not None else None)
        at_risk.append(point.get("n_at_risk") if point is not None else None)
    point_values = pd.to_numeric(d["cif"], errors="coerce").to_numpy()
    low_values = pd.to_numeric(pd.Series(ci_low), errors="coerce").to_numpy()
    high_values = pd.to_numeric(pd.Series(ci_high), errors="coerce").to_numpy()
    initial_n = pd.to_numeric(d.get("loan_count", pd.Series(index=d.index, dtype=float)), errors="coerce").to_numpy()
    fig = go.Figure()
    fig.add_bar(
        x=labels,
        y=point_values,
        marker_color=colors,
        text=[_pct(v, 1) for v in d["cif"]],
        textposition="outside",
        error_y=dict(type="data", symmetric=False,
                     array=np.maximum(0, high_values - point_values, where=np.isfinite(high_values), out=np.zeros(len(d))),
                     arrayminus=np.maximum(0, point_values - low_values, where=np.isfinite(low_values), out=np.zeros(len(d))),
                     visible=bool(np.isfinite(low_values).any() or np.isfinite(high_values).any()), color=C_DEFAULT),
        customdata=np.column_stack([low_values, high_values, at_risk, initial_n]),
        hovertemplate=("Năm giải ngân: %{x}<br>Default CIF: %{y:.2%}"
                       + "<br>95% CI: %{customdata[0]:.2%}–%{customdata[1]:.2%}"
                       + "<br>Còn trong risk set: %{customdata[2]:,.0f}"
                       + "<br>Số khoản ban đầu: %{customdata[3]:,.0f}<extra></extra>"),
    )
    fig.update_layout(
        height=380,
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis=dict(title="Năm giải ngân", type="category"),
        yaxis=dict(
            title="Xác suất vỡ nợ tích lũy",
            tickformat=".0%",
            gridcolor=LINE_GRID,
            range=[0, float(d["cif"].max()) * 1.25],
        ),
        showlegend=False,
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(family=FONT_STACK, size=14, color=C_NAVY),
    )
    st.plotly_chart(fig, width="stretch")
    st.caption(
        "Năm nào không có cột nghĩa là chưa đủ thời gian theo dõi ở mốc này "
        "(ví dụ khoản vay mới giải ngân gần đây) hoặc chưa có dữ liệu."
    )


def render() -> None:
    page_kicker(1, "Tổng quan danh mục theo nhóm khoản vay")

    with st.popover("Vấn đề & câu hỏi nghiên cứu"):
        st.markdown("### Vấn đề nghiên cứu")
        st.write(
            "Khoản vay thế chấp có thể kết thúc bằng vỡ nợ hoặc ZBC 01 (trả trước/đáo hạn gộp). "
            "Trả trước làm khoản vay rời khỏi nhóm còn có thể vỡ nợ, vì vậy cần "
            "được tính là một sự kiện cạnh tranh khi đo xác suất vỡ nợ theo thời gian. "
            "Nghiên cứu xem xét mối liên hệ của đặc điểm tín dụng/khoản vay và sự khác biệt giữa các năm giải ngân; không kết luận quan hệ nhân quả."
        )
        st.markdown("### Câu hỏi nghiên cứu")
        st.markdown(
            "1. Điểm tín dụng, LTV, DTI, lãi suất và kỳ hạn có liên quan thế nào đến rủi ro vỡ nợ theo thời gian?\n"
            "2. Xác suất vỡ nợ tích lũy thay đổi ra sao theo tuổi khoản vay?\n"
            "3. Tính ZBC 01 (trả trước/đáo hạn gộp) là sự kiện cạnh tranh làm thay đổi ước lượng vỡ nợ thế nào so với Kaplan–Meier?\n"
            "4. Rủi ro vỡ nợ có khác nhau giữa các năm giải ngân (vintage) không?"
        )

    summary_raw = ds.get_portfolio_summary()
    pd_raw = ds.get_pd_results()
    surv_raw = ds.get_survival_results()
    vintage_raw = ds.get_vintage_results()

    if summary_raw.empty and pd_raw.empty:
        st.warning(
            "Chưa đọc được dữ liệu portfolio_summary / pd_results. "
            "Kiểm tra thư mục query/ (xem cột 'Trạng thái dữ liệu' bên trái) "
            "hoặc đặt biến môi trường MORTGAGE_QUERY_DIR."
        )
        return

    # ---- Bộ lọc năm giải ngân ------------------------------------------------------
    # Vintage selectors must be backed by the dedicated vintage artifact.
    # Portfolio-level rows tagged "All" are never treated as vintage data.
    options, out_of_range = _available_vintages(vintage_raw)
    selected = None
    if options:
        if out_of_range:
            st.caption(
                f"Dữ liệu không có năm giải ngân nào trong khoảng {YEAR_MIN}–{YEAR_MAX}, "
                "nên đang hiển thị các nhóm giải ngân có trong dữ liệu."
            )
        choice = st.selectbox(
            "Chọn năm giải ngân (năm khách hàng vay tiền)",
            [ALL_YEARS] + options,
            index=0,
            format_func=lambda v: v if v == ALL_YEARS else _vintage_text(v),
            key="overview_vintage_v2",
        )
        selected = None if choice == ALL_YEARS else str(choice)
    else:
        selected = None

    # ---- Chọn dữ liệu theo phạm vi -------------------------------------------------
    km_note = None
    if selected is None:
        summary = _pick(summary_raw, vintage="All", score_band="All", ltv_band="All", dti_band="All")
        pd_res = _pick(pd_raw, group="portfolio", vintage="All")
        survival = _pick(surv_raw, group="portfolio")
    else:
        if not vintage_raw.empty and {"vintage", "horizon", "default_cif"}.issubset(vintage_raw.columns):
            v = vintage_raw[vintage_raw["vintage"].astype(str).str.replace(r"\.0$", "", regex=True) == selected].copy()
            count = pd.to_numeric(v.get("loan_count", pd.Series(dtype=float)), errors="coerce").dropna()
            summary = pd.DataFrame({"loan_count": [int(count.iloc[0])]}) if not count.empty else pd.DataFrame()
            pd_res = v.rename(columns={
                "default_cif": "cif_default", "prepayment_cif": "cif_prepayment",
                "n_at_risk": "number_at_risk", "follow_up_eligible": "follow_up_flag",
            })
            pd_res["group"] = "portfolio"
            survival = pd.DataFrame()
            km_note = "Kaplan–Meier curve chỉ có cho toàn danh mục; không ngoại suy theo vintage."
        else:
            summary = _pick(_only_vintage(summary_raw, selected), score_band="All", ltv_band="All", dti_band="All")
            pd_res = _pick(_only_vintage(pd_raw, selected), group="portfolio")
            if _vcol(surv_raw) is not None:
                survival = _pick(_only_vintage(surv_raw, selected), group="portfolio")
            else:
                survival = pd.DataFrame()
                km_note = "Đường sống sót hiện chỉ có cho toàn danh mục. Chọn \"Tất cả các năm\" để xem biểu đồ này."
        if summary.empty and pd_res.empty:
            st.info(f"Chưa có dữ liệu cho các khoản vay giải ngân {_vintage_text(selected).lower()}.")
            _render_vintage_compare(vintage_raw, options, selected)
            return

    # ---- Quy mô danh mục -------------------------------------------------------
    total_loans = None
    if not summary.empty and "loan_count" in summary.columns:
        loan_counts = pd.to_numeric(summary["loan_count"], errors="coerce")
        if loan_counts.notna().any():
            top = summary.loc[loan_counts.idxmax()]
            total_loans = int(loan_counts.max())
    # ---- PD / CIF theo horizon ---------------------------------------------------
    pd_by_horizon = _horizon_dict(_per_horizon(pd_res, "cif_default"), "cif_default")
    prepay_by_horizon = _horizon_dict(_per_horizon(pd_res, "cif_prepayment"), "cif_prepayment")
    # Show comparable fixed-horizon cumulative incidences; raw event shares in
    # portfolio_summary have unequal follow-up and must not be presented as PD.
    default_rate = pd_by_horizon.get(36)
    prepay_rate = prepay_by_horizon.get(36)

    risk_by_horizon = {}
    curve_group = "portfolio" if selected is None else "vintage_year"
    for endpoint in ("DEFAULT", "PREPAYMENT"):
        curves = ds.get_aj_curves(endpoint=endpoint, group_name=curve_group)
        if not curves.empty:
            if selected is not None and "group_value" in curves.columns:
                curves = curves[curves["group_value"].astype(str) == str(selected)]
            curves = curves[pd.to_numeric(curves["analysis_time"], errors="coerce").notna()]
            for h in pd_by_horizon:
                at_horizon = curves[pd.to_numeric(curves["analysis_time"], errors="coerce") <= h].sort_values("analysis_time")
                if at_horizon.empty:
                    continue
                point = at_horizon.iloc[-1]
                risk_by_horizon.setdefault(int(h), {})[endpoint] = {
                    "ci_lower": point.get("ci_lower"),
                    "ci_upper": point.get("ci_upper"),
                    "n_at_risk": point.get("n_at_risk"),
                }

    # ---- Đường sống sót Kaplan–Meier --------------------------------------------
    km_months = km_survival = km_ci_low = km_ci_high = km_at_risk = None
    if not survival.empty and {"analysis_time", "survival"}.issubset(survival.columns):
        km_df = pd.DataFrame({
            "analysis_time": pd.to_numeric(survival["analysis_time"], errors="coerce"),
            "survival": pd.to_numeric(survival["survival"], errors="coerce"),
            "ci_low": pd.to_numeric(survival["ci_low"] if "ci_low" in survival else pd.Series(index=survival.index, dtype=float), errors="coerce"),
            "ci_high": pd.to_numeric(survival["ci_high"] if "ci_high" in survival else pd.Series(index=survival.index, dtype=float), errors="coerce"),
            "n_at_risk": pd.to_numeric(survival["n_at_risk"] if "n_at_risk" in survival else pd.Series(index=survival.index, dtype=float), errors="coerce"),
        }).dropna(subset=["analysis_time", "survival"])
        if not km_df.empty:
            km_df = km_df.drop_duplicates("analysis_time", keep="last").sort_values("analysis_time")
            km_months = km_df["analysis_time"].tolist()
            km_survival = km_df["survival"].tolist()
            km_ci_low = km_df["ci_low"].tolist()
            km_ci_high = km_df["ci_high"].tolist()
            km_at_risk = km_df["n_at_risk"].tolist()

    render_plain_overview(
        loan_count=total_loans,
        default_rate=default_rate,
        prepay_rate=prepay_rate,
        pd_by_horizon=pd_by_horizon,
        prepay_by_horizon=prepay_by_horizon or None,
        km_months=km_months,
        km_survival=km_survival,
        km_ci_low=km_ci_low,
        km_ci_high=km_ci_high,
        km_at_risk=km_at_risk,
        scope_label=selected,
        km_note=km_note,
        risk_by_horizon=risk_by_horizon,
        extra_section=lambda: _render_vintage_compare(vintage_raw, options, selected),
    )
