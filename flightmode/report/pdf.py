"""
PDF Report Generator for FlightMode.ai

Converts the structured JSON report into a downloadable PDF.
Uses fpdf2 (pure Python, no external binaries required).
"""

from __future__ import annotations

import io
from datetime import datetime
from typing import Any

from fpdf import FPDF, XPos, YPos


# ── Colour palette ─────────────────────────────────────────────────────────────
C_DARK    = (30,  30,  50)    # headings / body text
C_ACCENT  = (41,  98, 255)    # section bars
C_LIGHT   = (240, 243, 255)   # alternating table rows
C_WHITE   = (255, 255, 255)
C_RED     = (220,  50,  50)
C_GREEN   = (34,  139,  34)
C_YELLOW  = (200, 140,   0)
C_BORDER  = (200, 205, 220)


class _PDF(FPDF):
    """FPDF subclass with FlightMode branding."""

    def header(self) -> None:
        self.set_fill_color(*C_ACCENT)
        self.rect(0, 0, 210, 12, "F")
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*C_WHITE)
        self.set_xy(10, 2)
        self.cell(0, 8, "FlightMode.ai - Travel Intelligence Report", align="L")
        self.set_xy(0, 2)
        self.cell(200, 8, "CONFIDENTIAL", align="R")
        self.ln(8)

    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(150, 150, 160)
        self.cell(0, 8, f"Page {self.page_no()}  |  Generated {datetime.utcnow().strftime('%Y-%m-%d')}", align="C")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _section_bar(pdf: _PDF, title: str) -> None:
    pdf.ln(4)
    pdf.set_fill_color(*C_ACCENT)
    pdf.set_text_color(*C_WHITE)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, _safe(f"  {title}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)
    pdf.ln(2)
    pdf.set_text_color(*C_DARK)


def _kv_row(pdf: _PDF, label: str, value: str, shade: bool = False) -> None:
    if shade:
        pdf.set_fill_color(*C_LIGHT)
    else:
        pdf.set_fill_color(*C_WHITE)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*C_DARK)
    pdf.cell(70, 6, _safe(label), border="B", fill=True)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(0, 6, _safe(str(value)), border="B", new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)


def _table_header(pdf: _PDF, cols: list[tuple[str, int]]) -> None:
    pdf.set_fill_color(*C_ACCENT)
    pdf.set_text_color(*C_WHITE)
    pdf.set_font("Helvetica", "B", 8)
    for label, width in cols:
        pdf.cell(width, 6, _safe(label), border=1, fill=True)
    pdf.ln()
    pdf.set_text_color(*C_DARK)


def _table_row(pdf: _PDF, values: list[str], widths: list[int], shade: bool) -> None:
    if shade:
        pdf.set_fill_color(*C_LIGHT)
    else:
        pdf.set_fill_color(*C_WHITE)
    pdf.set_font("Helvetica", "", 8)
    for val, w in zip(values, widths):
        pdf.cell(w, 5, _safe(str(val)), border="B", fill=True)
    pdf.ln()


def _flag_color(label: str) -> tuple:
    ll = label.lower()
    if "red" in ll or "fragment" in ll or "high" in ll or "significant" in ll:
        return C_RED
    if "yellow" in ll or "minor" in ll or "medium" in ll:
        return C_YELLOW
    return C_GREEN


def _status_cell(pdf: _PDF, status: str) -> None:
    color = _flag_color(status)
    pdf.set_fill_color(*color)
    pdf.set_text_color(*C_WHITE)
    pdf.set_font("Helvetica", "B", 8)
    clean = _safe(
        status
        .replace("\U0001f534", "").replace("\U0001f7e2", "").replace("\U0001f7e1", "")
        .replace("\u26a0\ufe0f", "").replace("\u26a0", "")
        .strip()
    )
    pdf.cell(50, 6, clean, border=0, fill=True)
    pdf.set_text_color(*C_DARK)


