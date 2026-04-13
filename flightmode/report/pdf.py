"""
PDF Report Generator for FlightMode.ai — Professional Edition

Charts drawn with fpdf2 native drawing primitives (no matplotlib).
No external dependencies beyond fpdf2.
"""

from __future__ import annotations

from datetime import datetime

from fpdf import FPDF, XPos, YPos

# ── Colour palette ─────────────────────────────────────────────────────────────
C_DARK    = (30,  30,  50)      # body text
C_ACCENT  = (17,  17,  17)      # section bars, header — black
C_LIGHT   = (245, 245, 245)     # alternating rows / stat box bg
C_MID     = (200, 200, 200)     # borders / dividers
C_WHITE   = (255, 255, 255)
C_RED     = (210,  50,  50)
C_GREEN   = (34,  139,  34)
C_YELLOW  = (200, 140,   0)
C_CHART   = (60,  60,  60)      # bar chart fill (dark grey)
C_CHART2  = (120, 120, 120)     # secondary bar colour
C_SUBHEAD = (80,  80,  100)     # sub-heading text

# Page geometry (A4 portrait)
PAGE_W    = 210
LMARGIN   = 15
RMARGIN   = 15
BODY_W    = PAGE_W - LMARGIN - RMARGIN   # 180mm
TOP_MARGIN = 22   # clear the 12mm header bar + 10mm breathing room


# ── Helpers ────────────────────────────────────────────────────────────────────

def _safe(text: str) -> str:
    """Sanitise Unicode to latin-1 for core PDF fonts."""
    return (
        str(text)
        .replace("\u2014", "-").replace("\u2013", "-")
        .replace("\u2192", "->").replace("\u20b9", "Rs.")
        .replace("\u26a0\ufe0f", "(!)").replace("\u26a0", "(!)")
        .replace("\ufe0f", "")
        .replace("\U0001f534", "").replace("\U0001f7e2", "").replace("\U0001f7e1", "")
        .replace("\u2714", "").replace("\u2713", "")
        .replace("\u2248", "~").replace("\u2265", ">=").replace("\u2264", "<=")
        .encode("latin-1", errors="replace").decode("latin-1")
    )


def _flag_color(label: str) -> tuple:
    ll = label.lower()
    if any(w in ll for w in ("red", "fragment", "high", "significant", "not available")):
        return C_RED
    if any(w in ll for w in ("yellow", "minor", "medium")):
        return C_YELLOW
    return C_GREEN


# ── PDF class ──────────────────────────────────────────────────────────────────

class _PDF(FPDF):
    def header(self) -> None:
        # Solid black banner
        self.set_fill_color(*C_ACCENT)
        self.rect(0, 0, PAGE_W, 13, "F")
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(*C_WHITE)
        self.set_xy(LMARGIN, 3)
        self.cell(BODY_W - 30, 7, "FlightMode.ai  -  Travel Intelligence Report", align="L")
        self.set_xy(0, 3)
        self.cell(PAGE_W - LMARGIN, 7, "CONFIDENTIAL", align="R")
        # Advance cursor well below the banner so content never overlaps
        self.set_xy(LMARGIN, TOP_MARGIN)

    def footer(self) -> None:
        self.set_y(-11)
        self.set_draw_color(*C_MID)
        self.line(LMARGIN, self.get_y(), PAGE_W - RMARGIN, self.get_y())
        self.set_font("Helvetica", "", 7)
        self.set_text_color(*C_SUBHEAD)
        self.cell(
            0, 8,
            _safe(f"Page {self.page_no()}   |   Generated {datetime.utcnow().strftime('%d %b %Y')}   |   FlightMode.ai"),
            align="C",
        )


# ── Typography helpers ─────────────────────────────────────────────────────────

