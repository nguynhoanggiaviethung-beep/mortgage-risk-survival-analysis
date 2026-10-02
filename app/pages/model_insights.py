"""Trang 4 — PD theo thời gian, competing risks và hệ số mô hình."""

from __future__ import annotations

import html

import pandas as pd
import streamlit as st

from app.components.charts import cif_chart, forest_plot, km_vs_cif_compare_chart
from app.components.page_blocks import (
    BLUE,
    NAVY,
    RED,
    TINT_BLUE,
    TINT_NAVY,
    TINT_RED,
    callout,
    inject_page_blocks_css,
    page_kicker,
    section_heading,
    stat_card,
)
from app.services import data_service as ds

_FACTOR_MODELS = ["Cox PH", "Time-varying Cox", "Cause-specific Hazard", "Fine-Gray"]
_MODEL_LABELS = {
    "Cox PH": "Cox (rủi ro tỷ lệ)",
    "Time-varying Cox": "Cox với biến thay đổi theo thời gian",
    "Cause-specific Hazard": "Hazard theo từng nguyên nhân",
    "Fine-Gray": "Fine–Gray (rủi ro cạnh tranh)",
}
_MAIN_HORIZONS = [12, 24, 36, 60]
_ELIGIBLE_TOKENS = {"true", "1", "1.0", "y", "yes", "ok", "eligible", "sufficient", "full"}
_VARIABLE_LABELS = {
    "fico": "Credit Score (FICO)",
    "original_ltv": "LTV ban đầu",
    "original_dti": "DTI ban đầu",
    "original_interest_rate": "Lãi suất ban đầu",
    "original_loan_term": "Kỳ hạn vay ban đầu",
    "lag_current_actual_upb": "Dư nợ thực tế tháng trước",
    "lag_current_interest_rate": "Lãi suất tháng trước",
    "lag_dq_1m": "Trễ hạn 1 tháng (tháng trước)",
    "lag_dq_2m": "Trễ hạn 2 tháng (tháng trước)",
}
_GLOSSARY = {
    "PD(t)": "Tỷ lệ khoản vay đã vỡ nợ tính lũy kế đến thời điểm t.",
    "CIF": "Xác suất tích lũy của một kết cục, có tính đến khả năng khoản vay kết thúc vì một kết cục khác.",
    "KM": "Phương pháp Kaplan–Meier ước tính tỷ lệ khoản vay chưa gặp kết cục đang xét theo thời gian.",
    "1 − KM": "Tỷ lệ ước tính đã gặp kết cục theo Kaplan–Meier; các kết cục khác được xem là ngừng theo dõi.",
    "HR": "Tỷ số so sánh tốc độ xảy ra kết cục giữa các nhóm. HR = 1 là tương đương; lớn hơn 1 là nhanh hơn, nhỏ hơn 1 là chậm hơn.",
    "SHR": "Tỷ số so sánh trong mô hình Fine–Gray, có xét đến các khoản vay kết thúc vì kết cục cạnh tranh.",
    "CI": "Khoảng tin cậy thể hiện độ bất định quanh ước lượng. Với HR/SHR, khoảng chứa 1 chưa cho thấy khác biệt rõ giữa các nhóm.",
    "p-value": "Chỉ số đánh giá bằng chứng thống kê; không phải xác suất khoản vay sẽ vỡ nợ.",
}


def _format_probability(value) -> str:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "—"
    return f"{value:.2%}" if pd.notna(value) else "—"


def _eligible_mask(frame: pd.DataFrame) -> pd.Series:
    if "follow_up_flag" not in frame.columns:
        return pd.Series(True, index=frame.index)
    value = frame["follow_up_flag"]
    if pd.api.types.is_bool_dtype(value):
        return value.fillna(False)
    return value.astype(str).str.strip().str.lower().isin(_ELIGIBLE_TOKENS)


