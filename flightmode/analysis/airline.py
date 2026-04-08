"""Step 3A: Airline Analysis - Distribution, top airline, fragmentation."""

import pandas as pd
from typing import Any


FRAGMENTATION_THRESHOLD = 0.60


def analyze_airline(df: pd.DataFrame) -> dict[str, Any]:
    """
    Compute airline distribution, identify top airline, and detect fragmentation.

    Returns deterministic metrics — no LLM involved.
    """
    if df.empty or "airline" not in df.columns:
        return {
            "total_flights": 0,
            "airline_distribution": {},
            "top_airline": None,
            "top_airline_share_pct": 0.0,
            "is_fragmented": False,
            "unique_airlines": 0,
        }

    total = len(df)
    counts = df["airline"].value_counts()
    distribution = {
        airline: {
            "flights": int(count),
            "share_pct": round(count / total * 100, 1),
        }
        for airline, count in counts.items()
    }

    top_airline = counts.idxmax()
    top_share = counts.max() / total

    return {
        "total_flights": total,
        "airline_distribution": distribution,
        "top_airline": top_airline,
        "top_airline_share_pct": round(top_share * 100, 1),
        "is_fragmented": bool(top_share < FRAGMENTATION_THRESHOLD),
        "unique_airlines": int(counts.nunique()),
    }