def _section_bar(pdf: _PDF, title: str) -> None:
    """Full-width black section heading bar."""
    pdf.ln(5)
    pdf.set_fill_color(*C_ACCENT)
    pdf.set_text_color(*C_WHITE)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(BODY_W, 8, _safe(f"  {title}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)
    pdf.ln(3)
    pdf.set_text_color(*C_DARK)


def _sub_label(pdf: _PDF, text: str) -> None:
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*C_SUBHEAD)
    pdf.cell(0, 5, _safe(text.upper()), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(*C_DARK)


def _body(pdf: _PDF, text: str) -> None:
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*C_DARK)
    pdf.multi_cell(BODY_W, 5, _safe(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def _divider(pdf: _PDF) -> None:
    pdf.set_draw_color(*C_MID)
    pdf.line(LMARGIN, pdf.get_y() + 1, PAGE_W - RMARGIN, pdf.get_y() + 1)
    pdf.ln(3)


# ── Stat box grid ──────────────────────────────────────────────────────────────

def _stat_box(pdf: _PDF, x: float, y: float, w: float, h: float,
              label: str, value: str, sub: str = "", color: tuple = C_ACCENT) -> None:
    """Draw a single metric box."""
    # Border
    pdf.set_draw_color(*C_MID)
    pdf.set_fill_color(*C_LIGHT)
    pdf.rect(x, y, w, h, "DF")
    # Coloured top accent strip
    pdf.set_fill_color(*color)
    pdf.rect(x, y, w, 2, "F")
    # Label
    pdf.set_xy(x + 3, y + 4)
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(*C_SUBHEAD)
    pdf.cell(w - 6, 5, _safe(label.upper()))
    # Value
    pdf.set_xy(x + 3, y + 10)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(*C_ACCENT)
    pdf.cell(w - 6, 7, _safe(str(value)))
    # Sub text
    if sub:
        pdf.set_xy(x + 3, y + 18)
        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(*C_SUBHEAD)
        pdf.cell(w - 6, 4, _safe(sub))
    pdf.set_text_color(*C_DARK)


# ── Chart helpers ──────────────────────────────────────────────────────────────

def _horiz_bar_chart(
    pdf: _PDF,
    data: list[tuple[str, float]],   # (label, pct_0_to_100)
    chart_w: float = BODY_W,
    bar_h: float = 6.5,
    max_items: int = 8,
    palette: list[tuple] | None = None,
) -> None:
    """
    Draw a horizontal bar chart using fpdf2 rect() primitives.
    data: list of (label, value_0_to_100)
    """
    if not data:
        return

    data = data[:max_items]
    max_val = max(v for _, v in data) or 1

    label_w = 52
    bar_area = chart_w - label_w - 18   # 18mm for value text
    gap = 2.5

    default_palette = [C_CHART, C_CHART2, (100, 100, 100), (140, 140, 140), (170, 170, 170)]
    palette = palette or default_palette

    for i, (label, val) in enumerate(data):
        y = pdf.get_y()

        # Label
        pdf.set_xy(LMARGIN, y)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*C_DARK)
        # Truncate label
        lbl = _safe(label)[:24]
        pdf.cell(label_w, bar_h, lbl, align="R")

        # Bar background
        bx = LMARGIN + label_w + 2
        by = y + 1
        pdf.set_fill_color(*C_LIGHT)
        pdf.set_draw_color(*C_MID)
        pdf.rect(bx, by, bar_area, bar_h - 2, "DF")

        # Bar fill
        fill_w = max(1.0, (val / max_val) * bar_area)
        color = palette[i % len(palette)]
        pdf.set_fill_color(*color)
        pdf.rect(bx, by, fill_w, bar_h - 2, "F")

        # Value label
        pdf.set_xy(bx + bar_area + 2, y)
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(*C_DARK)
        pdf.cell(16, bar_h, f"{val:.1f}%", align="L")

        pdf.ln(bar_h + gap)

    pdf.set_text_color(*C_DARK)


# ── Table helpers ──────────────────────────────────────────────────────────────

def _table_header(pdf: _PDF, cols: list[tuple[str, float]]) -> None:
    pdf.set_fill_color(*C_ACCENT)
    pdf.set_text_color(*C_WHITE)
    pdf.set_font("Helvetica", "B", 8)
    for label, w in cols:
        pdf.cell(w, 6, _safe(label), border=1, fill=True, align="C")
    pdf.ln()
    pdf.set_text_color(*C_DARK)


def _table_row(pdf: _PDF, values: list[str], widths: list[float],
               shade: bool, aligns: list[str] | None = None) -> None:
    aligns = aligns or ["L"] * len(values)
    pdf.set_fill_color(*(C_LIGHT if shade else C_WHITE))
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*C_DARK)
    for val, w, a in zip(values, widths, aligns):
        pdf.cell(w, 5.5, _safe(str(val)), border="B", fill=True, align=a)
    pdf.ln()


def _kv_row(pdf: _PDF, label: str, value: str, shade: bool = False) -> None:
    pdf.set_fill_color(*(C_LIGHT if shade else C_WHITE))
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*C_SUBHEAD)
    pdf.cell(70, 6, _safe(label), border="B", fill=True)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*C_DARK)
    pdf.cell(BODY_W - 70, 6, _safe(str(value)), border="B",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)


