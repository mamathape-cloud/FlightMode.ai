import tempfile
import os

import streamlit as st

from flightmode.core.ingestion import load_sheets
from flightmode.pipeline import run_pipeline

st.set_page_config(
    page_title="FlightMode.ai",
    page_icon="✈️",
    layout="wide",
)

st.title("FlightMode.ai – Travel Intelligence Report")
st.caption(
    "Upload your flight history to analyze spending, booking behavior, and missed benefits"
)

st.divider()

uploaded_file = st.file_uploader(
    "Upload your travel data file",
    type=["xlsx", "xls", "csv"],
    help=(
        "Excel file with a Travel_Data sheet (and optional Loyalty_Data sheet), "
        "or a CSV file. Column names are matched flexibly — any case or format is accepted."
    ),
)

if uploaded_file is not None:
    suffix = os.path.splitext(uploaded_file.name)[1]
    tmp_path = None

    with st.spinner("Analyzing your travel data…"):
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(uploaded_file.read())
                tmp_path = tmp.name

            # load_sheets() handles ALL column normalization and mapping
            travel_df, loyalty_df = load_sheets(tmp_path)
            result = run_pipeline(travel_df, loyalty_df, source_file=uploaded_file.name)

        except Exception as e:
            st.error(f"Analysis failed: {e}")
            st.stop()
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

    st.success("Analysis complete")

    st.markdown(result["markdown_report"])

    # ── PDF Download ──────────────────────────────────────────────────────────
    st.divider()
    with st.spinner("Preparing PDF report…"):
        try:
            from flightmode.report.pdf import build_pdf
            pdf_bytes = build_pdf(result["json_report"])
            st.download_button(
                label="⬇️ Download Report as PDF",
                data=pdf_bytes,
                file_name="FlightMode_Report.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        except Exception as e:
            st.warning(f"PDF generation unavailable: {e}")

    with st.expander("View raw JSON report"):
        st.json(result["json_report"])
