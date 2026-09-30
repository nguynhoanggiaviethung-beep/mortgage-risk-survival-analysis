"""
Trang 5 — Kết quả mô hình (trang học thuật/model)

Bố cục đọc từ trên xuống:
  ① Vỡ nợ tăng như thế nào theo thời gian?      (Default CIF / PD(t))
  ② Tại sao không dùng 1 − KM?                   (KM vs Default CIF)
  ③ Những đặc điểm nào liên quan đến vỡ nợ?      (Cox / TV-Cox / Cause-specific / Fine-Gray)
  ④ Kiểm định & chẩn đoán mô hình                (expander)
  ⑤ Phương pháp & định nghĩa sự kiện             (expander)

Lưu ý: chỉ nội dung hiển thị cho người dùng được Việt hóa; tên biến, tên cột dữ liệu
và giá trị model_type (Cox PH, Fine-Gray...) giữ nguyên để khớp với data_service.
"""
import pandas as pd
import streamlit as st
import html as _html
from app.components.charts import cif_chart, forest_plot, km_vs_cif_compare_chart, survival_curve_chart
from app.components.styling import section_title
from app.config import MODEL_TYPE_OPTIONS
from app.services import data_service as ds

# Các phương pháp phân tích yếu tố liên quan đến vỡ nợ (Phần 3).
# Aalen-Johansen / CIF không nằm ở đây: nó là ước lượng xác suất vỡ nợ tích lũy, hiển thị ở Phần 1.
_FACTOR_MODELS = ["Cox PH", "Time-varying Cox", "Cause-specific Hazard", "Fine-Gray"]

# Tên hiển thị tiếng Việt cho từng phương pháp (giá trị bên trong vẫn là tên gốc)
_MODEL_LABELS = {
    "Cox PH": "Cox (rủi ro tỷ lệ)",
    "Time-varying Cox": "Cox với biến thay đổi theo thời gian",
    "Cause-specific Hazard": "Rủi ro tức thời theo từng nguyên nhân",
    "Fine-Gray": "Fine–Gray (rủi ro cạnh tranh)",
}

# Các mốc thời gian chính theo specification (không hiển thị 48M)
_MAIN_HORIZONS = [12, 24, 36, 60]

# Giá trị của follow_up_flag được coi là "đủ thời gian theo dõi"
_ELIGIBLE_TOKENS = {"true", "1", "1.0", "y", "yes", "ok", "eligible", "sufficient", "full"}

# Tên cột có thể có trong risk_driver_results (chỉnh lại nếu schema thực tế khác)
_COEF_COLUMN_CANDIDATES = {
    "Biến": ["variable", "feature", "term", "covariate", "driver"],
    "HR": ["hazard_ratio", "hr", "shr", "subdistribution_hazard_ratio", "exp_coef"],
    "CI thấp": ["ci_lower", "ci_low", "lower_ci", "hr_lower", "lower_95"],
    "CI cao": ["ci_upper", "ci_high", "upper_ci", "hr_upper", "upper_95"],
    "p-value": ["p_value", "pvalue", "p", "p_val"],
}

# Tên cột hiển thị của bảng kiểm định mô hình
_DIAGNOSTIC_LABELS = {
    "model_version": "Phiên bản mô hình",
    "diagnostic_name": "Kiểm định",
    "metric": "Chỉ số",
    "value": "Giá trị",
    "threshold": "Ngưỡng",
    "interpretation": "Diễn giải",
}

# Chú thích các ký hiệu viết tắt (hiển thị nhỏ phía trên biểu đồ)
_GLOSSARY = {
    "PD(t)": "Xác suất vỡ nợ (Probability of Default) tính đến thời điểm t.",
    "CIF": "Hàm xác suất tích lũy (Cumulative Incidence Function): xác suất một sự kiện đã xảy ra "
           "đến thời điểm t, có tính đến sự kiện cạnh tranh.",
    "KM": "Kaplan–Meier: phương pháp ước lượng xác suất khoản vay chưa xảy ra sự kiện theo thời gian.",
    "1 − KM": "Xác suất đã xảy ra sự kiện nếu bỏ qua sự kiện cạnh tranh.",
    "HR": "Tỷ số rủi ro tức thời (Hazard Ratio): so sánh rủi ro tức thời của vỡ nợ khi biến tăng thêm "
          "một đơn vị. HR = 1 là không khác biệt; HR > 1 là rủi ro cao hơn; HR < 1 là rủi ro thấp hơn.",
    "SHR": "Tỷ số rủi ro phân phối con (Subdistribution Hazard Ratio): tương tự HR nhưng dùng trong "
           "mô hình Fine–Gray, có tính đến sự kiện cạnh tranh.",
    "CI": "Khoảng tin cậy 95% (Confidence Interval): khoảng giá trị hợp lý của HR/SHR. "
          "Nếu khoảng này chứa 1 thì chưa có bằng chứng rõ ràng về mối liên hệ.",
    "Giá trị p": "p-value: thường p < 0,05 được xem là có ý nghĩa thống kê.",
}


