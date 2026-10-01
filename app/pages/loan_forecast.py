"""Dự báo CIF hồ sơ mới cho Default và kết cục ZBC 01 gộp."""

from __future__ import annotations

import math

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.components.page_blocks import (
    BLUE,
    GREEN,
    NAVY,
    RED,
    TINT_BLUE,
    TINT_GREEN,
    TINT_RED,
    callout,
    inject_page_blocks_css,
    section_heading,
    stat_card,
    page_kicker,
)
from app.services.forecast_service import (
    FORECAST_HORIZONS,
    ForecastError,
    load_forecast_bundle,
    predict_profile,
)


FIELDS = {
    "fico": ("Điểm FICO", "Ví dụ: 700"),
    "ltv": ("LTV ban đầu (%)", "Ví dụ: 80"),
    "dti": ("DTI ban đầu (%)", "Ví dụ: 35"),
    "rate": ("Lãi suất ban đầu (%)", "Ví dụ: 6.5"),
    "term": ("Kỳ hạn ban đầu (tháng)", "Ví dụ: 360"),
}


def _parse_profile(raw: dict[str, str]) -> tuple[dict[str, float] | None, list[str]]:
    values: dict[str, float] = {}
    errors: list[str] = []
    for key, (label, _) in FIELDS.items():
        text = raw.get(key, "").strip().replace(",", ".")
        if not text:
            errors.append(f"{label}: vui lòng nhập giá trị.")
            continue
        try:
            number = float(text)
        except ValueError:
            errors.append(f"{label}: cần nhập một số hợp lệ.")
            continue
        if not math.isfinite(number):
            errors.append(f"{label}: giá trị phải hữu hạn.")
            continue
        values[key] = number

    checks = {
        "fico": (300, 850, "Điểm FICO phải nằm trong khoảng 300–850."),
        "ltv": (0, 998, "LTV phải lớn hơn 0% và nhỏ hơn 998%."),
        "dti": (0, 65, "DTI phải nằm trong khoảng 0–65%."),
        "rate": (0, 30, "Lãi suất phải lớn hơn 0% và không vượt quá 30%."),
        "term": (1, 600, "Kỳ hạn phải là số tháng dương, không vượt quá 600."),
    }
    for key, (low, high, message) in checks.items():
        value = values.get(key)
        if value is not None and not low <= value <= high:
            errors.append(message)
    if "fico" in values and not values["fico"].is_integer():
        errors.append("Điểm FICO phải là số nguyên.")
    if "term" in values and not values["term"].is_integer():
        errors.append("Kỳ hạn phải là số tháng nguyên.")
    if "term" in values and 0 < values["term"] < min(FORECAST_HORIZONS):
        errors.append("Kỳ hạn phải ít nhất 12 tháng để có mốc dự báo đã kiểm định.")
    return (None if errors else values), errors


def _render_profile_form() -> dict[str, float] | None:
    section_heading(
        1,
        "Thông tin khoản vay",
        "Nhập các đặc điểm tại thời điểm cấp khoản vay. Vintage không phải đầu vào của mô hình cá nhân; vintage được dùng làm nhóm thời gian trong nghiên cứu.",
    )
    with st.form("new_loan_forecast_form", clear_on_submit=False):
        c1, c2, c3 = st.columns(3)
        columns = [c1, c2, c3, c1, c2]
        raw: dict[str, str] = {}
        for key, column in zip(FIELDS, columns, strict=True):
            label, hint = FIELDS[key]
            with column:
                raw[key] = st.text_input(
                    label,
                    key=f"forecast_input_{key}",
                    placeholder=hint,
                    help=hint,
                )
        submitted = st.form_submit_button("Tính dự báo", type="primary", width="stretch")

    if submitted:
        st.session_state.pop("new_loan_forecast_profile", None)
        profile, errors = _parse_profile(raw)
        if errors:
            for error in errors:
                st.error(error)
        else:
            st.session_state["new_loan_forecast_profile"] = profile
    return st.session_state.get("new_loan_forecast_profile")