def _safe(text: str) -> str:
    """Replace non-latin-1 characters with ASCII-safe equivalents."""
    return (
        str(text)
        .replace("\u2014", "-")    # em dash
        .replace("\u2013", "-")    # en dash
        .replace("\u2192", "->")   # →
        .replace("\u20b9", "Rs.")  # ₹
        .replace("\u26a0", "(!)")  # ⚠
        .replace("\ufe0f", "")     # variation selector
        .replace("\U0001f534", "[RED]")
        .replace("\U0001f7e2", "[GREEN]")
        .replace("\U0001f7e1", "[YELLOW]")
        .replace("\u2714", "OK")   # ✔
        .replace("\u2713", "OK")   # ✓
        .encode("latin-1", errors="replace").decode("latin-1")
    )


def _multiline(pdf: _PDF, text: str, indent: int = 0) -> None:
    """Write wrapped body text, stripping markdown markers."""
    text = text.replace("**", "").replace("*", "").replace("`", "")
    text = _safe(text)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_x(pdf.l_margin + indent)
    pdf.multi_cell(0, 5, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)


# ── Section builders ───────────────────────────────────────────────────────────

def _cover(pdf: _PDF, meta: dict) -> None:
    pdf.add_page()
    pdf.set_fill_color(*C_ACCENT)
    pdf.rect(0, 30, 210, 60, "F")

    pdf.set_xy(15, 42)
    pdf.set_font("Helvetica", "B", 26)
    pdf.set_text_color(*C_WHITE)
    pdf.cell(0, 12, "FlightMode.ai", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_x(15)
    pdf.set_font("Helvetica", "", 13)
    pdf.cell(0, 8, "Travel Intelligence Diagnostic Report", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_xy(15, 100)
    pdf.set_text_color(*C_DARK)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, _safe(f"Analysis Period : {meta.get('date_range', 'N/A')}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_x(15)
    pdf.cell(0, 6, _safe(f"Total Flights   : {meta.get('total_flights_analyzed', 0)}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_x(15)
    pdf.cell(0, 6, _safe(f"Generated       : {meta.get('generated_at', '')[:10]}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_x(15)
    source = str(meta.get("source_file", ""))
    if len(source) > 60:
        source = "..." + source[-57:]
    pdf.cell(0, 6, _safe(f"Source          : {source}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def _executive_summary(pdf: _PDF, report: dict) -> None:
    pdf.add_page()
    _section_bar(pdf, "1. Executive Summary")

    airline  = report.get("airline_analysis", {})
    booking  = report.get("booking_behavior", {})
    loyalty  = report.get("loyalty_leakage", {})
    meta     = report.get("meta", {})

    fragmented     = airline.get("is_fragmented", False)
    top_airline    = airline.get("top_airline", "N/A")
    top_share      = airline.get("top_airline_share_pct", 0)
    last_min_pct   = booking.get("last_minute_pct", 0)
    missing_pct    = loyalty.get("missing_credit_pct", 0)
    inr_value      = loyalty.get("estimated_inr_value", 0)
    total          = meta.get("total_flights_analyzed", 0)

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*C_DARK)
    pdf.multi_cell(
        0, 6,
        _safe(f"This report covers {total} flights. Key diagnostic findings are listed below."),
        new_x=XPos.LMARGIN, new_y=YPos.NEXT,
    )
    pdf.ln(2)

    flags = []
    if fragmented:
        flags.append(("(!) Airline fragmentation", f"{top_airline} holds only {top_share}% - below 60% threshold", "red"))
    else:
        flags.append(("OK  Airline consolidated", f"{top_airline} holds {top_share}%", "green"))
    if last_min_pct > 30:
        flags.append(("(!) High last-minute booking rate", f"{last_min_pct}% booked within 3 days before travel", "red"))
    if missing_pct > 20:
        flags.append(("(!) Loyalty leakage", f"{missing_pct}% of flights uncredited", "red"))

    for flag, detail, tone in flags:
        color = C_RED if tone == "red" else C_GREEN
        pdf.set_fill_color(*color)
        pdf.set_text_color(*C_WHITE)
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(80, 6, _safe(f"  {flag}"), fill=True, border=0)
        pdf.set_fill_color(*C_LIGHT)
        pdf.set_text_color(*C_DARK)
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(0, 6, _safe(f"  {detail}"), fill=True, border=0, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_fill_color(*C_ACCENT)
    pdf.set_text_color(*C_WHITE)
    pdf.cell(0, 7, _safe(f"  Total recoverable value identified: Rs.{inr_value:,.0f}+"),
             fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(*C_DARK)


def _airline_section(pdf: _PDF, airline: dict) -> None:
    _section_bar(pdf, "2. Airline Utilization")

    fragmented = airline.get("is_fragmented", False)
    status_str = "🔴 Fragmented" if fragmented else "🟢 Consolidated"
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(30, 6, "Status: ")
    _status_cell(pdf, status_str)
    pdf.ln(8)

    _kv_row(pdf, "Top Airline",        f"{airline.get('top_airline', 'N/A')}  ({airline.get('top_airline_share_pct', 0)}%)", shade=False)
    _kv_row(pdf, "Unique Airlines",    str(airline.get("unique_airlines", 0)), shade=True)
    _kv_row(pdf, "Total Flights",      str(airline.get("total_flights", 0)), shade=False)
    pdf.ln(4)

    dist = airline.get("airline_distribution", {})
    if dist:
        cols = [("Airline", 90), ("Flights", 30), ("Share %", 30)]
        widths = [c[1] for c in cols]
        _table_header(pdf, cols)
        for i, (name, info) in enumerate(
            sorted(dist.items(), key=lambda x: -x[1]["share_pct"])
        ):
            _table_row(pdf, [name, str(info["flights"]), f"{info['share_pct']}%"], widths, shade=i % 2 == 1)


def _booking_section(pdf: _PDF, booking: dict) -> None:
    _section_bar(pdf, "3. Booking Behavior")

    _kv_row(pdf, "Average Booking Gap",            f"{booking.get('avg_booking_gap_days', 'N/A')} days", shade=False)
    _kv_row(pdf, "Median Booking Gap",             f"{booking.get('median_booking_gap_days', 'N/A')} days", shade=True)
    _kv_row(pdf, "Last-Minute (≤3 days)",          f"{booking.get('last_minute_count', 0)} trips  ({booking.get('last_minute_pct', 0)}%)", shade=False)
    _kv_row(pdf, "Early Bookings (≥10 days)",      f"{booking.get('early_booking_count', 0)} trips  ({booking.get('early_booking_pct', 0)}%)", shade=True)
    pdf.ln(4)

    gap = booking.get("gap_distribution", {})
    if gap:
        cols = [("Booking Window", 90), ("Flights", 30), ("Share %", 30)]
        widths = [c[1] for c in cols]
        _table_header(pdf, cols)
        for i, (label, info) in enumerate(gap.items()):
            _table_row(pdf, [label, str(info["count"]), f"{info['pct']}%"], widths, shade=i % 2 == 1)


def _route_section(pdf: _PDF, routes: dict) -> None:
    _section_bar(pdf, "4. Route Analysis")

    _kv_row(pdf, "Total Flights",         str(routes.get("total_routes_flown", 0)), shade=False)
    _kv_row(pdf, "Unique Routes",         str(routes.get("unique_routes", 0)), shade=True)
    _kv_row(pdf, "Most Frequent Route",   f"{routes.get('most_frequent_route', 'N/A')}  ({routes.get('most_frequent_route_count', 0)} flights)", shade=False)
    _kv_row(pdf, "Repeated Route %",      f"{routes.get('repeated_route_pct', 0)}%", shade=True)
    pdf.ln(4)

    top = routes.get("top_routes", [])
    if top:
        cols = [("#", 10), ("Route", 80), ("Flights", 30), ("Share %", 30)]
        widths = [c[1] for c in cols]
        _table_header(pdf, cols)
        for i, r in enumerate(top[:10]):
            _table_row(pdf, [str(i+1), r["route"], str(r["count"]), f"{r['share_pct']}%"], widths, shade=i % 2 == 1)


def _loyalty_section(pdf: _PDF, loyalty: dict) -> None:
    _section_bar(pdf, "5. Loyalty Leakage")

    missing_pct = loyalty.get("missing_credit_pct", 0)
    if not loyalty.get("loyalty_data_available"):
        status = "🔴 Not available"
    elif missing_pct > 20:
        status = "🔴 Significant leakage"
    elif missing_pct > 0:
        status = "🟡 Minor leakage"
    else:
        status = "🟢 Fully credited"

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(30, 6, "Status: ")
    _status_cell(pdf, status)
    pdf.ln(8)

    _kv_row(pdf, "Total Flights",         str(loyalty.get("total_flights", 0)), shade=False)
    _kv_row(pdf, "Credited Flights",      str(loyalty.get("credited_flights", 0)), shade=True)
    _kv_row(pdf, "Missing Credits",       f"{loyalty.get('missing_credits', 0)} ({missing_pct}%)", shade=False)
    _kv_row(pdf, "Estimated Miles Lost",  f"{loyalty.get('estimated_miles_lost', 0):,} miles", shade=True)
    _kv_row(pdf, "Estimated INR Value",   f"₹{loyalty.get('estimated_inr_value', 0):,.0f}", shade=False)


def _insights_section(pdf: _PDF, insights: list[dict]) -> None:
    _section_bar(pdf, "6. Insights & Recommendations")

    for ins in insights:
        idx = ins.get("id", "")
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_fill_color(*C_LIGHT)
        pdf.set_text_color(*C_ACCENT)
        pdf.cell(0, 7, _safe(f"  Insight {idx}"), fill=True, border=0, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_text_color(*C_DARK)

        for key, label in [
            ("observation",    "Observation"),
            ("implication",    "Implication"),
            ("recommendation", "Recommendation"),
            ("impact",         "Impact"),
        ]:
            val = ins.get(key, "")
            if val:
                pdf.set_font("Helvetica", "B", 8)
                pdf.cell(32, 5, f"  {label}:")
                pdf.set_font("Helvetica", "", 8)
                pdf.multi_cell(0, 5, _safe(val), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(2)


def _action_plan(pdf: _PDF) -> None:
    _section_bar(pdf, "7. Action Plan")

    items = [
        ("Within 7 days",  "Identify your primary airline target and enroll in their top-tier program."),
        ("Within 14 days", "Retro-claim any missing flight credits (up to 12 months back)."),
        ("Within 30 days", "Set a travel policy requiring minimum 10-day advance booking for domestic."),
        ("Within 60 days", "Contact your primary airline's corporate sales team for route-specific rates."),
        ("Ongoing",        "Review this report quarterly to track loyalty program progression."),
    ]
    for i, (when, what) in enumerate(items):
        shade = i % 2 == 1
        pdf.set_fill_color(*(C_LIGHT if shade else C_WHITE))
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(32, 6, _safe(f"  {when}"), fill=True, border="B")
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(0, 6, _safe(what), border="B", fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)


# ── Public API ─────────────────────────────────────────────────────────────────

def build_pdf(json_report: dict) -> bytes:
    """
    Convert the structured JSON report into a PDF and return raw bytes.

    Args:
        json_report: The dict produced by build_json_report().

    Returns:
        PDF as bytes, ready for st.download_button() or file.write().
    """
    pdf = _PDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_margins(15, 18, 15)

    meta    = json_report.get("meta", {})
    airline = json_report.get("airline_analysis", {})
    booking = json_report.get("booking_behavior", {})
    routes  = json_report.get("route_analysis", {})
    loyalty = json_report.get("loyalty_leakage", {})
    insights = json_report.get("insights", [])

    _cover(pdf, meta)
    _executive_summary(pdf, json_report)

    pdf.add_page()
    _airline_section(pdf, airline)
    pdf.ln(4)
    _booking_section(pdf, booking)

    pdf.add_page()
    _route_section(pdf, routes)
    pdf.ln(4)
    _loyalty_section(pdf, loyalty)

    pdf.add_page()
    _insights_section(pdf, insights)

    pdf.add_page()
    _action_plan(pdf)

    return bytes(pdf.output())
