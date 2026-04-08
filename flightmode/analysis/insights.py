"""
Step 4: Insight Engine

Converts deterministic metrics into structured insights.
All thresholds and rules are deterministic — LLM is only used
for prose explanation (optional, gracefully skipped if unavailable).
"""

from typing import Any


Insight = dict[str, str]


def _insight(observation: str, implication: str, recommendation: str, impact: str) -> Insight:
    return {
        "observation": observation,
        "implication": implication,
        "recommendation": recommendation,
        "impact": impact,
    }


def generate_airline_insights(airline_metrics: dict) -> list[Insight]:
    insights = []
    top = airline_metrics.get("top_airline", "Unknown")
    share = airline_metrics.get("top_airline_share_pct", 0)
    unique = airline_metrics.get("unique_airlines", 0)

    if airline_metrics.get("is_fragmented"):
        insights.append(_insight(
            observation=f"Travel is spread across {unique} airlines. Top airline ({top}) holds only {share}% share.",
            implication="Fragmented spend means no airline recognizes you as a valuable customer — no status, no upgrades, no priority.",
            recommendation=f"Consolidate at least 60–70% of flights on {top} or your preferred carrier to accelerate status.",
            impact="Tier status typically unlocks ₹40,000–₹1,20,000 in annual upgrade and lounge value.",
        ))
    else:
        insights.append(_insight(
            observation=f"{top} accounts for {share}% of your flights.",
            implication="Strong airline concentration — you are likely close to or at elite tier status.",
            recommendation="Verify your current tier and track progress toward the next tier for additional benefits.",
            impact="Maintaining top-tier status conserves ₹60,000+ in annual benefits.",
        ))

    if unique >= 5:
        insights.append(_insight(
            observation=f"You flew {unique} different airlines in the analysis period.",
            implication="High airline count suggests lack of a deliberate carrier strategy.",
            recommendation="Define a primary + one backup airline strategy aligned to your route network.",
            impact="Structural consolidation can recover ₹50,000–₹1,50,000 in loyalty value annually.",
        ))

    return insights


def generate_booking_insights(booking_metrics: dict) -> list[Insight]:
    insights = []
    avg_gap = booking_metrics.get("avg_booking_gap_days")
    last_min_pct = booking_metrics.get("last_minute_pct", 0)

    if avg_gap is not None and avg_gap < 7:
        savings_low = round(last_min_pct * 500)
        savings_high = round(last_min_pct * 1000)
        insights.append(_insight(
            observation=f"Average booking lead time is {avg_gap} days. {last_min_pct}% of bookings are within 3 days of travel.",
            implication="Last-minute bookings consistently attract 30–80% fare premiums on domestic routes.",
            recommendation="Shift to booking 10–15 days in advance for domestic, 30+ days for international.",
            impact=f"₹{savings_low:,}–₹{savings_high:,} potential savings per year.",
        ))
    elif avg_gap is not None and avg_gap >= 10:
        insights.append(_insight(
            observation=f"Average booking lead time is {avg_gap} days — above industry best practice.",
            implication="Good planning discipline reduces exposure to peak-pricing windows.",
            recommendation="Maintain this behavior; set calendar reminders for predictable recurring routes.",
            impact="Estimated ₹20,000–₹40,000 in annual fare savings vs. last-minute bookers.",
        ))

    if last_min_pct > 40:
        insights.append(_insight(
            observation=f"{last_min_pct}% of all bookings happen within 3 days of travel.",
            implication="More than 4 in 10 trips are booked at premium fares with no flexibility.",
            recommendation="Institute a travel policy requiring minimum 7-day advance booking except for emergencies.",
            impact="Enforcing a 7-day minimum could save ₹30,000–₹80,000 annually.",
        ))

    return insights