def _status_pill(pdf: _PDF, status: str) -> None:
    color = _flag_color(status)
    clean = _safe(
        status.replace("Not available", "Not Available")
              .replace("Significant leakage", "Significant Leakage")
              .replace("Minor leakage", "Minor Leakage")
              .replace("Fully credited", "Fully Credited")
    )
    pdf.set_fill_color(*color)
    pdf.set_text_color(*C_WHITE)
    pdf.set_font("Helvetica", "B", 8)
    pdf.cell(45, 6, f"  {clean}", fill=True, border=0)
    pdf.set_text_color(*C_DARK)


# ── Section builders ───────────────────────────────────────────────────────────

def _cover(pdf: _PDF, meta: dict) -> None:
    pdf.add_page()

    # Large black banner
    pdf.set_fill_color(*C_ACCENT)
    pdf.rect(0, 25, PAGE_W, 55, "F")

    # Brand name
    pdf.set_xy(LMARGIN, 36)
    pdf.set_font("Helvetica", "B", 28)
    pdf.set_text_color(*C_WHITE)
    pdf.cell(0, 13, "FlightMode.ai", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_x(LMARGIN)
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 7, "Travel Intelligence Diagnostic Report", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # Thin accent rule below banner
    pdf.set_fill_color(*C_MID)
    pdf.rect(0, 80, PAGE_W, 0.5, "F")

    # Metadata block
    pdf.set_xy(LMARGIN, 92)
    pdf.set_text_color(*C_DARK)
    pdf.set_font("Helvetica", "", 10)

    meta_items = [
        ("Analysis Period", meta.get("date_range", "N/A")),
        ("Total Flights Analysed", str(meta.get("total_flights_analyzed", 0))),
        ("Report Generated", meta.get("generated_at", "")[:10]),
        ("Source File", (str(meta.get("source_file", ""))[:55] + "...") if len(str(meta.get("source_file", ""))) > 55 else str(meta.get("source_file", ""))),
    ]
    for label, val in meta_items:
        pdf.set_x(LMARGIN)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*C_SUBHEAD)
        pdf.cell(55, 7, _safe(label + ":"))
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*C_DARK)
        pdf.cell(0, 7, _safe(val), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # Disclaimer at bottom
    pdf.set_y(260)
    pdf.set_font("Helvetica", "I", 7)
    pdf.set_text_color(*C_SUBHEAD)
    pdf.multi_cell(BODY_W, 4,
        "This report is generated by FlightMode.ai using deterministic analytics. "
        "All figures are derived from the uploaded dataset.",
        new_x=XPos.LMARGIN, new_y=YPos.NEXT,
    )


def _executive_summary(pdf: _PDF, report: dict) -> None:
    airline = report.get("airline_analysis", {})
    booking = report.get("booking_behavior", {})
    loyalty = report.get("loyalty_leakage", {})
    meta    = report.get("meta", {})

    fragmented   = airline.get("is_fragmented", False)
    top_airline  = airline.get("top_airline", "N/A")
    top_share    = airline.get("top_airline_share_pct", 0)
    last_min_pct = booking.get("last_minute_pct", 0)
    missing_pct  = loyalty.get("missing_credit_pct", 0)
    inr_value    = loyalty.get("estimated_inr_value", 0)
    total        = meta.get("total_flights_analyzed", 0)
    avg_gap      = booking.get("avg_booking_gap_days", "N/A")

    _section_bar(pdf, "1. Executive Summary")

    _body(pdf, f"Analysis of {total} flights. Key diagnostic findings are highlighted below.")
    pdf.ln(3)

    # ── 4-box KPI grid ────────────────────────────────────────────────────────
    bw = (BODY_W - 6) / 4
    bh = 26
    by = pdf.get_y()
    bx = LMARGIN
    gap = 2

    _stat_box(pdf, bx,            by, bw, bh, "Total Flights",    str(total),    "", C_ACCENT)
    _stat_box(pdf, bx+bw+gap,     by, bw, bh, "Top Airline",      str(top_airline), f"{top_share}% share",
              C_GREEN if not fragmented else C_RED)
    _stat_box(pdf, bx+2*(bw+gap), by, bw, bh, "Avg Booking Gap",  f"{avg_gap}d", "lead time", C_ACCENT)
    _stat_box(pdf, bx+3*(bw+gap), by, bw, bh, "Recoverable Value", f"Rs.{inr_value/1000:.0f}K", "estimated", C_ACCENT)

    pdf.set_xy(LMARGIN, by + bh + 5)

    # ── Flag rows ─────────────────────────────────────────────────────────────
    flags = []
    if fragmented:
        flags.append(("(!) Airline fragmentation", f"{top_airline} holds only {top_share}% - below 60% threshold", "red"))
    else:
        flags.append(("OK  Airline consolidated", f"{top_airline} holds {top_share}% - above threshold", "green"))
    if last_min_pct > 30:
        flags.append(("(!) Last-minute bookings", f"{last_min_pct}% of trips booked within 3 days of travel", "red"))
    if missing_pct > 20:
        flags.append(("(!) Loyalty leakage", f"{missing_pct}% of flights have no loyalty credit", "red"))

    for flag, detail, tone in flags:
        c_flag = C_RED if tone == "red" else C_GREEN
        pdf.set_fill_color(*c_flag)
        pdf.set_text_color(*C_WHITE)
        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(58, 6, _safe(f"  {flag}"), fill=True, border=0)
        pdf.set_fill_color(*C_LIGHT)
        pdf.set_text_color(*C_DARK)
        pdf.set_font("Helvetica", "", 8)
        pdf.cell(BODY_W - 58, 6, _safe(f"  {detail}"), fill=True, border=0,
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)


def _airline_section(pdf: _PDF, airline: dict) -> None:
    _section_bar(pdf, "2. Airline Utilization")

    fragmented = airline.get("is_fragmented", False)
    dist = airline.get("airline_distribution", {})

    # Status + key stats side by side
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*C_SUBHEAD)
    pdf.cell(28, 6, "Status:")
    _status_pill(pdf, "Fragmented" if fragmented else "Consolidated")
    pdf.ln(8)

    # Horizontal bar chart
    if dist:
        _sub_label(pdf, "Airline Share Distribution")
        pdf.ln(1)
        chart_data = [
            (name, info["share_pct"])
            for name, info in sorted(dist.items(), key=lambda x: -x[1]["share_pct"])
        ]
        _horiz_bar_chart(pdf, chart_data)
        pdf.ln(2)

    # Summary table
    _sub_label(pdf, "Summary")
    _kv_row(pdf, "Top Airline",    f"{airline.get('top_airline', 'N/A')} ({airline.get('top_airline_share_pct', 0)}%)", shade=False)
    _kv_row(pdf, "Unique Airlines", str(airline.get("unique_airlines", 0)), shade=True)
    _kv_row(pdf, "Total Flights",   str(airline.get("total_flights", 0)), shade=False)
    pdf.ln(3)


