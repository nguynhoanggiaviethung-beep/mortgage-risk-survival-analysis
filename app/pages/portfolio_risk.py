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

import re

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.components.kpi_card import kpi_row
from app.components.styling import section_title
from app.services import data_service as ds

# BẢNG MÀU TƯƠNG PHẢN ĐỒNG BỘ CHO TẤT CẢ BIỂU ĐỒ
COLOR_RISK_HIGH = "#C62828"     # Đỏ San Hô - Mức rủi ro cao
COLOR_RISK_MID = "#EF6C00"      # Vàng Hổ Phách - Mức trung bình
COLOR_RISK_LOW = "#2E7D32"      # Xanh Ngọc - Mức an toàn / rủi ro thấp
COLOR_PREPAYMENT = "#1565C0"    # Xanh Dương - Tỷ lệ trả trước
COLOR_TEXT_DARK = "#0F172A"     # Đen Đậm - Hiển thị chữ rõ 100%

DIM_ORDER = ["Điểm tín dụng (FICO)", "Tỷ lệ LTV", "Tỷ lệ DTI", "Lãi suất", "Kỳ hạn vay", "Năm giải ngân (Vintage)"]
METRICS = {
    "Tỷ lệ vỡ nợ tích lũy (Default CIF)": "cif_default",
    "Tỷ lệ trả trước tích lũy (Prepayment CIF)": "cif_prepayment",
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
        font=dict(family="Arial, sans-serif", size=13, color=COLOR_TEXT_DARK),
        plot_bgcolor="#FFFFFF",
        paper_bgcolor="#FFFFFF",
        margin=dict(l=10, r=10, t=35, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    fig.update_xaxes(showgrid=False, tickfont=dict(color=COLOR_TEXT_DARK, size=12, family="Arial"))
    fig.update_yaxes(showgrid=True, gridcolor="#E2E8F0", tickfont=dict(color=COLOR_TEXT_DARK, size=12, family="Arial"))
    return fig


def _chart_card_open():
    st.markdown('<div style="background-color:#FFFFFF; padding:14px; border-radius:8px; border:1px solid #CBD5E1;">', unsafe_allow_html=True)


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
        <div style="background:#F1F5F9; border:1px solid #94A3B8; border-left:6px solid #0F172A;
                    border-radius:8px; padding:16px; margin-bottom:12px;">
          <div style="font-weight:800; font-size:16px; color:#0F172A; margin-bottom:6px;">HƯỚNG DẪN ĐỌC TRANG</div>
          <div style="font-size:14px; line-height:1.6; color:{COLOR_TEXT_DARK};">
            <b>Tỷ lệ vỡ nợ tích lũy (Default CIF)</b> là xác suất một khoản vay
            <b>đã vỡ nợ</b> trong vòng <i>t</i> tháng kể từ thời điểm giải ngân, có tính đến việc khoản vay
            cũng có thể bị <b>tất toán sớm (Voluntary Prepayment)</b> trước khi vỡ nợ.
            Đây chính là <b>PD(t)</b> của dự án. Trang hiển thị PD theo năm giải ngân (Vintage) và các mốc theo dõi
            có đủ dữ liệu; các đường CIF theo FICO, LTV và DTI được ước lượng riêng cho từng nhóm.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ------------------------------------------------------------------- main ----
def render() -> None:
    st.markdown(f"<p style='color:{COLOR_TEXT_DARK}; font-weight:bold; font-size:16px; margin-bottom:4px;'>TRANG 2 · RỦI RO DANH MỤC THEO NHÓM KHOẢN VAY</p>", unsafe_allow_html=True)
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

    baseline_df = pd_raw[pd_raw["group"] == "portfolio"]
    data = pd_raw[pd_raw["group"] != "portfolio"]
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
                eligible = baseline_df[
                    _to_bool_series(
                        baseline_df["follow_up_flag"]
                    )
                ].copy()
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
    dim_labels = sorted(dim_map, key=lambda x: DIM_ORDER.index(x) if x in DIM_ORDER else 99)
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
        st.info(f"Chưa có bản ghi cho '{dim_label}' tại mốc {horizon} tháng.")
        _render_vintage_section(None)
        return

    sub = sub.groupby("group_value", as_index=False).agg(agg)
    if "follow_up_flag" in sub.columns:
        if _not_enough(sub["follow_up_flag"]):
            st.warning(
                f"Một số nhóm chưa có đủ quan sát còn theo dõi tại mốc "
                f"{horizon} tháng; các nhóm đó không được dùng để xếp hạng "
                "và không ngoại suy CIF."
            )

        sub = sub[
            _to_bool_series(sub["follow_up_flag"])
        ].copy()
    if sub.empty or sub[metric].dropna().empty:
        st.info(f"Không nhóm nào có đủ dữ liệu quan sát để ước lượng tại mốc {horizon} tháng.")
        _render_vintage_section(None)
        return
    sub = sub.sort_values("group_value", key=lambda s: s.map(_band_key)).reset_index(drop=True)
    if "number_at_risk" in sub and (sub["number_at_risk"] < MIN_AT_RISK_FOR_RANKING).any():
        st.warning(
            f"Nhóm có dưới {MIN_AT_RISK_FOR_RANKING} khoản vay có rủi ro vẫn được hiển thị, "
            "nhưng không dùng để xếp hạng vì ước lượng ở nhóm nhỏ dễ biến động."
        )

    base_val = None
    if not baseline_df.empty and metric in baseline_df.columns:
        b = baseline_df[baseline_df["horizon"] == horizon][metric]
        base_val = float(b.mean()) if not b.empty else None
    sub["ratio"] = sub[metric] / base_val if base_val else float("nan")

    # ---- KPI tóm tắt ---------------------------------------------------------------
    section_title(f"Tóm tắt chỉ số · {dim_label} · {horizon} tháng")
    ranked = sub[~sub["group_value"].isin({"Chưa có dữ liệu"})]
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
        {
            "label": f"Toàn danh mục · {horizon} tháng",
            "value": _pct(base_val),
            "help_text": "Default CIF của toàn bộ mẫu tại horizon đang chọn"
        },
        {"label": f"Nhóm cao nhất: {hi['group_value']}", "value": _pct(hi[metric]),
         "help_text": f"{hi['ratio']:.2f}× trung bình danh mục" if pd.notna(hi["ratio"]) else None},
        {"label": f"Nhóm thấp nhất: {lo['group_value']}", "value": _pct(lo[metric]),
         "help_text": f"{lo['ratio']:.2f}× trung bình danh mục" if pd.notna(lo["ratio"]) else None},
        {"label": "Chênh lệch Cao / Thấp", "value": f"{spread:.1f}×" if spread else "—",
         "help_text": "Tỷ lệ chênh lệch giữa nhóm rủi ro cao nhất và thấp nhất"},
    ])

    # ---- Biểu đồ cột phân loại màu tương phản ------------------------------------------
    section_title(f"{metric_label} ({horizon} tháng) theo {dim_label}")
    if is_default and base_val:
        colors = []
        for r in sub["ratio"]:
            if pd.isna(r):
                colors.append(COLOR_RISK_MID)
            elif r >= 1.25:  # Vượt 25% so với TB danh mục -> Cảnh báo Đỏ (Rủi ro cao)
                colors.append(COLOR_RISK_HIGH)
            elif r <= 0.80:  # Thấp hơn 20% so với TB danh mục -> Xanh (An toàn)
                colors.append(COLOR_RISK_LOW)
            else:            # Quanh mức trung bình -> Cam
                colors.append(COLOR_RISK_MID)
        st.markdown(
            f"""
            <div style="margin-bottom:12px; font-weight:bold; font-size:13px; color:{COLOR_TEXT_DARK};">
                <span style="color:{COLOR_RISK_HIGH}; font-size:16px;">■</span> Rủi ro cao (≥50% so với TB) &nbsp;&nbsp;&nbsp;
                <span style="color:{COLOR_RISK_MID}; font-size:16px;">■</span> Rủi ro trung bình &nbsp;&nbsp;&nbsp;
                <span style="color:{COLOR_RISK_LOW}; font-size:16px;">■</span> Rủi ro thấp (≤30% so với TB)
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        colors = COLOR_PREPAYMENT
        st.markdown(
            f"""
            <div style="margin-bottom:12px; font-weight:bold; font-size:13px; color:{COLOR_TEXT_DARK};">
                <span style="color:{COLOR_PREPAYMENT}; font-size:16px;">■</span> Tỷ lệ trả trước tích lũy (Prepayment CIF)
            </div>
            """,
            unsafe_allow_html=True,
        )

    fig = go.Figure(go.Bar(
        x=sub["group_value"], y=sub[metric], marker_color=colors,
        text=[_pct(v) for v in sub[metric]], textposition="outside",
        textfont=dict(color=COLOR_TEXT_DARK, size=12, family="Arial"),
        hovertemplate="%{x}<br>" + metric_label + ": %{y:.2%}<extra></extra>",
    ))
    if base_val:
        fig.add_hline(y=base_val, line_dash="dash", line_color="#334155", line_width=2,
                      annotation_text=f"TB danh mục: {_pct(base_val)}",
                      annotation_position="top left",
                      annotation_font=dict(size=12, color=COLOR_TEXT_DARK))
    fig.update_yaxes(title=dict(text=metric_label, font=dict(color=COLOR_TEXT_DARK, size=13)), tickformat=".0%", rangemode="tozero")
    fig.update_xaxes(title=dict(text=dim_label, font=dict(color=COLOR_TEXT_DARK, size=13)))
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

    # Chỉ giữ các horizon đủ điều kiện follow-up
    if "follow_up_flag" in heat_data.columns:
        heat_data = heat_data[
            _to_bool_series(
                heat_data["follow_up_flag"]
            )
        ].copy()

    if heat_data.empty:
        st.info(
            "Chưa có horizon nào đủ điều kiện follow-up để tạo heatmap."
        )
    else:
        pivot = (
            heat_data
            .groupby(
                ["group_value", "horizon"],
                as_index=False
            )[metric]
            .mean()
            .pivot(
                index="group_value",
                columns="horizon",
                values=metric
            )
        )

        if pivot.empty:
            st.info(
                "Chưa đủ dữ liệu để tạo heatmap."
            )
        else:
            pivot = pivot.loc[
                sorted(
                    pivot.index,
                    key=_band_key
                )
            ]

            if is_default:
                heat_colorscale = [
                    [0.0, "#2E7D32"],
                    [0.3, "#1565C0"],
                    [0.6, "#FDE047"],
                    [0.8, "#EF6C00"],
                    [1.0, COLOR_RISK_HIGH],
                ]
            else:
                heat_colorscale = "Blues"

            heat = go.Figure(
                go.Heatmap(
                    z=pivot.values,
                    x=[
                        f"{int(h)} tháng"
                        for h in pivot.columns
                    ],
                    y=list(pivot.index),
                    text=[
                        [
                            _pct(v)
                            for v in row
                        ]
                        for row in pivot.values
                    ],
                    texttemplate="%{text}",
                    textfont=dict(
                        size=12,
                        color=COLOR_TEXT_DARK
                    ),
                    colorscale=heat_colorscale,
                    colorbar=dict(
                        title=dict(
                            text=metric_label,
                            font=dict(
                                color=COLOR_TEXT_DARK,
                                size=12
                            )
                        ),
                        tickformat=".0%",
                    ),
                    hovertemplate=(
                        "%{y} · %{x}<br>"
                        + metric_label
                        + ": %{z:.2%}"
                        + "<extra></extra>"
                    ),
                )
            )

            heat.update_yaxes(
                autorange="reversed"
            )

            _chart_card_open()

            st.plotly_chart(
                _layout(
                    heat,
                    height=max(
                        260,
                        60 * len(pivot) + 80
                    )
                ),
                use_container_width=True
            )

            _chart_card_close()

    # ---- Chiều nào phân biệt rủi ro mạnh nhất -------------------------------------------
    section_title(
        f"6. Đặc điểm nào có chênh lệch rủi ro quan sát được lớn hơn? ({horizon} tháng)",
        "So sánh khoảng cách giữa nhóm cao nhất và thấp nhất của từng đặc điểm. "
        "Thanh dài hơn cho biết chênh lệch quan sát được giữa các nhóm lớn hơn; "
        "đây không phải là tác động nhân quả."
    )
    rows = []
    for label, gkey in dim_map.items():
        d = data[(data["group"] == gkey) & (data["horizon"] == horizon)].copy()
        d["group_value"] = d["group_value"].apply(_format_group_value)
        d = d[~d["group_value"].isin({"Chưa có dữ liệu"})]
        if "number_at_risk" in d:
            d = d[d["number_at_risk"] >= MIN_AT_RISK_FOR_RANKING]
        d = d.groupby("group_value")[metric].mean()
        if len(d) >= 2 and d.min() > 0:
            rows.append((label, d.max() / d.min(), d.idxmax(), d.idxmin()))
    if rows:
        rows.sort(key=lambda r: r[1], reverse=True)
        sp = go.Figure(go.Bar(
            x=[r[1] for r in rows], y=[r[0] for r in rows], orientation="h",
            marker_color=[COLOR_RISK_HIGH if r[0] == dim_label else "#2E7D32" for r in rows],
            text=[f"{r[1]:.1f}×  ({r[2]} vs {r[3]})" for r in rows], textposition="outside",
            textfont=dict(color=COLOR_TEXT_DARK, size=12),
            hovertemplate="%{y}: %{x:.2f}×<extra></extra>",
        ))
        sp.update_xaxes(title=dict(text="Tỷ lệ Cao nhất / Thấp nhất (lần)", font=dict(color=COLOR_TEXT_DARK, size=13)), rangemode="tozero")
        _chart_card_open()
        st.plotly_chart(_layout(sp, height=max(260, 55 * len(rows) + 80)), use_container_width=True)
        _chart_card_close()
    else:
        st.info("Chưa đủ nhóm để so sánh giữa các đặc điểm.")

    # ---- Bảng chi tiết + nhận xét ---------------------------------------------------------
    section_title("Bảng chi tiết thông số")
    table = pd.DataFrame({dim_label: sub["group_value"]})
    table["Default CIF (%)"] = sub["cif_default"] * 100 if "cif_default" in sub.columns else None
    if "cif_prepayment" in sub.columns:
        table["Prepayment CIF (%)"] = sub["cif_prepayment"] * 100
    if base_val:
        table["So với trung bình (lần)"] = sub["ratio"]
    if "number_at_risk" in sub.columns:
        table["Số khoản vay at-risk"] = sub["number_at_risk"]
    if "follow_up_flag" in sub.columns:
        table["Trạng thái theo dõi"] = sub["follow_up_flag"].astype(str).str.lower().map(
            lambda s: "Chưa đủ" if s in ("false", "0", "no") else "Đủ")
    if "number_at_risk" in sub.columns:
        table.loc[sub["number_at_risk"] < MIN_AT_RISK_FOR_RANKING, "Trạng thái theo dõi"] = "Mẫu at-risk nhỏ"
    if sub["group_value"].isin({"Chưa có dữ liệu"}).any():
        st.markdown(f"<p style='color:{COLOR_TEXT_DARK}; font-weight:bold; font-size:13px;'>* Nhóm thiếu dữ liệu vẫn được hiển thị riêng; không đưa nhóm này vào xếp hạng rủi ro.</p>", unsafe_allow_html=True)

    col_cfg = {
        "Default CIF (%)": st.column_config.ProgressColumn(
            "Default CIF (%)", format="%.2f%%", min_value=0,
            max_value=float(max(table["Default CIF (%)"].max(), 0.01))),
        "Prepayment CIF (%)": st.column_config.NumberColumn("Prepayment CIF (%)", format="%.2f%%"),
        "So với trung bình (lần)": st.column_config.NumberColumn("So với trung bình (lần)", format="%.2f×"),
        "Số khoản vay at-risk": st.column_config.NumberColumn("Số khoản vay at-risk (N)", format="%d"),
    }
    col_cfg = {k: v for k, v in col_cfg.items() if k in table.columns}
    st.dataframe(table, hide_index=True, column_config=col_cfg, use_container_width=True)

    insights = [
        f"**{hi['group_value']}** có {metric_label.lower()} mốc {horizon} tháng cao nhất ({_pct(hi[metric])})"
        + (f", bằng **{hi['ratio']:.2f} lần** mức trung bình danh mục." if pd.notna(hi["ratio"]) else "."),
        f"**{lo['group_value']}** thấp nhất ({_pct(lo[metric])})"
        + (f", bằng **{lo['ratio']:.2f} lần** mức trung bình." if pd.notna(lo["ratio"]) else "."),
    ]
    if spread:
        insights.append(f"Khoảng cách chênh lệch giữa hai nhóm là **{spread:.1f} lần**.")

    st.markdown(
        f"""
        <div style='background-color:#F8FAFC; border:1px solid #CBD5E1; border-radius:8px; padding:16px; margin-top:10px;'>
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
    **Competing Risk**, trong đó *Voluntary Prepayment* là sự kiện cạnh tranh.

    - **Không dùng 1 − Kaplan–Meier** làm xác suất Default tích lũy
    khi tồn tại competing event.

    - **Định nghĩa sự kiện:** Default được xác định theo event-definition
    của production pipeline, trong đó 90+ DPD là tín hiệu Default chính,
    kết hợp các quy tắc fallback từ RA và Zero Balance khi phù hợp.
    Voluntary Prepayment được xử lý là competing event;
    các trạng thái còn lại được xử lý theo event mapping của pipeline.

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
        st.info(
            "Chưa có dữ liệu Origination Vintage để hiển thị."
        )
        return

    required_vintage = {
        "vintage",
        "horizon",
        "default_cif",
    }

    if not required_vintage.issubset(v.columns):
        missing = required_vintage - set(v.columns)

        st.warning(
            "Dữ liệu Vintage đang thiếu cột: "
            + ", ".join(sorted(missing))
        )
        return
    section_title("Xu hướng theo Năm giải ngân (Origination Vintage)",
                  "Default CIF của từng năm giải ngân tại các mốc thời gian — so sánh giữa các thế hệ khoản vay.")
    v = v.copy()
    v["horizon"] = v["horizon"].astype(int)
    chart_data = v
    if "follow_up_eligible" in chart_data.columns:
        chart_data = chart_data[
            _to_bool_series(
                chart_data["follow_up_eligible"]
            )
        ].copy()
    if chart_data.empty:
        st.info("Chưa có năm giải ngân (Vintage) nào đủ điều kiện theo dõi tại các mốc thời gian được báo cáo.")
        return
    fig = go.Figure()

    # Bảng màu tương phản đồng bộ mốc thời gian Vintage
    vintage_palette = [COLOR_RISK_HIGH, COLOR_RISK_MID, COLOR_RISK_LOW, COLOR_PREPAYMENT]

    for i, h in enumerate(sorted(chart_data["horizon"].unique())):
        d = chart_data[chart_data["horizon"] == h].sort_values("vintage")
        fig.add_trace(go.Scatter(
            x=d["vintage"].astype(str), y=d["default_cif"], mode="lines+markers", name=f"{h} tháng",
            line=dict(color=vintage_palette[i % len(vintage_palette)], width=3 if h == selected_horizon else 2),
            marker=dict(size=8),
            opacity=1 if h == selected_horizon or selected_horizon is None else 0.6,
        ))
    fig.update_yaxes(title=dict(text="Default CIF", font=dict(color=COLOR_TEXT_DARK, size=13)), tickformat=".0%", rangemode="tozero")
    fig.update_xaxes(title=dict(text="Năm giải ngân (Vintage)", font=dict(color=COLOR_TEXT_DARK, size=13)))
    _chart_card_open()
    st.plotly_chart(_layout(fig), use_container_width=True)
    _chart_card_close()
    with st.expander("Bảng dữ liệu Vintage chi tiết (bao gồm trạng thái theo dõi)"):
        v_renamed = v.rename(columns={
            "vintage": "Năm Vintage",
            "horizon": "Mốc thời gian (Tháng)",
            "default_cif": "Default CIF",
            "prepayment_cif": "Prepayment CIF",
            "loan_count": "Số khoản vay",
            "n_at_risk": "Số lượng at-risk",
            "default_count": "Số ca vỡ nợ",
            "prepayment_count": "Số ca trả trước",
            "follow_up_eligible": "Đủ điều kiện theo dõi"
        })
        st.dataframe(v_renamed.sort_values(["Năm Vintage", "Mốc thời gian (Tháng)"]).reset_index(drop=True),
                     hide_index=True, use_container_width=True)