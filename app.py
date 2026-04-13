import tempfile
import os
import re

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
/* ── Report card shell ─────────────────────────────────── */
.fm-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 24px 28px;
    margin-bottom: 18px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
.fm-card h2, .fm-card h3 {
    margin-top: 0;
    color: #1e1e32;
}
.fm-card-title {
    font-size: 1.05rem;
    font-weight: 700;
    color: #2962ff;
    letter-spacing: 0.02em;
    border-bottom: 2px solid #e8eeff;
    padding-bottom: 8px;
    margin-bottom: 14px;
}

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

/* ── Analyse button ─────────────────────────────────────── */
div[data-testid="stButton"] > button[kind="primary"] {
    background-color: #2962ff !important;
    color: #ffffff !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    padding: 0.55rem 2rem !important;
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

    # ── Card-style report rendering ───────────────────────────────────────────
    _SECTION_RE = re.compile(r"^#{1,3} ", re.MULTILINE)

    def _render_cards(markdown_text: str) -> None:
        """
        Split the Markdown report on section headings and render each
        section as an individual card.
        """
        # Find positions of all headings
        heading_starts = [m.start() for m in _SECTION_RE.finditer(markdown_text)]

        if not heading_starts:
            # No headings — render as a single card
            st.markdown(
                f'<div class="fm-card">{markdown_text}</div>',
                unsafe_allow_html=True,
            )
            return

        # Emit any preamble before the first heading as a plain card
        preamble = markdown_text[: heading_starts[0]].strip()
        if preamble:
            st.markdown(f'<div class="fm-card">{preamble}</div>', unsafe_allow_html=True)

        # Slice each section from its heading start to the next heading start
        for i, start in enumerate(heading_starts):
            end = heading_starts[i + 1] if i + 1 < len(heading_starts) else len(markdown_text)
            section_md = markdown_text[start:end].strip()
            if not section_md:
                continue

            # Extract the heading line for the card title
            first_newline = section_md.find("\n")
            if first_newline == -1:
                heading_line = section_md
                body_md = ""
            else:
                heading_line = section_md[:first_newline].strip()
                body_md = section_md[first_newline:].strip()

            # Strip leading #s for display
            title_text = heading_line.lstrip("#").strip()

            # Render card: coloured title bar + body markdown
            st.markdown(
                f'<div class="fm-card"><div class="fm-card-title">{title_text}</div></div>',
                unsafe_allow_html=True,
            )
            if body_md:
                # Strip the horizontal rules (---) Markdown adds between sections
                body_md = re.sub(r"\n---\s*$", "", body_md).strip()
                with st.container():
                    st.markdown(body_md)

    _render_cards(result["markdown_report"])