def _booking_section(pdf: _PDF, booking: dict) -> None:
    _section_bar(pdf, "3. Booking Behavior")

    gap_dist = booking.get("gap_distribution", {})

    # Bar chart of booking window distribution
    if gap_dist:
        _sub_label(pdf, "Booking Window Distribution")
        pdf.ln(1)
        chart_data = [(label, info["pct"]) for label, info in gap_dist.items()]
        _horiz_bar_chart(pdf, chart_data)
        pdf.ln(2)

    # Key metrics table
    _sub_label(pdf, "Key Metrics")
    _kv_row(pdf, "Average Booking Gap",       f"{booking.get('avg_booking_gap_days', 'N/A')} days", shade=False)
    _kv_row(pdf, "Median Booking Gap",        f"{booking.get('median_booking_gap_days', 'N/A')} days", shade=True)
    _kv_row(pdf, "Last-Minute Bookings",      f"{booking.get('last_minute_count', 0)} trips  ({booking.get('last_minute_pct', 0)}%)", shade=False)
    _kv_row(pdf, "Early Bookings (>=10 days)", f"{booking.get('early_booking_count', 0)} trips  ({booking.get('early_booking_pct', 0)}%)", shade=True)
    pdf.ln(3)


def _route_section(pdf: _PDF, routes: dict) -> None:
    _section_bar(pdf, "4. Route Analysis")

    top = routes.get("top_routes", [])

    # Bar chart of top routes
    if top:
        _sub_label(pdf, "Top Routes by Frequency")
        pdf.ln(1)
        chart_data = [(r["route"], r["share_pct"]) for r in top[:8]]
        _horiz_bar_chart(pdf, chart_data)
        pdf.ln(2)

    # Summary stats
    _sub_label(pdf, "Summary")
    _kv_row(pdf, "Total Flights",        str(routes.get("total_routes_flown", 0)), shade=False)
    _kv_row(pdf, "Unique Routes",        str(routes.get("unique_routes", 0)), shade=True)
    _kv_row(pdf, "Most Frequent Route",  f"{routes.get('most_frequent_route', 'N/A')}  ({routes.get('most_frequent_route_count', 0)} flights)", shade=False)
    _kv_row(pdf, "Repeated Route %",     f"{routes.get('repeated_route_pct', 0)}%", shade=True)
    pdf.ln(3)


