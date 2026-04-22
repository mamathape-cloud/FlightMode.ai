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
        "flights_df": None,
        "loyalty_df": None,
        "json_report": None,
        "markdown_report": None,
        "pdf_bytes": None,
        "chat_history": [],
        "file_type": None,
        "source_name": "",
        "_xlsx_travel": None,
        "_xlsx_loyalty": None,
        "_pdf_flights": None,
        "_pdf_loyalty": None,
        # staged_files: dict of {filename -> {name, size, data (bytes), suffix}}
        # bytes are read immediately on upload so they survive Streamlit reruns
        "staged_files": {},
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
    st.markdown("Upload **PDF loyalty statements** (analysed via AWS Bedrock) and/or **Excel / CSV** files. You can add files in multiple batches — each browse adds to the queue.")

    # ── File uploader — reads bytes immediately so files survive reruns ────────
    new_uploads = st.file_uploader(
        "Add files",
        type=["xlsx", "xls", "csv", "pdf"],
        accept_multiple_files=True,
        label_visibility="collapsed",
        key="file_uploader",
    )
    if new_uploads:
        for f in new_uploads:
            if f.name not in st.session_state.staged_files:
                st.session_state.staged_files[f.name] = {
                    "name": f.name,
                    "size": f.size,
                    "data": f.read(),
                    "suffix": os.path.splitext(f.name)[1].lower(),
                }

    staged = st.session_state.staged_files

    # ── Show queued files ──────────────────────────────────────────────────────
    if staged:
        st.markdown(f"**{len(staged)} file(s) queued:**")
        for fname, meta in list(staged.items()):
            col_name, col_size, col_remove = st.columns([6, 2, 1])
            icon = "📄" if meta["suffix"] == ".pdf" else "📊"
            col_name.markdown(f"{icon} {fname}")
            col_size.caption(f"{round(meta['size'] / 1024, 1)} KB")
            if col_remove.button("✕", key=f"rm_{fname}", help="Remove"):
                del st.session_state.staged_files[fname]
                st.rerun()

        pdfs = [m for m in staged.values() if m["suffix"] == ".pdf"]
        sheets = [m for m in staged.values() if m["suffix"] in (".xlsx", ".xls", ".csv")]

        if pdfs:
            st.info(f"{len(pdfs)} PDF(s) — will be extracted via AWS Bedrock (~30–90 s each).")
        if pdfs and sheets:
            st.warning("Mixed types — PDFs via Bedrock, Excel/CSV loaded separately, then merged.")

        col_extract, col_clear = st.columns([4, 1])
        with col_clear:
            if st.button("Clear all", type="secondary"):
                st.session_state.staged_files = {}
                st.rerun()

        with col_extract:
            if st.button("Extract Data ▶", type="primary"):
                tmp_paths = []
                try:
                    all_flights, all_loyalty = [], []
                    flights_df = pd.DataFrame()
                    loyalty_df = pd.DataFrame()

                    if pdfs:
                        pdf_tmp_paths = []
                        for meta in pdfs:
                            with tempfile.NamedTemporaryFile(delete=False, suffix=meta["suffix"]) as tmp:
                                tmp.write(meta["data"])
                                pdf_tmp_paths.append(tmp.name)
                                tmp_paths.append(tmp.name)

                        with st.status(f"Extracting {len(pdfs)} PDF(s) via Bedrock…", expanded=True) as status:
                            from bedrock_python.pdf_extractor import extract_from_pdfs
                            for i, meta in enumerate(pdfs, 1):
                                st.write(f"📄 [{i}/{len(pdfs)}] {meta['name']}…")
                            extraction = extract_from_pdfs(pdf_tmp_paths)
                            if extraction.extraction_errors:
                                for err in extraction.extraction_errors:
                                    st.warning(err)
                            fc, lc = len(extraction.flights), len(extraction.loyalty_credits)
                            st.write(f"✅ {fc} flight records · {lc} loyalty records extracted")
                            status.update(label=f"PDF extraction complete — {fc} flights, {lc} loyalty", state="complete", expanded=False)

                        all_flights.extend(extraction.flights)
                        all_loyalty.extend(extraction.loyalty_credits)

                    if sheets:
                        sheet_frames, loyalty_frames = [], []
                        with st.status(f"Reading {len(sheets)} Excel/CSV file(s)…", expanded=True) as status:
                            from flightmode.core.ingestion import load_sheets
                            for meta in sheets:
                                with tempfile.NamedTemporaryFile(delete=False, suffix=meta["suffix"]) as tmp:
                                    tmp.write(meta["data"])
                                    tmp_paths.append(tmp.name)
                                    tmp_name = tmp.name
                                st.write(f"📂 {meta['name']}…")
                                t_df, l_df = load_sheets(tmp_name)
                                sheet_frames.append(t_df)
                                if l_df is not None:
                                    loyalty_frames.append(l_df)

                            merged_travel = pd.concat(sheet_frames, ignore_index=True) if sheet_frames else pd.DataFrame()
                            merged_loyalty = pd.concat(loyalty_frames, ignore_index=True) if loyalty_frames else None
                            st.write(f"✅ {len(merged_travel):,} travel records loaded")
                            status.update(label=f"Excel/CSV loaded — {len(merged_travel):,} records", state="complete", expanded=False)

                        if pdfs:
                            if not merged_travel.empty:
                                all_flights.extend(merged_travel.to_dict("records"))
                            if merged_loyalty is not None:
                                all_loyalty.extend(merged_loyalty.to_dict("records"))
                        else:
                            st.session_state.file_type = "xlsx"
                            st.session_state._xlsx_travel = merged_travel
                            st.session_state._xlsx_loyalty = merged_loyalty
                            flights_df = merged_travel
                            loyalty_df = merged_loyalty if merged_loyalty is not None else pd.DataFrame()

                    if pdfs:
                        st.session_state.file_type = "pdf"
                        st.session_state._pdf_flights = all_flights
                        st.session_state._pdf_loyalty = all_loyalty
                        flights_df = pd.DataFrame(all_flights) if all_flights else pd.DataFrame()
                        loyalty_df = pd.DataFrame(all_loyalty) if all_loyalty else pd.DataFrame()

                    st.session_state.flights_df = flights_df
                    st.session_state.loyalty_df = loyalty_df
                    st.session_state.source_name = " + ".join(staged.keys())
                    st.session_state.step = 2
                    st.rerun()

                except Exception as e:
                    st.error(f"**Extraction failed:** {e}")
                finally:
                    for p in tmp_paths:
                        try:
                            os.unlink(p)
                        except Exception:
                            pass
    else:
        st.caption("No files queued yet — click **Browse files** above or drag and drop.")


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
