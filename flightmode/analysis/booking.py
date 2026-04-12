"""Step 3B: Booking Behavior Analysis - Booking gap, last-minute patterns."""

import pandas as pd
from typing import Any


LAST_MINUTE_DAYS = 3
EARLY_BOOKING_DAYS = 10


def analyze_booking(df: pd.DataFrame) -> dict[str, Any]:
    """
    Compute booking gap metrics deterministically.

    booking_gap = travel_date - booking_date (in days)
    """
    if df.empty:
        return {
            "total_bookings": 0,
            "avg_booking_gap_days": None,
            "median_booking_gap_days": None,
            "min_booking_gap_days": None,
            "max_booking_gap_days": None,
            "last_minute_count": 0,
            "last_minute_pct": 0.0,
            "early_booking_count": 0,
            "early_booking_pct": 0.0,
            "gap_distribution": {},
        }

    df = df.copy()
    df["booking_gap"] = (df["travel_date"] - df["booking_date"]).dt.days

    valid = df["booking_gap"].dropna()
    valid = valid[valid >= 0]

    total = len(valid)
    if total == 0:
        return {
            "total_bookings": 0,
            "avg_booking_gap_days": None,
            "median_booking_gap_days": None,
            "min_booking_gap_days": None,
            "max_booking_gap_days": None,
            "last_minute_count": 0,
            "last_minute_pct": 0.0,
            "early_booking_count": 0,
            "early_booking_pct": 0.0,
            "gap_distribution": {},
        }

    last_minute = int((valid <= LAST_MINUTE_DAYS).sum())
    early = int((valid >= EARLY_BOOKING_DAYS).sum())

    buckets = [
        ("0-3 days (last minute)", 0, 3),
        ("4-7 days", 4, 7),
        ("8-14 days", 8, 14),
        ("15-30 days", 15, 30),
        ("31+ days (planned)", 31, 99999),
    ]
    gap_distribution = {}
    for label, lo, hi in buckets:
        count = int(((valid >= lo) & (valid <= hi)).sum())
        gap_distribution[label] = {
            "count": count,
            "pct": round(count / total * 100, 1),
        }

    return {
        "total_bookings": total,
        "avg_booking_gap_days": round(float(valid.mean()), 1),
        "median_booking_gap_days": round(float(valid.median()), 1),
        "min_booking_gap_days": int(valid.min()),
        "max_booking_gap_days": int(valid.max()),
        "last_minute_count": last_minute,
        "last_minute_pct": round(last_minute / total * 100, 1),
        "early_booking_count": early,
        "early_booking_pct": round(early / total * 100, 1),
        "gap_distribution": gap_distribution,
    }
