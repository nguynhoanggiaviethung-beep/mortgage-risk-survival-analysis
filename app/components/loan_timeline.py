import plotly.graph_objects as go
import pandas as pd

def loan_timeline_chart(df_timeline: pd.DataFrame, loan_age: int = None) -> go.Figure:
    """
    Vẽ Timeline khoản vay dựa trên dataframe timeline lấy từ database/csv.
    Tuân thủ đúng Research Spec: Không hiển thị post-event observations.
    """
    if df_timeline.empty:
        return go.Figure()

    # Sắp xếp dữ liệu theo tháng
    df_sorted = df_timeline.sort_values("analysis_time_month").copy()

    # 1. Xác định mốc kết thúc (Chỉ giữ dữ liệu đến khi xảy ra Event/Censoring đầu tiên)
    terminal_events = df_sorted[df_sorted["event_type"].isin(["DEFAULT", "VOLUNTARY_PREPAYMENT"])]
    if not terminal_events.empty:
        cutoff_month = terminal_events["analysis_time_month"].min()
        df_sorted = df_sorted[df_sorted["analysis_time_month"] <= cutoff_month]

    max_month = int(df_sorted["analysis_time_month"].max())
    last_event = df_sorted.iloc[-1].get("event_type", "ACTIVE")

    fig = go.Figure()

    # 2. Đường kẻ ngang nối từ Tháng 0 -> Tháng kết thúc
    fig.add_trace(go.Scatter(
        x=df_sorted["analysis_time_month"],
        y=[0] * len(df_sorted),
        mode="lines",
        line=dict(color="#94A3B8", width=3),
        hoverinfo="skip",
        showlegend=False
    ))

    # 3. Marker Origination (Tháng 0)
    fig.add_trace(go.Scatter(
        x=[0],
        y=[0],
        mode="markers+text",
        marker=dict(size=14, color="#2563EB", symbol="circle"),
        text=["Origination"],
        textposition="top center",
        name="Origination",
        hovertemplate="<b>Origination (T=0)</b><extra></extra>"
    ))

    # 4. Markers cho các kỳ Active hàng tháng
    active_obs = df_sorted[(df_sorted["analysis_time_month"] > 0) & (df_sorted["analysis_time_month"] < max_month)]
    if not active_obs.empty:
        fig.add_trace(go.Scatter(
            x=active_obs["analysis_time_month"],
            y=[0] * len(active_obs),
            mode="markers",
            marker=dict(size=8, color="#0EA5E9", symbol="circle"),
            name="Monthly Obs",
            hovertemplate="<b>Tháng %{x}</b>: Trạng thái Active<extra></extra>"
        ))

    # 5. Marker mốc cuối (Event/Censoring/Active)
    if last_event == "DEFAULT":
        color, symbol, label = "#EF4444", "x", "Event (Default)"
    elif last_event == "VOLUNTARY_PREPAYMENT":
        color, symbol, label = "#F59E0B", "diamond", "Censoring (Prepayment)"
    else:
        color, symbol, label = "#10B981", "circle", f"Current (Tháng {max_month})"

    if max_month > 0:
        fig.add_trace(go.Scatter(
            x=[max_month],
            y=[0],
            mode="markers+text",
            marker=dict(size=14, color=color, symbol=symbol, line=dict(width=2, color="white")),
            text=[label],
            textposition="top center",
            name=last_event,
            hovertemplate=f"<b>Mốc kết thúc: Tháng {max_month}</b><br>Trạng thái: {last_event}<extra></extra>"
        ))

    fig.update_layout(
        height=200,
        margin=dict(l=30, r=30, t=30, b=30),
        xaxis=dict(
            title="Loan Age (Tháng)",
            dtick=1 if max_month <= 12 else (3 if max_month <= 36 else 6),
            range=[-1, max_month + 2],
            showgrid=False
        ),
        yaxis=dict(showticklabels=False, showgrid=False, zeroline=False, range=[-0.5, 0.5]),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.5, xanchor="center", x=0.5)
    )

    return fig