def _format_profile(profile: dict[str, float]) -> pd.DataFrame:
    values = [
        ("Điểm FICO", f"{profile['fico']:.0f}"),
        ("LTV ban đầu", f"{profile['ltv']:g}%"),
        ("DTI ban đầu", f"{profile['dti']:g}%"),
        ("Lãi suất ban đầu", f"{profile['rate']:g}%"),
        ("Kỳ hạn ban đầu", f"{profile['term']:.0f} tháng"),
    ]
    return pd.DataFrame(values, columns=["Đặc điểm hồ sơ", "Giá trị nhập"])


def _render_results(profile: dict[str, float] | None) -> None:
    section_heading(
        2,
        "Kết quả dự báo",
        "Xác suất tích lũy đến mốc thời gian; ZBC 01 (trả trước/đáo hạn gộp) là sự kiện cạnh tranh với vỡ nợ.",
    )
    if not profile:
        st.info("Nhập đủ 5 đặc điểm bên trái rồi chọn **Tính dự báo** để xem kết quả.")
        return

    try:
        with st.spinner("Đang nạp dữ liệu, huấn luyện và kiểm định mô hình lần đầu… Việc này có thể mất vài phút."):
            bundle = load_forecast_bundle()
            result = predict_profile(bundle, profile)
    except ForecastError as exc:
        st.error(f"Chưa thể tính dự báo: {exc}")
        return
    except Exception as exc:  # Keep deployment/data failures visible, never substitute a fake score.
        st.error(f"Không thể khởi tạo bộ dự báo ({type(exc).__name__}): {exc}")
        return

    if result["outside"]:
        st.warning(
            "Một số giá trị nằm ngoài phạm vi quan sát trong dữ liệu huấn luyện. Mô hình vẫn tính được, "
            "nhưng đây là ngoại suy nên độ tin cậy thấp hơn: " + "; ".join(result["outside"])
        )

    estimates = result["estimates"]
    colors = [(RED, TINT_RED), (GREEN, TINT_GREEN), (BLUE, TINT_BLUE)]
    cards = st.columns(len(estimates))
    for column, horizon, (color, tint) in zip(cards, result["horizons"], colors, strict=False):
        estimate = estimates[horizon]
        with column:
            stat_card(
                f"Default CIF · {horizon} tháng",
                f"{float(estimate['default_cif'][0]):.2%}",
                "Xác suất tích lũy vỡ nợ, có tính ZBC 01 cạnh tranh",
                color,
                tint,
            )

    curves = result["curves"]
    figure = go.Figure()
    series = [
        ("Xác suất vỡ nợ tích lũy", curves["default_cif"] * 100, RED),
        ("Xác suất kết thúc bằng ZBC 01 (trả trước/đáo hạn gộp)", curves["prepay_cif"] * 100, GREEN),
        ("Chưa gặp hai sự kiện", curves["survival"] * 100, NAVY),
    ]
    for label, values, color in series:
        figure.add_trace(go.Scatter(
            x=curves["months"],
            y=values,
            mode="lines",
            name=label,
            line={"color": color, "width": 2.5, "shape": "hv"},
            hovertemplate="Tháng %{x:.0f}<br>%{y:.2f}%<extra>%{fullData.name}</extra>",
        ))
    figure.update_layout(
        height=380,
        margin={"l": 20, "r": 20, "t": 20, "b": 20},
        paper_bgcolor="#FFFEFA",
        plot_bgcolor="#FFFEFA",
        font={"family": "Lora, Georgia, serif", "color": NAVY},
        legend={"orientation": "h", "y": 1.12, "x": 0},
        hovermode="x unified",
    )
    figure.update_xaxes(title="Thời gian kể từ khi cấp khoản vay (tháng)", range=[0, max(curves["months"])], showgrid=False)
    figure.update_yaxes(title="Xác suất tích lũy (%)", range=[0, 100], ticksuffix="%", gridcolor="#E8E4D9")
    st.plotly_chart(figure, width="stretch")
    st.caption(
        "Tại mỗi mốc: Default CIF + CIF ZBC 01 (trả trước/đáo hạn gộp) + xác suất chưa gặp hai sự kiện = 100%. "
        "Các mốc hiển thị bị giới hạn bởi kỳ hạn đã nhập và phạm vi mô hình hỗ trợ."
    )

    rows = []
    for horizon in result["horizons"]:
        estimate = estimates[horizon]
        rows.append({
            "Mốc dự báo": f"{horizon} tháng",
            "Vỡ nợ tích lũy": f"{float(estimate['default_cif'][0]):.2%}",
            "ZBC 01 (trả trước/đáo hạn gộp)": f"{float(estimate['prepay_cif'][0]):.2%}",
            "Chưa gặp sự kiện": f"{float(estimate['survival'][0]):.2%}",
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

    with st.expander("Hồ sơ và kiểm tra độ tin cậy", expanded=False):
        st.markdown("**Đặc điểm đã nhập**")
        st.dataframe(_format_profile(profile), hide_index=True, width="stretch")
        st.markdown("**Kiểm định theo thời gian trên vintage 2021**")
        validation = bundle.validation_summary.rename(columns={
            "Horizon (tháng)": "Mốc (tháng)",
            "Số hồ sơ kiểm định": "Số hồ sơ đủ theo dõi",
            "Default quan sát": "Số Default quan sát",
            "Trả trước quan sát": "Số kết cục ZBC 01 quan sát",
            "Brier đa lớp (thấp tốt hơn)": "Brier đa lớp · thấp tốt hơn",
            "Log-loss (thấp tốt hơn)": "Log-loss · thấp tốt hơn",
            "CIF Default dự báo TB": "Default dự báo trung bình",
            "Default quan sát TB": "Default quan sát trung bình",
        }).copy()
        for col in ("Default dự báo trung bình", "Default quan sát trung bình"):
            validation[col] = validation[col].map(lambda value: f"{float(value):.2%}")
        for col in ("Brier đa lớp · thấp tốt hơn", "Log-loss · thấp tốt hơn"):
            validation[col] = validation[col].map(lambda value: f"{float(value):.4f}")
        st.dataframe(validation, hide_index=True, width="stretch")
        st.caption(
            f"Huấn luyện đánh giá ngoài thời gian: vintage đến {2020}; kiểm định trên vintage 2021 "
            f"({bundle.n_validation:,} hồ sơ gốc; tập huấn luyện {bundle.n_train:,} hồ sơ). "
            "Chỉ số tính trên hồ sơ có kết cục quan sát được đến mốc; chưa hiệu chỉnh trọng số kiểm duyệt, "
            "chưa phải kiểm định độc lập bên ngoài và không phải khoảng tin cậy cho cá nhân."
        )
        if bundle.default_convergence != "PASS" or bundle.prepayment_convergence != "PASS":
            st.warning(
                "Ít nhất một mô hình ghi nhận cảnh báo hội tụ. Hãy xem xét kết quả thận trọng và kiểm tra log mô hình."
            )


def render() -> None:
    inject_page_blocks_css()
    page_kicker(6, "Dự báo khoản vay mới")
    callout(
        "Dự báo hai kết cục cạnh tranh cho hồ sơ có đặc điểm ban đầu: Default theo định nghĩa nghiên cứu "
        "(90+ DPD/RA hoặc ZBC 02/03/09) và kết cục ZBC 01 (trả trước/đáo hạn gộp). Đây không phải dự báo quá hạn 30+ DPD."
    )
    left, right = st.columns([0.92, 1.35], gap="large")
    with left:
        profile = _render_profile_form()
        st.caption("Mô hình dùng FICO, LTV, DTI, lãi suất và kỳ hạn ban đầu. Không nhập dữ liệu định danh cá nhân.")
    with right:
        _render_results(profile)
    with st.expander("Cách tính và giới hạn diễn giải", expanded=False):
        st.markdown(
            "Dự báo sử dụng hai mô hình Cox cause-specific đã khóa cho Default và ZBC 01 (trả trước/đáo hạn gộp). "
            "Từ hazard cơ sở và điểm rủi ro của năm biến đầu vào, hệ thống tích lũy CIF theo tháng bằng "
            "xấp xỉ hazard piecewise-exponential; hai CIF cộng với xác suất chưa gặp sự kiện bằng 1. "
            "Mốc hiển thị là 12, 24 và 36 tháng, giới hạn theo kỳ hạn khoản vay. "
            "Ước lượng là xác suất theo mô hình của quần thể nghiên cứu, không phải bảo đảm kết cục cá nhân, "
            "khuyến nghị phê duyệt hay xác suất đã hiệu chuẩn cho mọi nhóm khách hàng."
        )
