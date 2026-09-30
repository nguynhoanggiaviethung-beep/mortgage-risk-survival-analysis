"""Trang 3 — Các đặc điểm khoản vay liên quan đến kết cục theo thời gian."""

import math

import pandas as pd
import streamlit as st

from app.components.charts import forest_plot
from app.components.page_blocks import (
    BLUE,
    GREEN,
    NAVY,
    RED,
    TINT_BLUE,
    TINT_NAVY,
    TINT_RED,
    TINT_GREEN,
    callout,
    inject_page_blocks_css,
    section_heading,
    stat_card,
)
from app.services import data_service as ds


def _is_fine_gray(model_type: str) -> bool:
    normalized = "".join(character for character in model_type.lower() if character.isalnum())
    return "finegray" in normalized


def _effect_measure(model_type: str) -> str:
    return "SHR" if _is_fine_gray(model_type) else "HR"


def _numeric(value):
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _format_value(value, digits: int = 3) -> str:
    number = _numeric(value)
    return f"{number:.{digits}f}" if number is not None else "—"


def _format_p_value(value) -> str:
    number = _numeric(value)
    if number is None:
        return "—"
    return "<0.0001" if number < 0.0001 else f"{number:.4f}"


def _variable_label(variable: str) -> str:
    labels = {
        "fico": "Credit Score (FICO)",
        "original_ltv": "LTV ban đầu",
        "original_dti": "DTI ban đầu",
        "original_interest_rate": "Lãi suất ban đầu",
        "original_loan_term": "Kỳ hạn vay ban đầu",
        "lag_current_actual_upb": "Dư nợ thực tế tháng trước",
        "lag_current_interest_rate": "Lãi suất hiện tại tháng trước",
        "lag_dq_1m": "Trễ hạn 1 tháng (tháng trước)",
        "lag_dq_2m": "Trễ hạn 2 tháng (tháng trước)",
    }
    return labels.get(variable.strip().lower(), variable.replace("_", " "))


def _unit_label(variable: str) -> str:
    """Document model input scale; never infer a categorical reference level."""
    key = variable.strip().lower()
    if key in {"fico", "credit_score"} or "credit_score" in key:
        return "mỗi +1 điểm FICO"
    if "ltv" in key:
        return "mỗi +1 điểm phần trăm LTV"
    if "dti" in key:
        return "mỗi +1 điểm phần trăm DTI"
    if "interest_rate" in key or "current_interest_rate" in key:
        return "mỗi +1 điểm phần trăm lãi suất"
    if "loan_term" in key:
        return "mỗi +1 tháng kỳ hạn"
    if "actual_upb" in key:
        return "mỗi +1 USD dư nợ theo dữ liệu nguồn"
    if "dq_" in key:
        return "trạng thái chỉ báo 0 → 1"
    return "mỗi +1 đơn vị theo scale đầu vào"


def _interpretation_line(row, metric_label: str, model_type: str) -> str:
    measure = _numeric(row.get("hr_shr"))
    raw_variable = str(row.get("variable", "Biến"))
    variable = _variable_label(raw_variable)
    endpoint = str(row.get("endpoint", "Default"))
    unit = _unit_label(raw_variable)
    if measure is None:
        return f"{variable}: chưa có ước lượng hợp lệ để diễn giải."
    if measure > 1:
        relation = "liên quan với mức cao hơn"
    elif measure < 1:
        relation = "liên quan với mức thấp hơn"
    else:
        relation = "không cho thấy thay đổi tương đối"
    if metric_label == "SHR":
        outcome = f"subdistribution hazard của {endpoint}"
    else:
        outcome = f"cause-specific hazard của {endpoint}"
    return f"{variable}: {unit} {relation} của {outcome} trong mô hình."


def _statistical_evidence(row) -> str:
    p_value = _numeric(row.get("p_value"))
    ci_low = _numeric(row.get("ci_low"))
    ci_high = _numeric(row.get("ci_high"))
    if p_value is None or ci_low is None or ci_high is None:
        return "Chưa đủ thông tin"
    ci_excludes_one = ci_low > 1 or ci_high < 1
    p_below_threshold = p_value < 0.05
    if p_below_threshold and ci_excludes_one:
        return "Có bằng chứng danh nghĩa (p < 0,05)"
    if not p_below_threshold and not ci_excludes_one:
        return "Chưa đủ bằng chứng (CI chứa 1)"
    return "p-value và CI cần đối chiếu"


