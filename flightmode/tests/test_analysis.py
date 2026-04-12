"""Unit tests for FlightMode.ai analysis modules."""

import numpy as np
import pandas as pd
import pytest
from datetime import datetime, timedelta

from flightmode.analysis.airline import analyze_airline, FRAGMENTATION_THRESHOLD
from flightmode.analysis.booking import analyze_booking
from flightmode.analysis.route import analyze_routes
from flightmode.analysis.loyalty import analyze_loyalty
from flightmode.analysis.insights import generate_insights
from flightmode.core.normalization import normalize_travel, _standardize_airline, _parse_dates


# ── Fixtures ─────────────────────────────────────────────────────────────────

def make_travel_df(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    df["booking_date"] = pd.to_datetime(df["booking_date"])
    df["travel_date"] = pd.to_datetime(df["travel_date"])
    df["route"] = df["origin"] + " → " + df["destination"]
    return df


def sample_df():
    base = datetime(2024, 6, 1)
    rows = []
    airlines = ["IndiGo"] * 7 + ["Air India"] * 2 + ["SpiceJet"] * 1
    for i, airline in enumerate(airlines):
        td = base + timedelta(days=i * 10)
        gap = 1 if i < 4 else 15
        rows.append({
            "airline": airline,
            "origin": "DEL",
            "destination": "BOM" if i % 2 == 0 else "BLR",
            "booking_date": td - timedelta(days=gap),
            "travel_date": td,
            "pnr": f"PNR{i:03d}",
        })
    return make_travel_df(rows)


# ── Airline Analysis ──────────────────────────────────────────────────────────

class TestAirlineAnalysis:
    def test_top_airline_identified(self):
        df = sample_df()
        result = analyze_airline(df)
        assert result["top_airline"] == "IndiGo"
        assert result["top_airline_share_pct"] == 70.0

    def test_not_fragmented_when_above_threshold(self):
        df = sample_df()
        result = analyze_airline(df)
        assert result["is_fragmented"] is False

    def test_fragmented_when_below_threshold(self):
        rows = [{"airline": f"Airline{i}", "origin": "A", "destination": "B",
                 "booking_date": datetime(2024, 1, i+1),
                 "travel_date": datetime(2024, 1, i+2)} for i in range(10)]
        df = make_travel_df(rows)
        result = analyze_airline(df)
        assert result["is_fragmented"] is True

    def test_distribution_sums_to_100(self):
        df = sample_df()
        result = analyze_airline(df)
        total = sum(v["share_pct"] for v in result["airline_distribution"].values())
        assert abs(total - 100.0) < 1.0

    def test_empty_df(self):
        df = pd.DataFrame(columns=["airline", "origin", "destination", "booking_date", "travel_date", "route"])
        result = analyze_airline(df)
        assert result["total_flights"] == 0
        assert result["top_airline"] is None


# ── Booking Behavior ──────────────────────────────────────────────────────────

class TestBookingBehavior:
    def test_avg_gap_correct(self):
        # Same travel_date, different booking gaps: 5, 10, 15 days → avg = 10
        base = datetime(2024, 1, 10)
        rows = [
            {"airline": "IndiGo", "origin": "DEL", "destination": "BOM",
             "booking_date": base - timedelta(days=g),
             "travel_date": base}
            for g in [5, 10, 15]
        ]
        df = make_travel_df(rows)
        result = analyze_booking(df)
        assert result["avg_booking_gap_days"] == 10.0

    def test_last_minute_count(self):
        # Gaps: 1, 2, 3 (≤3), 10, 20 (>3) → 3 last-minute out of 5
        base = datetime(2024, 1, 10)
        rows = [
            {"airline": "IndiGo", "origin": "DEL", "destination": "BOM",
             "booking_date": base - timedelta(days=g),
             "travel_date": base}
            for g in [1, 2, 3, 10, 20]
        ]
        df = make_travel_df(rows)
        result = analyze_booking(df)
        assert result["last_minute_count"] == 3
        assert result["last_minute_pct"] == 60.0

    def test_empty_df(self):
        df = pd.DataFrame(columns=["airline", "origin", "destination", "booking_date", "travel_date", "route"])
        result = analyze_booking(df)
        assert result["total_bookings"] == 0
        assert result["avg_booking_gap_days"] is None


# ── Route Analysis ────────────────────────────────────────────────────────────

class TestRouteAnalysis:
    def test_most_frequent_route(self):
        df = sample_df()
        result = analyze_routes(df)
        assert result["most_frequent_route"] is not None

    def test_unique_routes_count(self):
        df = sample_df()
        result = analyze_routes(df)
        assert result["unique_routes"] == 2

    def test_top_routes_have_correct_keys(self):
        df = sample_df()
        result = analyze_routes(df)
        for r in result["top_routes"]:
            assert "route" in r
            assert "count" in r
            assert "share_pct" in r

    def test_empty_df(self):
        df = pd.DataFrame(columns=["airline", "origin", "destination", "booking_date", "travel_date", "route"])
        result = analyze_routes(df)
        assert result["total_routes_flown"] == 0


# ── Loyalty Leakage ───────────────────────────────────────────────────────────

class TestLoyaltyLeakage:
    def test_no_loyalty_data(self):
        df = sample_df()
        result = analyze_loyalty(df, None)
        assert result["loyalty_data_available"] is False
        assert result["missing_credits"] == len(df)
        assert result["estimated_miles_lost"] > 0

    def test_with_loyalty_data_pnr_match(self):
        travel = sample_df()
        pnrs = travel["pnr"].tolist()[:6]
        loyalty = pd.DataFrame({"pnr": pnrs, "miles_earned": [500] * 6})
        result = analyze_loyalty(travel, loyalty)
        assert result["loyalty_data_available"] is True
        assert result["credited_flights"] == 6
        assert result["missing_credits"] == len(travel) - 6

    def test_miles_lost_estimate(self):
        df = sample_df()
        result = analyze_loyalty(df, None)
        assert result["estimated_miles_lost"] == len(df) * 1500


# ── Insight Engine ────────────────────────────────────────────────────────────

class TestInsightEngine:
    def test_minimum_5_insights(self):
        df = sample_df()
        airline_m = analyze_airline(df)
        booking_m = analyze_booking(df)
        route_m = analyze_routes(df)
        loyalty_m = analyze_loyalty(df, None)
        insights = generate_insights(airline_m, booking_m, route_m, loyalty_m)
        assert len(insights) >= 5

    def test_insights_have_required_keys(self):
        df = sample_df()
        insights = generate_insights(
            analyze_airline(df),
            analyze_booking(df),
            analyze_routes(df),
            analyze_loyalty(df, None),
        )
        for ins in insights:
            assert "observation" in ins
            assert "implication" in ins
            assert "recommendation" in ins
            assert "impact" in ins


# ── Normalization ─────────────────────────────────────────────────────────────

class TestNormalization:
    def test_airline_alias_resolved(self):
        assert _standardize_airline("6e") == "IndiGo"
        assert _standardize_airline("AI") == "Air India"
        assert _standardize_airline("indigo") == "IndiGo"

    def test_duplicates_removed(self):
        base = datetime(2024, 1, 1)
        row = {
            "airline": "IndiGo", "origin": "DEL", "destination": "BOM",
            "booking_date": base - timedelta(days=5),
            "travel_date": base,
        }
        df = pd.DataFrame([row, row])
        normalized = normalize_travel(df)
        assert len(normalized) == 1

    def test_route_column_created(self):
        base = datetime(2024, 1, 1)
        df = pd.DataFrame([{
            "airline": "IndiGo", "origin": "DEL", "destination": "BOM",
            "booking_date": (base - timedelta(days=5)).strftime("%Y-%m-%d"),
            "travel_date": base.strftime("%Y-%m-%d"),
        }])
        df["booking_date"] = pd.to_datetime(df["booking_date"])
        df["travel_date"] = pd.to_datetime(df["travel_date"])
        normalized = normalize_travel(df)
        assert "route" in normalized.columns
        assert normalized.iloc[0]["route"] == "DEL → BOM"


# ── Pandas boolean safety ─────────────────────────────────────────────────────

class TestPandasBooleanSafety:
    """
    Guard against 'truth value of a Series is ambiguous' errors.
    All values that participate in boolean conditions must be Python scalars.
    """

    def test_analyze_airline_returns_python_bool(self):
        df = sample_df()
        result = analyze_airline(df)
        assert type(result["is_fragmented"]) is bool

    def test_analyze_airline_fragmented_bool(self):
        rows = [{"airline": f"A{i}", "origin": "X", "destination": "Y",
                 "booking_date": datetime(2024, 1, i+1),
                 "travel_date": datetime(2024, 1, i+2)} for i in range(10)]
        df = make_travel_df(rows)
        result = analyze_airline(df)
        assert type(result["is_fragmented"]) is bool

    def test_analyze_booking_counts_are_python_int(self):
        base = datetime(2024, 1, 10)
        rows = [{"airline": "IndiGo", "origin": "DEL", "destination": "BOM",
                 "booking_date": base - timedelta(days=g), "travel_date": base}
                for g in [1, 5, 15]]
        df = make_travel_df(rows)
        result = analyze_booking(df)
        assert type(result["last_minute_count"]) is int
        assert type(result["early_booking_count"]) is int
        for bucket in result["gap_distribution"].values():
            assert type(bucket["count"]) is int

    def test_analyze_route_repeated_pct_is_float(self):
        df = sample_df()
        result = analyze_routes(df)
        assert isinstance(result["repeated_route_pct"], float)
        assert type(result["most_frequent_route_count"]) is int

    def test_loyalty_miles_earned_is_python_int(self):
        travel = sample_df()
        pnrs = travel["pnr"].tolist()[:5]
        loyalty = pd.DataFrame({
            "pnr": pnrs,
            "miles_earned": np.array([1000, 1200, 800, 1500, 900], dtype=np.int64),
        })
        result = analyze_loyalty(travel, loyalty)
        assert type(result["miles_already_earned"]) is int

    def test_parse_dates_no_chained_assignment(self):
        # Exercises the CoW-safe .where() path — must not raise ChainedAssignmentError.
        # Uses ISO dates (always parseable) and an unparseable value.
        series = pd.Series(["2024-06-01", "2024-07-15", "not-a-date", None])
        result = _parse_dates(series, "test_col")
        # pandas 2.x uses datetime64[us]; older uses datetime64[ns] — accept either
        assert str(result.dtype).startswith("datetime64")
        # Valid ISO dates parse correctly
        assert pd.notna(result.iloc[0])
        assert pd.notna(result.iloc[1])
        # Unparseable string → NaT
        assert pd.isna(result.iloc[2])
        # None → NaT
        assert pd.isna(result.iloc[3])

    def test_normalize_travel_no_boolean_series_error(self):
        # Full normalize_travel() run — would raise if any Series appeared in if-condition
        base = datetime(2024, 1, 1)
        rows = []
        for i in range(5):
            td = base + timedelta(days=i * 7)
            rows.append({
                "airline": "6e",
                "origin": "del",
                "destination": "bom",
                "booking_date": (td - timedelta(days=3)).strftime("%Y-%m-%d"),
                "travel_date": td.strftime("%Y-%m-%d"),
                "pnr": f"PNR{i:03d}",
            })
        df = pd.DataFrame(rows)
        df["booking_date"] = pd.to_datetime(df["booking_date"])
        df["travel_date"] = pd.to_datetime(df["travel_date"])
        result = normalize_travel(df)
        assert len(result) == 5
        assert result["airline"].iloc[0] == "IndiGo"
