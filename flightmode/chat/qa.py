"""
Step 7: Chat Layer

ask_question(question, report_context) — answers ONLY from report data.

Rules:
- No hallucination: answers are grounded in the JSON report context.
- Deterministic path first: keyword-based fast lookup.
- Optional LLM path: if OpenAI key is set, uses GPT for fluent prose,
  but the context injected is ONLY the structured JSON report.
- If data not in report → explicit "not available" response.
"""

import json
import os
from typing import Any

NOT_AVAILABLE = "This data is not available in the report."


def _extract_relevant_facts(question: str, report: dict) -> dict | None:
    """
    Fast deterministic lookup: extract report sections relevant to the question.
    Returns a sub-dict of the report, or None if nothing relevant found.
    """
    q = question.lower()
    facts: dict[str, Any] = {}

    keyword_map = {
        ("airline", "carrier", "fragm", "consolidat", "distribution"):
            "airline_analysis",
        ("booking", "lead time", "advance", "last.?minute", "gap", "days before"):
            "booking_behavior",
        ("route", "flight path", "origin", "destination", "frequent route"):
            "route_analysis",
        ("loyalty", "miles", "credit", "uncredited", "points", "leak"):
            "loyalty_leakage",
        ("insight", "recommendation", "suggest", "action", "strategy", "optim"):
            "insights",
    }

    import re
    for keywords, section_key in keyword_map.items():
        pattern = "|".join(keywords)
        if re.search(pattern, q) and section_key in report:
            facts[section_key] = report[section_key]

    if "total" in q or "overview" in q or "summary" in q:
        facts["meta"] = report.get("meta", {})
        facts["airline_analysis"] = report.get("airline_analysis", {})

    return facts if facts else None


def ask_question(question: str, report_context: dict) -> str:
    """
    Answer a question grounded strictly in report_context.

    Tries OpenAI (if OPENAI_API_KEY is set), falls back to deterministic
    rule-based extraction.

    Args:
        question: Natural language question from the user.
        report_context: The JSON report dict from build_json_report().

    Returns:
        A string answer grounded in the report, or a "not available" message.
    """
    if not report_context:
        return NOT_AVAILABLE

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()

    if api_key:
        return _ask_with_llm(question, report_context, api_key)
    else:
        return _ask_deterministic(question, report_context)


def _ask_deterministic(question: str, report: dict) -> str:
    """
    Rule-based Q&A over the report. Handles common question patterns.
    Returns NOT_AVAILABLE if the question cannot be answered from the data.
    """
    q = question.lower().strip()
    import re

    airline = report.get("airline_analysis", {})
    booking = report.get("booking_behavior", {})
    routes = report.get("route_analysis", {})
    loyalty = report.get("loyalty_leakage", {})
    meta = report.get("meta", {})

    if re.search(r"top airline|primary airline|most.?used airline|which airline", q):
        top = airline.get("top_airline")
        share = airline.get("top_airline_share_pct")
        if top:
            return f"Your top airline is **{top}**, accounting for {share}% of your flights."
        return NOT_AVAILABLE

    if re.search(r"fragment|consolidat", q):
        is_frag = airline.get("is_fragmented")
        if is_frag is None:
            return NOT_AVAILABLE
        if is_frag:
            return (
                f"Yes, your travel is fragmented. Your top airline ({airline.get('top_airline')}) "
                f"holds only {airline.get('top_airline_share_pct')}% of flights — below the 60% "
                "threshold for loyalty status benefits."
            )
        return (
            f"No, your travel is consolidated. Your top airline ({airline.get('top_airline')}) "
            f"holds {airline.get('top_airline_share_pct')}% — above the 60% threshold."
        )

    if re.search(r"how many (airlines|carriers)", q):
        n = airline.get("unique_airlines")
        if n is not None:
            return f"You flew **{n} different airlines** in the analysis period."
        return NOT_AVAILABLE

    if re.search(r"average booking|avg booking|lead time|how far in advance|booking gap", q):
        avg = booking.get("avg_booking_gap_days")
        if avg is not None:
            return f"Your average booking lead time is **{avg} days** before travel."
        return NOT_AVAILABLE

    if re.search(r"last.?minute|within 3 days|3.?day booking", q):
        pct = booking.get("last_minute_pct")
        count = booking.get("last_minute_count")
        if pct is not None:
            return f"**{pct}%** of your bookings ({count} trips) were made within 3 days of travel."
        return NOT_AVAILABLE

    if re.search(r"most frequent route|top route|busiest route", q):
        route = routes.get("most_frequent_route")
        count = routes.get("most_frequent_route_count")
        if route:
            return f"Your most frequent route is **{route}**, flown {count} times."
        return NOT_AVAILABLE

    if re.search(r"how many routes|unique routes|total routes", q):
        n = routes.get("unique_routes")
        if n is not None:
            return f"You flew **{n} unique routes** in the analysis period."
        return NOT_AVAILABLE

    if re.search(r"miles lost|miles.?miss|uncredited miles|estimated miles", q):
        miles = loyalty.get("estimated_miles_lost")
        if miles is not None:
            inr = loyalty.get("estimated_inr_value", 0)
            return (
                f"Approximately **{miles:,} miles** are estimated as lost/uncredited, "
                f"worth roughly ₹{inr:,.0f}."
            )
        return NOT_AVAILABLE

    if re.search(r"credited|missing credit|loyalty leak|uncredited flights", q):
        missing = loyalty.get("missing_credits")
        pct = loyalty.get("missing_credit_pct")
        if missing is not None:
            return (
                f"**{missing} flights** ({pct}%) have no matching loyalty credit recorded."
            )
        return NOT_AVAILABLE

    if re.search(r"total flights|how many flights|flights analyzed", q):
        total = meta.get("total_flights_analyzed") or airline.get("total_flights")
        if total is not None:
            return f"The report analyzed **{total} flights** in total."
        return NOT_AVAILABLE

    if re.search(r"recommendation|suggest|what should|how (can|do) i|improve|optim", q):
        insights = report.get("insights", [])
        if insights:
            recs = [ins.get("recommendation", "") for ins in insights[:3] if ins.get("recommendation")]
            if recs:
                return "Top recommendations from your report:\n" + "\n".join(
                    f"{i+1}. {r}" for i, r in enumerate(recs)
                )
        return NOT_AVAILABLE

    if re.search(r"insight|finding|key point", q):
        insights = report.get("insights", [])
        if insights:
            obs_list = [ins.get("observation", "") for ins in insights[:5] if ins.get("observation")]
            return "Key observations from your report:\n" + "\n".join(
                f"{i+1}. {o}" for i, o in enumerate(obs_list)
            )
        return NOT_AVAILABLE

    return NOT_AVAILABLE


def _ask_with_llm(question: str, report: dict, api_key: str) -> str:
    """
    Use OpenAI to answer the question — but ONLY from the provided report context.
    The system prompt strictly prohibits guessing beyond the report.
    """
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        report_text = json.dumps(report, indent=2, default=str)

        system_prompt = (
            "You are a travel intelligence assistant for FlightMode.ai. "
            "You can ONLY answer questions using the structured travel report provided below. "
            "Do NOT use any outside knowledge, assumptions, or estimates not present in the report. "
            "If the answer is not found in the report, respond exactly with: "
            "'This data is not available in the report.' "
            "Be concise, factual, and precise.\n\n"
            f"REPORT DATA:\n{report_text}"
        )

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question},
            ],
            temperature=0,
            max_tokens=500,
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        return f"LLM unavailable ({e}). Falling back to rule-based lookup:\n\n" + _ask_deterministic(
            question, report
        )