def _has_nominal_evidence(row) -> bool:
    p_value = _numeric(row.get("p_value"))
    ci_low = _numeric(row.get("ci_low"))
    ci_high = _numeric(row.get("ci_high"))
    return (
        p_value is not None
        and p_value < 0.05
        and ci_low is not None
        and ci_high is not None
        and (ci_low > 1 or ci_high < 1)
    )


def _model_explanation(model_type: str, endpoint: str) -> str:
    metric_label = _effect_measure(model_type)
    if metric_label == "SHR":
        return (
            f"**Fine–Gray · SHR.** SHR > 1 cho biết mỗi đơn vị tăng của biến liên quan "
            f"với subdistribution hazard cao hơn của {endpoint}; SHR < 1 cho biết mức thấp hơn. "
            "Mô hình xét Voluntary Prepayment là rủi ro cạnh tranh. SHR không phải xác suất "
            "Default riêng của một khoản vay."
        )
    if "cause-specific" in model_type.lower():
        return (
            f"**Cause-specific Cox · HR.** HR > 1 cho biết mỗi đơn vị tăng của biến liên quan "
            f"với cause-specific hazard cao hơn của {endpoint}; HR < 1 cho biết mức thấp hơn. "
            "Sự kiện cạnh tranh được censor tại thời điểm nó xảy ra."
        )
    if "time-varying" in model_type.lower():
        return (
            f"**Time-varying Cox · HR.** HR mô tả mối liên hệ với hazard của {endpoint}; "
            "các giá trị monthly predictor được lấy trễ để không dùng dữ liệu trong chính tháng event "
            "làm dự báo cho event đó."
        )
    return (
        f"**Cox PH · HR.** HR > 1 cho biết mỗi đơn vị tăng của biến liên quan với "
        f"cause-specific hazard cao hơn của {endpoint}; HR < 1 cho biết mức thấp hơn."
    )


