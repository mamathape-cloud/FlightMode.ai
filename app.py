import tempfile
import os

import streamlit as st
import pandas as pd

from flightmode.pipeline import run_pipeline_from_file

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
    help="Excel file with a Travel Data sheet (and optional Loyalty Data sheet), or a CSV file.",
)

if uploaded_file is not None:
    suffix = os.path.splitext(uploaded_file.name)[1]

    with st.spinner("Analyzing your travel data…"):
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(uploaded_file.read())
                tmp_path = tmp.name

            result = run_pipeline_from_file(tmp_path)

        except Exception as e:
            st.error(f"Analysis failed: {e}")
            st.stop()
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    st.success("Analysis complete")

    st.markdown(result["markdown_report"])

    with st.expander("View raw JSON report"):
        st.json(result["json_report"])
