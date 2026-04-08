"""Step 3C: Route Analysis - Frequent routes, repetition rate."""

import pandas as pd
from typing import Any


def analyze_routes(df: pd.DataFrame) -> dict[str, Any]:
    """
    Identify most frequent routes and compute repetition rate.

    A route is considered 'repeated' if it appears more than once.
    """
    if df.empty or "route" not in df.columns:
        return {
            "total_routes_flown": 0,
            "unique_routes": 0,
            "repeated_route_pct": 0.0,
            "top_routes": [],
            "route_distribution": {},
        }

    total = len(df)
    route_counts = df["route"].value_counts()
    unique = len(route_counts)

    repeated_flights = int((route_counts[route_counts > 1]).sum())
    repeated_pct = round(repeated_flights / total * 100, 1) if total else 0.0

    top_routes = [
        {
            "route": route,
            "count": int(count),
            "share_pct": round(count / total * 100, 1),
        }
        for route, count in route_counts.head(10).items()
    ]

    route_distribution = {
        route: {"count": int(count), "share_pct": round(count / total * 100, 1)}
        for route, count in route_counts.items()
    }

    most_frequent_route = route_counts.idxmax() if not route_counts.empty else None

    return {
        "total_routes_flown": total,
        "unique_routes": unique,
        "most_frequent_route": most_frequent_route,
        "most_frequent_route_count": int(route_counts.max()) if not route_counts.empty else 0,
        "repeated_route_pct": repeated_pct,
        "top_routes": top_routes,
        "route_distribution": route_distribution,
    }
