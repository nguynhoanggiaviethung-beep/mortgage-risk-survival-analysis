"""Các builder chart dùng chung (Plotly), style đồng bộ theme của app."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from app.config import CHART_SEQUENCE, DANGER, FONT_STACK, PRIMARY, PRIMARY_DARK, SUCCESS, TEXT_MUTED

_LAYOUT_DEFAULTS = dict(
    font=dict(family=FONT_STACK, size=12, color="#303A34"),
    plot_bgcolor="#FFFEFA",
    paper_bgcolor="#FFFEFA",
    margin=dict(l=18, r=18, t=42, b=18),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    colorway=CHART_SEQUENCE,
)


def _apply_layout(fig: go.Figure, height: int = 360) -> go.Figure:
    fig.update_layout(height=height, **_LAYOUT_DEFAULTS)
    fig.update_xaxes(showgrid=False, linecolor="#DCD7C8", tickfont=dict(family=FONT_STACK, color="#536056"))
    fig.update_yaxes(showgrid=True, gridcolor="#E8E4D9", zerolinecolor="#DCD7C8", tickfont=dict(family=FONT_STACK, color="#536056"))
    fig.update_layout(
        legend=dict(font=dict(family=FONT_STACK, color=PRIMARY_DARK)),
        hoverlabel=dict(bgcolor=PRIMARY_DARK, font=dict(family=FONT_STACK, color="#FFFEFA")),
    )
    return fig


def survival_curve_chart(df: pd.DataFrame, group_col: str = "group_value") -> go.Figure:
    """KM survival curve từ survival_results (analysis_time, survival, ci_low, ci_high, group_value)."""
    fig = go.Figure()
    groups = df[group_col].unique() if group_col in df.columns else [None]
    for i, g in enumerate(groups):
        sub = df[df[group_col] == g] if g is not None else df
        sub = sub.sort_values("analysis_time")
        color = CHART_SEQUENCE[i % len(CHART_SEQUENCE)]
        if {"ci_low", "ci_high"}.issubset(sub.columns):
            fig.add_trace(go.Scatter(
                x=pd.concat([sub["analysis_time"], sub["analysis_time"][::-1]]),
                y=pd.concat([sub["ci_high"], sub["ci_low"][::-1]]),
                fill="toself", fillcolor=color, opacity=0.12,
                line=dict(width=0), showlegend=False, hoverinfo="skip",
            ))
        fig.add_trace(go.Scatter(
            x=sub["analysis_time"], y=sub["survival"],
            mode="lines", name=str(g) if g is not None else "Survival",
            line=dict(color=color, width=2, shape="hv"),
        ))
    fig.update_yaxes(title="Survival S(t)", range=[0, 1])
    fig.update_xaxes(title="Months since origination-month proxy (first payment = month 1)")
    return _apply_layout(fig)


def cif_chart(df: pd.DataFrame) -> go.Figure:
    """Aalen–Johansen step CIF curves with pointwise confidence bands."""
    fig = go.Figure()
    if {"endpoint", "analysis_time", "cumulative_incidence"}.issubset(df.columns):
        palette = {"DEFAULT": (DANGER, "Default CIF"), "PREPAYMENT": (PRIMARY, "Voluntary Prepayment (ZBC 01) CIF")}
        for endpoint, (color, label) in palette.items():
            d = df[df["endpoint"].astype(str).str.upper() == endpoint].sort_values("analysis_time")
            if d.empty:
                continue
            if {"ci_lower", "ci_upper"}.issubset(d.columns):
                x_band = pd.concat([d["analysis_time"], d["analysis_time"][::-1]])
                y_band = pd.concat([d["ci_upper"], d["ci_lower"][::-1]])
                fig.add_trace(go.Scatter(
                    x=x_band, y=y_band, fill="toself", fillcolor=color, opacity=0.12,
                    line=dict(width=0), showlegend=False, hoverinfo="skip",
                ))
            custom = d[[c for c in ("ci_lower", "ci_upper", "n_at_risk") if c in d.columns]].to_numpy()
            fig.add_trace(go.Scatter(
                x=d["analysis_time"], y=d["cumulative_incidence"], mode="lines",
                name=label, line=dict(color=color, width=2.5, shape="hv"), customdata=custom,
                hovertemplate=("Tháng %{x}<br>CIF: %{y:.2%}" +
                    ("<br>CI 95%: %{customdata[0]:.2%}–%{customdata[1]:.2%}" if {"ci_lower", "ci_upper"}.issubset(d.columns) else "") +
                    ("<br>Còn at-risk: %{customdata[2]:,}" if "n_at_risk" in d.columns and {"ci_lower", "ci_upper"}.issubset(d.columns) else "") +
                    "<extra></extra>"),
            ))
        fig.update_xaxes(title="Tháng kể từ mốc origination vận hành")
    else:
        # Backward-compatible fallback for legacy horizon tables: show points
        # without interpolating between fixed horizons.
        d = df.sort_values("horizon")
        fig.add_trace(go.Scatter(x=d["horizon"], y=d["cif_default"], mode="markers", name="Default CIF", marker_color=DANGER))
        if "cif_prepayment" in d.columns:
            fig.add_trace(go.Scatter(x=d["horizon"], y=d["cif_prepayment"], mode="markers", name="Voluntary Prepayment (ZBC 01) CIF", marker_color=PRIMARY))
        fig.update_xaxes(title="Horizon (tháng)")
    fig.update_yaxes(title="Cumulative incidence", tickformat=".0%", range=[0, 1])
    return _apply_layout(fig)


def km_vs_cif_compare_chart(df_km: pd.DataFrame, df_cif: pd.DataFrame) -> go.Figure:
    """So sánh 1 − KM survival với Default CIF (competing-risk) trên cùng 1 trục thời gian.

    Minh hoạ đúng LOCKED RULE trong specification: khi Voluntary Prepayment
    là competing event, 1 − KM survival KHÔNG bằng Default CIF.
    """
    fig = go.Figure()
    km = df_km.sort_values("analysis_time")
    km_ci_upper = km.get("ci_upper", km.get("ci_high"))
    km_ci_lower = km.get("ci_lower", km.get("ci_low"))
    km_low = (1 - km_ci_upper) if km_ci_upper is not None else None
    km_high = (1 - km_ci_lower) if km_ci_lower is not None else None
    if km_low is not None:
        fig.add_trace(go.Scatter(
            x=pd.concat([km["analysis_time"], km["analysis_time"][::-1]]),
            y=pd.concat([km_high, km_low[::-1]]), fill="toself",
            fillcolor=TEXT_MUTED, opacity=0.12, line=dict(width=0),
            showlegend=False, hoverinfo="skip",
        ))
    km_custom_cols = [c for c in ("ci_lower", "ci_upper", "ci_low", "ci_high", "n_at_risk") if c in km.columns]
    km_custom = km[km_custom_cols].to_numpy()
    km_ci_indices = (km_custom_cols.index("ci_lower"), km_custom_cols.index("ci_upper")) if {"ci_lower", "ci_upper"}.issubset(km_custom_cols) else (
        (km_custom_cols.index("ci_low"), km_custom_cols.index("ci_high")) if {"ci_low", "ci_high"}.issubset(km_custom_cols) else None
    )
    km_hover = "Tháng %{x}<br>1−KM: %{y:.2%}"
    if km_ci_indices:
        km_hover += f"<br>95% CI: %{{customdata[{km_ci_indices[0]}]:.2%}}–%{{customdata[{km_ci_indices[1]}]:.2%}}"
    km_hover += "<extra></extra>"
    fig.add_trace(go.Scatter(
        x=km["analysis_time"], y=1 - km["survival"], mode="lines",
        name="1 − KM survival (censor prepayment)",
        line=dict(color=TEXT_MUTED, width=2, dash="dash", shape="hv"), customdata=km_custom,
        hovertemplate=km_hover,
    ))
    if {"endpoint", "analysis_time", "cumulative_incidence"}.issubset(df_cif.columns):
        cif = df_cif[df_cif["endpoint"].astype(str).str.upper() == "DEFAULT"].sort_values("analysis_time")
        cif_x, cif_y = cif["analysis_time"], cif["cumulative_incidence"]
        if {"ci_lower", "ci_upper"}.issubset(cif.columns):
            fig.add_trace(go.Scatter(
                x=pd.concat([cif_x, cif_x[::-1]]), y=pd.concat([cif["ci_upper"], cif["ci_lower"][::-1]]),
                fill="toself", fillcolor=DANGER, opacity=0.12, line=dict(width=0),
                showlegend=False, hoverinfo="skip",
            ))
        custom_cols = [c for c in ("ci_lower", "ci_upper", "n_at_risk") if c in cif.columns]
        custom = cif[custom_cols].to_numpy()
        cif_hover = "Tháng %{x}<br>Default CIF: %{y:.2%}"
        if {"ci_lower", "ci_upper"}.issubset(custom_cols):
            cif_hover += "<br>95% CI: %{customdata[0]:.2%}–%{customdata[1]:.2%}"
        if "n_at_risk" in custom_cols:
            cif_hover += f"<br>At-risk: %{{customdata[{custom_cols.index('n_at_risk')}]:,}}"
        cif_hover += "<extra></extra>"
    else:
        cif = df_cif.sort_values("horizon")
        cif_x, cif_y = cif["horizon"], cif["cif_default"]
        custom = None
    fig.add_trace(go.Scatter(
        x=cif_x, y=cif_y, mode="lines",
        name="Default CIF (competing risk)",
        line=dict(color=DANGER, width=2.5, shape="hv"), customdata=custom,
        hovertemplate=cif_hover if custom is not None else "Tháng %{x}<br>Default CIF: %{y:.2%}<extra></extra>",
    ))
    fig.update_xaxes(title="Tháng kể từ mốc origination vận hành")
    fig.update_yaxes(title="Probability", tickformat=".0%", range=[0, 1])
    return _apply_layout(fig)


def risk_by_band_bar(df: pd.DataFrame, x_col: str, y_col: str, y_title: str) -> go.Figure:
    fig = go.Figure(go.Bar(
        x=df[x_col], y=df[y_col],
        marker_color=PRIMARY,
        text=[f"{v:.1%}" for v in df[y_col]],
        textposition="outside",
    ))
    fig.update_yaxes(title=y_title, tickformat=".0%")
    fig.update_xaxes(title=x_col)
    return _apply_layout(fig, height=320)


def forest_plot(df: pd.DataFrame) -> go.Figure:
    """HR/SHR forest plot từ risk_driver_results (variable, hr_shr, ci_low, ci_high)."""
    d = df.sort_values("hr_shr")
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=d["hr_shr"], y=d["variable"], mode="markers",
        marker=dict(size=10, color=PRIMARY, symbol="diamond"),
        error_x=dict(
            type="data",
            symmetric=False,
            array=d["ci_high"] - d["hr_shr"],
            arrayminus=d["hr_shr"] - d["ci_low"],
            color=PRIMARY,
        ),
        name="HR / SHR",
    ))
    fig.add_vline(x=1, line_dash="dash", line_color=TEXT_MUTED, annotation_text="HR = 1")
    fig.update_xaxes(title="Hazard Ratio / Sub-distribution Hazard Ratio (log scale)", type="log")
    return _apply_layout(fig, height=max(280, 60 * len(d)))


def loan_timeline_chart(df: pd.DataFrame, loan_age: int | None = None) -> go.Figure:
    """Two aligned monthly series: delinquency status and current actual UPB."""
    if df.empty or "analysis_time_month" not in df.columns:
        return go.Figure()
    d = df.sort_values("analysis_time_month").drop_duplicates("analysis_time_month", keep="last").copy()
    d["analysis_time_month"] = pd.to_numeric(d["analysis_time_month"], errors="coerce")
    d = d.dropna(subset=["analysis_time_month"])
    if d.empty:
        return go.Figure()

    def status_rank(row):
        is_ra = row.get("is_ra", False)
        if pd.notna(is_ra) and bool(is_ra):
            return 4
        value = row.get("delinquency_num")
        try:
            value = int(value)
            return min(max(value, 0), 3)
        except (TypeError, ValueError, OverflowError):
            raw = str(row.get("current_delinquency_status", "")).strip().upper()
            if raw == "RA":
                return 4
            return None

    d["status_rank"] = d.apply(status_rank, axis=1)
    d["current_actual_upb"] = pd.to_numeric(d.get("current_actual_upb"), errors="coerce")
    min_month, max_month = int(d["analysis_time_month"].min()), int(d["analysis_time_month"].max())
    monthly = d.set_index("analysis_time_month").reindex(range(min_month, max_month + 1))
    terminal = d.iloc[-1]
    event_type = str(terminal.get("event_type", "CENSOR")).upper()
    event_label = {
        "DEFAULT": "Default",
        "VOLUNTARY_PREPAYMENT": "Voluntary Prepayment (ZBC 01)",
        "PREPAYMENT": "Voluntary Prepayment (ZBC 01)",
    }.get(event_type, "Censoring termination / cuối kỳ quan sát")

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.12,
                        row_heights=[0.42, 0.58], subplot_titles=("Trạng thái quá hạn", "Current Actual UPB"))
    fig.add_trace(go.Scatter(
        x=monthly.index, y=monthly["status_rank"], mode="lines+markers",
        line=dict(color=PRIMARY, width=2, shape="hv"),
        marker=dict(size=6, color=PRIMARY), name="Delinquency status",
        customdata=monthly[[c for c in ("current_delinquency_status", "delinquency_num", "is_ra") if c in monthly.columns]].to_numpy(),
        hovertemplate="Tháng %{x}<br>Status: %{customdata[0]}<br>Delinquency code: %{customdata[1]}<extra></extra>",
        connectgaps=False,
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=monthly.index, y=monthly["current_actual_upb"], mode="lines+markers",
        line=dict(color="#2E7D32", width=2),
        marker=dict(size=4, color="#2E7D32"), name="Current Actual UPB",
        hovertemplate="Tháng %{x}<br>Current Actual UPB: $%{y:,.0f}<extra></extra>",
        connectgaps=False,
    ), row=2, col=1)
    fig.add_vline(x=int(terminal["analysis_time_month"]), line_dash="dash", line_color=DANGER,
                  annotation_text=event_label, annotation_position="top right")
    fig.add_vline(x=0, line_dash="dot", line_color=TEXT_MUTED, annotation_text="Origination proxy", row=1, col=1)
    fig.add_vline(x=1, line_dash="dot", line_color=PRIMARY, annotation_text="First payment month", row=1, col=1)
    fig.update_yaxes(title="Delinquency status", tickmode="array", tickvals=[0, 1, 2, 3, 4],
                     ticktext=["Current", "30 DPD", "60 DPD", "90+ DPD", "RA"], range=[-0.5, 4.5], row=1, col=1)
    fig.update_yaxes(title="UPB (USD)", tickprefix="$", separatethousands=True, rangemode="tozero", row=2, col=1)
    fig.update_xaxes(title="Months since origination-month proxy (first payment = month 1)", row=2, col=1)
    fig.update_layout(legend=dict(orientation="h", y=-0.18), margin=dict(l=35, r=30, t=55, b=70))
    return _apply_layout(fig, height=430)
