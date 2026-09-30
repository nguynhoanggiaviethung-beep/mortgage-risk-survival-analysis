"""Trang 4 — Tra cứu và khám phá hồ sơ khoản vay."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.components.charts import loan_timeline_chart
from app.components.page_blocks import (
    BLUE,
    GREEN,
    NAVY,
    RED,
    TINT_BLUE,
    TINT_GRAY,
    TINT_GREEN,
    TINT_NAVY,
    TINT_RED,
    callout,
    inject_page_blocks_css,
    section_heading,
    stat_card,
)
from app.services import data_service as ds


_EVENT_LABELS = {
    "DEFAULT": "Vỡ nợ",
    "PREPAYMENT": "Trả trước hạn",
    "VOLUNTARY_PREPAYMENT": "Trả trước hạn",
    "CENSOR": "Kết thúc theo dõi",
    "CENSORED": "Kết thúc theo dõi",
}


def _credit_score_band(score: float) -> str:
    if score < 650:
        return "<650"
    if score < 700:
        return "650–699"
    if score < 750:
        return "700–749"
    return "750+"


def _delinquency_label(value) -> str:
    """Translate Freddie/MBA status codes while preserving the source code."""
    if value is None or pd.isna(value):
        return "Không có dữ liệu quá hạn"
    code = str(value).strip().upper()
    if code in {"", "XX", "NAN", "NONE"}:
        return "Không có dữ liệu quá hạn"
    if code == "RA":
        return "RA · trạng thái đặc biệt"
    try:
        number = int(float(code))
    except (TypeError, ValueError, OverflowError):
        return f"{code} · mã trạng thái gốc"
    if number <= 0:
        return f"{code.zfill(2)} · hiện tại"
    if number == 1:
        return f"{code.zfill(2)} · trễ 30 ngày"
    if number == 2:
        return f"{code.zfill(2)} · trễ 60 ngày"
    return f"{code.zfill(2)} · trễ từ 90 ngày trở lên"


def _event_label(profile_event, timeline_event) -> tuple[str, str, str]:
    """Use the loan-level final event as authority; fall back to the terminal row."""
    value = profile_event
    if value is None or pd.isna(value) or str(value).strip() == "":
        value = timeline_event
    normalized = str(value).strip().upper() if value is not None else ""
    if normalized == "DEFAULT":
        return "Vỡ nợ", "bad", "Khoản vay ghi nhận Default tại tháng kết thúc theo dõi."
    if normalized in {"PREPAYMENT", "VOLUNTARY_PREPAYMENT"}:
        return "Đã trả trước", "warn", "Khoản vay ghi nhận Voluntary Prepayment tại tháng kết thúc theo dõi."
    if normalized in {"CENSOR", "CENSORED", "RIGHT_CENSOR"}:
        return (
            "Kết thúc theo dõi",
            "neutral",
            "Không ghi nhận Default hoặc Voluntary Prepayment trong thời gian quan sát. "
            "Trạng thái này không xác nhận khoản vay vẫn còn active hiện nay.",
        )
    return "Chưa xác định", "neutral", "Không có event type hợp lệ để xác nhận trạng thái."


def _set_example_loan(loan_id: str) -> None:
    # Do not mutate the text-input key here: the widget is already instantiated
    # earlier in this page run, so Streamlit raises WidgetAlreadyInstantiatedError.
    st.session_state["active_loan_id"] = loan_id


def _catalog_label(row) -> str:
    event = _EVENT_LABELS.get(str(row.get("event_type", "")).upper(), "Chưa xác định")
    fico = row.get("fico")
    fico_text = f"FICO {int(fico)}" if pd.notna(fico) else "Chưa có FICO"
    return f"{row['loan_id']} · {int(row['origination_vintage'])} · {event} · {fico_text}"


def _render_search_and_catalog() -> None:
    catalog = ds.get_loan_catalog()
    section_heading(
        1,
        "Chọn khoản vay để tra cứu",
        "Nhập Loan ID hoặc chọn một hồ sơ mẫu trong danh mục bên dưới.",
    )

    sample_rows = pd.DataFrame()
    if not catalog.empty and "event_type" in catalog.columns:
        wanted_events = ["DEFAULT", "PREPAYMENT", "CENSOR"]
        sample_rows = pd.concat(
            [
                catalog[catalog["event_type"].astype(str).str.upper() == event].head(1)
                for event in wanted_events
            ],
            ignore_index=True,
        ).drop_duplicates("loan_id")

    if not sample_rows.empty:
        st.caption("Gợi ý tra cứu nhanh · mỗi nút mở một hồ sơ đại diện theo kết cục")
        sample_cols = st.columns(len(sample_rows))
        for col, (_, row) in zip(sample_cols, sample_rows.iterrows()):
            event = str(row["event_type"]).upper()
            color, tint = {
                "DEFAULT": (RED, TINT_RED),
                "PREPAYMENT": (BLUE, TINT_BLUE),
                "CENSOR": (NAVY, TINT_NAVY),
            }.get(event, (NAVY, TINT_GRAY))
            label = _EVENT_LABELS.get(event, event)
            with col:
                stat_card(
                    label,
                    str(row["loan_id"]),
                    f"Vintage {int(row['origination_vintage'])} · "
                    f"FICO {int(row['fico']) if pd.notna(row.get('fico')) else '—'}",
                    color,
                    tint,
                )
                st.button(
                    f"Mở hồ sơ {label.lower()}",
                    key=f"sample_loan_{event}",
                    on_click=_set_example_loan,
                    args=(str(row["loan_id"]),),
                    use_container_width=True,
                )

    with st.container(border=True):
        with st.form("loan_id_search_form"):
            col_input, col_action = st.columns([4, 1])
            with col_input:
                typed_id = st.text_input(
                    "Loan ID",
                    placeholder="Nhập Loan Sequence Number, ví dụ: F16Q10001234",
                    key="loan_lookup_id",
                )
            with col_action:
                st.markdown("<div style='height:1.75rem'></div>", unsafe_allow_html=True)
                submitted = st.form_submit_button(
                    "Tra cứu hồ sơ",
                    type="primary",
                    use_container_width=True,
                )
        if submitted:
            st.session_state["active_loan_id"] = typed_id.strip().upper()

    section_heading(
        2,
        "Danh mục khoản vay mẫu",
        "Bảng gợi ý gồm các hồ sơ có thể mở timeline; bộ dữ liệu gốc vẫn chứa toàn bộ khoản vay.",
    )
    if catalog.empty:
        st.info("Không đọc được danh mục gợi ý. Bạn vẫn có thể nhập Loan ID ở ô tra cứu phía trên.")
        return

    filter_vintage, filter_event = st.columns([1, 1])
    vintages = ["Tất cả"] + sorted(catalog["origination_vintage"].dropna().astype(int).unique().tolist())
    events = ["Tất cả"] + sorted(catalog["event_type"].dropna().astype(str).str.upper().unique().tolist())
    with filter_vintage:
        selected_vintage = st.selectbox("Năm giải ngân", vintages, key="catalog_vintage")
    with filter_event:
        selected_event = st.selectbox(
            "Kết cục trong dữ liệu",
            events,
            format_func=lambda value: "Tất cả kết cục" if value == "Tất cả" else _EVENT_LABELS.get(value, value),
            key="catalog_event",
        )

    visible = catalog.copy()
    if selected_vintage != "Tất cả":
        visible = visible[visible["origination_vintage"].astype(int) == selected_vintage]
    if selected_event != "Tất cả":
        visible = visible[visible["event_type"].astype(str).str.upper() == selected_event]
    display = visible.rename(
        columns={
            "loan_id": "Loan ID",
            "origination_vintage": "Vintage",
            "event_type": "Kết cục",
            "fico": "FICO",
            "original_ltv": "LTV (%)",
            "original_dti": "DTI (%)",
            "original_loan_term": "Kỳ hạn (tháng)",
            "duration_months": "Thời gian quan sát (tháng)",
        }
    ).copy()
    if "Kết cục" in display:
        display["Kết cục"] = display["Kết cục"].map(
            lambda value: _EVENT_LABELS.get(str(value).upper(), str(value))
        )
    show_columns = [
        name for name in [
            "Loan ID", "Vintage", "Kết cục", "FICO", "LTV (%)", "DTI (%)",
            "Kỳ hạn (tháng)", "Thời gian quan sát (tháng)",
        ] if name in display.columns
    ]
    st.dataframe(
        display[show_columns].reset_index(drop=True),
        hide_index=True,
        width="stretch",
        height=300,
    )

    if not visible.empty:
        by_id = visible.set_index("loan_id", drop=False)
        options = visible["loan_id"].astype(str).tolist()
        with st.form("sample_catalog_selection"):
            chosen_id = st.selectbox(
                "Chọn mã trong bảng để mở hồ sơ",
                options,
                format_func=lambda loan_id: _catalog_label(by_id.loc[loan_id]),
                key="catalog_loan_choice",
            )
            open_sample = st.form_submit_button("Mở hồ sơ đã chọn", type="primary")
        if open_sample:
            _set_example_loan(str(chosen_id))


def _render_loan_profile(loan_id: str) -> None:
    profile = ds.get_loan_profile(loan_id=loan_id)
    if profile.empty:
        st.error(f"Không tìm thấy Loan ID '{loan_id}' trong dữ liệu khoản vay.")
        return

    timeline = ds.get_loan_timeline(loan_id=loan_id)
    p = profile.iloc[0]
    ordered_timeline = (
        timeline.sort_values("analysis_time_month")
        if not timeline.empty and "analysis_time_month" in timeline.columns
        else timeline
    )
    last_row = ordered_timeline.iloc[-1] if not ordered_timeline.empty else None
    loan_age = (
        int(last_row["analysis_time_month"])
        if last_row is not None and pd.notna(last_row.get("analysis_time_month"))
        else None
    )

    timeline_event = last_row.get("event_type") if last_row is not None else None
    label, kind, explanation = _event_label(p.get("event_type"), timeline_event)
    color, tint = {
        "bad": (RED, TINT_RED),
        "warn": (BLUE, TINT_BLUE),
        "neutral": (NAVY, TINT_NAVY),
    }.get(kind, (NAVY, TINT_GRAY))

    section_heading(
        3,
        "Hồ sơ khoản vay",
        f"Loan ID {p.get('loan_id', loan_id)} · Vintage {p.get('origination_vintage', '—')}",
    )
    callout(
        f"<b>Trạng thái trong kỳ quan sát: {label}.</b> {explanation} "
        f"Dữ liệu performance hiện đến 31/03/2026."
    )

    values = [
        ("Credit Score (FICO)", p.get("credit_score"), "{:.0f}", NAVY, TINT_NAVY),
        ("LTV ban đầu", p.get("original_ltv"), "{:.1f}%", BLUE, TINT_BLUE),
        ("DTI ban đầu", p.get("original_dti"), "{:.1f}%", BLUE, TINT_BLUE),
        ("Lãi suất ban đầu", p.get("original_interest_rate"), "{:.2f}%", NAVY, TINT_NAVY),
        ("Kỳ hạn ban đầu", p.get("original_loan_term"), "{:.0f} tháng", NAVY, TINT_NAVY),
        ("Dư nợ ban đầu", p.get("original_upb"), "${:,.0f}", GREEN, TINT_GREEN),
        ("Thời gian theo dõi", loan_age, "{:.0f} tháng", NAVY, TINT_NAVY),
        ("Quá hạn tại kỳ cuối", _delinquency_label(last_row.get("current_delinquency_status")) if last_row is not None else None, "{}", color, tint),
    ]
    metric_cols = st.columns(4)
    for idx, (title, value, fmt, card_color, card_tint) in enumerate(values):
        if value is None or pd.isna(value):
            shown = "—"
        else:
            shown = fmt.format(value)
        with metric_cols[idx % 4]:
            stat_card(title, shown, "Theo hồ sơ khoản vay đã chuẩn hóa.", card_color, card_tint)
        if idx % 4 == 3 and idx < len(values) - 1:
            metric_cols = st.columns(4)

    section_heading(
        4,
        "Diễn biến theo thời gian",
        "Trục thời gian dùng origination-month proxy; kỳ thanh toán đầu tiên được quy ước là tháng 1.",
    )
    callout(
        "Mốc khởi tạo là First Payment Date trừ một tháng theo định nghĩa nghiên cứu; "
        "không phải ngày origination trực tiếp do Freddie Mac cung cấp."
    )
    if timeline.empty:
        st.info("Hồ sơ có tồn tại nhưng chưa có monthly timeline đủ điều kiện để hiển thị.")
    else:
        with st.container(border=True):
            st.plotly_chart(loan_timeline_chart(timeline, loan_age=loan_age), width="stretch")
        with st.expander("Xem bảng lịch sử theo tháng"):
            show_cols = [
                column for column in [
                    "performance_month", "analysis_time_month", "current_delinquency_status",
                    "current_actual_upb", "current_interest_rate", "zero_balance_code", "event_type",
                ] if column in timeline.columns
            ]
            table = timeline[show_cols].sort_values("analysis_time_month").reset_index(drop=True)
            table = table.rename(columns={
                "performance_month": "Tháng performance",
                "analysis_time_month": "Tháng phân tích",
                "current_delinquency_status": "Mã quá hạn",
                "current_actual_upb": "Dư nợ thực tế",
                "current_interest_rate": "Lãi suất hiện tại",
                "zero_balance_code": "Mã tất toán",
                "event_type": "Kết cục tại kỳ",
            })
            st.dataframe(table, width="stretch", hide_index=True)

    section_heading(
        5,
        "So sánh với nhóm FICO tương đồng",
        "CIF nhóm là mức tích lũy mô tả của nhóm, không phải PD cá nhân của khoản vay này.",
    )
    score = p.get("credit_score")
    if pd.isna(score):
        st.info("Không xác định được nhóm FICO vì hồ sơ thiếu điểm tín dụng.")
        return

    band = _credit_score_band(float(score))
    comparison = ds.get_pd_results(group="credit_score_band", group_value=band)
    if comparison.empty:
        st.info(f"Chưa có Default CIF cho nhóm FICO {band}.")
        return
    if "follow_up_flag" in comparison.columns:
        eligible = comparison["follow_up_flag"].astype(str).str.lower().isin({"true", "1", "yes"})
        comparison = comparison[eligible]
    comparison = comparison.sort_values("horizon")
    if comparison.empty:
        st.info(f"Nhóm FICO {band} chưa có horizon đủ theo dõi; không ngoại suy CIF.")
        return

    cards = st.columns(min(len(comparison), 4))
    for idx, (_, row) in enumerate(comparison.iterrows()):
        value = row.get("cif_default")
        shown = f"{float(value):.2%}" if pd.notna(value) else "—"
        at_risk = row.get("number_at_risk")
        note = f"Còn {int(at_risk):,} khoản at risk" if pd.notna(at_risk) else "Có tính đến trả trước là rủi ro cạnh tranh"
        with cards[idx % len(cards)]:
            stat_card(
                f"Default CIF · {int(row['horizon'])} tháng",
                shown,
                note,
                RED,
                TINT_RED,
            )
    st.caption(
        f"Khoản vay có FICO {float(score):.0f}, thuộc nhóm {band}. Đây là CIF theo nhóm tham chiếu, "
        "không phải xác suất vỡ nợ riêng của khoản vay đang tra cứu."
    )


def render() -> None:
    inject_page_blocks_css()
    st.caption("TRANG 4 · TRA CỨU KHOẢN VAY")
    callout(
        "Tra cứu hồ sơ theo Loan ID, xem thông tin khoản vay và lịch sử performance theo tháng. "
        "Các hồ sơ gợi ý bên dưới giúp bạn thử nhanh ba kết cục trong bộ dữ liệu."
    )

    _render_search_and_catalog()
    active_loan_id = str(st.session_state.get("active_loan_id", "")).strip().upper()
    if active_loan_id:
        _render_loan_profile(active_loan_id)
    else:
        section_heading(
            3,
            "Hồ sơ khoản vay sẽ xuất hiện tại đây",
            "Nhập mã ở trên hoặc mở một mã từ danh mục gợi ý để xem chi tiết.",
        )
        callout(
            "Gợi ý: thử một hồ sơ vỡ nợ, một hồ sơ trả trước hạn và một hồ sơ kết thúc theo dõi "
            "để so sánh cách mỗi kết cục xuất hiện trên timeline."
        )
