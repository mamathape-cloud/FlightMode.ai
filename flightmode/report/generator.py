"""
Steps 5 & 6: Report Generation

Produces:
1. Structured JSON (machine-readable)
2. Human-readable Markdown diagnostic report

All content is derived deterministically from metrics.
LLM prose generation is optional and invoked separately.
"""

import json
from datetime import datetime
from typing import Any, Optional


def build_json_report(
    airline_metrics: dict,
    booking_metrics: dict,
    route_metrics: dict,
    loyalty_metrics: dict,
    insights: list[dict],
    source_file: str,
    row_count: int,
    travel_df_meta: dict,
) -> dict:
    """Assemble the full structured JSON output."""
    return {
        "meta": {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "source_file": source_file,
            "total_flights_analyzed": row_count,
            "date_range": travel_df_meta.get("date_range"),
            "report_version": "1.0",
        },
        "airline_analysis": airline_metrics,
        "booking_behavior": booking_metrics,
        "route_analysis": route_metrics,
        "loyalty_leakage": loyalty_metrics,
        "insights": insights,
    }


def _fmt_dist_table(distribution: dict, key_label: str = "Airline") -> str:
    """Format a distribution dict as a Markdown table."""
    if not distribution:
        return "_No data available._\n"
    lines = [f"| {key_label} | Flights | Share |", "|---|---|---|"]
    for name, info in sorted(distribution.items(), key=lambda x: -x[1]["share_pct"]):
        lines.append(f"| {name} | {info['flights']} | {info['share_pct']}% |")
    return "\n".join(lines) + "\n"


def _fmt_route_table(top_routes: list) -> str:
    if not top_routes:
        return "_No route data available._\n"
    lines = ["| # | Route | Flights | Share |", "|---|---|---|---|"]
    for i, r in enumerate(top_routes, 1):
        lines.append(f"| {i} | {r['route']} | {r['count']} | {r['share_pct']}% |")
    return "\n".join(lines) + "\n"


def _fmt_gap_table(gap_distribution: dict) -> str:
    if not gap_distribution:
        return "_No booking gap data available._\n"
    lines = ["| Booking Window | Flights | Share |", "|---|---|---|"]
    for label, info in gap_distribution.items():
        lines.append(f"| {label} | {info['count']} | {info['pct']}% |")
    return "\n".join(lines) + "\n"


def _fmt_insight(insight: dict, idx: int) -> str:
    return (
        f"### Insight {idx}\n\n"
        f"**Observation:** {insight['observation']}\n\n"
        f"**Implication:** {insight['implication']}\n\n"
        f"**Recommendation:** {insight['recommendation']}\n\n"
        f"**Impact:** {insight['impact']}\n"
    )


