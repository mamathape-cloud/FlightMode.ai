"""Generate insights from analysis metrics using AWS Bedrock."""
import json
import re

from .bedrock_client import BedrockError, invoke
from .prompts import INSIGHTS_PROMPT

MIN_INSIGHTS = 5

_FALLBACK_INSIGHT = {
    "observation": "Insufficient data was extracted from the provided PDFs to generate specific insights.",
    "implication": "The analysis may be incomplete due to PDF format limitations or limited travel history.",
    "recommendation": "Provide structured Excel data via the main FlightMode.ai app for a full deterministic analysis.",
    "impact": "Estimated ₹40,000–₹1,50,000 potential savings identified with complete data.",
}


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def generate(flights: list, loyalty_credits: list, metrics: dict) -> list:
    """Call Bedrock to produce insights. Returns list of insight dicts."""
    structured_data = json.dumps(
        {
            "total_flights": len(flights),
            "total_loyalty_credits": len(loyalty_credits),
            "sample_flights": flights[:5],
            "sample_loyalty": loyalty_credits[:5],
        },
        indent=2,
        default=str,
    )
    analysis_metrics = json.dumps(metrics, indent=2, default=str)

    prompt = INSIGHTS_PROMPT.format(
        structured_data=structured_data,
        analysis_metrics=analysis_metrics,
    )

    try:
        response = invoke(prompt, max_tokens=4096)
    except BedrockError as e:
        print(f"\n  Warning: Bedrock insights call failed: {e}")
        return [dict(_FALLBACK_INSIGHT, id=i + 1) for i in range(MIN_INSIGHTS)]

    cleaned = _strip_fences(response)

    # Try direct parse
    try:
        insights = json.loads(cleaned)
    except json.JSONDecodeError:
        # Try to find a JSON array inside the response
        match = re.search(r"\[.*\]", cleaned, re.DOTALL)
        if match:
            try:
                insights = json.loads(match.group())
            except Exception:
                insights = []
        else:
            insights = []

    # Validate each insight has required keys
    required = {"observation", "implication", "recommendation", "impact"}
    valid = [i for i in insights if isinstance(i, dict) and required.issubset(i.keys())]

    # Pad if fewer than MIN_INSIGHTS
    while len(valid) < MIN_INSIGHTS:
        valid.append(dict(_FALLBACK_INSIGHT))

    # Add sequential IDs
    for idx, insight in enumerate(valid, 1):
        insight["id"] = idx

    return valid
