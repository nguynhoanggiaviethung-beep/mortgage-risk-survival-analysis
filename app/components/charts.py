"""Các builder chart dùng chung (Plotly), style đồng bộ theme của app."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from app.config import CHART_SEQUENCE, DANGER, FONT_STACK, PRIMARY, SUCCESS, TEXT_MUTED

_LAYOUT_DEFAULTS = dict(
    font=dict(family=FONT_STACK, size=12, color="#1A1A1A"),
    plot_bgcolor="white",
    paper_bgcolor="white",
    margin=dict(l=10, r=10, t=30, b=10),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    colorway=CHART_SEQUENCE,
)


def _apply_layout(fig: go.Figure, height: int = 360) -> go.Figure:
    fig.update_layout(height=height, **_LAYOUT_DEFAULTS)
    fig.update_xaxes(showgrid=True, gridcolor="#EEF2F6")
    fig.update_yaxes(showgrid=True, gridcolor="#EEF2F6")
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
    """Default CIF vs Voluntary Prepayment CIF theo horizon (từ pd_results)."""
    fig = go.Figure()
    d = df.sort_values("horizon")
    fig.add_trace(go.Scatter(
        x=d["horizon"], y=d["cif_default"], mode="lines+markers",
        name="Default CIF", line=dict(color=DANGER, width=2.5),
    ))
    if "cif_prepayment" in d.columns:
        fig.add_trace(go.Scatter(
            x=d["horizon"], y=d["cif_prepayment"], mode="lines+markers",
            name="Voluntary Prepayment CIF", line=dict(color=PRIMARY, width=2.5, dash="dot"),
        ))
    fig.update_xaxes(title="Horizon (tháng)")
    fig.update_yaxes(title="Cumulative Incidence", tickformat=".0%")
    return _apply_layout(fig)


def km_vs_cif_compare_chart(df_km: pd.DataFrame, df_cif: pd.DataFrame) -> go.Figure:
    """So sánh 1 − KM survival với Default CIF (competing-risk) trên cùng 1 trục thời gian.

    Minh hoạ đúng LOCKED RULE trong specification: khi Voluntary Prepayment
    là competing event, 1 − KM survival KHÔNG bằng Default CIF.
    """
    fig = go.Figure()
    km = df_km.sort_values("analysis_time")
    fig.add_trace(go.Scatter(
        x=km["analysis_time"], y=1 - km["survival"], mode="lines",
        name="1 − KM survival (censor prepayment)",
        line=dict(color=TEXT_MUTED, width=2, dash="dash"),
    ))
    cif = df_cif.sort_values("horizon")
    fig.add_trace(go.Scatter(
        x=cif["horizon"], y=cif["cif_default"], mode="lines+markers",
        name="Default CIF (competing risk)",
        line=dict(color=DANGER, width=2.5),
    ))
    fig.update_xaxes(title="Time (tháng)")
    fig.update_yaxes(title="Probability", tickformat=".0%")
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
    fig.update_xaxes(title="Hazard Ratio / Sub-distribution Hazard Ratio")
    return _apply_layout(fig, height=max(280, 60 * len(d)))


def loan_timeline_chart(df: pd.DataFrame, loan_age: int | None = None) -> go.Figure:
    """Timeline 1 khoản vay: trục ngang analysis_time, đánh dấu event/current."""
    d = df.sort_values("analysis_time_month")
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=d["analysis_time_month"], y=[0] * len(d), mode="lines",
        line=dict(color=PRIMARY, width=3), showlegend=False, hoverinfo="skip",
    ))
    fig.add_trace(go.Scatter(
        x=[0], y=[0], mode="markers+text",
        marker=dict(size=12, color=TEXT_MUTED, symbol="diamond"),
        text=["Origination month (proxy)"], textposition="top center",
        name="Origination month (proxy)",
    ))
    fig.add_trace(go.Scatter(
        x=[1], y=[0], mode="markers+text",
        marker=dict(size=10, color=PRIMARY), text=["First payment"],
        textposition="bottom center", name="First payment month",
    ))
    if loan_age is not None:
        fig.add_trace(go.Scatter(
            x=[loan_age], y=[0], mode="markers+text",
            marker=dict(size=13, color=DANGER, symbol="star"),
            text=["Current"], textposition="top center", name="Current",
        ))
    event_rows = d[d.get("event_type", pd.Series(dtype=object)).isin(["DEFAULT", "VOLUNTARY_PREPAYMENT"])]
    if not event_rows.empty:
        fig.add_trace(go.Scatter(
            x=event_rows["analysis_time_month"], y=[0] * len(event_rows), mode="markers+text",
            marker=dict(size=13, color=SUCCESS, symbol="x"),
            text=event_rows["event_type"], textposition="bottom center", name="Event",
        ))
    fig.update_yaxes(visible=False, range=[-1, 1])
    fig.update_xaxes(title="Months since origination-month proxy (first payment = month 1)")
    return _apply_layout(fig, height=220)
