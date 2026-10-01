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
    "PREPAYMENT": "Trả trước hạn (ZBC 01)",
    "VOLUNTARY_PREPAYMENT": "Trả trước hạn (ZBC 01)",
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
        return "ZBC 01 theo quy ước project", "warn", "Khoản vay ghi nhận Zero Balance Code 01 tại tháng kết thúc theo dõi. Nguồn Freddie Mac gộp prepaid/matured trong mã này."
    if normalized in {"CENSOR", "CENSORED", "RIGHT_CENSOR"}:
        return (
            "Kết thúc theo dõi",
            "neutral",
            "Không ghi nhận Default hoặc Zero Balance Code 01 trong thời gian quan sát. "
            "Trạng thái này không xác nhận khoản vay vẫn còn active hiện nay.",
        )
    return "Chưa xác định", "neutral", "Không có event type hợp lệ để xác nhận trạng thái."


def _set_example_loan(loan_id: str) -> None:
    # Do not mutate the text-input key here: the widget is already instantiated
    # earlier in this page run, so Streamlit raises WidgetAlreadyInstantiatedError.
    st.session_state["active_loan_id"] = loan_id
    st.session_state["scroll_to_loan_profile"] = True


def _catalog_label(row) -> str:
    event = _EVENT_LABELS.get(str(row.get("event_type", "")).upper(), "Chưa xác định")
    fico = row.get("fico")
    fico_text = f"FICO {int(fico)}" if pd.notna(fico) else "Chưa có FICO"
    return f"{row['loan_id']} · {int(row['origination_vintage'])} · {event} · {fico_text}"


