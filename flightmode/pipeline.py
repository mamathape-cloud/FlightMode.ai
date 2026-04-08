"""
FlightMode.ai — Main Pipeline Orchestrator

Runs all steps in sequence:
  1. Ingest  →  2. Normalize  →  3. Analyze  →  4. Insights  →  5-6. Report
"""

import json
from typing import Optional

from flightmode.core.ingestion import ingest
from flightmode.core.normalization import normalize
from flightmode.analysis.airline import analyze_airline
from flightmode.analysis.booking import analyze_booking
from flightmode.analysis.route import analyze_routes
from flightmode.analysis.loyalty import analyze_loyalty
from flightmode.analysis.insights import generate_insights
from flightmode.report.generator import build_json_report, build_markdown_report


def _get_date_range(df) -> Optional[str]:
    try:
        start = df["travel_date"].min().strftime("%Y-%m-%d")
        end = df["travel_date"].max().strftime("%Y-%m-%d")
        return f"{start} to {end}"
    except Exception:
        return None


def run_pipeline(filepath: str) -> dict:
    """
    Full FlightMode pipeline.

    Args:
        filepath: Path to .xlsx, .xls, or .csv travel data file.

    Returns:
        dict with keys:
          - json_report: structured dict
          - markdown_report: human-readable string
          - metrics: intermediate metrics dict
    """
    print(f"\n[FlightMode] Starting pipeline for: {filepath}")

    print("[1/6] Ingesting data...")
    raw = ingest(filepath)
    print(f"      Loaded {raw['row_count']} rows. Loyalty data: {raw['has_loyalty']}")

    print("[2/6] Normalizing data...")
    cleaned = normalize(raw)
    travel_df = cleaned["travel"]
    loyalty_df = cleaned.get("loyalty")
    print(f"      Clean rows: {len(travel_df)}")

    print("[3/6] Running analysis modules...")
    airline_metrics = analyze_airline(travel_df)
    booking_metrics = analyze_booking(travel_df)
    route_metrics = analyze_routes(travel_df)
    loyalty_metrics = analyze_loyalty(travel_df, loyalty_df)
    print(f"      Airlines: {airline_metrics['unique_airlines']}, "
          f"Routes: {route_metrics['unique_routes']}, "
          f"Avg gap: {booking_metrics['avg_booking_gap_days']} days")

    print("[4/6] Generating insights...")
    insights = generate_insights(airline_metrics, booking_metrics, route_metrics, loyalty_metrics)
    print(f"      {len(insights)} insights generated")

    print("[5/6] Building JSON report...")
    travel_df_meta = {"date_range": _get_date_range(travel_df)}
    json_report = build_json_report(
        airline_metrics=airline_metrics,
        booking_metrics=booking_metrics,
        route_metrics=route_metrics,
        loyalty_metrics=loyalty_metrics,
        insights=insights,
        source_file=filepath,
        row_count=len(travel_df),
        travel_df_meta=travel_df_meta,
    )

    print("[6/6] Building Markdown report...")
    markdown_report = build_markdown_report(json_report)

    print(f"\n[FlightMode] Pipeline complete.\n")

    return {
        "json_report": json_report,
        "markdown_report": markdown_report,
        "metrics": {
            "airline": airline_metrics,
            "booking": booking_metrics,
            "routes": route_metrics,
            "loyalty": loyalty_metrics,
        },
    }