def _main_horizon_rows(
    cif: pd.DataFrame,
    km: pd.DataFrame | None = None,
    aj: pd.DataFrame | None = None,
) -> pd.DataFrame:
    if cif.empty or not {"horizon", "cif_default"}.issubset(cif.columns):
        return pd.DataFrame()
    eligible = cif.loc[_eligible_mask(cif)].copy()
    eligible["horizon"] = pd.to_numeric(eligible["horizon"], errors="coerce")
    max_km_time = None
    if km is not None and not km.empty and "analysis_time" in km.columns:
        max_km_time = pd.to_numeric(km["analysis_time"], errors="coerce").max()
    keep = eligible[eligible["horizon"].isin(_MAIN_HORIZONS)]
    if max_km_time is not None and pd.notna(max_km_time):
        keep = keep[keep["horizon"] <= max_km_time]
    keep = keep.sort_values("horizon").drop_duplicates("horizon")
    # The dashboard's plotted competing-risk curves and reported CIs come from
    # the Aalen–Johansen output. Use that same source for point estimates so a
    # stale/misaligned pd_results row cannot disagree with the chart or CI.
    if aj is not None and not aj.empty:
        points = []
        for horizon in keep["horizon"].astype(int):
            point = _curve_at(aj, "DEFAULT", horizon)
            if point and pd.notna(point.get("value")):
                points.append({"horizon": horizon, "cif_default": float(point["value"])})
        if points:
            keep = pd.DataFrame(points)
    return keep


def _portfolio_cif() -> pd.DataFrame:
    result = ds.get_pd_results(group="portfolio")
    return result if not result.empty else ds.get_pd_results()


def _portfolio_km() -> pd.DataFrame:
    result = ds.get_survival_results(group="portfolio")
    return result if not result.empty else ds.get_survival_results()


def _portfolio_aj() -> pd.DataFrame:
    return ds.get_aj_curves(group_name="portfolio")


def _curve_at(curves: pd.DataFrame, endpoint: str, horizon: int) -> dict:
    if curves.empty or not {"endpoint", "analysis_time", "cumulative_incidence"}.issubset(curves.columns):
        return {}
    part = curves[
        (curves["endpoint"].astype(str).str.upper() == endpoint)
        & (pd.to_numeric(curves["analysis_time"], errors="coerce") <= horizon)
    ].sort_values("analysis_time")
    if part.empty:
        return {}
    row = part.iloc[-1]
    return {
        "value": row.get("cumulative_incidence"),
        "ci_low": row.get("ci_lower"),
        "ci_high": row.get("ci_upper"),
        "n_at_risk": row.get("n_at_risk"),
    }


def _ci_note(point: dict) -> str:
    low, high = point.get("ci_low"), point.get("ci_high")
    at_risk = point.get("n_at_risk")
    bits = []
    if pd.notna(low) and pd.notna(high):
        bits.append(f"CI 95% {float(low):.2%}–{float(high):.2%}")
    if pd.notna(at_risk):
        bits.append(f"at-risk {int(at_risk):,}")
    return " · ".join(bits) if bits else "Khoảng tin cậy chưa có trong bảng horizon."


def _render_glossary(keys: list[str]) -> None:
    rows = "".join(
        '<div style="display:flex;gap:12px;align-items:flex-start;margin:7px 0;">'
        f'<span style="min-width:58px;text-align:center;background:{NAVY};color:#fff;'
        f'font-weight:700;padding:3px 9px;border-radius:999px;">{html.escape(key)}</span>'
        f'<span style="color:#536056;line-height:1.5;">{html.escape(_GLOSSARY[key])}</span></div>'
        for key in keys if key in _GLOSSARY
    )
    if rows:
        st.markdown(
            '<div style="background:#F6F3E9;border:1px solid #DCD7C8;border-left:4px solid '
            f'#B99B53;border-radius:4px;padding:12px 16px;margin:8px 0 14px;box-shadow:4px 4px 0 rgba(89,82,60,.08);">'
            f'<strong style="color:{NAVY};">Chú thích · đọc trước khi xem kết quả</strong>{rows}</div>',
            unsafe_allow_html=True,
        )


