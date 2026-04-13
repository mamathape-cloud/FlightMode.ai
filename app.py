import tempfile
import os

import streamlit as st

from flightmode.core.ingestion import load_sheets
from flightmode.pipeline import run_pipeline

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="FlightMode.ai",
    page_icon="✈️",
    layout="wide",
)

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── PDF download button ────────────────────────────────── */
div[data-testid="stDownloadButton"] > button {
    background-color: #111111 !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    padding: 0.5rem 1.2rem !important;
}
div[data-testid="stDownloadButton"] > button:hover {
    background-color: #333333 !important;
    color: #ffffff !important;
}

/* ── Analyse button — black background, white text ──────── */
div[data-testid="stButton"] > button[kind="primary"] {
    background-color: #111111 !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    padding: 0.55rem 2rem !important;
}
div[data-testid="stButton"] > button[kind="primary"]:hover {
    background-color: #333333 !important;
    color: #ffffff !important;
}
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.title("FlightMode.ai – Travel Intelligence Report")
st.caption(
    "Upload your flight history to analyze spending, booking behavior, and missed benefits"
)
st.divider()

# ── File uploader ─────────────────────────────────────────────────────────────
uploaded_file = st.file_uploader(
    "Upload your travel data file",
    type=["xlsx", "xls", "csv"],
    help=(
        "Excel file with a Travel_Data sheet (and optional Loyalty_Data sheet), "
        "or a CSV file. Column names are matched flexibly — any case or format is accepted."
    ),
)

# Show Analyse button only when a file has been uploaded
if uploaded_file is not None:
    analyse_clicked = st.button("Analyse", type="primary")
else:
    analyse_clicked = False

# ── Analysis flow ─────────────────────────────────────────────────────────────
if analyse_clicked and uploaded_file is not None:
    suffix = os.path.splitext(uploaded_file.name)[1]
    tmp_path = None
    result = None

    # Loader animation while processing
    with st.status("Analysing your travel data…", expanded=True) as status:
        st.write("📂 Reading file and normalising columns…")
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(uploaded_file.read())
                tmp_path = tmp.name

            travel_df, loyalty_df = load_sheets(tmp_path)
            st.write(f"✅ Loaded {len(travel_df):,} travel records")

            st.write("🔍 Running analysis modules…")
            result = run_pipeline(travel_df, loyalty_df, source_file=uploaded_file.name)

            st.write("📊 Building report…")
            status.update(label="Analysis complete!", state="complete", expanded=False)

        except Exception as e:
            status.update(label="Analysis failed", state="error", expanded=True)
            st.error(f"Error: {e}")
            st.stop()
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

    if result is None:
        st.stop()

    # ── PDF bytes (pre-built once) ────────────────────────────────────────────
    pdf_bytes = None
    try:
        from flightmode.report.pdf import build_pdf
        pdf_bytes = build_pdf(result["json_report"])
    except Exception:
        pass

    # ── PDF download button — black, 30% wide, left-aligned ──────────────────
    if pdf_bytes:
        dl_col, _ = st.columns([3, 7])
        with dl_col:
            st.download_button(
                label="⬇  Download Report as PDF",
                data=pdf_bytes,
                file_name="FlightMode_Report.pdf",
                mime="application/pdf",
                use_container_width=True,
            )

    st.divider()

    # ── Report — plain continuous rendering, no decorative wrappers ─────────
    st.markdown(result["markdown_report"])