# Bảng màu theo từng mô hình: accent = màu chính, dark = chữ đậm, soft = nền nhạt
_MODEL_THEMES = {
    "Cox PH":                {"accent": "#1E6FD9", "dark": "#0B3D7A", "soft": "#EAF3FF"},  # xanh dương
    "Time-varying Cox":      {"accent": "#0F9D8A", "dark": "#075E52", "soft": "#E6F7F4"},  # xanh ngọc
    "Cause-specific Hazard": {"accent": "#E07A10", "dark": "#7A3F00", "soft": "#FFF2E3"},  # cam
    "Fine-Gray":             {"accent": "#7B3FE4", "dark": "#40208A", "soft": "#F1EAFF"},  # tím
}
_DEFAULT_THEME = {"accent": "#1E6FD9", "dark": "#0B3D7A", "soft": "#EAF3FF"}


def _get_theme(model_type: str | None) -> dict:
    return _MODEL_THEMES.get(model_type, _DEFAULT_THEME)


def _inject_theme_css(theme: dict) -> None:
    """Đổi màu viền ô chọn phương pháp theo mô hình đang chọn."""
    st.markdown(
        f"""
        <style>
        div[data-baseweb="select"] > div {{
            border: 2px solid {theme['accent']} !important;
            background: {theme['soft']} !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_model_banner(label: str, theme: dict) -> None:
    """Dải màu đầy đủ báo mô hình đang xem."""
    st.markdown(
        f"""
        <div style="background:linear-gradient(90deg,{theme['accent']},{theme['dark']});
                    color:#fff;padding:12px 18px;border-radius:10px;margin:6px 0 12px;
                    font-weight:700;font-size:1.05rem;">
            Đang xem: {_html.escape(label)}
        </div>
        """,
        unsafe_allow_html=True,
    )

def _render_glossary(keys: list[str], theme: dict | None = None) -> None:
    """Chú thích ký hiệu nổi bật, đặt phía trên biểu đồ để người xem đọc trước."""
    theme = theme or _DEFAULT_THEME
    items = [(k, _GLOSSARY[k]) for k in keys if k in _GLOSSARY]
    if not items:
        return

    rows = "".join(
        f"""
        <div style="display:flex;gap:12px;align-items:flex-start;margin:8px 0;">
            <span style="flex:0 0 auto;min-width:64px;text-align:center;background:{theme['accent']};
                         color:#fff;font-weight:700;padding:3px 10px;border-radius:999px;
                         font-size:0.95rem;">{_html.escape(k)}</span>
            <span style="color:#1f2937;font-size:0.98rem;line-height:1.5;">{_html.escape(desc)}</span>
        </div>
        """
        for k, desc in items
    )
    st.markdown(
        f"""
        <div style="background:{theme['soft']};border:1px solid {theme['accent']};
                    border-left:8px solid {theme['accent']};border-radius:10px;
                    padding:14px 18px;margin:10px 0 14px;">
            <div style="font-weight:800;font-size:1.1rem;color:{theme['dark']};margin-bottom:6px;">
                📖 Chú thích ký hiệu — đọc trước khi xem biểu đồ
            </div>
            {rows}
        </div>
        """,
        unsafe_allow_html=True,
    )

# Nội dung giải thích riêng cho từng phương pháp ở Phần 3
_MODEL_INFO = {
    "Cox PH": {
        "title": "Cox (rủi ro tỷ lệ) — Yếu tố liên quan đến rủi ro tức thời của vỡ nợ",
        "intro": (
            "Mô hình Cox đánh giá mối liên hệ giữa đặc điểm khoản vay và rủi ro tức thời "
            "(hazard) của vỡ nợ, tức tốc độ xảy ra vỡ nợ theo thời gian."
        ),
        "label": "HR",
        "outcome": "rủi ro tức thời của vỡ nợ",
        "guide": [
            "HR (tỷ số rủi ro tức thời) = 1: không có khác biệt về rủi ro tức thời",
            "HR > 1: rủi ro tức thời của vỡ nợ cao hơn khi biến tăng",
            "HR < 1: rủi ro tức thời của vỡ nợ thấp hơn khi biến tăng",
        ],
        "key": "endpoint_cox",
    },
    "Time-varying Cox": {
        "title": "Cox với biến thay đổi theo thời gian — Yếu tố liên quan đến rủi ro tức thời của vỡ nợ",
        "intro": (
            "Mô hình Cox với biến thay đổi theo thời gian cho phép giá trị của biến "
            "được cập nhật trong suốt vòng đời khoản vay khi đánh giá rủi ro tức thời của vỡ nợ."
        ),
        "label": "HR",
        "outcome": "rủi ro tức thời của vỡ nợ",
        "guide": [
            "HR (tỷ số rủi ro tức thời) = 1: không có khác biệt về rủi ro tức thời",
            "HR > 1: rủi ro tức thời của vỡ nợ cao hơn khi biến tăng",
            "HR < 1: rủi ro tức thời của vỡ nợ thấp hơn khi biến tăng",
        ],
        "key": "endpoint_tvcox",
    },
    "Cause-specific Hazard": {
        "title": "Rủi ro tức thời theo từng nguyên nhân — Yếu tố liên quan đến từng loại sự kiện",
        "intro": (
            "Mô hình này ước lượng rủi ro tức thời của từng loại sự kiện (vỡ nợ, tất toán trước hạn tự nguyện) "
            "một cách riêng biệt; các sự kiện còn lại được xem như dữ liệu bị kiểm duyệt "
            "trong mô hình của sự kiện đang xét."
        ),
        "label": "HR",
        "outcome": "rủi ro tức thời của sự kiện đang chọn",
        "guide": [
            "HR (tỷ số rủi ro tức thời) = 1: không có khác biệt",
            "HR > 1: rủi ro tức thời của sự kiện đang chọn cao hơn khi biến tăng",
            "HR < 1: rủi ro tức thời của sự kiện đang chọn thấp hơn khi biến tăng",
        ],
        "key": "endpoint_csh",
    },
    "Fine-Gray": {
        "title": "Fine–Gray — Yếu tố liên quan đến xác suất vỡ nợ tích lũy",
        "intro": (
            "Fine–Gray xem tất toán trước hạn tự nguyện là sự kiện cạnh tranh và đánh giá mối liên hệ "
            "giữa các biến với rủi ro tức thời phân phối con (subdistribution hazard) của vỡ nợ."
        ),
        "label": "SHR",
        "outcome": "rủi ro tức thời phân phối con của vỡ nợ (và do đó xác suất vỡ nợ tích lũy)",
        "guide": [
            "SHR (tỷ số rủi ro phân phối con) = 1: không có khác biệt",
            "SHR > 1: rủi ro tức thời phân phối con của vỡ nợ cao hơn",
            "SHR < 1: rủi ro tức thời phân phối con của vỡ nợ thấp hơn",
        ],
        "key": "fg_endpoint",
    },
}


def render() -> None:
    st.caption("Trang 5 · Kết quả mô hình")

    # -------------------------------------------------------------------------
    # TRANG NÀY CHO BẠN BIẾT ĐIỀU GÌ?
    # -------------------------------------------------------------------------
    section_title("Trang này cho bạn biết điều gì?")
    st.markdown(
        "Vỡ nợ xảy ra như thế nào theo thời gian, và các mô hình thống kê cho biết "
        "những đặc điểm nào của khoản vay có liên quan đến vỡ nợ?"
    )
    st.caption(
        "Các mô hình chỉ dùng những khoản vay có đầy đủ dữ liệu ở các biến lõi của mô hình; "
        "phạm vi dữ liệu thuộc bộ dữ liệu mẫu giai đoạn 2016–2026, với thời gian theo dõi đến 31/03/2026. "
        "Bảng xác suất vỡ nợ theo năm giải ngân (vintage) được xem riêng ở trang Rủi ro danh mục; "
        "hiện chưa có hệ số mô hình phân tầng theo năm giải ngân hoặc theo nhóm điểm tín dụng."
    )

    st.divider()
    _render_default_cif_overview()

    st.divider()
    _render_competing_risk_comparison()

    st.divider()
    model_type = _render_factor_analysis()

    st.divider()
    _render_diagnostics(model_type)

    _render_methodology_note()


# =============================================================================
# HELPERS
# =============================================================================
def _eligible_mask(df: pd.DataFrame) -> pd.Series:
    """Trả về mask các dòng đủ thời gian theo dõi (theo follow_up_flag nếu có)."""
    if "follow_up_flag" not in df.columns:
        return pd.Series(True, index=df.index)
    col = df["follow_up_flag"]
    if col.dtype == bool:
        return col
    return col.astype(str).str.strip().str.lower().isin(_ELIGIBLE_TOKENS)


def _available_horizons(cif: pd.DataFrame, km: pd.DataFrame | None = None) -> list[int]:
    """Các mốc chính có dữ liệu CIF, đủ thời gian theo dõi và (nếu có KM) không vượt quá
    thời gian quan sát tối đa của KM -> không ngoại suy."""
    if cif.empty or "horizon" not in cif.columns:
        return []
    cif_ok = cif[_eligible_mask(cif)]
    km_max = None
    if km is not None and not km.empty and "analysis_time" in km.columns:
        km_max = km["analysis_time"].max()

    horizons = []
    for h in _MAIN_HORIZONS:
        if not (cif_ok["horizon"] == h).any():
            continue
        if km_max is not None and km_max < h:
            continue
        horizons.append(h)
    return horizons


def _get_portfolio_pd() -> pd.DataFrame:
    pd_res = ds.get_pd_results(group="portfolio")
    if pd_res.empty:
        pd_res = ds.get_pd_results()
    return pd_res


def _get_portfolio_km() -> pd.DataFrame:
    km = ds.get_survival_results(group="portfolio")
    if km.empty:
        km = ds.get_survival_results()
    return km


def _pick_columns(df: pd.DataFrame) -> dict:
    lowered = {c.lower(): c for c in df.columns}
    picked = {}
    for label, candidates in _COEF_COLUMN_CANDIDATES.items():
        for cand in candidates:
            if cand in lowered:
                picked[label] = lowered[cand]
                break
    return picked


def _coef_table(df: pd.DataFrame, value_label: str = "HR") -> pd.DataFrame:
    """Bảng rút gọn: Biến | HR | Khoảng tin cậy 95% | Giá trị p."""
    picked = _pick_columns(df)
    if "HR" not in picked:
        return pd.DataFrame()

    out = pd.DataFrame()
    if "Biến" in picked:
        out["Biến"] = df[picked["Biến"]].values
    out[value_label] = pd.to_numeric(df[picked["HR"]], errors="coerce").map(
        lambda v: "" if pd.isna(v) else f"{v:.3f}"
    ).values
    if "CI thấp" in picked and "CI cao" in picked:
        lo = pd.to_numeric(df[picked["CI thấp"]], errors="coerce")
        hi = pd.to_numeric(df[picked["CI cao"]], errors="coerce")
        out["Khoảng tin cậy 95%"] = [
            "" if pd.isna(a) or pd.isna(b) else f"[{a:.3f}; {b:.3f}]"
            for a, b in zip(lo, hi)
        ]
    if "p-value" in picked:
        pv = pd.to_numeric(df[picked["p-value"]], errors="coerce")
        out["Giá trị p"] = pv.map(
            lambda v: "" if pd.isna(v) else ("<0.001" if v < 0.001 else f"{v:.3f}")
        ).values
    return out


def _interpretation_lines(sub: pd.DataFrame, value_label: str, outcome: str, max_items: int = 8) -> list[str]:
    """Sinh câu diễn giải từ kết quả mô hình (chỉ mô tả mối liên hệ, không kết luận nhân quả)."""
    picked = _pick_columns(sub)
    if "HR" not in picked or "Biến" not in picked:
        return []

    lines = []
    for _, row in sub.iterrows():
        hr = pd.to_numeric(row[picked["HR"]], errors="coerce")
        if pd.isna(hr):
            continue
        name = row[picked["Biến"]]

        significant = None
        if "p-value" in picked:
            p = pd.to_numeric(row[picked["p-value"]], errors="coerce")
            if not pd.isna(p):
                significant = p < 0.05
        if significant is None and "CI thấp" in picked and "CI cao" in picked:
            lo = pd.to_numeric(row[picked["CI thấp"]], errors="coerce")
            hi = pd.to_numeric(row[picked["CI cao"]], errors="coerce")
            if not pd.isna(lo) and not pd.isna(hi):
                significant = not (lo <= 1 <= hi)

        if significant is False:
            lines.append(
                f"**{name}**: {value_label} = {hr:.2f}, chưa có bằng chứng thống kê rõ ràng "
                f"về mối liên hệ với {outcome} trong mô hình này."
            )
        elif hr > 1:
            lines.append(
                f"**{name}**: {value_label} > 1 ({hr:.2f}) cho thấy giá trị cao hơn có liên quan "
                f"với {outcome} cao hơn."
            )
        elif hr < 1:
            lines.append(
                f"**{name}**: {value_label} < 1 ({hr:.2f}) cho thấy giá trị cao hơn có liên quan "
                f"với {outcome} thấp hơn."
            )
        else:
            lines.append(f"**{name}**: {value_label} = 1, không có khác biệt.")
        if len(lines) >= max_items:
            break
    return lines


# =============================================================================
# PHẦN 1 — VỠ NỢ TĂNG NHƯ THẾ NÀO THEO THỜI GIAN?
# =============================================================================
def _render_default_cif_overview() -> None:
    section_title("① Vỡ nợ tăng như thế nào theo thời gian?")

    pd_res = _get_portfolio_pd()
    if pd_res.empty:
        st.info("Chưa có kết quả xác suất vỡ nợ (pd_results).")
        return

    st.markdown("**Xác suất vỡ nợ tích lũy — PD(t)**")
    st.caption(
        "Xác suất một khoản vay đã vỡ nợ tính đến mốc thời gian t, trong đó "
        "việc tất toán trước hạn tự nguyện được xử lý là sự kiện cạnh tranh (competing event)."
    )

    # 1. Chỉ số theo các mốc chính (chỉ hiện nếu đủ thời gian theo dõi)
    horizons = _available_horizons(pd_res)
    values = {}
    if horizons and "cif_default" in pd_res.columns:
        cif_ok = pd_res[_eligible_mask(pd_res)]
        for h in horizons:
            values[h] = cif_ok.loc[cif_ok["horizon"] == h, "cif_default"].iloc[0]

    if values:
        cols = st.columns(len(values))
        for col, (h, v) in zip(cols, values.items()):
            col.metric(f"{h} tháng", f"{v:.2%}")
        if 60 in values:
            st.caption("* Mốc 60 tháng chỉ hiển thị khi đủ thời gian theo dõi.")
    else:
        st.info("Chưa có mốc chính (12/24/36/60 tháng) nào đủ thời gian theo dõi.")

    # 2. Ví dụ cách đọc (ưu tiên mốc 36 tháng nếu có)
    if values:
        h_ex = 36 if 36 in values else max(values)
        st.markdown(
            f"*Ví dụ: xác suất vỡ nợ tích lũy tại mốc {h_ex} tháng = {values[h_ex]:.2%} nghĩa là xác suất "
            f"khoản vay đã vỡ nợ tính đến tháng {h_ex} trong nhóm khoản vay nghiên cứu là {values[h_ex]:.2%}, "
            "với tất toán trước hạn được xử lý là sự kiện cạnh tranh.*"
        )

    # 3. Biểu đồ xác suất vỡ nợ tích lũy
    _render_glossary(["PD(t)", "CIF"])
    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    st.plotly_chart(cif_chart(pd_res), width="stretch")
    st.markdown("</div>", unsafe_allow_html=True)


# =============================================================================
# PHẦN 2 — TẠI SAO KHÔNG DÙNG 1 − KM?
# =============================================================================
def _render_km(group: str = "portfolio") -> None:
    section_title("Đường xác suất chưa vỡ nợ Kaplan–Meier")
    survival = ds.get_survival_results(group=group)
    if survival.empty:
        survival = ds.get_survival_results()
    if survival.empty:
        st.info("Chưa có kết quả survival (survival_results).")
        return
    _render_glossary(["KM"])
    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    st.plotly_chart(survival_curve_chart(survival), width="stretch")
    st.markdown("</div>", unsafe_allow_html=True)
    st.caption(
        "S(t) = P(T > t) là xác suất khoản vay chưa xảy ra sự kiện đến thời điểm t. "
        "Khi phân tích vỡ nợ bằng Kaplan–Meier, tất toán trước hạn tự nguyện được xem như "
        "dữ liệu bị kiểm duyệt nếu rủi ro cạnh tranh không được mô hình hóa riêng. Vì vậy, 1 − KM "
        "không tương đương xác suất vỡ nợ tích lũy khi tất toán trước hạn là sự kiện cạnh tranh."
    )


def _render_competing_risk_comparison(group: str = "portfolio") -> None:
    section_title("② Tại sao không dùng 1 − KM?")

    km = _get_portfolio_km()
    cif = _get_portfolio_pd()

    if km.empty or cif.empty:
        st.info("Cần cả kết quả survival (survival_results) và kết quả xác suất vỡ nợ (pd_results) để vẽ so sánh này.")
        return

    # 1. Biểu đồ so sánh
    st.markdown("**Xác suất vỡ nợ tích lũy so với 1 − KM**")
    _render_glossary(["KM", "1 − KM", "CIF"])
    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    st.plotly_chart(km_vs_cif_compare_chart(km, cif), width="stretch")
    st.markdown("</div>", unsafe_allow_html=True)

    # 2. Bảng theo các mốc chính (đủ thời gian theo dõi, không ngoại suy)
    available = _available_horizons(cif, km)
    if available and "cif_default" in cif.columns and "analysis_time" in km.columns:
        cif_ok = cif[_eligible_mask(cif)]
        rows = []

        for h in available:
            cif_sub = cif_ok[cif_ok["horizon"] == h]
            km_sub = km[km["analysis_time"] <= h]

            if not cif_sub.empty and not km_sub.empty:
                val_cif = cif_sub["cif_default"].values[0]
                val_km_pd = 1 - km_sub.sort_values("analysis_time")["survival"].values[-1]
                diff = val_km_pd - val_cif

                rows.append({
                    "Mốc": f"{h} tháng",
                    "1 − KM": f"{val_km_pd:.2%}",
                    "Xác suất vỡ nợ tích lũy": f"{val_cif:.2%}",
                    "Chênh lệch": f"{diff:+.2%}",
                })

        if rows:
            st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
        else:
            st.info("Chưa có mốc chính (12/24/36/60 tháng) nào đủ thời gian theo dõi để so sánh.")
    else:
        st.info("Chưa có mốc chính (12/24/36/60 tháng) nào đủ thời gian theo dõi để so sánh.")

    # 3. Một câu giải thích
    st.markdown(
        "Vì một khoản vay có thể được tất toán trước hạn trước khi vỡ nợ, 1 − KM không phải là xác suất "
        "vỡ nợ tích lũy. Xác suất vỡ nợ tích lũy xử lý tất toán trước hạn như một sự kiện cạnh tranh."
    )

    with st.expander("Xem đường xác suất chưa vỡ nợ Kaplan–Meier"):
        _render_km()


# =============================================================================
# PHẦN 3 — NHỮNG ĐẶC ĐIỂM NÀO LIÊN QUAN ĐẾN VỠ NỢ?
# =============================================================================
def _render_factor_analysis() -> str:
    section_title("③ Những đặc điểm nào liên quan đến vỡ nợ?")
    st.markdown("**Phân tích yếu tố liên quan đến vỡ nợ**")
    st.caption(
        "Các mô hình dưới đây giúp đánh giá mối liên hệ giữa đặc điểm khoản vay "
        "và thời gian xảy ra vỡ nợ."
    )

    options = [m for m in MODEL_TYPE_OPTIONS if m in _FACTOR_MODELS] or list(_FACTOR_MODELS)
    model_type = st.selectbox(
        "Chọn phương pháp",
        options,
        format_func=lambda m: _MODEL_LABELS.get(m, m),
    )
    info = _MODEL_INFO[model_type]
    theme = _get_theme(model_type)
    _inject_theme_css(theme)

    section_title(info["title"])
    _render_model_banner(_MODEL_LABELS.get(model_type, model_type), theme)
    st.markdown(info["intro"])

    st.markdown("**Cách đọc**")
    st.markdown("\n".join(f"- {g}" for g in info["guide"]))

    risk_df = ds.get_risk_driver_results(model_type=model_type)
    if risk_df.empty:
        st.info(f"Chưa có kết quả yếu tố rủi ro (risk_driver_results) cho phương pháp '{_MODEL_LABELS.get(model_type, model_type)}'.")
        return model_type

    if "endpoint" in risk_df.columns:
        endpoints = sorted(risk_df["endpoint"].dropna().unique())
        endpoint = (
            st.radio("Sự kiện đang xét", endpoints, horizontal=True, key=info["key"])
            if len(endpoints) > 1
            else (endpoints[0] if len(endpoints) > 0 else None)
        )
        sub = risk_df[risk_df["endpoint"] == endpoint] if endpoint else risk_df
    else:
        sub = risk_df

    # Biểu đồ forest plot
    _render_glossary([info["label"], "CI", "Giá trị p"], theme)
    st.markdown(
        f'<div class="chart-card" style="border:2px solid {theme["accent"]};'
        f'border-top:8px solid {theme["accent"]};">',
        unsafe_allow_html=True,
    )
    st.plotly_chart(forest_plot(sub), width="stretch")
    st.markdown("</div>", unsafe_allow_html=True)

    # Bảng hệ số rút gọn
    table = _coef_table(sub, value_label=info["label"])
    if table.empty:
        st.info("Chưa xác định được cột hệ số (HR/SHR) trong kết quả yếu tố rủi ro để hiển thị bảng.")
    else:
        st.dataframe(table.reset_index(drop=True), width="stretch", hide_index=True)

    # Đọc kết quả
    lines = _interpretation_lines(sub, info["label"], info["outcome"])
    if lines:
        st.markdown("**Đọc kết quả**")
        st.markdown("\n".join(f"- {line}" for line in lines))
        st.caption("Đây là mối liên hệ thống kê trong mô hình, không phải kết luận về quan hệ nhân quả.")

    return model_type


# =============================================================================
# PHẦN 4 — KIỂM ĐỊNH & CHẨN ĐOÁN MÔ HÌNH (expander)
# =============================================================================
def _render_diagnostics(model_type: str) -> None:
    section_title("④ Kiểm định & chẩn đoán mô hình")
    diagnostics = ds.get_model_diagnostics(model_type=model_type)

    with st.expander("Xem chi tiết kiểm định mô hình"):
        if diagnostics.empty:
            st.info(f"Chưa có kết quả kiểm định cho phương pháp '{_MODEL_LABELS.get(model_type, model_type)}'.")
        else:
            show_cols = [c for c in [
                "model_version", "diagnostic_name", "metric", "value", "threshold", "interpretation",
            ] if c in diagnostics.columns]
            display_df = diagnostics[show_cols].reset_index(drop=True).rename(columns=_DIAGNOSTIC_LABELS)
            st.dataframe(display_df, width="stretch")


# =============================================================================
# PHẦN 5 — PHƯƠNG PHÁP & ĐỊNH NGHĨA SỰ KIỆN (expander)
# =============================================================================
def _render_methodology_note() -> None:
    section_title("⑤ Phương pháp & định nghĩa sự kiện")
    with st.expander("Xem phương pháp"):
        st.markdown(
            "- **Vỡ nợ:** quá hạn từ 90 ngày trở lên (90+ DPD), RA và ZBC 02/03/09.\n"
            "- **Tất toán trước hạn tự nguyện:** ZBC 01.\n"
            "- **Kết thúc bị kiểm duyệt (censoring):** ZBC 15/16/96.\n"
            "- Sự kiện xảy ra sớm nhất được chọn; nếu vỡ nợ và tất toán trước hạn cùng tháng, "
            "vỡ nợ được ưu tiên.\n\n"
            "Xác suất vỡ nợ tích lũy PD(t) là tỷ lệ vỡ nợ tích lũy (cumulative default incidence) "
            "dùng cho phân tích tín dụng; đây không phải tổn thất tín dụng kỳ vọng (ECL) đầy đủ theo IFRS 9."
        )