def _method_note(title: str, question: str, method: str, reading: str, limit: str) -> None:
    """Show a plain-language method guide next to the chart it explains."""
    parts = [
        ("Câu hỏi phân tích", question),
        ("Phương pháp", method),
        ("Cách đọc", reading),
        ("Giới hạn", limit),
    ]
    rows = "".join(
        '<div style="margin-top:7px;line-height:1.55;">'
        f'<strong style="color:{NAVY};">{html.escape(label)}:</strong> '
        f'<span style="color:#536056;">{html.escape(text)}</span></div>'
        for label, text in parts
    )
    st.markdown(
        '<div style="background:#F6F3E9;border:1px solid #DCD7C8;border-left:4px solid '
        f'#637E69;border-radius:4px;padding:12px 16px;margin:4px 0 12px;">'
        f'<strong style="color:{NAVY};font-family:Lora,Georgia,serif;">{html.escape(title)}</strong>'
        f'{rows}</div>',
        unsafe_allow_html=True,
    )


def _render_default_cif() -> tuple[pd.DataFrame, pd.DataFrame]:
    section_heading(
        1,
        "Vỡ nợ tăng như thế nào theo thời gian?",
        "Default CIF / PD(t) ước lượng xác suất vỡ nợ tích lũy; ZBC 01 (trả trước/đáo hạn gộp) là sự kiện cạnh tranh.",
    )
    cif = _portfolio_cif()
    km = _portfolio_km()
    aj = _portfolio_aj()
    if cif.empty:
        st.info("Chưa có kết quả xác suất vỡ nợ (pd_results) đã công bố.")
        return cif, km

    horizons = _main_horizon_rows(cif, aj=aj)
    if horizons.empty:
        st.info("Chưa có mốc 12/24/36/60 tháng đủ thời gian theo dõi để báo cáo.")
    else:
        columns = st.columns(len(horizons))
        for column, (_, row) in zip(columns, horizons.iterrows()):
            with column:
                stat_card(
                    f"Xác suất vỡ nợ tích lũy · {int(row['horizon'])} tháng",
                    _format_probability(row["cif_default"]),
                    _ci_note(_curve_at(aj, "DEFAULT", int(row["horizon"]))),
                    RED,
                    TINT_RED,
                )

    _render_glossary(["PD(t)", "CIF"])
    _method_note(
        "Ước lượng xác suất tích lũy · Aalen–Johansen (CIF)",
        "Tỷ lệ vỡ nợ tích lũy của danh mục thay đổi thế nào theo thời gian, khi một khoản vay cũng có thể kết thúc bằng ZBC 01?",
        "Aalen–Johansen cộng dồn các khoản vỡ nợ theo từng tháng, đồng thời tính đến những khoản đã kết thúc vì ZBC 01. Sau khi kết thúc, khoản vay không còn được xem là có thể vỡ nợ trong các tháng tiếp theo. Đây là điểm giúp phương pháp phản ánh các loại kết cục cạnh tranh trong cùng danh mục.",
        "Trục ngang thể hiện số tháng theo dõi; trục dọc là tỷ lệ vỡ nợ tích lũy. Đường càng cao, tỷ lệ khoản vay đã vỡ nợ tính đến thời điểm đó càng lớn. Dải quanh đường, nếu có, thể hiện khoảng bất định của ước lượng.",
        "Kết quả mô tả toàn bộ nhóm nghiên cứu, không phải dự báo chắc chắn cho từng khoản vay. ZBC 01 gộp trả trước và đáo hạn; mốc bắt đầu được xác định bằng First Payment Date trừ một tháng, do dữ liệu không cung cấp ngày giải ngân trực tiếp.",
    )
    chart_data = aj.copy()
    if not chart_data.empty:
        with st.container(border=True):
            st.plotly_chart(cif_chart(chart_data), width="stretch")
    st.caption(
        "Ví dụ cách đọc: Default CIF tại 36 tháng là tỷ lệ tích lũy khoản vay đã vỡ nợ đến tháng 36 "
        "trong nhóm nghiên cứu; đây không phải xác suất vỡ nợ cá nhân hay ECL theo IFRS 9."
    )
    return cif, km


