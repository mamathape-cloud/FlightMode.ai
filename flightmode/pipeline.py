"""
FlightMode.ai — Main Pipeline Orchestrator

Two entry points:

  run_pipeline(travel_df, loyalty_df=None)
      Core pipeline — accepts DataFrames directly.
      Used by the Streamlit app and tests.

  run_pipeline_from_file(filepath)
      Convenience wrapper — reads the Excel/CSV file,
      extracts Travel_Data + Loyalty_Data sheets, then
      calls run_pipeline().
"""

from typing import Optional

import pandas as pd

from flightmode.core.ingestion import load_sheets
from flightmode.core.normalization import normalize_travel, normalize_loyalty
from flightmode.analysis.airline import analyze_airline
from flightmode.analysis.booking import analyze_booking
from flightmode.analysis.route import analyze_routes
from flightmode.analysis.loyalty import analyze_loyalty
from flightmode.analysis.insights import generate_insights
from flightmode.report.generator import build_json_report, build_markdown_report


def _get_date_range(df: pd.DataFrame) -> Optional[str]:
    try:
        start = df["travel_date"].min().strftime("%Y-%m-%d")
        end = df["travel_date"].max().strftime("%Y-%m-%d")
        return f"{start} to {end}"
    except Exception:
        return None


def run_pipeline(
    travel_df: pd.DataFrame,
    loyalty_df: Optional[pd.DataFrame] = None,
    source_file: str = "uploaded_file",
) -> dict:
    """
    Core FlightMode pipeline.

    Args:
        travel_df:   Normalized travel DataFrame (required).
        loyalty_df:  Normalized loyalty DataFrame (optional, may be None).
        source_file: Label used in the report metadata.

    Returns:
        dict with keys:
          - json_report:      structured dict
          - markdown_report:  human-readable Markdown string
          - metrics:          intermediate metrics dict
    """
    print(f"\n[FlightMode] Starting pipeline  (source: {source_file})")

    # Step 2: Normalize
    print("[2/6] Normalizing data...")
    travel_df = normalize_travel(travel_df)
    loyalty_df = normalize_loyalty(loyalty_df)
    print(f"      Clean rows: {len(travel_df)}, loyalty: {loyalty_df is not None}")

    # Step 3: Analysis
    print("[3/6] Running analysis modules...")
    airline_metrics = analyze_airline(travel_df)
    booking_metrics = analyze_booking(travel_df)
    route_metrics   = analyze_routes(travel_df)
    loyalty_metrics = analyze_loyalty(travel_df, loyalty_df)
    print(
        f"      Airlines: {airline_metrics['unique_airlines']}, "
        f"Routes: {route_metrics['unique_routes']}, "
        f"Avg gap: {booking_metrics['avg_booking_gap_days']} days"
    )

    # Step 4: Insights
    print("[4/6] Generating insights...")
    insights = generate_insights(
        airline_metrics, booking_metrics, route_metrics, loyalty_metrics
    )
    print(f"      {len(insights)} insights generated")

    # Steps 5-6: Reports
    print("[5/6] Building JSON report...")
    json_report = build_json_report(
        airline_metrics=airline_metrics,
        booking_metrics=booking_metrics,
        route_metrics=route_metrics,
        loyalty_metrics=loyalty_metrics,
        insights=insights,
        source_file=source_file,
        row_count=len(travel_df),
        travel_df_meta={"date_range": _get_date_range(travel_df)},
    )

    print("[6/6] Building Markdown report...")
    markdown_report = build_markdown_report(json_report)

    print("[FlightMode] Pipeline complete.\n")

    return {
        "json_report":     json_report,
        "markdown_report": markdown_report,
        "metrics": {
            "airline": airline_metrics,
            "booking": booking_metrics,
            "routes":  route_metrics,
            "loyalty": loyalty_metrics,
        },
    }


def run_pipeline_from_file(filepath: str) -> dict:
    """
    Convenience entry point: read file → extract sheets → run pipeline.

    Accepts:
      - .xlsx / .xls with sheets "Travel_Data" (required) + "Loyalty_Data" (optional)
      - .csv  (travel data only)

    Raises:
      IngestionError if the file cannot be read or Travel_Data is missing.
    """
    print(f"\n[FlightMode] Ingesting file: {filepath}")
    print("[1/6] Reading sheets...")
    travel_df, loyalty_df = load_sheets(filepath)
    print(
        f"      Travel rows: {len(travel_df)}, "
        f"Loyalty rows: {len(loyalty_df) if loyalty_df is not None else 0}"
    )
    return run_pipeline(travel_df, loyalty_df, source_file=filepath)