def _loyalty_section(pdf: _PDF, loyalty: dict) -> None:
    _section_bar(pdf, "5. Loyalty Leakage")

    missing_pct = loyalty.get("missing_credit_pct", 0)
    if not loyalty.get("loyalty_data_available"):
        status = "Not available"
    elif missing_pct > 20:
        status = "Significant leakage"
    elif missing_pct > 0:
        status = "Minor leakage"
    else:
        status = "Fully credited"

    # Leakage bar visualisation
    total_fl = loyalty.get("total_flights", 0)
    credited = loyalty.get("credited_flights", 0)
    missing  = loyalty.get("missing_credits", 0)

    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*C_SUBHEAD)
    pdf.cell(25, 6, "Status:")
    _status_pill(pdf, status)
    pdf.ln(8)

    if total_fl > 0:
        _sub_label(pdf, "Credit Coverage")
        pdf.ln(1)
        chart_data = [
            ("Credited Flights", round(credited / total_fl * 100, 1)),
            ("Missing Credits",  round(missing  / total_fl * 100, 1)),
        ]
        _horiz_bar_chart(pdf, chart_data,
                         palette=[C_GREEN, C_RED])
        pdf.ln(2)

    _sub_label(pdf, "Metrics")
    _kv_row(pdf, "Total Flights",        str(total_fl), shade=False)
    _kv_row(pdf, "Credited Flights",     str(credited), shade=True)
    _kv_row(pdf, "Missing Credits",      f"{missing} ({missing_pct}%)", shade=False)
    _kv_row(pdf, "Est. Miles Lost",      f"{loyalty.get('estimated_miles_lost', 0):,} miles", shade=True)
    _kv_row(pdf, "Est. INR Value",       f"Rs.{loyalty.get('estimated_inr_value', 0):,.0f}", shade=False)
    pdf.ln(3)