def generate_route_insights(route_metrics: dict) -> list[Insight]:
    insights = []
    top_route = route_metrics.get("most_frequent_route")
    top_count = route_metrics.get("most_frequent_route_count", 0)
    total = route_metrics.get("total_routes_flown", 0)
    repeated_pct = route_metrics.get("repeated_route_pct", 0)
    unique_routes = route_metrics.get("unique_routes", 0)

    if top_route and top_count > 0:
        share = round(top_count / total * 100, 1) if total else 0
        insights.append(_insight(
            observation=f"Most frequent route: {top_route} ({top_count} flights, {share}% of all travel).",
            implication="High-frequency routes are ideal candidates for bulk fare contracts or corporate deals.",
            recommendation=f"Negotiate a corporate rate or volume discount on {top_route} with your primary carrier.",
            impact="Corporate route contracts typically deliver 15–25% savings: ₹25,000–₹60,000 per route annually.",
        ))

    if repeated_pct > 60:
        insights.append(_insight(
            observation=f"{repeated_pct}% of your flights are on repeated routes.",
            implication="Route predictability is leverage — airlines and travel management companies value committed volume.",
            recommendation="Use predictable routes to negotiate multi-trip fare bundles or annual pass products.",
            impact="Multi-trip bundles can save 10–20% vs. individual bookings.",
        ))

    if unique_routes > 15:
        insights.append(_insight(
            observation=f"You traveled {unique_routes} unique routes in 24 months.",
            implication="Wide route spread may make hub-based flying more efficient than point-to-point.",
            recommendation="Evaluate whether connecting through a hub airline's home airport reduces overall travel cost.",
            impact="Hub connectivity can reduce fares by 5–15% on select origin-destination pairs.",
        ))

    return insights


def generate_loyalty_insights(loyalty_metrics: dict) -> list[Insight]:
    insights = []
    missing_pct = loyalty_metrics.get("missing_credit_pct", 0)
    miles_lost = loyalty_metrics.get("estimated_miles_lost", 0)
    inr_value = loyalty_metrics.get("estimated_inr_value", 0)
    loyalty_available = loyalty_metrics.get("loyalty_data_available", False)

    if not loyalty_available:
        insights.append(_insight(
            observation="No loyalty program data was provided for cross-reference.",
            implication=f"Based on {loyalty_metrics.get('total_flights', 0)} flights, significant miles may have gone uncredited.",
            recommendation="Enroll in a single primary frequent-flyer program and link all future bookings to it.",
            impact=f"Estimated ₹{inr_value:,.0f} in recoverable miles value over the analysis period.",
        ))
    elif missing_pct > 20:
        insights.append(_insight(
            observation=f"{missing_pct}% of flights ({loyalty_metrics.get('missing_credits', 0)} trips) have no matching loyalty credit.",
            implication="Miles are earned but left on the table — a direct financial loss.",
            recommendation="Retro-claim missing miles immediately (most programs allow 12-month retro-claims).",
            impact=f"Estimated {miles_lost:,} miles (~₹{inr_value:,.0f}) recoverable through retro-claims.",
        ))
    elif missing_pct > 0:
        insights.append(_insight(
            observation=f"{missing_pct}% of flights have missing loyalty credits.",
            implication="Minor leakage — likely isolated booking channel issues.",
            recommendation="Always book through the airline's own channel or an accredited agent to guarantee credit.",
            impact=f"Closing this gap recovers ~{miles_lost:,} miles (₹{inr_value:,.0f}).",
        ))

    return insights


def generate_insights(
    airline_metrics: dict,
    booking_metrics: dict,
    route_metrics: dict,
    loyalty_metrics: dict,
) -> list[Insight]:
    """
    Combine all module insights into a single list.
    Guarantees at least 5 insights.
    """
    all_insights: list[Insight] = []

    all_insights.extend(generate_airline_insights(airline_metrics))
    all_insights.extend(generate_booking_insights(booking_metrics))
    all_insights.extend(generate_route_insights(route_metrics))
    all_insights.extend(generate_loyalty_insights(loyalty_metrics))

    while len(all_insights) < 5:
        all_insights.append(_insight(
            observation="Insufficient data for additional specific insights.",
            implication="More travel data will enable deeper pattern recognition.",
            recommendation="Ensure complete travel records (all flights, all dates) are included for the next analysis cycle.",
            impact="Better data coverage leads to higher-precision recommendations.",
        ))

    for i, insight in enumerate(all_insights, 1):
        insight["id"] = i

    return all_insights
