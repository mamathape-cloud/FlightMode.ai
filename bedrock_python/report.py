"""Generate a Markdown report from Bedrock pipeline results for display in Streamlit."""
import json


def _fmt_pct(val) -> str:
    if val is None:
        return "N/A"
    return f"{val * 100:.1f}%"


def _fmt_inr(val) -> str:
    if val is None:
        return "N/A"
    return f"₹{int(val):,}"


def generate_markdown(
    flights: list,
    loyalty_credits: list,
    metrics: dict,
    insights: list,
    source_notes: list | None = None,
) -> str:
    a = metrics["airline"]
    b = metrics["booking"]
    r = metrics["routes"]
    ly = metrics["loyalty"]

    lines = []

    # Header
    lines.append("## FlightMode.ai — Bedrock PDF Analysis")
    lines.append("")
    if source_notes:
        for note in source_notes:
            lines.append(f"> {note}")
        lines.append("")

    # Travel Overview
    lines.append("### Travel Overview")
    lines.append("")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Total Flights | **{a['total_flights']}** |")
    lines.append(f"| Unique Airlines | {a['unique_airlines']} |")
    lines.append(f"| Top Airline | **{a.get('top_airline') or 'N/A'}** ({_fmt_pct(a.get('top_airline_share'))}) |")
    lines.append(f"| Airline Fragmented? | {'Yes ⚠️' if a.get('fragmented') else 'No ✅'} |")
    lines.append(f"| Unique Routes | {r['unique_routes']} |")
    lines.append(f"| Most Frequent Route | **{r.get('top_route') or 'N/A'}** ({r.get('top_route_count', 0)}x) |")
    lines.append("")

    # Booking Behaviour
    lines.append("### Booking Behaviour")
    lines.append("")
    if b.get("avg_lead_days") is not None:
        lines.append(f"| Metric | Value |")
        lines.append(f"|--------|-------|")
        lines.append(f"| Average Lead Time | {b['avg_lead_days']} days |")
        lines.append(f"| Last-Minute Bookings (≤3 days) | {_fmt_pct(b.get('last_minute_pct'))} |")
        lines.append(f"| Early Bookings (≥10 days) | {_fmt_pct(b.get('early_booking_pct'))} |")
    else:
        lines.append(
            "_Booking dates are not available in loyalty program statements. "
            "Book via your travel portal to capture lead-time data._"
        )
    lines.append("")

    # Loyalty Summary
    lines.append("### Loyalty Programme Summary")
    lines.append("")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Total Activity Records | {ly['total_loyalty_activities']} |")
    lines.append(f"| Total Miles Earned | **{ly['total_miles_earned']:,}** |")
    lines.append(f"| Estimated Miles Value | **{_fmt_inr(ly['estimated_miles_value_inr'])}** |")
    lines.append(f"| Uncredited Flights | {ly['uncredited_flights']} |")
    lines.append(f"| Loyalty Leakage (est.) | {_fmt_inr(ly['leakage_value_inr'])} |")
    if ly.get("programs"):
        programs_str = ", ".join(f"{k} ({v})" for k, v in ly["programs"].items())
        lines.append(f"| Programmes | {programs_str} |")
    lines.append("")

    # Top Routes
    if r.get("route_distribution"):
        lines.append("### Top Routes")
        lines.append("")
        lines.append("| Route | Flights |")
        lines.append("|-------|---------|")
        for route, count in list(r["route_distribution"].items())[:8]:
            lines.append(f"| {route} | {count} |")
        lines.append("")

    # Insights
    lines.append("### Insights & Recommendations")
    lines.append("")
    for insight in insights:
        idx = insight.get("id", "")
        lines.append(f"#### {idx}. {insight.get('observation', '')[:80]}")
        lines.append("")
        lines.append(f"**Implication:** {insight.get('implication', '')}")
        lines.append("")
        lines.append(f"**Recommendation:** {insight.get('recommendation', '')}")
        lines.append("")
        lines.append(f"**Estimated Impact:** {insight.get('impact', '')}")
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)