def build_markdown_report(json_report: dict) -> str:
    """Convert the JSON report into a premium Markdown diagnostic document."""
    meta = json_report["meta"]
    airline = json_report["airline_analysis"]
    booking = json_report["booking_behavior"]
    routes = json_report["route_analysis"]
    loyalty = json_report["loyalty_leakage"]
    insights = json_report["insights"]

    date_range = meta.get("date_range") or "24-Month Period"
    total_flights = meta.get("total_flights_analyzed", 0)
    top_airline = airline.get("top_airline", "N/A")
    top_share = airline.get("top_airline_share_pct", 0)
    fragmented = airline.get("is_fragmented", False)
    avg_gap = booking.get("avg_booking_gap_days", "N/A")
    last_min_pct = booking.get("last_minute_pct", 0)
    most_freq_route = routes.get("most_frequent_route", "N/A")
    miles_lost = loyalty.get("estimated_miles_lost", 0)
    inr_value = loyalty.get("estimated_inr_value", 0)

    sections = []

    sections.append(f"""# FlightMode.ai — Travel Diagnostic Report

> Generated: {meta['generated_at'][:10]}  
> Source: `{meta['source_file']}`  
> Analysis Period: {date_range}

---
""")

    exec_flags = []
    if fragmented:
        exec_flags.append(f"⚠️ **Airline fragmentation detected** — top carrier holds only {top_share}% share")
    if last_min_pct > 30:
        exec_flags.append(f"⚠️ **High last-minute booking rate** — {last_min_pct}% within 3 days of travel")
    if loyalty.get("missing_credit_pct", 0) > 20:
        exec_flags.append(f"⚠️ **Loyalty leakage** — {loyalty.get('missing_credit_pct')}% of flights uncredited")
    if not exec_flags:
        exec_flags.append("✅ Travel program appears optimized — see recommendations for fine-tuning")

    sections.append(f"""## 1. Executive Summary

This report analyzes **{total_flights} flights** over {date_range}. Key findings:

{"  ".join(chr(10) + '- ' + f for f in exec_flags)}

**Total recoverable value identified:** ₹{inr_value + (30000 if last_min_pct > 30 else 0):,.0f}+

---
""")

    sections.append(f"""## 2. Travel Overview

| Metric | Value |
|---|---|
| Total Flights | {total_flights} |
| Unique Airlines | {airline.get('unique_airlines', 0)} |
| Unique Routes | {routes.get('unique_routes', 0)} |
| Analysis Period | {date_range} |
| Average Booking Lead Time | {avg_gap} days |
| Most Frequent Route | {most_freq_route} |

---
""")

    frag_label = "🔴 Fragmented" if fragmented else "🟢 Consolidated"
    sections.append(f"""## 3. Airline Utilization

**Status: {frag_label}**

Top airline: **{top_airline}** ({top_share}% share)

{_fmt_dist_table(airline.get('airline_distribution', {}))}

> **Rule:** If top airline share < 60%, the portfolio is considered fragmented.
> Fragmented portfolios forfeit tier status benefits worth ₹40,000–₹1,20,000 annually.

---
""")

    sections.append(f"""## 4. Booking Behavior

| Metric | Value |
|---|---|
| Average Booking Gap | {avg_gap} days |
| Median Booking Gap | {booking.get('median_booking_gap_days', 'N/A')} days |
| Last-Minute Bookings (≤3 days) | {booking.get('last_minute_count', 0)} ({last_min_pct}%) |
| Early Bookings (≥10 days) | {booking.get('early_booking_count', 0)} ({booking.get('early_booking_pct', 0)}%) |

**Booking Window Distribution:**

{_fmt_gap_table(booking.get('gap_distribution', {}))}

> **Rule:** Last-minute bookings (≤3 days) typically carry 30–80% fare premiums.

---
""")

    missing_credits = loyalty.get("missing_credits", 0)
    missing_pct = loyalty.get("missing_credit_pct", 0)
    loyalty_status = "🔴 Not available" if not loyalty.get("loyalty_data_available") else (
        "🔴 Significant leakage" if missing_pct > 20 else
        "🟡 Minor leakage" if missing_pct > 0 else
        "🟢 Fully credited"
    )

    sections.append(f"""## 5. Loyalty Leakage

**Status: {loyalty_status}**

| Metric | Value |
|---|---|
| Total Flights | {loyalty.get('total_flights', 0)} |
| Credited Flights | {loyalty.get('credited_flights', 0)} |
| Missing Credits | {missing_credits} ({missing_pct}%) |
| Estimated Miles Lost | {miles_lost:,} miles |
| Estimated INR Value | ₹{inr_value:,.0f} |

{"_Note: Loyalty data was not provided. Estimates based on average 1,500 miles/flight._" if not loyalty.get('loyalty_data_available') else ""}

---
""")

    sections.append("""## 6. Optimization Strategy

| Priority | Area | Action | Estimated Value |
|---|---|---|---|
| 🔴 High | Airline Consolidation | Concentrate 60%+ on primary airline | ₹40,000–₹1,20,000/year |
| 🔴 High | Booking Behavior | Shift to 10+ day advance booking | ₹30,000–₹80,000/year |
| 🟡 Medium | Loyalty Recovery | Retro-claim missing flight credits | Per miles lost (see above) |
| 🟡 Medium | Route Negotiation | Corporate rates on top routes | ₹25,000–₹60,000/route/year |
| 🟢 Low | Program Strategy | Align credit card to primary airline | ₹15,000–₹30,000/year |

---
""")

    action_items = [
        "**Within 7 days:** Identify your primary airline target based on route coverage and enroll in their top-tier program.",
        "**Within 14 days:** Retro-claim any missing flight credits (up to 12 months back).",
        "**Within 30 days:** Set a travel policy requiring minimum 10-day advance booking for all domestic travel.",
        "**Within 60 days:** Contact your primary airline's corporate sales team to negotiate route-specific rates.",
        "**Ongoing:** Review this report quarterly to track loyalty program progression and maintain consolidation discipline.",
    ]

    action_block = "\n".join(f"{i+1}. {item}" for i, item in enumerate(action_items))
    sections.append(f"""## 7. Action Plan

{action_block}

---
""")

    insight_blocks = "\n\n".join(
        _fmt_insight(ins, i + 1) for i, ins in enumerate(insights)
    )
    sections.append(f"""## Appendix: Detailed Insights

{insight_blocks}

---

*Report generated by FlightMode.ai — Deterministic Travel Intelligence System v1.0*
""")

    return "\n".join(sections)
