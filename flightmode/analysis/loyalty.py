"""Step 3D: Loyalty Leakage Analysis - Missing credits, estimated miles lost."""

import pandas as pd
from typing import Any, Optional

MILES_PER_FLIGHT_ESTIMATE = 1500


def analyze_loyalty(
    travel_df: pd.DataFrame, loyalty_df: Optional[pd.DataFrame]
) -> dict[str, Any]:
    """
    Compare travel records vs loyalty credits.

    If loyalty data is missing, estimate potential value based on travel volume.
    """
    total_flights = len(travel_df)

    if loyalty_df is None or loyalty_df.empty:
        estimated_miles = total_flights * MILES_PER_FLIGHT_ESTIMATE
        return {
            "loyalty_data_available": False,
            "total_flights": total_flights,
            "credited_flights": 0,
            "missing_credits": total_flights,
            "missing_credit_pct": 100.0 if total_flights else 0.0,
            "estimated_miles_lost": estimated_miles,
            "estimated_inr_value": estimated_miles * 0.5,
            "note": "No loyalty data provided. All flights assumed uncredited.",
        }

    pnr_col_travel = "pnr" if "pnr" in travel_df.columns else None
    pnr_col_loyalty = "pnr" if "pnr" in loyalty_df.columns else None

    if pnr_col_travel and pnr_col_loyalty:
        travel_pnrs = set(travel_df[pnr_col_travel].dropna().astype(str).str.upper())
        loyalty_pnrs = set(loyalty_df[pnr_col_loyalty].dropna().astype(str).str.upper())

        credited = travel_pnrs & loyalty_pnrs
        missing_pnrs = travel_pnrs - loyalty_pnrs

        credited_count = len(credited)
        missing_count = len(missing_pnrs)
    else:
        credited_count = len(loyalty_df)
        missing_count = max(0, total_flights - credited_count)
        missing_pnrs = set()

    estimated_miles_lost = missing_count * MILES_PER_FLIGHT_ESTIMATE
    missing_pct = round(missing_count / total_flights * 100, 1) if total_flights else 0.0

    miles_earned = 0
    if "miles_earned" in loyalty_df.columns:
        miles_earned = int(loyalty_df["miles_earned"].sum(skipna=True))

    return {
        "loyalty_data_available": True,
        "total_flights": total_flights,
        "credited_flights": credited_count,
        "missing_credits": missing_count,
        "missing_credit_pct": missing_pct,
        "miles_already_earned": miles_earned,
        "estimated_miles_lost": estimated_miles_lost,
        "estimated_inr_value": round(estimated_miles_lost * 0.5, 0),
        "missing_pnrs": list(missing_pnrs)[:20],
    }
