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

    print(f"\n[FlightMode] Starting pipeline  (source: {source_file})")

    # -----------------------------
    # 🔍 DEBUG: Check ingestion output
    # -----------------------------
    print("BEFORE NORMALIZATION:", travel_df.columns.tolist())

    # -----------------------------
    # 🚨 SAFETY CHECK: Ensure critical columns exist
    # -----------------------------
    required_cols = ["airline", "booking_date", "travel_date", "origin", "destination"]

    for col in required_cols:
        if col not in travel_df.columns:
            raise ValueError(f"❌ Column missing BEFORE normalization: {col}")

    # -----------------------------
    # Step 2: Normalize
    # -----------------------------
    print("[2/6] Normalizing data...")

    travel_df = normalize_travel(travel_df)
    loyalty_df = normalize_loyalty(loyalty_df)

    # -----------------------------
    # 🔍 DEBUG: Check after normalization
    # -----------------------------
    print("AFTER NORMALIZATION:", travel_df.columns.tolist())

    # -----------------------------
    # 🚨 SAFETY CHECK: Ensure columns still exist
    # -----------------------------
    for col in required_cols:
        if col not in travel_df.columns:
            raise ValueError(f"❌ Column LOST during normalization: {col}")

    print(f"      Clean rows: {len(travel_df)}, loyalty: {loyalty_df is not None}")

    # -----------------------------
    # Step 3: Analysis
    # -----------------------------
    print("[3/6] Running analysis modules...")

    airline_metrics = analyze_airline(travel_df)
    booking_metrics = analyze_booking(travel_df)
    route_metrics   = analyze_routes(travel_df)
    loyalty_metrics = analyze_loyalty(travel_df, loyalty_df)

    print(
        f"      Airlines: {airline_metrics.get('unique_airlines', 0)}, "
        f"Routes: {route_metrics.get('unique_routes', 0)}, "
        f"Avg gap: {booking_metrics.get('avg_booking_gap_days', 0)} days"
    )

    # -----------------------------
    # Step 4: Insights
    # -----------------------------
    print("[4/6] Generating insights...")

    insights = generate_insights(
        airline_metrics, booking_metrics, route_metrics, loyalty_metrics
    )

    print(f"      {len(insights)} insights generated")

    # -----------------------------
    # Step 5: JSON Report
    # -----------------------------
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

    # -----------------------------
    # Step 6: Markdown Report
    # -----------------------------
    print("[6/6] Building Markdown report...")

    markdown_report = build_markdown_report(json_report)

    print("[FlightMode] Pipeline complete.\n")

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


def run_pipeline_from_file(filepath: str) -> dict:
    print(f"\n[FlightMode] Ingesting file: {filepath}")
    print("[1/6] Reading sheets...")

    travel_df, loyalty_df = load_sheets(filepath)

    print(
        f"      Travel rows: {len(travel_df)}, "
        f"Loyalty rows: {len(loyalty_df) if loyalty_df is not None else 0}"
    )

    return run_pipeline(travel_df, loyalty_df, source_file=filepath)
