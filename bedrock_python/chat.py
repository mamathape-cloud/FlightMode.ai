"""Bedrock-powered grounded chat grounded in the json_report context."""
import json
import os

from dotenv import load_dotenv

load_dotenv()

MAX_HISTORY_MESSAGES = 10  # last N messages kept in the conversation window

SYSTEM_PROMPT_TEMPLATE = """You are a travel optimization assistant for FlightMode.ai.
You have been given a structured travel intelligence report for a specific traveller.
Answer ONLY using the report data, metrics, and insights supplied below.
If the information is not available in the report, say exactly: "That information isn't available in your report."
Do not invent numbers, flights, savings, or miles that are not in the report.
Be concise and specific. Cite numbers from the report when relevant.
When asked for recommendations, refer to the insights and action plan in the report.

--- TRAVEL REPORT DATA ---
{context}
--- END OF REPORT DATA ---"""


def build_context(json_report: dict) -> str:
    """Compact JSON context string from the report — kept under 8 000 chars."""
    route_analysis = dict(json_report.get("route_analysis", {}))
    route_analysis.pop("route_distribution", None)  # large, skip

    context = {
        "meta": json_report.get("meta", {}),
        "airline_analysis": json_report.get("airline_analysis", {}),
        "booking_behavior": json_report.get("booking_behavior", {}),
        "route_analysis": route_analysis,
        "loyalty_leakage": json_report.get("loyalty_leakage", {}),
        "insights": json_report.get("insights", []),
    }
    text = json.dumps(context, indent=None, default=str)
    if len(text) > 8000:
        text = text[:8000] + "… [truncated]"
    return text


def ask(question: str, json_report: dict, history: list[dict]) -> str:
    """
    Ask a question grounded in the report.

    history: list of {"role": "user"|"assistant", "content": str} — prior turns
    Returns the assistant's reply as a string.
    """
    import boto3

    context = build_context(json_report)
    system = SYSTEM_PROMPT_TEMPLATE.format(context=context)

    # Trim history to last N messages (must alternate user/assistant)
    recent = history[-MAX_HISTORY_MESSAGES:] if len(history) > MAX_HISTORY_MESSAGES else list(history)

    # Bedrock requires messages to alternate; ensure we start with a user message
    messages = [m for m in recent if m.get("role") in ("user", "assistant")]
    messages.append({"role": "user", "content": question})

    model_id = os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1024,
        "system": system,
        "messages": messages,
    }

    try:
        client = boto3.client(
            "bedrock-runtime",
            region_name=os.environ["AWS_REGION"],
            aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        )
        import json as _json
        response = client.invoke_model(
            modelId=model_id,
            contentType="application/json",
            accept="application/json",
            body=_json.dumps(body),
        )
        result = _json.loads(response["body"].read())
        return result["content"][0]["text"]
    except Exception as e:
        err = str(e)
        if "AccessDenied" in err:
            return "Chat is unavailable — Bedrock model access denied. Check your AWS console."
        return f"Sorry, I couldn't process your question right now. ({err[:80]})"