def _insights_section(pdf: _PDF, insights: list[dict]) -> None:
    _section_bar(pdf, "6. Insights & Recommendations")

    for ins in insights:
        idx = ins.get("id", "")
        # Insight sub-heading
        pdf.set_fill_color(*C_LIGHT)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*C_DARK)
        pdf.cell(BODY_W, 6, _safe(f"  Insight {idx}"),
                 fill=True, border="B", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        for key, label in [
            ("observation",    "Observation"),
            ("implication",    "Implication"),
            ("recommendation", "Recommendation"),
            ("impact",         "Impact"),
        ]:
            val = ins.get(key, "")
            if not val:
                continue
            pdf.set_xy(LMARGIN + 3, pdf.get_y())
            pdf.set_font("Helvetica", "B", 8)
            pdf.set_text_color(*C_SUBHEAD)
            pdf.cell(28, 5, _safe(f"{label}:"))
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(*C_DARK)
            pdf.multi_cell(BODY_W - 31, 5, _safe(val),
                           new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(2)


def _action_plan(pdf: _PDF) -> None:
    _section_bar(pdf, "7. Action Plan")

    items = [
        ("Within 7 days",  "Identify your primary airline target and enroll in their top-tier program."),
        ("Within 14 days", "Retro-claim any missing flight credits (most programs allow 12-month retro-claims)."),
        ("Within 30 days", "Set a travel policy requiring minimum 10-day advance booking for domestic travel."),
        ("Within 60 days", "Contact your primary airline's corporate sales team to negotiate route rates."),
        ("Ongoing",        "Review this report quarterly to track loyalty program progression."),
    ]

    cols  = [("Timeframe", 38), ("Action", BODY_W - 38)]
    widths = [c[1] for c in cols]
    aligns = ["C", "L"]
    _table_header(pdf, cols)
    for i, (when, what) in enumerate(items):
        _table_row(pdf, [when, what], widths, shade=i % 2 == 1, aligns=aligns)
    pdf.ln(3)


# ── Public API ─────────────────────────────────────────────────────────────────

def build_pdf(json_report: dict) -> bytes:
    """
    Build a professional PDF from the structured JSON report.
    Returns raw bytes for st.download_button().
    """
    pdf = _PDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.set_margins(LMARGIN, TOP_MARGIN, RMARGIN)

    meta     = json_report.get("meta", {})
    airline  = json_report.get("airline_analysis", {})
    booking  = json_report.get("booking_behavior", {})
    routes   = json_report.get("route_analysis", {})
    loyalty  = json_report.get("loyalty_leakage", {})
    insights = json_report.get("insights", [])

    # Cover on its own page; all content flows continuously after that
    _cover(pdf, meta)

    pdf.add_page()
    _executive_summary(pdf, json_report)
    _airline_section(pdf, airline)
    _booking_section(pdf, booking)
    _route_section(pdf, routes)
    _loyalty_section(pdf, loyalty)
    _insights_section(pdf, insights)
    _action_plan(pdf)

    return bytes(pdf.output())
