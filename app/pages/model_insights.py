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
    "PD(t)": "Xác suất đã vỡ nợ tích lũy đến thời điểm t.",
    "CIF": "Xác suất một kết cục đã xảy ra đến thời điểm t, có tính đến sự kiện cạnh tranh.",
    "KM": "Kaplan–Meier: ước lượng xác suất chưa gặp sự kiện theo thời gian.",
    "1 − KM": "Xác suất có sự kiện theo Kaplan–Meier khi sự kiện cạnh tranh được kiểm duyệt.",
    "HR": "Tỷ số hazard tức thời. HR = 1 là mốc tham chiếu; HR > 1 hoặc < 1 biểu thị hazard cao hơn hoặc thấp hơn.",
    "SHR": "Tỷ số subdistribution hazard trong Fine–Gray, có xét sự kiện cạnh tranh.",
    "CI": "Khoảng tin cậy 95%. Nếu khoảng chứa 1 thì chưa có bằng chứng rõ về liên hệ khác 1.",
    "p-value": "Mức bằng chứng thống kê; p < 0,05 thường được xem là có ý nghĩa danh nghĩa.",
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


def _main_horizon_rows(cif: pd.DataFrame, km: pd.DataFrame | None = None) -> pd.DataFrame:
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
    return keep.sort_values("horizon").drop_duplicates("horizon")


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


def _render_default_cif() -> tuple[pd.DataFrame, pd.DataFrame]:
    section_heading(
        1,
        "Vỡ nợ tăng như thế nào theo thời gian?",
        "Default CIF / PD(t) ước lượng xác suất vỡ nợ tích lũy và tính đến trả trước hạn như sự kiện cạnh tranh.",
    )
    cif = _portfolio_cif()
    km = _portfolio_km()
    aj = _portfolio_aj()
    if cif.empty:
        st.info("Chưa có kết quả xác suất vỡ nợ (pd_results) đã công bố.")
        return cif, km

    horizons = _main_horizon_rows(cif)
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
    chart_data = aj.copy()
    if not chart_data.empty:
        with st.container(border=True):
            st.plotly_chart(cif_chart(chart_data), width="stretch")
    st.caption(
        "Ví dụ cách đọc: Default CIF tại 36 tháng là tỷ lệ tích lũy khoản vay đã vỡ nợ đến tháng 36 "
        "trong nhóm nghiên cứu; đây không phải xác suất vỡ nợ cá nhân hay ECL theo IFRS 9."
    )
    return cif, km


def _render_competing_risk_comparison(cif: pd.DataFrame, km: pd.DataFrame) -> None:
    section_heading(
        2,
        "Tại sao không dùng 1 − KM?",
        "So sánh ước lượng Kaplan–Meier với Default CIF khi trả trước hạn là sự kiện cạnh tranh.",
    )
    if cif.empty or km.empty:
        st.info("Cần cả survival_results và pd_results để so sánh.")
        return
    horizons = _main_horizon_rows(cif, km)
    if horizons.empty:
        st.info("Chưa có mốc chính đủ thời gian theo dõi để so sánh, không ngoại suy kết quả.")
        return

    last_horizon = int(horizons["horizon"].max())
    km_display = km[pd.to_numeric(km["analysis_time"], errors="coerce") <= last_horizon].copy()
    cif_display = _portfolio_aj()
    cif_display = cif_display[
        (cif_display["endpoint"].astype(str).str.upper() == "DEFAULT")
        & (pd.to_numeric(cif_display["analysis_time"], errors="coerce") <= last_horizon)
    ].copy()
    _render_glossary(["KM", "1 − KM", "CIF"])
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
        cif_value = float(row["cif_default"])
        rows.append({
            "Mốc theo dõi": f"{horizon} tháng",
            "1 − KM": _format_probability(naive),
            "Xác suất vỡ nợ tích lũy": _format_probability(cif_value),
            "Chênh lệch (1 − KM) − CIF": f"{naive - cif_value:+.2%}",
        })
    if rows:
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    callout(
        "1 − KM xem khoản trả trước hạn như bị kiểm duyệt và có thể đánh giá cao xác suất vỡ nợ. "
        "Default CIF tính trả trước hạn là một kết cục cạnh tranh, nên phù hợp hơn để mô tả xác suất "
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
    effect_column = "hr_shr" if "hr_shr" in sub.columns else None
    if effect_column is None or "variable" not in sub.columns:
        st.info("Bảng hệ số chưa có các cột cần hiển thị.")
        return model_type

    plot_df = sub.copy()
    plot_df["variable"] = plot_df["variable"].astype(str).map(_variable_label)
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
            "- **Voluntary Prepayment:** Zero Balance Code 01 theo quy ước event của project. Freddie Mac gộp prepaid/matured trong mã nguồn này, nên project không tách riêng maturity.\n"
            "- **Censoring termination:** Zero Balance Code 15/16/96; kết thúc quan sát mà chưa ghi nhận Default hoặc mã 01.\n"
            "- **Thứ tự sự kiện:** chọn sự kiện sớm nhất; nếu vỡ nợ và trả trước hạn cùng tháng, vỡ nợ được ưu tiên.\n"
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
        "đồng thời giải thích vai trò của trả trước hạn như một rủi ro cạnh tranh."
    )
    cif, km = _render_default_cif()
    _render_competing_risk_comparison(cif, km)
    factor_model = _render_factor_analysis()
    _render_diagnostics(factor_model)
    _render_methodology()