def _render_competing_risk_comparison(
    cif: pd.DataFrame, km: pd.DataFrame, aj: pd.DataFrame
) -> None:
    section_heading(
        2,
        "Tại sao không dùng 1 − KM?",
        "So sánh Kaplan–Meier với Default CIF khi ZBC 01 (trả trước/đáo hạn gộp) là sự kiện cạnh tranh.",
    )
    if cif.empty or km.empty or aj.empty:
        st.info("Cần cả kết quả PD, Kaplan–Meier và Aalen–Johansen để so sánh.")
        return
    horizons = _main_horizon_rows(cif, km, aj)
    if horizons.empty:
        st.info("Chưa có mốc chính đủ thời gian theo dõi để so sánh, không ngoại suy kết quả.")
        return

    last_horizon = int(horizons["horizon"].max())
    km_display = km[pd.to_numeric(km["analysis_time"], errors="coerce") <= last_horizon].copy()
    cif_display = aj
    cif_display = cif_display[
        (cif_display["endpoint"].astype(str).str.upper() == "DEFAULT")
        & (pd.to_numeric(cif_display["analysis_time"], errors="coerce") <= last_horizon)
    ].copy()
    _render_glossary(["KM", "1 − KM", "CIF"])
    _method_note(
        "So sánh hai cách ước lượng · Kaplan–Meier và Aalen–Johansen",
        "Cách xử lý ZBC 01 ảnh hưởng thế nào đến ước lượng tỷ lệ vỡ nợ tích lũy?",
        "Kaplan–Meier xem khoản vay kết thúc bằng ZBC 01 là ngừng theo dõi. Aalen–Johansen xem đây là một kết cục riêng có thể xảy ra thay cho vỡ nợ. Vì vậy, hai phương pháp đưa ra các ước lượng cho hai cách đặt vấn đề khác nhau.",
        "Đối chiếu hai đường tại cùng một mốc thời gian. Nếu đường 1 − KM cao hơn, phương pháp Kaplan–Meier ước lượng tỷ lệ vỡ nợ cao hơn khi ZBC 01 được xem là ngừng theo dõi. Khoảng cách giữa hai đường không phải thước đo độ chính xác của mô hình.",
        "Khi câu hỏi nghiên cứu cần tính đến việc khoản vay có thể kết thúc theo nhiều cách, Aalen–Johansen phù hợp hơn để mô tả xác suất tích lũy quan sát được. 1 − KM không phải xác suất vỡ nợ riêng của từng khoản vay.",
    )
    with st.container(border=True):
        st.plotly_chart(km_vs_cif_compare_chart(km_display, cif_display), width="stretch")

    rows = []
    for _, row in horizons.iterrows():
        horizon = int(row["horizon"])
        km_at_horizon = km.loc[
            pd.to_numeric(km["analysis_time"], errors="coerce") <= horizon
        ].sort_values("analysis_time")
        if km_at_horizon.empty:
            continue
        naive = 1 - float(km_at_horizon["survival"].iloc[-1])
        point = _curve_at(aj, "DEFAULT", horizon)
        if not point or pd.isna(point.get("value")):
            continue
        cif_value = float(point["value"])
        rows.append({
            "Mốc theo dõi": f"{horizon} tháng",
            "1 − KM": _format_probability(naive),
            "Xác suất vỡ nợ tích lũy": _format_probability(cif_value),
            "Chênh lệch (1 − KM) − CIF": f"{naive - cif_value:+.2%}",
        })
    if rows:
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    callout(
        "1 − KM xem ZBC 01 như bị kiểm duyệt và có thể đánh giá cao xác suất vỡ nợ. "
        "Default CIF tính ZBC 01 là kết cục cạnh tranh, nên phù hợp hơn để mô tả xác suất "
        "vỡ nợ tích lũy trong bài toán này."
    )


def _variable_label(value: str) -> str:
    return _VARIABLE_LABELS.get(value.strip().lower(), value)