def _render_search_and_catalog() -> None:
    examples = ds.get_loan_catalog_examples()
    section_heading(
        1,
        "Chọn khoản vay để tra cứu",
        "Nhập Loan ID hoặc chọn một hồ sơ mẫu trong danh mục bên dưới.",
    )

    sample_rows = pd.DataFrame()
    if not examples.empty and "event_type" in examples.columns:
        wanted_events = ["DEFAULT", "PREPAYMENT", "CENSOR"]
        sample_rows = pd.concat(
            [
                examples[examples["event_type"].astype(str).str.upper() == event].head(1)
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
            st.session_state["scroll_to_loan_profile"] = True

    section_heading(2, "Danh mục khoản vay", "Toàn bộ hồ sơ đủ điều kiện trong mẫu nghiên cứu; có thể lọc, tìm và mở từng khoản vay.")
    if examples.empty:
        st.info("Không đọc được danh mục gợi ý. Bạn vẫn có thể nhập Loan ID ở ô tra cứu phía trên.")
        return

    vintages = list(range(2016, 2027))
    events = ["DEFAULT", "PREPAYMENT", "CENSOR"]
    filter_vintage, filter_event, filter_search = st.columns([1, 1, 2])
    with filter_vintage:
        selected_vintage = st.selectbox("Năm giải ngân", ["Tất cả"] + vintages, key="catalog_vintage")
    with filter_event:
        selected_event = st.selectbox(
            "Kết cục trong dữ liệu",
            ["Tất cả"] + events,
            format_func=lambda value: "Tất cả kết cục" if value == "Tất cả" else _EVENT_LABELS.get(value, value),
            key="catalog_event",
        )
    with filter_search:
        search_text = st.text_input("Tìm theo Loan ID", placeholder="Nhập một phần hoặc toàn bộ mã khoản vay", key="catalog_search")
    vintage_filter = None if selected_vintage == "Tất cả" else int(selected_vintage)
    event_filter = None if selected_event == "Tất cả" else str(selected_event)
    total = ds.get_loan_catalog_count(vintage_filter, event_filter, search_text)
    page_size = 100
    page_count = max(1, (total + page_size - 1) // page_size)
    page = st.number_input(
        "Trang danh mục", min_value=1, max_value=page_count, value=1, step=1,
        key=f"catalog_page_{vintage_filter}_{event_filter}_{search_text}",
    )
    offset = (int(page) - 1) * page_size
    visible = ds.get_loan_catalog_page(vintage_filter, event_filter, search_text, offset, page_size)
    st.caption(f"{total:,} khoản vay phù hợp · hiển thị {offset + 1 if total else 0}–{min(offset + page_size, total):,} · trang {int(page)}/{page_count}")
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

    should_scroll = bool(st.session_state.pop("scroll_to_loan_profile", False))
    st.html("<div id='loan-profile-anchor'></div>")
    if should_scroll:
        try:
            st.html("<script>setTimeout(() => document.getElementById('loan-profile-anchor')?.scrollIntoView({behavior:'smooth', block:'start'}), 180);</script>", unsafe_allow_javascript=True)
        except TypeError:
            st.markdown("<a href='#loan-profile-anchor'>Đã mở hồ sơ khoản vay</a>", unsafe_allow_html=True)
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
        "Theo dõi tình trạng quá hạn và dư nợ thực tế theo tháng; mỗi biểu đồ có đơn vị riêng.",
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
            st.caption("Khoảng trống trên chart biểu thị tháng không có bản ghi; marker cuối là kết cục hoặc kỳ performance cuối. Trục thời gian tính từ origination-month proxy, không phải ngày origination trực tiếp.")
        with st.expander("Xem bảng lịch sử theo tháng"):
            show_cols = [
                column for column in [
                    "performance_month", "analysis_time_month", "current_delinquency_status",
                    "delinquency_num", "is_ra", "current_actual_upb", "current_interest_rate", "zero_balance_code", "event_type",
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
        st.info(f"Chưa tìm thấy kết quả đã công bố cho nhóm FICO {band}. Điều này không có nghĩa là nhóm không phát sinh vỡ nợ.")
        return
    if "follow_up_status" in comparison.columns:
        supported = comparison["follow_up_status"].astype(str).str.upper().eq("ELIGIBLE")
    elif "follow_up_flag" in comparison.columns:
        supported = comparison["follow_up_flag"].astype(str).str.lower().isin({"true", "1", "yes"})
    else:
        supported = pd.Series(True, index=comparison.index)
    unsupported = comparison.loc[~supported].copy()
    if "follow_up_flag" in comparison.columns or "follow_up_status" in comparison.columns:
        comparison = comparison[supported]
    comparison = comparison.sort_values("horizon")
    if comparison.empty:
        at_risk_col = "number_at_risk" if "number_at_risk" in unsupported else "n_at_risk"
        risk_values = pd.to_numeric(unsupported.get(at_risk_col, pd.Series(dtype=float)), errors="coerce")
        max_risk = int(risk_values.max()) if risk_values.notna().any() else 0
        st.info(
            f"Nhóm FICO {band} có hồ sơ trong mẫu, nhưng CIF ở các mốc này không được ước lượng "
            f"vì không còn đủ khoản vay đang được theo dõi tại horizon (số còn trong diện rủi ro tối đa: {max_risk:,}). "
            "Đây không phải kết luận rằng nhóm không có ca vỡ nợ; hệ thống không ngoại suy khi thiếu hỗ trợ dữ liệu."
        )
        return

    cards = st.columns(min(len(comparison), 4))
    for idx, (_, row) in enumerate(comparison.iterrows()):
        value = row.get("cif_default")
        shown = f"{float(value):.2%}" if pd.notna(value) else "—"
        at_risk = row.get("number_at_risk", row.get("n_at_risk"))
        note = f"Còn {int(at_risk):,} khoản còn theo dõi" if pd.notna(at_risk) else "Có tính trả trước là rủi ro cạnh tranh"
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
        "Các hồ sơ gợi ý bên dưới giúp bạn thử nhanh Default, ZBC 01 và censoring termination."
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
            "Gợi ý: thử một hồ sơ Default, một hồ sơ ZBC 01 và một hồ sơ kết thúc theo dõi "
            "để so sánh cách mỗi kết cục xuất hiện trên timeline."
        )
