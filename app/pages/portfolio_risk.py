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
"""

import math
import re

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.components.kpi_card import kpi_row
from app.components.page_blocks import page_kicker
from app.components.styling import section_title
from app.config import FONT_STACK
from app.services import data_service as ds

# BẢNG MÀU TƯƠNG PHẢN ĐỒNG BỘ CHO TẤT CẢ BIỂU ĐỒ
COLOR_RISK_HIGH = "#AD6254"     # đất nung dịu cho Default
COLOR_RISK_MID = "#B08C45"      # vàng đồng
COLOR_RISK_LOW = "#64816A"      # xanh sage
COLOR_PREPAYMENT = "#637E69"   # xanh rêu dịu cho ZBC 01
COLOR_TEXT_DARK = "#293A32"    # xanh rừng cho chữ

DIM_ORDER = ["Điểm tín dụng (FICO)", "Tỷ lệ LTV", "Tỷ lệ DTI", "Lãi suất", "Kỳ hạn vay", "Năm giải ngân (Vintage)"]
METRICS = {
    "Tỷ lệ vỡ nợ tích lũy (Default CIF)": "cif_default",
    "Tỷ lệ trả trước tích lũy (ZBC 01)": "cif_prepayment",
}
MIN_AT_RISK_FOR_RANKING = 100


# ---------------------------------------------------------------- helpers ----
def _dim_label(key) -> str:
    k = str(key).lower()
    if "score" in k or "fico" in k:
        return "Điểm tín dụng (FICO)"
    if "ltv" in k:
        return "Tỷ lệ LTV"
    if "dti" in k:
        return "Tỷ lệ DTI"
    if "rate" in k or "interest" in k:
        return "Lãi suất"
    if "term" in k:
        return "Kỳ hạn vay"
    if "vintage" in k or "orig" in k:
        return "Năm giải ngân (Vintage)"
    return str(key)


def _format_group_value(val) -> str:
    s = str(val).strip()
    if s.lower() in ["missing", "unknown", "none", "nan"]:
        return "Chưa có dữ liệu"
    return s


def _band_key(label):
    """Sắp xếp band theo thứ tự tự nhiên: <650, 650–699, 700–749, 750+."""
    s = str(label).strip()
    if s == "Chưa có dữ liệu":
        return (2, 999999.0, s)
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


def _layout(fig: go.Figure, height: int = 380) -> go.Figure:
    fig.update_layout(
        height=height,
        font=dict(family=FONT_STACK, size=13, color=COLOR_TEXT_DARK),
        plot_bgcolor="#FFFEFA",
        paper_bgcolor="#FFFEFA",
        margin=dict(l=10, r=10, t=35, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    fig.update_xaxes(showgrid=False, tickfont=dict(color=COLOR_TEXT_DARK, size=12, family=FONT_STACK))
    fig.update_yaxes(showgrid=True, gridcolor="#E8E4D9", tickfont=dict(color=COLOR_TEXT_DARK, size=12, family=FONT_STACK))
    return fig


def _chart_card_open():
    st.markdown('<div style="background-color:#FFFEFA; padding:14px; border-radius:4px; border:1px solid #DCD7C8; box-shadow:4px 4px 0 rgba(89,82,60,.10);">', unsafe_allow_html=True)


def _chart_card_close():
    st.markdown("</div>", unsafe_allow_html=True)


def _to_bool_series(series: pd.Series) -> pd.Series:
    """
    Chuẩn hóa các dạng True/False có thể xuất hiện trong dataset.
    Tránh lỗi bool("False") == True.
    """
    if series.dtype == bool:
        return series

    return (
        series.astype(str)
        .str.strip()
        .str.lower()
        .map({
            "true": True,
            "1": True,
            "yes": True,
            "y": True,
            "false": False,
            "0": False,
            "no": False,
            "n": False,
        })
        .fillna(False)
    )


def _not_enough(flag_series: pd.Series) -> bool:
    return (~_to_bool_series(flag_series)).any()


# ------------------------------------------------------------------ intro ----
def _render_intro() -> None:
    st.markdown(
        f"""
        <div style="background:#F6F3E9; border:1px solid #DCD7C8; border-left:5px solid #B99B53;
                    border-radius:4px; padding:16px; margin-bottom:12px;">
          <div style="font-weight:800; font-size:16px; color:#293A32; margin-bottom:6px;">HƯỚNG DẪN ĐỌC TRANG</div>
          <div style="font-size:14px; line-height:1.6; color:{COLOR_TEXT_DARK};">
            <b>Tỷ lệ vỡ nợ tích lũy (Default CIF)</b> là xác suất một khoản vay
            <b>đã vỡ nợ</b> trong vòng <i>t</i> tháng kể từ thời điểm giải ngân, có tính đến việc khoản vay
            cũng có thể ghi nhận <b>ZBC 01</b> trước khi Default.
            Đây chính là <b>PD(t)</b> của dự án. Trang hiển thị PD theo năm giải ngân (Vintage) và các mốc theo dõi
            có đủ dữ liệu; các đường CIF theo FICO, LTV và DTI được ước lượng riêng cho từng nhóm.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ------------------------------------------------------------------- main ----