def _unit_label(variable: str) -> str:
    key = variable.strip().lower()
    if key in {"fico", "credit_score"}:
        return "mỗi +1 điểm FICO"
    if "ltv" in key:
        return "mỗi +1 điểm phần trăm LTV"
    if "dti" in key:
        return "mỗi +1 điểm phần trăm DTI"
    if "interest_rate" in key:
        return "mỗi +1 điểm phần trăm lãi suất"
    if "loan_term" in key:
        return "mỗi +1 tháng kỳ hạn"
    if "actual_upb" in key:
        return "theo một đơn vị dư nợ đầu vào"
    if "dq_" in key:
        return "trạng thái chỉ báo 0 → 1"
    return "theo đơn vị biến đầu vào"


def _render_factor_analysis() -> str:
    section_heading(
        3,
        "Những đặc điểm nào liên quan đến vỡ nợ?",
        "Chọn mô hình để xem HR/SHR, khoảng tin cậy và mức bằng chứng thống kê.",
    )
    _render_glossary(["HR", "SHR", "CI", "p-value"])
    model_type = st.selectbox(
        "Chọn phương pháp",
        _FACTOR_MODELS,
        format_func=lambda value: _MODEL_LABELS.get(value, value),
        key="page5_factor_model",
    )
    if model_type == "Cox PH":
        diagnostics = ds.get_model_diagnostics(model_type=model_type)
        ph = diagnostics[
            diagnostics.get("diagnostic_name", pd.Series(index=diagnostics.index, dtype=str))
            .astype(str).str.contains("ph_global", case=False, na=False)
        ] if not diagnostics.empty else pd.DataFrame()
        if not ph.empty and ph.get("interpretation", pd.Series(dtype=str)).astype(str).str.upper().eq("FLAGGED").any():
            st.warning(
                "Cox PH: kiểm định proportional-hazards bị đánh dấu vi phạm. "
                "Không diễn giải HR bên dưới như một tỷ số cố định theo thời gian; hãy đối chiếu với mô hình thay đổi theo thời gian."
            )
    risk_df = ds.get_risk_driver_results(model_type=model_type)
    if risk_df.empty:
        st.info(f"Chưa có hệ số đã công bố cho phương pháp {_MODEL_LABELS[model_type]}.")
        return model_type

    sub = risk_df.copy()
    endpoints = sorted(sub["endpoint"].dropna().unique()) if "endpoint" in sub.columns else []
    if endpoints:
        endpoint = endpoints[0]
        if len(endpoints) > 1:
            endpoint = st.radio(
                "Sự kiện đang xét", endpoints, horizontal=True, key="page5_factor_endpoint"
            )
        sub = sub[sub["endpoint"] == endpoint]

    metric = "SHR" if model_type == "Fine-Gray" else "HR"
    endpoint_key = str(endpoint).strip().upper() if endpoints else "DEFAULT"
    endpoint_label = "ZBC 01 (trả trước/đáo hạn gộp)" if "PREPAY" in endpoint_key else "Default"
    competing_label = "Default" if "PREPAY" in endpoint_key else "ZBC 01 (trả trước/đáo hạn gộp)"
    effect_column = "hr_shr" if "hr_shr" in sub.columns else None
    if effect_column is None or "variable" not in sub.columns:
        st.info("Bảng hệ số chưa có các cột cần hiển thị.")
        return model_type

    plot_df = sub.copy()
    plot_df["variable"] = plot_df["variable"].astype(str).map(_variable_label)
    if model_type == "Fine-Gray":
        method = (
            f"Fine–Gray ước lượng mối liên hệ giữa đặc điểm khoản vay và {endpoint_label}, đồng thời tính đến khả năng khoản vay kết thúc vì {competing_label}. "
            "Phương pháp này phù hợp khi câu hỏi quan tâm đến xác suất tích lũy của một kết cục trong bối cảnh có kết cục cạnh tranh."
        )
        reading = "SHR = 1 là mốc tham chiếu. SHR lớn hơn 1 cho thấy mối liên hệ với tỷ lệ tích lũy cao hơn; nhỏ hơn 1 cho thấy mối liên hệ với tỷ lệ thấp hơn, khi các yếu tố khác được giữ cố định."
        limit = "SHR không phải xác suất hay mức tăng tính bằng điểm phần trăm. SHR = 1,2 không có nghĩa xác suất vỡ nợ tăng 20 điểm phần trăm; kết quả cũng không chứng minh quan hệ nhân quả."
    elif model_type == "Cause-specific Hazard":
        method = (
            f"Mô hình này tập trung vào tốc độ xảy ra {endpoint_label}. Khoản vay kết thúc vì {competing_label} được tính là đã rời khỏi nhóm có thể gặp kết cục đang xét từ thời điểm đó."
        )
        reading = f"HR so sánh tốc độ xảy ra {endpoint_label} giữa các khoản vay còn đang được theo dõi. HR = 1,2 tương ứng tốc độ ước tính cao hơn khoảng 20% so với mốc tham chiếu."
        limit = "HR không phải xác suất khoản vay sẽ gặp kết cục. Đây là mối liên hệ trong dữ liệu, không chứng minh một đặc điểm gây ra kết cục."
    elif model_type == "Time-varying Cox":
        method = (
            f"Mô hình Cox này cho phép một số thông tin khoản vay thay đổi theo tháng khi phân tích {endpoint_label}. "
            "Trong dự án, số dư, lãi suất và tình trạng trễ hạn của tháng trước được dùng để xem xét mối liên hệ với kết cục ở thời điểm sau."
        )
        reading = "HR lớn hơn 1 cho thấy tốc độ xảy ra kết cục cao hơn theo mô hình; nhỏ hơn 1 cho thấy thấp hơn, khi so sánh các hồ sơ tương tự về những yếu tố khác."
        limit = "HR không phải xác suất cá nhân. Thông tin tháng trước cũng có thể không phản ánh đầy đủ tình trạng khoản vay ở tháng hiện tại."
    else:
        method = (
            f"Cox PH so sánh tốc độ xảy ra {endpoint_label} theo các đặc điểm ban đầu của khoản vay. "
            "Mô hình giả định mức chênh lệch giữa các nhóm tương đối ổn định trong suốt thời gian theo dõi."
        )
        reading = "HR = 1 là mốc tham chiếu. HR = 1,2 tương ứng tốc độ ước tính cao hơn khoảng 20%; HR = 0,8 tương ứng thấp hơn khoảng 20%."
        limit = "Nếu kiểm định có cảnh báo, chênh lệch có thể thay đổi theo thời gian nên không nên xem HR là con số cố định. HR không phải xác suất cá nhân và không chứng minh quan hệ nhân quả."
    _method_note(
        f"Phương pháp đang chọn · {_MODEL_LABELS.get(model_type, model_type)} · thước đo {metric}",
        f"Đặc điểm nào có liên hệ với tốc độ xảy ra {endpoint_label}?",
        method,
        reading,
        limit,
    )
    with st.container(border=True):
        st.plotly_chart(forest_plot(plot_df), width="stretch")

    rows = []
    for _, row in sub.iterrows():
        variable = str(row.get("variable", ""))
        try:
            estimate = float(row.get(effect_column))
        except (TypeError, ValueError):
            estimate = float("nan")
        ci_low = pd.to_numeric(pd.Series([row.get("ci_low")]), errors="coerce").iloc[0]
        ci_high = pd.to_numeric(pd.Series([row.get("ci_high")]), errors="coerce").iloc[0]
        p_value = pd.to_numeric(pd.Series([row.get("p_value")]), errors="coerce").iloc[0]
        unit = _unit_label(variable)
        if pd.isna(estimate):
            interpretation = "Chưa có ước lượng hợp lệ."
        else:
            direction = "cao hơn" if estimate > 1 else "thấp hơn" if estimate < 1 else "không đổi"
            interpretation = f"{unit.capitalize()} liên quan với hazard {direction} trong mô hình."
        if pd.notna(p_value) and pd.notna(ci_low) and pd.notna(ci_high):
            evidence = "Có bằng chứng danh nghĩa" if p_value < 0.05 and (ci_low > 1 or ci_high < 1) else "Chưa rõ"
        else:
            evidence = "Thiếu p-value hoặc CI"
        rows.append({
            "Biến": variable,
            metric: f"{estimate:.3f}" if pd.notna(estimate) else "—",
            "Đơn vị diễn giải": unit,
            "Khoảng tin cậy 95%": (
                f"[{ci_low:.3f}; {ci_high:.3f}]" if pd.notna(ci_low) and pd.notna(ci_high) else "—"
            ),
            "Giá trị p": "<0.0001" if pd.notna(p_value) and p_value < 0.0001 else (
                f"{p_value:.4f}" if pd.notna(p_value) else "—"
            ),
            "Bằng chứng": evidence,
            "Diễn giải": interpretation,
        })
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    callout(
        f"{metric} > 1 liên quan với hazard {'phân phối con ' if metric == 'SHR' else ''}cao hơn; "
        f"{metric} < 1 liên quan với mức thấp hơn. Đây là mối liên hệ trong mô hình, không phải quan hệ "
        "nhân quả hay PD riêng của một khoản vay. p < 0,05 là bằng chứng danh nghĩa, chưa điều chỉnh "
        "cho kiểm định nhiều biến."
    )
    return model_type


