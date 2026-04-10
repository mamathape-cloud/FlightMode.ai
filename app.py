import streamlit as st
import pandas as pd

# Import your pipeline
from flightmode.main import run_analysis, ask_question_streamlit

st.set_page_config(page_title="FlightMode.ai", layout="wide")

st.title("✈️ FlightMode.ai – Travel Intelligence")
st.caption("Analyze your flights. Maximize savings. Unlock loyalty value.")

# Upload section
uploaded_file = st.file_uploader("Upload your travel data (Excel)", type=["xlsx"])

if uploaded_file:
    st.success("File uploaded successfully")

    if st.button("Analyze My Travel"):

        with st.spinner("Analyzing your travel patterns..."):

            report, context = run_analysis(uploaded_file)

            st.session_state.report = report
            st.session_state.context = context


# Display Results
if "report" in st.session_state:

    report = st.session_state.report

    st.divider()

    # Executive Summary
    st.subheader("📊 Executive Summary")
    st.info(report.get("executive_summary", "No summary available"))

    st.divider()

    # Top Insights
    st.subheader("🔥 Top Insights")

    for insight in report.get("top_insights", []):
        st.markdown(f"""
        **Observation:** {insight.get('observation', '')}  
        **Implication:** {insight.get('implication', '')}  
        **Recommendation:** {insight.get('recommendation', '')}  
        **Impact:** {insight.get('impact', '')}
        """)
        st.divider()

    # Full Report
    st.subheader("📄 Full Report")
    st.markdown(report.get("full_report", "No report generated"))

    st.divider()

    # Chat
    st.subheader("💬 Ask Questions")

    question = st.text_input("Ask about your travel behavior")

    if question:
        answer = ask_question_streamlit(question, st.session_state.context)
        st.success(answer)
