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

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.pages.portfolio_risk import _render_intro
from app.services import data_service as ds


# --------------------------------------------------------------------------
# BẢNG MÀU (chỉnh ở đây là đổi toàn trang)
# --------------------------------------------------------------------------
C_NAVY = "#1F4E79"      # tiêu đề chung / tóm tắt
C_TOTAL = "#2E7D32"     # tổng số khoản vay
C_DEFAULT = "#C62828"   # vỡ nợ
C_PREPAY = "#1565C0"    # trả trước hạn
C_OK = "#2E7D32"         # survival / trạng thái chưa xảy ra default
C_WARN = "#EF6C00"      # rủi ro trung bình

T_NAVY = "#EAF1F8"
T_TOTAL = "#ECEFF1"
T_DEFAULT = "#FDECEA"
T_PREPAY = "#E3F0FD"
T_OK = "#E8F5E9"
T_WARN = "#FFF3E0"

DOT_OK = "#A5D6A7"      # chấm khoản vay bình thường
LINE_GRID = "#E6EBF0"

HORIZON_LABEL = {12: "1 năm", 24: "2 năm", 36: "3 năm", 48: "4 năm", 60: "5 năm"}

# Khoảng năm giải ngân (vintage) cho phép chọn
YEAR_MIN = 2016
YEAR_MAX = 2026

# CSS viết liền, không thụt dòng, không dòng trống -> markdown không hiểu nhầm là code
_CSS = (
    "<style>"
    ".po-sec{display:flex;align-items:center;gap:14px;margin:34px 0 14px 0;"
    "padding:10px 16px;border-radius:10px;}"
    ".po-num{flex:0 0 auto;width:34px;height:34px;border-radius:50%;color:#fff;"
    "font-weight:700;font-size:1.05rem;display:flex;align-items:center;justify-content:center;}"
    ".po-sec-t{font-size:1.3rem;font-weight:700;color:#14263A;line-height:1.3;}"
    ".po-sec-s{font-size:0.95rem;color:#55606E;margin-top:2px;}"
    ".po-summary{border-radius:12px;padding:18px 22px;font-size:1.15rem;line-height:1.75;"
    "color:#14263A;}"
    ".po-card{border-radius:12px;padding:16px 18px;height:100%;box-sizing:border-box;}"
    ".po-title{font-size:0.95rem;font-weight:600;margin-bottom:4px;}"
    ".po-big{font-size:2.1rem;font-weight:800;line-height:1.2;}"
    ".po-plain{font-size:1rem;color:#14263A;margin-top:6px;line-height:1.5;}"
    ".po-note{font-size:0.82rem;color:#5F6B78;margin-top:8px;line-height:1.45;}"
    ".po-badge{display:inline-block;padding:3px 12px;border-radius:999px;color:#fff;"
    "font-weight:700;font-size:0.9rem;}"
    ".po-result{border-radius:12px;padding:18px 22px;}"
    ".po-headline{font-size:1.25rem;color:#14263A;line-height:1.7;}"
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
        f'<div class="po-sec" style="background:{tint};border-left:8px solid {color}">'
        f'<div class="po-num" style="background:{color}">{num}</div>'
        f'<div><div class="po-sec-t">{title}</div><div class="po-sec-s">{sub}</div></div></div>'
    )