def _render_diagnostics(model_type: str) -> None:
    section_heading(4, "Kiểm định & chẩn đoán mô hình")
    with st.expander("Xem chi tiết kiểm định mô hình"):
        st.caption(f"Phương pháp đang chọn: {_MODEL_LABELS[model_type]}")
        diagnostics = ds.get_model_diagnostics(model_type=model_type)
        if diagnostics.empty:
            st.info(f"Chưa có kết quả kiểm định cho phương pháp {_MODEL_LABELS[model_type]}.")
            return
        columns = [column for column in [
            "model_version", "diagnostic_name", "metric", "value", "threshold", "interpretation",
        ] if column in diagnostics.columns]
        table = diagnostics[columns].rename(columns={
            "model_version": "Phiên bản mô hình",
            "diagnostic_name": "Kiểm định",
            "metric": "Chỉ số",
            "value": "Giá trị",
            "threshold": "Ngưỡng",
            "interpretation": "Diễn giải",
        })
        st.dataframe(table.reset_index(drop=True), width="stretch", hide_index=True)


def _render_methodology() -> None:
    section_heading(5, "Phương pháp & định nghĩa sự kiện")
    with st.expander("Xem phương pháp và quy ước dữ liệu"):
        st.markdown(
            "- **Mốc thời gian:** origination month được vận hành bằng First Payment Date trừ một tháng; "
            "tháng thanh toán đầu tiên tương ứng tháng phân tích 1.\n"
            "- **Default:** 90+ DPD, mã RA hoặc Zero Balance Code 02/03/09.\n"
            "- **ZBC 01:** mã nguồn gộp trả trước và đáo hạn (prepaid or matured); dữ liệu dự án không tách riêng hai trường hợp, vì vậy không diễn giải là voluntary prepayment thuần túy.\n"
            "- **Censoring termination:** Zero Balance Code 15/16/96; kết thúc quan sát mà chưa ghi nhận Default hoặc mã 01.\n"
            "- **Thứ tự sự kiện:** chọn sự kiện sớm nhất; nếu Default và ZBC 01 cùng tháng, Default được ưu tiên.\n"
            "- **Phạm vi:** vintage 2016–2026; dữ liệu performance đến 31/03/2026. Các mô hình dùng cohort "
            "complete-case theo biến đầu vào tương ứng.\n\n"
            "Default CIF mô tả xác suất vỡ nợ tích lũy khi có rủi ro cạnh tranh; đây không phải tổn thất tín dụng "
            "kỳ vọng (ECL) đầy đủ theo IFRS 9."
        )


def render() -> None:
    inject_page_blocks_css()
    page_kicker(4, "Kết quả mô hình")
    callout(
        "Trang này dẫn từ xác suất vỡ nợ theo thời gian đến cách mô hình hóa yếu tố liên quan, "
            "đồng thời giải thích vai trò của ZBC 01 (trả trước/đáo hạn gộp) như một kết cục cạnh tranh."
    )
    cif, km = _render_default_cif()
    _render_competing_risk_comparison(cif, km, _portfolio_aj())
    factor_model = _render_factor_analysis()
    _render_diagnostics(factor_model)
    _render_methodology()
