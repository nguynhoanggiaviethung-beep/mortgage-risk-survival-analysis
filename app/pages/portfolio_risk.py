"""
Trang 2 — Rủi ro danh mục
Trả lời: "Nhóm khoản vay nào có mức rủi ro khác nhau?"

Nội dung trang:
  1. Hướng dẫn đọc trang (định nghĩa Default CIF, horizon, competing risk)
  2. Bộ chọn: chiều so sánh, horizon, chỉ số
  3. Tóm tắt: baseline danh mục, nhóm rủi ro cao/thấp nhất, chênh lệch
  4. Biểu đồ cột theo nhóm + đường baseline danh mục
  5. Heatmap rủi ro theo nhóm x horizon
  6. Chiều nào phân biệt rủi ro mạnh nhất
  7. Bảng chi tiết + nhận xét tự động
  8. Xu hướng theo Origination Vintage (vintage_results)
  9. Ghi chú phương pháp

Nguồn dữ liệu: pd_results (group, group_value, horizon, cif_default,
cif_prepayment, number_at_risk, follow_up_flag), vintage_results.
Trang chỉ gọi ds.get_xxx() không tham số rồi lọc bằng pandas — không tự tính lại metric.
"""

import re

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.components.kpi_card import kpi_row
from app.components.styling import section_title
from app.config import DANGER, FONT_STACK, PRIMARY, PRIMARY_DARK, SUCCESS, TEXT_MUTED
from app.services import data_service as ds

NEAR_COLOR = "#7FB3D5"
DIM_ORDER = ["Credit Score", "LTV", "DTI", "Interest Rate", "Loan Term", "Origination Vintage"]
METRICS = {
    "Default CIF": "cif_default",
    "Voluntary Prepayment CIF": "cif_prepayment",
}
MIN_AT_RISK_FOR_RANKING = 100


# ---------------------------------------------------------------- helpers ----
def _dim_label(key) -> str:
    k = str(key).lower()
    if "score" in k or "fico" in k:
        return "Credit Score"
    if "ltv" in k:
        return "LTV"
    if "dti" in k:
        return "DTI"
    if "rate" in k or "interest" in k:
        return "Interest Rate"
    if "term" in k:
        return "Loan Term"
    if "vintage" in k or "orig" in k:
        return "Origination Vintage"
    return str(key)


def _band_key(label):
    """Sắp xếp band theo thứ tự tự nhiên: <650, 650–699, 700–749, 750+."""
    s = str(label).strip()
    m = re.search(r"-?\d+(\.\d+)?", s)
    if not m:
        return (1, 0.0, s)
    n = float(m.group())
    if s.startswith(("<", "≤")):
        n -= 0.5
    elif s.startswith((">", "≥")) or s.endswith("+"):
        n += 0.5
    return (0, n, s)


def _pct(v, digits=2) -> str:
    return f"{v:.{digits}%}" if v is not None and pd.notna(v) else "—"


def _layout(fig: go.Figure, height: int = 360) -> go.Figure:
    fig.update_layout(
        height=height,
        font=dict(family=FONT_STACK, size=12, color="#1A1A1A"),
        plot_bgcolor="white",
        paper_bgcolor="white",
        margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor="#EEF2F6")
    return fig


def _chart_card_open():
    st.markdown('<div class="chart-card">', unsafe_allow_html=True)


def _chart_card_close():
    st.markdown("</div>", unsafe_allow_html=True)


def _not_enough(flag_series: pd.Series) -> bool:
    return flag_series.astype(str).str.lower().isin(["false", "0", "no"]).any()