def _card(title: str, big: str, plain: str, note: str, color: str, tint: str) -> str:
    note_html = f'<div class="po-note">{note}</div>' if note else ""
    return (
        f'<div class="po-card" style="background:{tint};border:1px solid {color}55;'
        f'border-top:6px solid {color}">'
        f'<div class="po-title" style="color:{color}">{title}</div>'
        f'<div class="po-big" style="color:{color}">{big}</div>'
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
    scope_label=None,
    km_note=None,
    extra_section=None,
) -> None:
    st.markdown(_CSS, unsafe_allow_html=True)

    pd_h = _clean_horizons(pd_by_horizon)
    pp_h = _clean_horizons(prepay_by_horizon)
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
            f'Trong <b>100 khoản vay</b>, khoảng <b style="color:{C_DEFAULT}">'
            f"{_per_txt(default_rate, 100)} khoản</b> khách hàng không trả được nợ (vỡ nợ)"
        )
        if _ok(prepay_rate):
            parts[-1] += (
                f' và khoảng <b style="color:{C_PREPAY}">{_per_txt(prepay_rate, 100)} khoản</b> '
                f"được khách hàng trả xong sớm trước hạn."
            )
        else:
            parts[-1] += "."
    elif _ok(prepay_rate):
        parts.append(
            f'Trong <b>100 khoản vay</b>, khoảng <b style="color:{C_PREPAY}">'
            f"{_per_txt(prepay_rate, 100)} khoản</b> được khách hàng trả xong sớm trước hạn."
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
                "Tỷ lệ vỡ nợ",
                _pct(default_rate),
                f"Cứ 100 khoản vay có khoảng <b>{_per_txt(default_rate, 100)}</b> khoản không trả được nợ",
                "Vỡ nợ = khoản vay không trả được nợ",
                C_DEFAULT,
                T_DEFAULT,
            ),
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            _card(
                "Tỷ lệ trả trước hạn",
                _pct(prepay_rate),
                f"Cứ 100 khoản vay có khoảng <b>{_per_txt(prepay_rate, 100)}</b> khoản được trả xong sớm",
                "Trả trước hạn = khoản vay được tất toán trước thời hạn",
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
                    f'{_dots_html(p, 1000)}'
                    f'<div class="po-legend">'
                    f'<span class="po-dot" style="background:{C_DEFAULT}"></span>'
                    f'Khoản vay đã xảy ra vỡ nợ'
                    f'<span class="po-dot" style="background:{DOT_OK}"></span>'
                    f'Khoản vay chưa xảy ra vỡ nợ'
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
                            "",
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
                "Vỡ nợ và trả trước hạn theo thời gian",
                "So sánh tỷ lệ vỡ nợ tích lũy và trả trước hạn tích lũy tại các mốc thời gian.",
                C_PREPAY,
                T_PREPAY,
            ),
            unsafe_allow_html=True,
        )
        fig = go.Figure()
        fig.add_bar(
            x=[f"Sau {_h_label(h)}" for h in horizons],
            y=[pd_h[h] for h in horizons],
            name="Vỡ nợ (không trả được nợ)",
            marker_color=C_DEFAULT,
            text=[_pct(pd_h[h], 1) for h in horizons],
            textposition="outside",
            hovertemplate="%{x}: %{y:.2%} khoản vay vỡ nợ<extra></extra>",
        )
        ymax = max(pd_h.values())
        pp_keys = [h for h in horizons if h in pp_h]
        if pp_keys:
            fig.add_bar(
                x=[f"Sau {_h_label(h)}" for h in pp_keys],
                y=[pp_h[h] for h in pp_keys],
                name="Trả nợ trước hạn",
                marker_color=C_PREPAY,
                text=[_pct(pp_h[h], 1) for h in pp_keys],
                textposition="outside",
                hovertemplate="%{x}: %{y:.2%} khoản vay trả trước hạn<extra></extra>",
            )
            ymax = max(ymax, max(pp_h[h] for h in pp_keys))
        fig.update_layout(
            barmode="group",
            height=400,
            margin=dict(l=10, r=10, t=40, b=10),
            yaxis=dict(
                tickformat=".0%",
                title="Tỷ lệ trên tổng số khoản vay",
                gridcolor=LINE_GRID,
                range=[0, ymax * 1.25],
            ),
            legend=dict(orientation="h", y=1.12, x=0),
            plot_bgcolor="white",
            paper_bgcolor="white",
            font=dict(size=14),
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
                "Xác suất chưa xảy ra vỡ nợ theo thời gian",
                "Đường Kaplan–Meier thể hiện xác suất khoản vay chưa xảy ra sự kiện vỡ nợ khi tuổi khoản vay tăng.",
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
        fig2.add_scatter(
            x=years,
            y=surv,
            mode="lines",
            line=dict(color=C_OK, width=3),
            fill="tozeroy",
            fillcolor="rgba(46,125,50,0.12)",
            hovertemplate="Sau %{x:.1f} năm: %{y:.1%} xác suất chưa xảy ra vỡ nợ<extra></extra>",
        )
        fig2.update_layout(
            height=380,
            margin=dict(l=10, r=10, t=20, b=10),
            xaxis=dict(title="Số năm kể từ khi giải ngân", gridcolor=LINE_GRID),
            yaxis=dict(
                title="Xác suất chưa xảy ra vỡ nợ",
                tickformat=".0%",
                range=[low, 1.005],
                gridcolor=LINE_GRID,
            ),
            showlegend=False,
            plot_bgcolor="white",
            paper_bgcolor="white",
            font=dict(size=14),
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
            "- **Default CIF:** tỷ lệ vỡ nợ tích lũy đến một mốc thời gian, có xét đến các sự kiện cạnh tranh.\n"
            "- **Prepayment CIF:** tỷ lệ trả trước hạn tích lũy đến một mốc thời gian.\n"
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
    """Mỗi horizon 1 dòng (lấy trung bình nếu còn nhiều dòng).
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
    return tmp.groupby("horizon", as_index=False)[value_col].mean().sort_values("horizon")


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


def _render_vintage_compare(pd_raw: pd.DataFrame, options: list, selected) -> None:
    """Mục 5: so sánh tỷ lệ vỡ nợ giữa các năm giải ngân."""
    vc = _vcol(pd_raw)
    if vc is None or not {"horizon", "cif_default"}.issubset(pd_raw.columns):
        return
    base = pd_raw
    if "group" in base.columns:
        g = base[base["group"].astype(str) == "portfolio"]
        base = g if not g.empty else base
    tmp = pd.DataFrame({
        "label": _vstr(base[vc]),
        "horizon": pd.to_numeric(base["horizon"].astype(str).str.extract(r"(\d+)")[0], errors="coerce"),
        "cif": pd.to_numeric(base["cif_default"], errors="coerce"),
    }).dropna()
    tmp = tmp[tmp["label"].isin(options)]
    if tmp["label"].nunique() < 2:
        return

    st.markdown(
        _section(
            5,
            "Khác biệt về tỷ lệ vỡ nợ giữa các năm giải ngân",
            "So sánh tỷ lệ vỡ nợ tích lũy tại cùng một mốc thời gian giữa các năm giải ngân.",
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
    d = tmp[tmp["horizon"] == chosen].groupby("label", as_index=False)["cif"].mean()
    if d.empty:
        st.info("Chưa có dữ liệu ở mốc thời gian này.")
        return
    d["label"] = pd.Categorical(d["label"], categories=options, ordered=True)
    d = d.sort_values("label")
    labels = [str(x) for x in d["label"]]
    colors = [
        C_DEFAULT if (selected is None or lb == selected) else "#E9A3A3" for lb in labels
    ]
    fig = go.Figure()
    fig.add_bar(
        x=labels,
        y=d["cif"].tolist(),
        marker_color=colors,
        text=[_pct(v, 1) for v in d["cif"]],
        textposition="outside",
        hovertemplate="Giải ngân %{x}: %{y:.2%} khoản vay vỡ nợ<extra></extra>",
    )
    fig.update_layout(
        height=380,
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis=dict(title="Năm giải ngân", type="category"),
        yaxis=dict(
            title="Tỷ lệ vỡ nợ",
            tickformat=".0%",
            gridcolor=LINE_GRID,
            range=[0, float(d["cif"].max()) * 1.25],
        ),
        showlegend=False,
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(size=14),
    )
    st.plotly_chart(fig, width="stretch")
    st.caption(
        "Năm nào không có cột nghĩa là chưa đủ thời gian theo dõi ở mốc này "
        "(ví dụ khoản vay mới giải ngân gần đây) hoặc chưa có dữ liệu."
    )


def render() -> None:
    st.markdown("<p style='color:#1E3A8A; font-weight:bold; font-size:15px; margin-bottom:4px;'>TRANG 1 · TỔNG QUAN DANH MỤC THEO NHÓM KHOẢN VAY</p>", unsafe_allow_html=True)

    summary_raw = ds.get_portfolio_summary()
    pd_raw = ds.get_pd_results()
    surv_raw = ds.get_survival_results()

    if summary_raw.empty and pd_raw.empty:
        st.warning(
            "Chưa đọc được dữ liệu portfolio_summary / pd_results. "
            "Kiểm tra thư mục query/ (xem cột 'Trạng thái dữ liệu' bên trái) "
            "hoặc đặt biến môi trường MORTGAGE_QUERY_DIR."
        )
        return

    # ---- Bộ lọc năm giải ngân ------------------------------------------------------
    options, out_of_range = _available_vintages(pd_raw, summary_raw)
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
        summary = _pick(_only_vintage(summary_raw, selected), score_band="All", ltv_band="All", dti_band="All")
        pd_res = _pick(_only_vintage(pd_raw, selected), group="portfolio")
        if _vcol(surv_raw) is not None:
            survival = _pick(_only_vintage(surv_raw, selected), group="portfolio")
        else:
            survival = pd.DataFrame()
            km_note = (
                "Đường sống sót hiện chỉ có cho toàn danh mục. "
                "Chọn \"Tất cả các năm\" để xem biểu đồ này."
            )
        if summary.empty and pd_res.empty:
            st.info(f"Chưa có dữ liệu cho các khoản vay giải ngân {_vintage_text(selected).lower()}.")
            _render_vintage_compare(pd_raw, options, selected)
            return

    # ---- Chỉ số tổng quan ------------------------------------------------------
    total_loans = default_rate = prepay_rate = None
    if not summary.empty and "loan_count" in summary.columns:
        loan_counts = pd.to_numeric(summary["loan_count"], errors="coerce")
        if loan_counts.notna().any():
            top = summary.loc[loan_counts.idxmax()]
            total_loans = int(loan_counts.max())
            if "default_count" in summary.columns:
                default_rate = _safe_rate(top["default_count"], total_loans)
            if "prepayment_count" in summary.columns:
                prepay_rate = _safe_rate(top["prepayment_count"], total_loans)

    # ---- PD / CIF theo horizon ---------------------------------------------------
    pd_by_horizon = _horizon_dict(_per_horizon(pd_res, "cif_default"), "cif_default")
    prepay_by_horizon = _horizon_dict(_per_horizon(pd_res, "cif_prepayment"), "cif_prepayment")

    # ---- Đường sống sót Kaplan–Meier --------------------------------------------
    km_months = km_survival = None
    if not survival.empty and {"analysis_time", "survival"}.issubset(survival.columns):
        km_df = pd.DataFrame({
            "analysis_time": pd.to_numeric(survival["analysis_time"], errors="coerce"),
            "survival": pd.to_numeric(survival["survival"], errors="coerce"),
        }).dropna()
        if not km_df.empty:
            km_df = (
                km_df.groupby("analysis_time", as_index=False)["survival"]
                .mean()
                .sort_values("analysis_time")
            )
            km_months = km_df["analysis_time"].tolist()
            km_survival = km_df["survival"].tolist()

    render_plain_overview(
        loan_count=total_loans,
        default_rate=default_rate,
        prepay_rate=prepay_rate,
        pd_by_horizon=pd_by_horizon,
        prepay_by_horizon=prepay_by_horizon or None,
        km_months=km_months,
        km_survival=km_survival,
        scope_label=selected,
        km_note=km_note,
        extra_section=lambda: _render_vintage_compare(pd_raw, options, selected),
    )