def render() -> None:
    inject_page_blocks_css()
    st.caption("TRANG 3 · YẾU TỐ RỦI RO")

    risk_df = ds.get_risk_driver_results()
    if risk_df.empty:
        st.warning(
            "Chưa có kết quả hệ số mô hình đã publish. Trang này cần risk_driver_results."
        )
        return

    section_heading(
        1,
        "Chọn kết quả cần xem",
        "Chọn mô hình và kết cục để xem các yếu tố liên quan trong ước lượng.",
    )
    with st.container(border=True):
        c1, c2, c3 = st.columns([1.15, 0.9, 1.2])
        model_options = sorted(risk_df["model_type"].dropna().unique())
        with c1:
            model_type = st.selectbox("Mô hình", model_options)
    endpoints = sorted(
        risk_df.loc[
            risk_df["model_type"] == model_type, "endpoint"
        ].dropna().unique()
    )
    if not endpoints:
        st.info("Mô hình này chưa có kết cục để hiển thị.")
        return
    with c2:
        endpoint = st.selectbox("Kết cục", endpoints)
    versions = sorted(
        risk_df.loc[
            (risk_df["model_type"] == model_type)
            & (risk_df["endpoint"] == endpoint),
            "model_version",
        ].dropna().unique()
    )
    with c3:
        model_version = st.selectbox("Phiên bản mô hình", versions) if versions else None

    sub = risk_df[
        (risk_df["model_type"] == model_type)
        & (risk_df["endpoint"] == endpoint)
        & ((risk_df["model_version"] == model_version) if model_version else True)
    ].copy()
    if sub.empty:
        st.info("Không có hệ số khớp với lựa chọn hiện tại.")
        return

    metric_label = _effect_measure(model_type)
    section_heading(
        2,
        "Tóm tắt kết quả",
        f"{model_type} · {endpoint} · thước đo {metric_label}",
    )
    explanation = _model_explanation(model_type, endpoint)
    callout(explanation)

    valid_effects = sub[sub["hr_shr"].map(lambda value: (_numeric(value) or 0) > 0)].copy()
    nominal_count = int(sub.apply(_has_nominal_evidence, axis=1).sum())
    above_one = int(valid_effects["hr_shr"].map(lambda value: _numeric(value) > 1).sum())
    strongest_name = "—"
    strongest_value = "Chưa có ước lượng hợp lệ"
    if not valid_effects.empty:
        strongest_idx = valid_effects["hr_shr"].map(
            lambda value: abs(math.log(_numeric(value)))
        ).idxmax()
        strongest_row = valid_effects.loc[strongest_idx]
        strongest_name = _variable_label(str(strongest_row["variable"]))
        strongest_value = f"{metric_label} {_format_value(strongest_row['hr_shr'])}"

    card1, card2, card3 = st.columns(3)
    with card1:
        stat_card(
            "Đặc điểm được ước lượng",
            str(len(sub)),
            "Số hệ số có trong kết quả mô hình đang chọn.",
            NAVY,
            TINT_NAVY,
        )
    with card2:
        stat_card(
            "Bằng chứng thống kê danh nghĩa",
            f"{nominal_count}/{len(sub)}",
            "p < 0,05 và khoảng tin cậy 95% không chứa 1.",
            RED if endpoint.lower() == "default" else BLUE,
            TINT_RED if endpoint.lower() == "default" else TINT_BLUE,
        )
    with card3:
        stat_card(
            f"{metric_label} lớn nhất theo khoảng cách tới 1",
            strongest_value,
            f"{strongest_name} · chỉ là liên hệ trong mô hình, không phải tác động nhân quả.",
            GREEN,
            TINT_GREEN,
        )

    st.caption(
        f"Có {above_one} hệ số {metric_label} lớn hơn 1. Diễn giải phụ thuộc đơn vị của từng biến; "
        "không dùng riêng HR/SHR để dự báo PD cho một khoản vay."
    )

    section_heading(
        3,
        f"Các yếu tố liên quan đến {endpoint}",
        f"Điểm ước lượng {metric_label} và khoảng tin cậy 95%; đường dọc tại 1 là mốc không thay đổi tương đối.",
    )
    plot_data = sub.copy()
    plot_data["variable"] = plot_data["variable"].map(_variable_label)
    with st.container(border=True):
        st.plotly_chart(forest_plot(plot_data), width="stretch")

    section_heading(
        4,
        "Bảng hệ số chi tiết",
        "Mỗi dòng trình bày ước lượng, độ bất định và cách đọc theo đơn vị biến.",
    )
    table = sub.copy()
    table["Đặc điểm"] = table["variable"].map(_variable_label)
    table["Đơn vị diễn giải"] = table["variable"].map(_unit_label)
    table[metric_label] = table["hr_shr"].map(_format_value)
    table["CI 95%"] = table.apply(
        lambda row: (
            f"[{_format_value(row['ci_low'])}, {_format_value(row['ci_high'])}]"
            if _numeric(row.get("ci_low")) is not None
            and _numeric(row.get("ci_high")) is not None
            else "—"
        ),
        axis=1,
    )
    table["p-value"] = table["p_value"].map(_format_p_value)
    table["Bằng chứng thống kê"] = table.apply(_statistical_evidence, axis=1)
    table["Diễn giải"] = table.apply(
        lambda row: _interpretation_line(row, metric_label, model_type),
        axis=1,
    )
    display_cols = [
        "Đặc điểm",
        metric_label,
        "Đơn vị diễn giải",
        "CI 95%",
        "p-value",
        "Bằng chứng thống kê",
        "Diễn giải",
    ]
    st.dataframe(
        table[display_cols].reset_index(drop=True),
        width="stretch",
        hide_index=True,
    )
    section_heading(5, "Cách diễn giải và giới hạn")
    callout(
        "Ngưỡng p < 0,05 là bằng chứng danh nghĩa và chưa hiệu chỉnh cho việc kiểm định nhiều biến. "
        "HR/SHR mô tả mối liên hệ có điều kiện trong mô hình; chúng không chứng minh quan hệ nhân quả "
        "và không phải PD riêng của một khoản vay. Đơn vị là scale dữ liệu đầu vào: FICO theo điểm, "
        "LTV/DTI/lãi suất theo điểm phần trăm, kỳ hạn theo tháng; biến chỉ báo được so sánh từ 0 sang 1."
    )