# ------------------------------------------------------------------ intro ----
def _render_intro() -> None:
    st.markdown(
        f"""
        <div style="background:#F5F8FB;border:1px solid #BBDAF0;border-left:5px solid {PRIMARY};
                    border-radius:10px;padding:14px 18px;margin-bottom:6px;">
          <div style="font-weight:700;color:{PRIMARY_DARK};margin-bottom:6px;">Cách đọc trang này</div>
          <div style="font-size:14px;line-height:1.6;">
            <b>Default CIF</b> (Cumulative Incidence of Default) là xác suất một khoản vay
            <b>đã vỡ nợ</b> trong vòng <i>t</i> tháng kể từ origination, có tính đến việc khoản vay
            cũng có thể bị <b>tất toán sớm (Voluntary Prepayment)</b> trước khi vỡ nợ.
            Đây chính là <b>PD(t)</b> của dự án. Trang hiển thị PD theo vintage và các mốc theo dõi
            có đủ dữ liệu; các đường CIF theo FICO, LTV và DTI được ước lượng riêng cho từng nhóm.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ------------------------------------------------------------------- main ----
def render() -> None:
    st.caption("Trang 2 · Rủi ro danh mục theo nhóm khoản vay")
    _render_intro()

    pd_raw = ds.get_pd_results()
    required = {"horizon", "group", "group_value", "cif_default"}
    if pd_raw.empty or not required.issubset(pd_raw.columns):
        st.warning(
            "Chưa có pd_results hợp lệ (cần các cột: horizon, group, group_value, cif_default). "
            "Trang sẽ hiển thị đầy đủ khi dataset này được publish vào query/."
        )
        _render_vintage_section(None)
        return

    pd_raw = pd_raw.copy()
    pd_raw["group"] = pd_raw["group"].astype(str)
    pd_raw["horizon"] = pd_raw["horizon"].astype(int)

    baseline_df = pd_raw[pd_raw["group"] == "portfolio"]
    data = pd_raw[pd_raw["group"] != "portfolio"]
    if "vintage" in data.columns and (data["vintage"].astype(str) == "All").any():
        data = data[data["vintage"].astype(str) == "All"]

    if data.empty:
        st.info(
            "Run backend hiện tại đã có PD toàn danh mục và theo năm vintage. "
            "Chưa có bảng CIF ước lượng riêng theo nhóm FICO/LTV/DTI, nên trang không tạo các nhóm thay thế."
        )
        if not baseline_df.empty:
            baseline_df = baseline_df.sort_values("horizon")
            eligible = baseline_df[baseline_df.get("follow_up_flag", True).astype(bool)] if "follow_up_flag" in baseline_df else baseline_df
            if not eligible.empty:
                section_title("Default CIF toàn danh mục")
                cols = st.columns(len(eligible))
                for col, (_, row) in zip(cols, eligible.iterrows()):
                    with col:
                        st.metric(f"{int(row['horizon'])} tháng", _pct(row["cif_default"]))
        _render_vintage_section(None)
        return

    # ---- chiều so sánh khả dụng ------------------------------------------------
    dim_map = {}
    for g in data["group"].unique():
        dim_map.setdefault(_dim_label(g), g)
    dim_labels = sorted(dim_map, key=lambda x: DIM_ORDER.index(x) if x in DIM_ORDER else 99)
    horizons = sorted(data["horizon"].unique())

    section_title("Bộ lọc so sánh")
    c1, c2, c3 = st.columns([3, 1, 2])
    with c1:
        dim_label = st.radio("So sánh theo đặc điểm", dim_labels, horizontal=True)
    with c2:
        default_idx = horizons.index(36) if 36 in horizons else len(horizons) - 1
        horizon = st.selectbox("Horizon (tháng)", horizons, index=default_idx)
    with c3:
        metric_options = [k for k, v in METRICS.items() if v in data.columns]
        metric_label = st.radio("Chỉ số", metric_options, horizontal=True)
    metric = METRICS[metric_label]
    is_default = metric == "cif_default"

    group_key = dim_map[dim_label]
    dim_all = data[data["group"] == group_key]
    agg = {c: "mean" for c in ["cif_default", "cif_prepayment"] if c in dim_all.columns}
    if "number_at_risk" in dim_all.columns:
        agg["number_at_risk"] = "max"
    if "follow_up_flag" in dim_all.columns:
        agg["follow_up_flag"] = "min"

    sub = dim_all[dim_all["horizon"] == horizon]
    if sub.empty:
        st.info(f"Chưa có bản ghi cho '{dim_label}' tại horizon {horizon}M.")
        _render_vintage_section(None)
        return

    sub = sub.groupby("group_value", as_index=False).agg(agg)
    if "follow_up_flag" in sub.columns and _not_enough(sub["follow_up_flag"]):
        st.warning(
            f"Một số nhóm chưa có đủ quan sát còn theo dõi tại horizon {horizon}M; "
            "các nhóm đó được giữ là chưa có ước lượng, không ngoại suy CIF."
        )
        sub = sub[sub["follow_up_flag"].astype(bool)].copy()
    if sub.empty or sub[metric].dropna().empty:
        st.info(f"Không nhóm nào có đủ dữ liệu quan sát để ước lượng tại horizon {horizon}M.")
        _render_vintage_section(None)
        return
    sub = sub.sort_values("group_value", key=lambda s: s.map(_band_key)).reset_index(drop=True)
    if "number_at_risk" in sub and (sub["number_at_risk"] < MIN_AT_RISK_FOR_RANKING).any():
        st.warning(
            f"Nhóm có dưới {MIN_AT_RISK_FOR_RANKING} khoản vay còn at risk vẫn được hiển thị, "
            "nhưng không dùng để xếp hạng vì ước lượng ở nhóm nhỏ dễ biến động."
        )

    base_val = None
    if not baseline_df.empty and metric in baseline_df.columns:
        b = baseline_df[baseline_df["horizon"] == horizon][metric]
        base_val = float(b.mean()) if not b.empty else None
    sub["ratio"] = sub[metric] / base_val if base_val else float("nan")

    # ---- KPI tóm tắt ---------------------------------------------------------------
    section_title(f"Tóm tắt · {dim_label} · {metric_label} {horizon}M")
    ranked = sub[~sub["group_value"].astype(str).str.casefold().isin({"missing", "unknown"})]
    if "number_at_risk" in ranked:
        adequately_supported = ranked[ranked["number_at_risk"] >= MIN_AT_RISK_FOR_RANKING]
        if not adequately_supported.empty:
            ranked = adequately_supported
    ranked = ranked[ranked[metric].notna()]
    if ranked.empty:
        ranked = sub[sub[metric].notna()]
    hi = ranked.loc[ranked[metric].idxmax()]
    lo = ranked.loc[ranked[metric].idxmin()]
    spread = (hi[metric] / lo[metric]) if lo[metric] and lo[metric] > 0 else None
    kpi_row([
        {"label": f"Baseline danh mục ({horizon}M)", "value": _pct(base_val),
         "help_text": "Mức trung bình toàn danh mục (dòng 'portfolio' trong pd_results)"},
        {"label": f"Cao nhất: {hi['group_value']}", "value": _pct(hi[metric]),
         "help_text": f"{hi['ratio']:.2f}× baseline" if pd.notna(hi["ratio"]) else None},
        {"label": f"Thấp nhất: {lo['group_value']}", "value": _pct(lo[metric]),
         "help_text": f"{lo['ratio']:.2f}× baseline" if pd.notna(lo["ratio"]) else None},
        {"label": "Chênh lệch cao/thấp", "value": f"{spread:.1f}×" if spread else "—",
         "help_text": "Nhóm cao nhất gấp bao nhiêu lần nhóm thấp nhất"},
    ])

    # ---- Biểu đồ cột -------------------------------------------------------------------
    section_title(f"{metric_label} {horizon}M theo {dim_label}")
    if is_default and base_val:
        colors = [
            DANGER if r >= 1.25 else (SUCCESS if r <= 0.8 else NEAR_COLOR) for r in sub["ratio"]
        ]
        st.markdown(
            f'<span style="color:{DANGER};">■</span> cao hơn baseline ≥25% &nbsp;'
            f'<span style="color:{NEAR_COLOR};">■</span> gần baseline &nbsp;'
            f'<span style="color:{SUCCESS};">■</span> thấp hơn baseline ≥20%',
            unsafe_allow_html=True,
        )
    else:
        colors = PRIMARY

    fig = go.Figure(go.Bar(
        x=sub["group_value"], y=sub[metric], marker_color=colors,
        text=[_pct(v) for v in sub[metric]], textposition="outside",
        hovertemplate="%{x}<br>" + metric_label + ": %{y:.2%}<extra></extra>",
    ))
    if base_val:
        fig.add_hline(y=base_val, line_dash="dash", line_color=TEXT_MUTED,
                      annotation_text=f"Baseline danh mục {_pct(base_val)}",
                      annotation_position="top left")
    fig.update_yaxes(title=metric_label, tickformat=".0%", rangemode="tozero")
    fig.update_xaxes(title=dim_label)
    _chart_card_open()
    st.plotly_chart(_layout(fig), width="stretch")
    _chart_card_close()

    # ---- Heatmap nhóm x horizon ---------------------------------------------------------
    section_title(f"Rủi ro theo nhóm qua các horizon — {dim_label}",
                  "Màu đậm hơn = rủi ro cao hơn. Cho thấy nhóm nào tích lũy rủi ro nhanh hơn theo thời gian.")
    pivot = (
        dim_all.groupby(["group_value", "horizon"], as_index=False)[metric].mean()
        .pivot(index="group_value", columns="horizon", values=metric)
    )
    pivot = pivot.loc[sorted(pivot.index, key=_band_key)]
    heat = go.Figure(go.Heatmap(
        z=pivot.values, x=[f"{int(h)}M" for h in pivot.columns], y=list(pivot.index),
        text=[[_pct(v) for v in row] for row in pivot.values], texttemplate="%{text}",
        colorscale=[[0, "#EAF3FA"], [0.5, "#7FB3D5"], [1, PRIMARY_DARK]],
        colorbar=dict(title=metric_label, tickformat=".0%"),
        hovertemplate="%{y} · %{x}<br>%{z:.2%}<extra></extra>",
    ))
    heat.update_yaxes(autorange="reversed")
    _chart_card_open()
    st.plotly_chart(_layout(heat, height=max(240, 60 * len(pivot) + 80)), width="stretch")
    _chart_card_close()

    # ---- Chiều nào phân biệt rủi ro mạnh nhất -------------------------------------------
    section_title(f"Đặc điểm nào phân biệt rủi ro mạnh nhất? ({horizon}M)",
                  "Tỷ lệ giữa nhóm rủi ro cao nhất và thấp nhất trong từng đặc điểm — thanh dài = phân biệt mạnh.")
    rows = []
    for label, gkey in dim_map.items():
        d = data[(data["group"] == gkey) & (data["horizon"] == horizon)]
        d = d[~d["group_value"].astype(str).str.casefold().isin({"missing", "unknown"})]
        if "number_at_risk" in d:
            d = d[d["number_at_risk"] >= MIN_AT_RISK_FOR_RANKING]
        d = d.groupby("group_value")[metric].mean()
        if len(d) >= 2 and d.min() > 0:
            rows.append((label, d.max() / d.min(), d.idxmax(), d.idxmin()))
    if rows:
        rows.sort(key=lambda r: r[1])
        sp = go.Figure(go.Bar(
            x=[r[1] for r in rows], y=[r[0] for r in rows], orientation="h",
            marker_color=[PRIMARY if r[0] == dim_label else NEAR_COLOR for r in rows],
            text=[f"{r[1]:.1f}×  ({r[2]} vs {r[3]})" for r in rows], textposition="outside",
            hovertemplate="%{y}: %{x:.2f}×<extra></extra>",
        ))
        sp.update_xaxes(title="Cao nhất / thấp nhất (×)", rangemode="tozero")
        _chart_card_open()
        st.plotly_chart(_layout(sp, height=max(240, 55 * len(rows) + 80)), width="stretch")
        _chart_card_close()
    else:
        st.info("Chưa đủ nhóm để so sánh giữa các đặc điểm.")

    # ---- Bảng chi tiết + nhận xét ---------------------------------------------------------
    section_title("Bảng chi tiết")
    table = pd.DataFrame({dim_label: sub["group_value"]})
    table["Default CIF (%)"] = sub["cif_default"] * 100 if "cif_default" in sub.columns else None
    if "cif_prepayment" in sub.columns:
        table["Prepayment CIF (%)"] = sub["cif_prepayment"] * 100
    if base_val:
        table["So với baseline (×)"] = sub["ratio"]
    if "number_at_risk" in sub.columns:
        table["Number at risk"] = sub["number_at_risk"]
    if "follow_up_flag" in sub.columns:
        table["Follow-up"] = sub["follow_up_flag"].astype(str).str.lower().map(
            lambda s: "Chưa đủ" if s in ("false", "0", "no") else "Đủ")
    if "number_at_risk" in sub.columns:
        table.loc[sub["number_at_risk"] < MIN_AT_RISK_FOR_RANKING, "Follow-up"] = "Mẫu at risk nhỏ"
    if sub["group_value"].astype(str).str.casefold().isin({"missing", "unknown"}).any():
        st.caption("Nhóm thiếu dữ liệu vẫn được hiển thị riêng; không đưa nhóm này vào xếp hạng rủi ro.")

    col_cfg = {
        "Default CIF (%)": st.column_config.ProgressColumn(
            "Default CIF", format="%.2f%%", min_value=0,
            max_value=float(max(table["Default CIF (%)"].max(), 0.01))),
        "Prepayment CIF (%)": st.column_config.NumberColumn("Prepayment CIF", format="%.2f%%"),
        "So với baseline (×)": st.column_config.NumberColumn("So với baseline", format="%.2f×"),
        "Number at risk": st.column_config.NumberColumn("Number at risk", format="%d"),
    }
    col_cfg = {k: v for k, v in col_cfg.items() if k in table.columns}
    st.dataframe(table, hide_index=True, column_config=col_cfg, width="stretch")

    insights = [
        f"**{hi['group_value']}** có {metric_label} {horizon}M cao nhất ({_pct(hi[metric])})"
        + (f", bằng {hi['ratio']:.2f}× baseline danh mục." if pd.notna(hi["ratio"]) else "."),
        f"**{lo['group_value']}** thấp nhất ({_pct(lo[metric])})"
        + (f", bằng {lo['ratio']:.2f}× baseline." if pd.notna(lo["ratio"]) else "."),
    ]
    if spread:
        insights.append(f"Khoảng cách giữa hai nhóm là **{spread:.1f} lần**.")
    st.markdown("**Nhận xét nhanh:**\n\n" + "\n".join(f"- {t}" for t in insights))

    # ---- Vintage ------------------------------------------------------------------------------
    _render_vintage_section(horizon)

    # ---- Ghi chú phương pháp ----------------------------------------------------------------------
    with st.expander("Ghi chú phương pháp & giới hạn diễn giải"):
        st.markdown(
            """
- **Default CIF = PD(t)** của dự án; ước lượng theo khung competing risk, coi *Voluntary Prepayment* là competing event.
- **Không dùng 1 − Kaplan–Meier** làm xác suất vỡ nợ khi có competing event (LOCKED RULE trong specification).
- Default gồm ZBC 03 và 09; ZBC 01 là Voluntary Prepayment; ZBC 02, 15, 16, 96 được xử lý là censored.
- Phạm vi: khoản vay origination 2016–2026, performance đến 31/03/2026; vintage 2026 là một phần kỳ và horizon 60M chỉ hiển thị khi đủ follow-up.
- Đây là **so sánh mô tả** giữa các nhóm, chưa phải hiệu ứng nhân quả riêng của từng đặc điểm — xem trang *Yếu tố rủi ro* (Cox / Fine–Gray) để có hệ số đã kiểm soát các biến khác.
- PD(t) là đầu vào phân tích tín dụng, không đủ để tuyên bố đã tính ECL/IFRS 9.
            """
        )


def _render_vintage_section(selected_horizon) -> None:
    v = ds.get_vintage_results()
    if v.empty or not {"vintage", "horizon", "default_cif"}.issubset(v.columns):
        return
    section_title("Xu hướng theo Origination Vintage",
                  "Default CIF của từng năm origination tại các horizon — so sánh các thế hệ khoản vay.")
    v = v.copy()
    v["horizon"] = v["horizon"].astype(int)
    chart_data = v
    if "follow_up_eligible" in chart_data.columns:
        chart_data = chart_data[chart_data["follow_up_eligible"].fillna(False).astype(bool)]
    if chart_data.empty:
        st.info("Chưa có vintage nào đủ follow-up tại các horizon được báo cáo.")
        return
    fig = go.Figure()
    palette = [PRIMARY_DARK, PRIMARY, "#4C86B5", NEAR_COLOR]
    for i, h in enumerate(sorted(chart_data["horizon"].unique())):
        d = chart_data[chart_data["horizon"] == h].sort_values("vintage")
        fig.add_trace(go.Scatter(
            x=d["vintage"].astype(str), y=d["default_cif"], mode="lines+markers", name=f"{h}M",
            line=dict(color=palette[i % len(palette)], width=3 if h == selected_horizon else 1.8),
            opacity=1 if h == selected_horizon or selected_horizon is None else 0.6,
        ))
    fig.update_yaxes(title="Default CIF", tickformat=".0%", rangemode="tozero")
    fig.update_xaxes(title="Origination vintage")
    _chart_card_open()
    st.plotly_chart(_layout(fig), width="stretch")
    _chart_card_close()
    with st.expander("Bảng vintage results (bao gồm trạng thái follow-up)"):
        st.dataframe(v.sort_values(["vintage", "horizon"]).reset_index(drop=True),
                     hide_index=True, width="stretch")
