import tempfile
import os

import streamlit as st
import pandas as pd

# ✅ FIX: import correct function
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
    help="Excel file with a Travel_Data sheet (and optional Loyalty_Data sheet), or a CSV file.",
)

if uploaded_file is not None:
    suffix = os.path.splitext(uploaded_file.name)[1]

    with st.spinner("Analyzing your travel data…"):
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(uploaded_file.read())
                tmp_path = tmp.name

            # ✅ FIX: read sheets here (instead of pipeline_from_file)
            sheets = pd.read_excel(tmp_path, sheet_name=None)

            travel_df = sheets.get("Travel_Data")
            loyalty_df = sheets.get("Loyalty_Data")

            if travel_df is None:
                raise ValueError("Travel_Data sheet is required")

            # ✅ FIX: call correct pipeline
            result = run_pipeline(travel_df, loyalty_df)

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
