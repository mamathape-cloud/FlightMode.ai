import os
import tempfile

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(page_title="FlightMode.ai", page_icon="✈️", layout="wide")

# ── CSS ────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
div[data-testid="stDownloadButton"] > button {
    background-color: #111 !important; color: #fff !important;
    border: none !important; border-radius: 8px !important;
    font-weight: 600 !important; padding: 0.5rem 1.2rem !important;
}
div[data-testid="stDownloadButton"] > button:hover { background-color: #333 !important; }
div[data-testid="stButton"] > button[kind="primary"] {
    background-color: #111 !important; color: #fff !important;
    border: none !important; border-radius: 8px !important;
    font-weight: 600 !important; padding: 0.55rem 2rem !important;
}
div[data-testid="stButton"] > button[kind="primary"]:hover { background-color: #333 !important; }
div[data-testid="stButton"] > button[kind="secondary"] {
    border-radius: 8px !important; font-weight: 500 !important;
}
.step-badge {
    display: inline-block; background: #111; color: #fff;
    border-radius: 50%; width: 28px; height: 28px;
    text-align: center; line-height: 28px; font-weight: 700;
    font-size: 14px; margin-right: 8px;
}
</style>
""", unsafe_allow_html=True)


# ── Session state init ─────────────────────────────────────────────────────────
def _init():
    defaults = {
        "step": 1,
        "flights_df": None,       # pd.DataFrame for display
        "loyalty_df": None,       # pd.DataFrame for display
        "json_report": None,
        "markdown_report": None,
        "pdf_bytes": None,
        "chat_history": [],
        "file_type": None,        # "pdf" | "xlsx"
        "source_name": "",
        # internal raw data for analysis step
        "_xlsx_travel": None,
        "_xlsx_loyalty": None,
        "_pdf_flights": None,
        "_pdf_loyalty": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _reset():
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.rerun()


_init()

# ── Column display maps ────────────────────────────────────────────────────────
_FLIGHT_COL_LABELS = {
    "pnr": "PNR", "flight_number": "Flight No.", "airline": "Airline",
    "origin": "From", "destination": "To",
    "travel_date": "Travel Date", "booking_date": "Booking Date",
    "fare": "Fare (₹)", "amount_inr": "Amount (₹)", "amount": "Amount (₹)",
    "class": "Class", "trip_type": "Trip Type",
    "booking_source": "Booked Via", "route": "Route",
}
_LOYALTY_COL_LABELS = {
    "airline": "Airline", "loyalty_program": "Program",
    "loyalty_program_name": "Program", "program_name": "Program",
    "loyalty_number": "Loyalty No.", "current_tier": "Tier",
    "pnr": "PNR", "credited_pnr": "PNR",
    "travel_date": "Date", "credited_travel_date": "Date", "activity_date": "Date",
    "miles_earned": "Miles", "miles_credited": "Miles",
    "description": "Description",
}

_PREFERRED_FLIGHT_ORDER = [
    "pnr", "flight_number", "airline", "origin", "destination",
    "travel_date", "booking_date", "fare", "amount_inr", "amount",
    "class", "trip_type", "booking_source", "route",
]
_PREFERRED_LOYALTY_ORDER = [
    "airline", "loyalty_program", "loyalty_program_name", "program_name",
    "loyalty_number", "current_tier", "pnr", "credited_pnr",
    "travel_date", "credited_travel_date", "activity_date",
    "miles_earned", "miles_credited", "description",
]


def _display_df(df: pd.DataFrame, col_labels: dict, preferred_order: list) -> pd.DataFrame:
    """Return a renamed, ordered DataFrame for display — only columns that exist."""
    if df is None or df.empty:
        return pd.DataFrame()
    cols_present = [c for c in preferred_order if c in df.columns]
    extra = [c for c in df.columns if c not in preferred_order]
    ordered = cols_present + extra
    out = df[ordered].rename(columns=col_labels)
    # Format dates nicely
    for col in out.columns:
        if "date" in col.lower() or "Date" in col:
            try:
                out[col] = pd.to_datetime(out[col], errors="coerce").dt.strftime("%d %b %Y")
            except Exception:
                pass
    return out


# ── Header ─────────────────────────────────────────────────────────────────────
st.title("FlightMode.ai — Travel Intelligence")
st.caption("Upload your travel data · review extracted records · get a full diagnostic report · chat with your data")

# ── Progress indicator ─────────────────────────────────────────────────────────
step = st.session_state.step
cols_prog = st.columns(3)
for i, (label, icon) in enumerate([
    ("Upload & Extract", "📂"),
    ("Review & Analyse", "🔍"),
    ("Report & Chat", "💬"),
], 1):
    with cols_prog[i - 1]:
        active = step == i
        done = step > i
        prefix = "✅ " if done else (f"{icon} " if active else "○ ")
        weight = "**" if active else ""
        st.markdown(f"{prefix}{weight}Step {i}: {label}{weight}")

st.divider()


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — Upload & Extract
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state.step == 1:
    st.subheader("Step 1 — Upload your travel data")
    st.markdown("Upload an **Excel / CSV** file (structured travel data) or a **PDF** (loyalty statement / travel report — analysed via AWS Bedrock).")

    uploaded_file = st.file_uploader(
        "Choose a file",
        type=["xlsx", "xls", "csv", "pdf"],
        label_visibility="collapsed",
    )

    if uploaded_file:
        file_size_kb = round(uploaded_file.size / 1024, 1)
        st.caption(f"📎 {uploaded_file.name}  ·  {file_size_kb} KB")
        suffix = os.path.splitext(uploaded_file.name)[1].lower()
        is_pdf = suffix == ".pdf"

        if is_pdf:
            st.info("PDF detected — FlightMode will use AWS Bedrock to extract travel and loyalty data from this document. This may take 30–90 seconds.")

        if st.button("Extract Data ▶", type="primary"):
            tmp_path = None
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp.write(uploaded_file.read())
                    tmp_path = tmp.name

                if is_pdf:
                    with st.status("Extracting data from PDF via Bedrock…", expanded=True) as status:
                        from bedrock_python.pdf_extractor import extract_from_pdfs
                        st.write("📄 Reading PDF pages with pdfplumber…")
                        extraction = extract_from_pdfs([tmp_path])
                        if extraction.extraction_errors:
                            for err in extraction.extraction_errors:
                                st.warning(err)
                        flights_count = len(extraction.flights)
                        loyalty_count = len(extraction.loyalty_credits)
                        st.write(f"✅ Extracted **{flights_count}** flight records and **{loyalty_count}** loyalty records")
                        status.update(label=f"Extraction complete — {flights_count} flights, {loyalty_count} loyalty records", state="complete", expanded=False)

                    flights_df = pd.DataFrame(extraction.flights) if extraction.flights else pd.DataFrame()
                    loyalty_df = pd.DataFrame(extraction.loyalty_credits) if extraction.loyalty_credits else pd.DataFrame()
                    st.session_state.file_type = "pdf"
                    st.session_state._pdf_flights = extraction.flights
                    st.session_state._pdf_loyalty = extraction.loyalty_credits

                else:
                    with st.status("Reading file…", expanded=True) as status:
                        from flightmode.core.ingestion import load_sheets
                        st.write("📂 Parsing sheets and mapping columns…")
                        travel_df, loyalty_df_raw = load_sheets(tmp_path)
                        st.write(f"✅ Loaded **{len(travel_df):,}** travel records")
                        if loyalty_df_raw is not None:
                            st.write(f"✅ Loaded **{len(loyalty_df_raw):,}** loyalty records")
                        status.update(label=f"File loaded — {len(travel_df):,} travel records", state="complete", expanded=False)

                    flights_df = travel_df
                    loyalty_df = loyalty_df_raw if loyalty_df_raw is not None else pd.DataFrame()
                    st.session_state.file_type = "xlsx"
                    st.session_state._xlsx_travel = travel_df
                    st.session_state._xlsx_loyalty = loyalty_df_raw

                st.session_state.flights_df = flights_df
                st.session_state.loyalty_df = loyalty_df
                st.session_state.source_name = uploaded_file.name
                st.session_state.step = 2
                st.rerun()

            except Exception as e:
                st.error(f"**Extraction failed:** {e}")
            finally:
                if tmp_path:
                    try:
                        os.unlink(tmp_path)
                    except Exception:
                        pass


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — Review extracted data + trigger analysis
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.step == 2:
    flights_df: pd.DataFrame = st.session_state.flights_df
    loyalty_df: pd.DataFrame = st.session_state.loyalty_df
    file_type = st.session_state.file_type

    st.subheader("Step 2 — Review Extracted Data")
    st.caption(f"Source: `{st.session_state.source_name}`")

    # Metric summary row
    n_flights = len(flights_df) if flights_df is not None and not flights_df.empty else 0
    n_loyalty = len(loyalty_df) if loyalty_df is not None and not loyalty_df.empty else 0
    n_airlines = 0
    if flights_df is not None and not flights_df.empty and "airline" in flights_df.columns:
        n_airlines = flights_df["airline"].nunique()

    m1, m2, m3 = st.columns(3)
    m1.metric("✈️ Flights Extracted", n_flights)
    m2.metric("🏢 Airlines", n_airlines)
    m3.metric("🎯 Loyalty Records", n_loyalty)

    st.markdown("---")

    # ── Travel Records Table ───────────────────────────────────────────────────
    st.markdown("#### Travel Records")
    if flights_df is not None and not flights_df.empty:
        display = _display_df(flights_df, _FLIGHT_COL_LABELS, _PREFERRED_FLIGHT_ORDER)
        st.dataframe(display, use_container_width=True, height=min(400, 60 + 35 * len(display)))
    else:
        st.info("No flight records were extracted from this file.")

    st.markdown("---")

    # ── Loyalty Records Table ──────────────────────────────────────────────────
    st.markdown("#### Loyalty Records")
    if loyalty_df is not None and not loyalty_df.empty:
        display_l = _display_df(loyalty_df, _LOYALTY_COL_LABELS, _PREFERRED_LOYALTY_ORDER)
        st.dataframe(display_l, use_container_width=True, height=min(350, 60 + 35 * len(display_l)))
    else:
        st.info("No loyalty records found in this file.")

    st.markdown("---")

    # ── Action buttons ─────────────────────────────────────────────────────────
    btn_col, reset_col = st.columns([3, 1])

    with reset_col:
        if st.button("← Upload Different File", type="secondary"):
            _reset()

    with btn_col:
        if n_flights == 0:
            st.warning("No flights were extracted — cannot run analysis. Try a different file.")
        else:
            if st.button("Run Full Analysis ▶", type="primary"):
                with st.status("Running diagnostics…", expanded=True) as status:
                    try:
                        from flightmode.report.generator import build_markdown_report
                        from flightmode.report.pdf import build_pdf

                        if file_type == "pdf":
                            from bedrock_python.analyzer import run_all, get_date_range
                            from bedrock_python.insights_generator import generate
                            from flightmode.report.generator import build_json_report, build_markdown_report
                            from flightmode.report.pdf import build_pdf

                            st.write("🔍 Running airline, booking, route & loyalty analysis…")
                            pdf_flights = st.session_state._pdf_flights or []
                            pdf_loyalty = st.session_state._pdf_loyalty or []
                            metrics = run_all(pdf_flights, pdf_loyalty)

                            st.write("💡 Generating insights via Bedrock…")
                            insights = generate(pdf_flights, pdf_loyalty, metrics)

                            st.write("📊 Building report…")
                            date_range = get_date_range(pdf_flights) or "PDF Analysis"
                            json_report = build_json_report(
                                airline_metrics=metrics["airline"],
                                booking_metrics=metrics["booking"],
                                route_metrics=metrics["routes"],
                                loyalty_metrics=metrics["loyalty"],
                                insights=insights,
                                source_file=st.session_state.source_name,
                                row_count=len(pdf_flights),
                                travel_df_meta={"date_range": date_range},
                            )

                        else:  # xlsx / csv
                            from flightmode.pipeline import run_pipeline

                            st.write("🔍 Running airline, booking, route & loyalty analysis…")
                            travel_df = st.session_state._xlsx_travel
                            loyalty_df_raw = st.session_state._xlsx_loyalty
                            result = run_pipeline(travel_df, loyalty_df_raw, source_file=st.session_state.source_name)
                            json_report = result["json_report"]
                            st.write("💡 Insights generated")
                            st.write("📊 Building report…")

                        markdown_report = build_markdown_report(json_report)
                        pdf_bytes = build_pdf(json_report)

                        st.session_state.json_report = json_report
                        st.session_state.markdown_report = markdown_report
                        st.session_state.pdf_bytes = pdf_bytes
                        st.session_state.step = 3
                        status.update(label="Analysis complete!", state="complete", expanded=False)
                        st.rerun()

                    except Exception as e:
                        status.update(label="Analysis failed", state="error", expanded=True)
                        st.error(f"**Analysis failed:** {e}")


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — Full Report + Chat
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.step == 3:
    # Top bar: source info + reset
    top_left, top_right = st.columns([6, 2])
    with top_left:
        st.subheader("Step 3 — Report & Chat")
        st.caption(f"Source: `{st.session_state.source_name}`")
    with top_right:
        st.write("")
        if st.button("← Start Over", type="secondary"):
            _reset()

    # PDF download
    if st.session_state.pdf_bytes:
        dl_col, _ = st.columns([3, 7])
        with dl_col:
            st.download_button(
                label="⬇  Download Report as PDF",
                data=st.session_state.pdf_bytes,
                file_name="FlightMode_Report.pdf",
                mime="application/pdf",
                use_container_width=True,
            )

    st.divider()

    # Full report
    st.markdown(st.session_state.markdown_report)

    st.divider()

    # ── Chat section ───────────────────────────────────────────────────────────
    st.subheader("💬 Chat with your Report")
    st.caption("Ask questions grounded in your travel data. Claude will only answer from your report — no hallucination.")

    # Render existing chat history
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input
    if prompt := st.chat_input("Ask about your travel report…  e.g. 'What is my top route?' or 'How can I improve my loyalty?'"):
        # Show user message immediately
        with st.chat_message("user"):
            st.markdown(prompt)

        # Get Bedrock response
        with st.chat_message("assistant"):
            with st.spinner("Thinking…"):
                from bedrock_python.chat import ask
                reply = ask(
                    question=prompt,
                    json_report=st.session_state.json_report,
                    history=st.session_state.chat_history,
                )
            st.markdown(reply)

        # Persist to history
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        st.session_state.chat_history.append({"role": "assistant", "content": reply})