def render() -> None:
    page_kicker(2, "Rủi ro danh mục theo nhóm khoản vay")
    _render_intro()

    pd_raw = ds.get_pd_results()
    required = {"horizon", "group", "group_value", "cif_default"}
    if pd_raw.empty or not required.issubset(pd_raw.columns):
        st.warning(
            "Chưa có pd_results hợp lệ (cần các cột: horizon, group, group_value, cif_default). "
            "Trang sẽ hiển thị đầy đủ khi dataset này được xuất bản vào thư mục query/."
        )
        _render_vintage_section(None)
        return

    pd_raw = pd_raw.copy()
    pd_raw["group"] = pd_raw["group"].astype(str)
    pd_raw["horizon"] = pd_raw["horizon"].astype(int)
    pd_raw["group_value"] = pd_raw["group_value"].apply(_format_group_value)

    baseline_df = pd_raw[pd_raw["group"] == "portfolio"].copy()
    data = pd_raw[pd_raw["group"] != "portfolio"].copy()

    if "vintage" in data.columns and (data["vintage"].astype(str) == "All").any():
        data = data[data["vintage"].astype(str) == "All"]

    if data.empty:
        st.info(
            "Dữ liệu hiện tại đã có PD toàn danh mục và theo năm giải ngân (Vintage). "
            "Chưa có bảng CIF ước lượng riêng theo nhóm FICO/LTV/DTI, nên trang không tạo các nhóm thay thế."
        )
        if not baseline_df.empty:
            baseline_df = baseline_df.sort_values("horizon")
            if "follow_up_flag" in baseline_df.columns:
                eligible = baseline_df[_to_bool_series(baseline_df["follow_up_flag"])].copy()
            else:
                eligible = baseline_df.copy()
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
    dim_labels = sorted(dim_map.keys(), key=lambda x: DIM_ORDER.index(x) if x in DIM_ORDER else 99)
    horizons = sorted(data["horizon"].unique())

    section_title("Bộ lọc so sánh")
    c1, c2, c3 = st.columns([3, 1, 2])
    with c1:
        dim_label = st.radio("So sánh theo đặc điểm", dim_labels, horizontal=True)
    with c2:
        default_idx = horizons.index(36) if 36 in horizons else len(horizons) - 1
        horizon = st.selectbox("Khung thời gian (Tháng)", horizons, index=default_idx)
    with c3:
        metric_options = [k for k, v in METRICS.items() if v in data.columns]
        metric_label = st.radio("Chỉ số phân tích", metric_options, horizontal=True)
    metric = METRICS[metric_label]
    is_default = (metric == "cif_default")

    group_key = dim_map[dim_label]
    dim_all = data[data["group"] == group_key].copy()
    sub = dim_all[dim_all["horizon"] == horizon].copy()
    if sub.empty:
        st.info(f"Chưa có bản ghi cho '{dim_label}' tại mốc {horizon} tháng.")
        _render_vintage_section(None)
        return

    # A CIF is an estimate for a defined group/horizon; averaging duplicate
    # rows would create a statistic with no clear risk-set denominator.
    sub = sub.drop_duplicates("group_value", keep="last")
    if "follow_up_flag" in sub.columns:
        if _not_enough(sub["follow_up_flag"]):
            st.warning(
                f"Một số nhóm chưa có đủ quan sát còn theo dõi tại mốc "
                f"{horizon} tháng; các nhóm đó không được dùng để xếp hạng "
                "và không ngoại suy CIF."
            )
        sub = sub[_to_bool_series(sub["follow_up_flag"])].copy()

    if sub.empty or sub[metric].dropna().empty:
        st.info(f"Không nhóm nào có đủ dữ liệu quan sát để ước lượng tại mốc {horizon} tháng.")
        _render_vintage_section(None)
        return

    sub = sub.sort_values("group_value", key=lambda s: s.map(_band_key)).reset_index(drop=True)
    if "number_at_risk" in sub.columns and (sub["number_at_risk"] < MIN_AT_RISK_FOR_RANKING).any():
        st.warning(
            f"Nhóm có dưới {MIN_AT_RISK_FOR_RANKING} khoản vay có rủi ro vẫn được hiển thị, "
            "nhưng không dùng để xếp hạng vì ước lượng ở nhóm nhỏ dễ biến động."
        )

    base_val = None
    if not baseline_df.empty and metric in baseline_df.columns:
        b = baseline_df[baseline_df["horizon"] == horizon][metric].dropna()
        base_val = float(b.iloc[-1]) if not b.empty else None
    sub["ratio"] = sub[metric] / base_val if base_val else float("nan")

    # ---- KPI tóm tắt ---------------------------------------------------------------
    section_title(f"Tóm tắt chỉ số · {dim_label} · {horizon} tháng")
    ranked = sub[~sub["group_value"].isin({"Chưa có dữ liệu"})].copy()
    if "number_at_risk" in ranked.columns:
        adequately_supported = ranked[ranked["number_at_risk"] >= MIN_AT_RISK_FOR_RANKING]
        if not adequately_supported.empty:
            ranked = adequately_supported
    ranked = ranked[ranked[metric].notna()]
    if ranked.empty:
        ranked = sub[sub[metric].notna()].copy()

    hi = ranked.loc[ranked[metric].idxmax()]
    lo = ranked.loc[ranked[metric].idxmin()]
    spread = hi[metric] - lo[metric]

    kpi_row([
        {
            "label": f"Toàn danh mục · {horizon} tháng",
            "value": _pct(base_val),
            "help_text": "Default CIF của toàn bộ mẫu tại horizon đang chọn"
        },
        {
            "label": f"Nhóm cao nhất: {hi['group_value']}",
            "value": _pct(hi[metric]),
            "help_text": f"{hi['ratio']:.2f}× trung bình danh mục" if pd.notna(hi["ratio"]) else None
        },
        {
            "label": f"Nhóm thấp nhất: {lo['group_value']}",
            "value": _pct(lo[metric]),
            "help_text": f"{lo['ratio']:.2f}× trung bình danh mục" if pd.notna(lo["ratio"]) else None
        },
        {
            "label": "Chênh lệch Cao − Thấp",
            "value": f"{spread * 100:.2f} điểm %",
            "help_text": "Chênh lệch tuyệt đối giữa hai CIF mô tả; không phải tác động nhân quả"
        },
    ])

    # ---- Biểu đồ cột phân loại màu tương phản ------------------------------------------
    section_title(f"{metric_label} ({horizon} tháng) theo {dim_label}")
    if is_default and base_val:
        colors = []
        for r in sub["ratio"]:
            if pd.isna(r):
                colors.append(COLOR_RISK_MID)
            elif r >= 1.25:   # Vượt 25% so với TB danh mục -> Cảnh báo Đỏ (Rủi ro cao)
                colors.append(COLOR_RISK_HIGH)
            elif r <= 0.80:   # Thấp hơn 20% so với TB danh mục -> Xanh (An toàn)
                colors.append(COLOR_RISK_LOW)
            else:             # Quanh mức trung bình -> Cam
                colors.append(COLOR_RISK_MID)
        st.markdown(
            f"""
            <div style="margin-bottom:12px; font-weight:bold; font-size:13px; color:{COLOR_TEXT_DARK};">
                <span style="color:{COLOR_RISK_HIGH}; font-size:16px;">■</span> Rủi ro cao (≥125% so với TB) &nbsp;&nbsp;&nbsp;
                <span style="color:{COLOR_RISK_MID}; font-size:16px;">■</span> Rủi ro trung bình &nbsp;&nbsp;&nbsp;
                <span style="color:{COLOR_RISK_LOW}; font-size:16px;">■</span> Rủi ro thấp (≤80% so với TB)
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        colors = COLOR_PREPAYMENT
        st.markdown(
            f"""
            <div style="margin-bottom:12px; font-weight:bold; font-size:13px; color:{COLOR_TEXT_DARK};">
                <span style="color:{COLOR_PREPAYMENT}; font-size:16px;">■</span> Xác suất trả trước tích lũy (ZBC 01)
            </div>
            """,
            unsafe_allow_html=True,
        )

    fig = go.Figure(go.Bar(
        x=sub["group_value"], y=sub[metric], marker_color=colors,
        text=[_pct(v) for v in sub[metric]], textposition="outside",
        textfont=dict(color=COLOR_TEXT_DARK, size=12, family=FONT_STACK),
        hovertemplate="%{x}<br>" + metric_label + ": %{y:.2%}<extra></extra>",
    ))
    if base_val:
        fig.add_hline(
            y=base_val, line_dash="dash", line_color="#536056", line_width=2,
            annotation_text=f"TB danh mục: {_pct(base_val)}",
            annotation_position="top left",
            annotation_font=dict(family=FONT_STACK, size=12, color=COLOR_TEXT_DARK)
        )
    fig.update_yaxes(title=dict(text=metric_label, font=dict(family=FONT_STACK, color=COLOR_TEXT_DARK, size=13)), tickformat=".0%", rangemode="tozero")
    fig.update_xaxes(title=dict(text=dim_label, font=dict(family=FONT_STACK, color=COLOR_TEXT_DARK, size=13)))
    _chart_card_open()
    st.plotly_chart(_layout(fig), use_container_width=True)
    _chart_card_close()
    # ---- Heatmap rủi ro tương phản đồng bộ --------------------------------------------
    section_title(
        f"Rủi ro theo nhóm qua các mốc thời gian — {dim_label}",
        "Mỗi ô cho biết mức rủi ro tích lũy của một nhóm tại một mốc theo dõi. "
        "Chỉ các horizon đủ điều kiện follow-up mới được hiển thị."
    )

    heat_data = dim_all.copy()
    if "follow_up_flag" in heat_data.columns:
        heat_data = heat_data[_to_bool_series(heat_data["follow_up_flag"])].copy()

    if heat_data.empty:
        st.info("Chưa có horizon nào đủ điều kiện follow-up để tạo heatmap.")
    else:
        pivot = (
            heat_data
            .drop_duplicates(["group_value", "horizon"], keep="last")
            .pivot(index="group_value", columns="horizon", values=metric)
        )

        if pivot.empty:
            st.info("Chưa đủ dữ liệu để tạo heatmap.")
        else:
            pivot = pivot.loc[sorted(pivot.index, key=_band_key)]

            eligible_for_scale = data.copy()
            if "follow_up_flag" in eligible_for_scale.columns:
                eligible_for_scale = eligible_for_scale[_to_bool_series(eligible_for_scale["follow_up_flag"])]
            scale_values = pd.to_numeric(eligible_for_scale.get(metric, pd.Series(dtype=float)), errors="coerce").dropna()
            color_ceiling = min(1.0, max(0.05, float(scale_values.max()) if not scale_values.empty else 0.05))
            color_ceiling = min(1.0, max(0.05, math.ceil(color_ceiling / 0.05) * 0.05))
            heat_colorscale = "YlOrRd" if is_default else "Blues"

            heat = go.Figure(
                go.Heatmap(
                    z=pivot.values,
                    x=[f"{int(h)} tháng" for h in pivot.columns],
                    y=list(pivot.index),
                    text=[[_pct(v) for v in row] for row in pivot.values],
                    texttemplate="%{text}",
                    textfont=dict(family=FONT_STACK, size=12, color=COLOR_TEXT_DARK),
                    colorscale=heat_colorscale,
                    zmin=0,
                    zmax=color_ceiling,
                    hoverongaps=False,
                    colorbar=dict(
                        title=dict(text=metric_label, font=dict(family=FONT_STACK, color=COLOR_TEXT_DARK, size=12)),
                        tickfont=dict(family=FONT_STACK, color=COLOR_TEXT_DARK),
                        tickformat=".0%",
                    ),
                    hovertemplate="%{y} · %{x}<br>" + metric_label + ": %{z:.2%}<extra></extra>",
                )
            )
            heat.update_yaxes(autorange="reversed")

            _chart_card_open()
            st.plotly_chart(
                _layout(heat, height=max(260, 60 * len(pivot) + 80)),
                use_container_width=True
            )
            _chart_card_close()
            st.caption(f"Thang màu cho dataset hiện tại: 0%–{color_ceiling:.0%}. Ô trống nghĩa là horizon chưa đủ dữ liệu, không phải 0%.")

    # ---- Chiều nào phân biệt rủi ro mạnh nhất -------------------------------------------
    section_title(
        f"Đặc điểm nào có chênh lệch rủi ro quan sát được lớn hơn? ({horizon} tháng)",
        "So sánh khoảng cách giữa nhóm cao nhất và thấp nhất của từng đặc điểm. "
        "Thanh dài hơn cho biết chênh lệch quan sát được giữa các nhóm lớn hơn; "
        "đây không phải là tác động nhân quả."
    )
    rows = []
    for label, gkey in dim_map.items():
        d = data[(data["group"] == gkey) & (data["horizon"] == horizon)].copy()
        if d.empty:
            continue
        d["group_value"] = d["group_value"].apply(_format_group_value)
        d = d[~d["group_value"].isin({"Chưa có dữ liệu"})]
        if "number_at_risk" in d.columns:
            d = d[d["number_at_risk"] >= MIN_AT_RISK_FOR_RANKING]
        d_grouped = d.drop_duplicates("group_value").set_index("group_value")[metric]
        if len(d_grouped) >= 2:
            spread_value = d_grouped.max() - d_grouped.min()
            if pd.notna(spread_value):
                rows.append((label, spread_value, d_grouped.idxmax(), d_grouped.idxmin()))

    if rows:
        rows.sort(key=lambda r: r[1], reverse=True)
        sp = go.Figure(go.Bar(
            x=[r[1] * 100 for r in rows],
            y=[r[0] for r in rows],
            orientation="h",
            marker_color=[COLOR_RISK_HIGH if r[0] == dim_label else COLOR_RISK_LOW for r in rows],
            text=[f"{r[1] * 100:.2f} điểm %  ({r[2]} vs {r[3]})" for r in rows],
            textposition="outside",
            textfont=dict(family=FONT_STACK, color=COLOR_TEXT_DARK, size=12),
            hovertemplate="%{y}: %{x:.2f} điểm %<extra></extra>",
        ))
        sp.update_xaxes(title=dict(text="Chênh lệch CIF max − min (điểm %)", font=dict(family=FONT_STACK, color=COLOR_TEXT_DARK, size=13)), rangemode="tozero")
        _chart_card_open()
        st.plotly_chart(_layout(sp, height=max(260, 55 * len(rows) + 80)), use_container_width=True)
        _chart_card_close()
    else:
        st.info("Chưa đủ nhóm để so sánh giữa các đặc điểm.")

    # ---- Bảng chi tiết + nhận xét ---------------------------------------------------------
    section_title("Bảng chi tiết thông số")
    table = pd.DataFrame({dim_label: sub["group_value"]})
    if "cif_default" in sub.columns:
        table["Xác suất vỡ nợ tích lũy (%)"] = sub["cif_default"] * 100
    if "cif_prepayment" in sub.columns:
        table["Xác suất trả trước tích lũy (ZBC 01) (%)"] = sub["cif_prepayment"] * 100
    if base_val:
        table["So với trung bình (lần)"] = sub["ratio"]
    if "number_at_risk" in sub.columns:
        table["Số khoản vay còn trong diện rủi ro"] = sub["number_at_risk"]
    if "follow_up_flag" in sub.columns:
        table["Trạng thái theo dõi"] = sub["follow_up_flag"].astype(str).str.lower().map(
            lambda s: "Chưa đủ" if s in ("false", "0", "no") else "Đủ"
        )
        if "number_at_risk" in sub.columns:
            table.loc[sub["number_at_risk"] < MIN_AT_RISK_FOR_RANKING, "Trạng thái theo dõi"] = "Mẫu at-risk nhỏ"

    if sub["group_value"].isin({"Chưa có dữ liệu"}).any():
        st.markdown(f"<p style='color:{COLOR_TEXT_DARK}; font-weight:bold; font-size:13px;'>* Nhóm thiếu dữ liệu vẫn được hiển thị riêng; không đưa nhóm này vào xếp hạng rủi ro.</p>", unsafe_allow_html=True)

    col_cfg = {}
    if "Xác suất vỡ nợ tích lũy (%)" in table.columns:
        max_cif = float(max(table["Xác suất vỡ nợ tích lũy (%)"].max(), 0.01))
        col_cfg["Xác suất vỡ nợ tích lũy (%)"] = st.column_config.ProgressColumn(
            "Xác suất vỡ nợ tích lũy (%)", format="%.2f%%", min_value=0, max_value=max_cif
        )
    if "Xác suất trả trước tích lũy (ZBC 01) (%)" in table.columns:
        col_cfg["Xác suất trả trước tích lũy (ZBC 01) (%)"] = st.column_config.NumberColumn("Xác suất trả trước tích lũy (ZBC 01) (%)", format="%.2f%%")
    if "So với trung bình (lần)" in table.columns:
        col_cfg["So với trung bình (lần)"] = st.column_config.NumberColumn("So với trung bình (lần)", format="%.2f×")
    if "Số khoản vay còn trong diện rủi ro" in table.columns:
        col_cfg["Số khoản vay còn trong diện rủi ro"] = st.column_config.NumberColumn("Số khoản vay còn trong diện rủi ro (N)", format="%d")

    st.dataframe(table, hide_index=True, column_config=col_cfg, use_container_width=True)

    insights = [
        f"**{hi['group_value']}** có {metric_label.lower()} mốc {horizon} tháng cao nhất ({_pct(hi[metric])})"
        + (f", bằng **{hi['ratio']:.2f} lần** mức trung bình danh mục." if pd.notna(hi["ratio"]) else "."),
        f"**{lo['group_value']}** thấp nhất ({_pct(lo[metric])})"
        + (f", bằng **{lo['ratio']:.2f} lần** mức trung bình." if pd.notna(lo["ratio"]) else "."),
    ]
    if spread:
        insights.append(f"Chênh lệch tuyệt đối giữa hai nhóm là **{spread * 100:.2f} điểm phần trăm**.")

    st.markdown(
        f"""
        <div style='background-color:#F6F3E9; border:1px solid #DCD7C8; border-radius:4px; padding:16px; margin-top:10px;'>
            <p style='color:{COLOR_TEXT_DARK}; font-weight:bold; font-size:15px; margin-bottom:8px;'>Nhận xét đánh giá nhanh:</p>
            <ul style='color:{COLOR_TEXT_DARK}; font-size:14px; line-height:1.6; margin-left:-15px;'>
                {"".join([f"<li>{t}</li>" for t in insights])}
            </ul>
        </div>
        """,
        unsafe_allow_html=True
    )

    # ---- Vintage ------------------------------------------------------------------------------
    _render_vintage_section(horizon)

    # ---- Ghi chú phương pháp ----------------------------------------------------------------------
    with st.expander("Ghi chú phương pháp & giới hạn diễn giải"):
        st.markdown(
            """
    - **Default CIF = PD(t)** của dự án; ước lượng theo khung
    **rủi ro cạnh tranh**, trong đó *trả trước hạn (ZBC 01)* là sự kiện cạnh tranh.

    - **Không dùng 1 − Kaplan–Meier** làm xác suất Default tích lũy
    khi tồn tại competing event.

    - **Định nghĩa sự kiện:** Default = 90+ DPD, RA hoặc Zero Balance Code 02/03/09.
    Trả trước hạn theo quy ước nghiên cứu = Zero Balance Code 01; ZBC 15/16/96 = kết thúc theo dõi.
    Sự kiện sớm nhất được chọn; nếu vỡ nợ và ZBC 01 cùng tháng, vỡ nợ được ưu tiên.
    Freddie Mac gộp trả trước/đáo hạn trong ZBC 01 nên nghiên cứu không tách riêng đáo hạn.

    - **Phạm vi:** Freddie Mac Sample Dataset 2016–2026,
    theo dõi đến 31/03/2026. Vintage 2026 là kỳ chưa đầy đủ.

    - Các horizon như **12, 24, 36 và 60 tháng** chỉ được hiển thị
    khi có đủ follow-up theo quy tắc của pipeline.

    - Đây là **so sánh mô tả giữa các nhóm**, chưa phải hiệu ứng nhân quả
    riêng của từng đặc điểm. Các kết quả Cox / Fine–Gray được trình bày
    ở trang **Yếu tố rủi ro**.

    - **PD(t)** là xác suất Default tích lũy phục vụ phân tích rủi ro tín dụng;
    không đủ để tuyên bố đã tính toán **ECL/IFRS 9 hoàn chỉnh**.
            """
        )


def _render_vintage_section(selected_horizon) -> None:
    v = ds.get_vintage_results()
    if v.empty:
        st.info("Chưa có dữ liệu Origination Vintage để hiển thị.")
        return

    required_vintage = {"vintage", "horizon", "default_cif"}
    if not required_vintage.issubset(v.columns):
        missing = required_vintage - set(v.columns)
        st.warning("Dữ liệu Vintage đang thiếu cột: " + ", ".join(sorted(missing)))
        return

    section_title(
        "So sánh rủi ro theo năm giải ngân",
        "Chọn một mốc theo dõi để so sánh các nhóm khoản vay cùng tuổi quan sát; khoảng tin cậy thể hiện độ bất định."
    )
    v = v.copy()
    v["horizon"] = v["horizon"].astype(int)
    chart_data = v.copy()
    if "follow_up_eligible" in chart_data.columns:
        chart_data = chart_data[_to_bool_series(chart_data["follow_up_eligible"])].copy()

    if chart_data.empty:
        st.info("Chưa có năm giải ngân (Vintage) nào đủ điều kiện theo dõi tại các mốc thời gian được báo cáo.")
        return

    available_horizons = sorted(chart_data["horizon"].dropna().astype(int).unique().tolist())
    if not available_horizons:
        st.info("Chưa có mốc theo dõi nào đủ dữ liệu.")
        return
    default_h = int(selected_horizon) if selected_horizon in available_horizons else available_horizons[0]
    chosen_horizon = st.selectbox(
        "Mốc theo dõi để so sánh",
        available_horizons,
        index=available_horizons.index(default_h),
        format_func=lambda h: f"{h} tháng",
        key="vintage_trend_horizon",
    )
    fig = go.Figure()
    vintage_palette = [COLOR_RISK_HIGH]
    vintage_curves = ds.get_aj_curves(endpoint="DEFAULT", group_name="vintage_year")
    d = chart_data[chart_data["horizon"] == chosen_horizon].sort_values("vintage").copy()
    lows, highs = [], []
    for _, row in d.iterrows():
        curve = vintage_curves[
            (vintage_curves["group_value"].astype(str) == str(int(row["vintage"])))
            & (pd.to_numeric(vintage_curves["analysis_time"], errors="coerce") <= chosen_horizon)
        ].sort_values("analysis_time") if not vintage_curves.empty else pd.DataFrame()
        point = curve.iloc[-1] if not curve.empty else None
        lows.append(float(point["ci_lower"]) if point is not None and pd.notna(point.get("ci_lower")) else None)
        highs.append(float(point["ci_upper"]) if point is not None and pd.notna(point.get("ci_upper")) else None)
    values = pd.to_numeric(d["default_cif"], errors="coerce").tolist()
    customdata = np.column_stack([
        pd.to_numeric(d[c], errors="coerce").to_numpy() if c in d.columns else np.full(len(d), np.nan)
        for c in ("loan_count", "n_at_risk", "default_count")
    ])
    fig.add_trace(go.Scatter(
        x=d["vintage"].astype(str), y=values, mode="lines+markers",
        name=f"Vỡ nợ tích lũy sau {chosen_horizon} tháng",
        line=dict(color=COLOR_RISK_HIGH, width=2), marker=dict(size=9),
        error_y=dict(
            type="data", symmetric=False,
            array=[max(0, hi - val) if hi is not None and pd.notna(val) else 0 for hi, val in zip(highs, values)],
            arrayminus=[max(0, val - lo) if lo is not None and pd.notna(val) else 0 for lo, val in zip(lows, values)],
            visible=any(value is not None for value in highs), color=COLOR_RISK_HIGH,
        ),
        customdata=customdata,
        hovertemplate="Năm giải ngân: %{x}<br>Xác suất vỡ nợ tích lũy: %{y:.2%}<br>Số khoản trong nhóm: %{customdata[0]:,.0f}<br>Số khoản còn theo dõi: %{customdata[1]:,.0f}<br>Số ca vỡ nợ quan sát được: %{customdata[2]:,.0f}<extra></extra>",
    ))
    positive = [v for v in values + [v for v in highs if v is not None] if pd.notna(v) and v >= 0]
    y_max = min(1.0, max(0.01, (max(positive) * 1.12 if positive else 0.05)))
    fig.update_yaxes(title=dict(text="Xác suất vỡ nợ tích lũy", font=dict(family=FONT_STACK, color=COLOR_TEXT_DARK, size=13)), tickformat=".1%", range=[0, y_max])
    fig.update_xaxes(title=dict(text="Năm giải ngân khoản vay", font=dict(family=FONT_STACK, color=COLOR_TEXT_DARK, size=13)), type="category")
    _chart_card_open()
    st.plotly_chart(_layout(fig), use_container_width=True)
    _chart_card_close()

    st.caption(
        "Chỉ hiển thị vintage đủ hỗ trợ ước lượng ở mốc đã chọn; năm không xuất hiện không được hiểu là rủi ro bằng 0. "
        "Khác biệt giữa các năm là mô tả, không chứng minh nguyên nhân."
    )

    with st.expander("Bảng dữ liệu Vintage chi tiết (bao gồm trạng thái theo dõi)"):
        v_renamed = v.rename(columns={
            "vintage": "Năm giải ngân",
            "horizon": "Mốc theo dõi (tháng)",
            "default_cif": "Xác suất vỡ nợ tích lũy",
            "prepayment_cif": "Xác suất trả trước tích lũy",
            "loan_count": "Số khoản vay",
            "n_at_risk": "Số khoản còn theo dõi",
            "default_count": "Số ca vỡ nợ",
            "prepayment_count": "Số ca trả trước",
            "follow_up_eligible": "Đủ điều kiện theo dõi"
        })
        st.dataframe(
            v_renamed.sort_values(["Năm giải ngân", "Mốc theo dõi (tháng)"]).reset_index(drop=True),
            hide_index=True,
            use_container_width=True
        )
