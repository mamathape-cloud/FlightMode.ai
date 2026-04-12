"""Tests for flexible column mapping in the ingestion layer.

Covers all three mapping passes:
  Pass 1 — exact alias table
  Pass 2 — prefix regex match
  Pass 3 — contains match
And validates that mapping always precedes column validation.
"""

import os
import tempfile

import pandas as pd
import pytest

from flightmode.core.ingestion import (
    _normalize_col,
    _map_columns,
    load_travel_data,
    IngestionError,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _write_excel(columns: list[str], suffix: str = ".xlsx") -> str:
    """Write a one-row Excel (or CSV) file with the given column names."""
    row = {}
    for c in columns:
        cl = c.lower()
        if any(k in cl for k in ("airline", "carrier")):
            row[c] = "IndiGo"
        elif any(k in cl for k in ("origin", "departure", "from", "source")):
            row[c] = "DEL"
        elif any(k in cl for k in ("destination", "arrival", "to")):
            row[c] = "BOM"
        else:
            row[c] = "2024-06-01"

    df = pd.DataFrame([row])
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
        path = f.name

    if suffix == ".csv":
        df.to_csv(path, index=False)
    else:
        df.to_excel(path, index=False, sheet_name="Travel Data")
    return path


def _load(columns: list[str], suffix: str = ".xlsx") -> pd.DataFrame:
    path = _write_excel(columns, suffix)
    try:
        return load_travel_data(path)
    finally:
        os.unlink(path)


# ── _normalize_col ────────────────────────────────────────────────────────────

class TestNormalizeCol:
    def test_strips_and_lowercases(self):
        assert _normalize_col("  Booking_Date  ") == "booking_date"

    def test_spaces_to_underscores(self):
        assert _normalize_col("Travel Date") == "travel_date"

    def test_multiple_spaces_collapsed(self):
        # Multiple spaces collapse to a single underscore
        assert _normalize_col("Origin  Airport") == "origin_airport"

    def test_already_clean(self):
        assert _normalize_col("airline") == "airline"

    def test_mixed_case(self):
        assert _normalize_col("Destination_(Airport_Code)") == "destination_(airport_code)"


# ── _map_columns ──────────────────────────────────────────────────────────────

class TestMapColumns:

    # Pass 1: explicit alias
    def test_pass1_booking_date_yyyy(self):
        assert _map_columns(["booking_date_(yyyy-mm-dd)"])["booking_date_(yyyy-mm-dd)"] == "booking_date"

    def test_pass1_travel_date_yyyy(self):
        assert _map_columns(["travel_date_(yyyy-mm-dd)"])["travel_date_(yyyy-mm-dd)"] == "travel_date"

    def test_pass1_origin_airport_code(self):
        assert _map_columns(["origin_(airport_code)"])["origin_(airport_code)"] == "origin"

    def test_pass1_destination_airport_code(self):
        assert _map_columns(["destination_(airport_code)"])["destination_(airport_code)"] == "destination"

    def test_pass1_departure_alias(self):
        assert _map_columns(["departure"])["departure"] == "origin"

    def test_pass1_arrival_alias(self):
        assert _map_columns(["arrival"])["arrival"] == "destination"

    def test_pass1_carrier_alias(self):
        assert _map_columns(["carrier"])["carrier"] == "airline"

    def test_pass1_flight_date_alias(self):
        assert _map_columns(["flight_date"])["flight_date"] == "travel_date"

    def test_pass1_date_of_booking(self):
        assert _map_columns(["date_of_booking"])["date_of_booking"] == "booking_date"

    # Pass 2: prefix match
    def test_pass2_booking_date_suffix(self):
        assert _map_columns(["booking_date_(custom)"])["booking_date_(custom)"] == "booking_date"

    def test_pass2_travel_date_utc(self):
        assert _map_columns(["travel_date_utc"])["travel_date_utc"] == "travel_date"

    def test_pass2_origin_code(self):
        assert _map_columns(["origin_code"])["origin_code"] == "origin"

    def test_pass2_destination_iata(self):
        assert _map_columns(["destination_iata"])["destination_iata"] == "destination"

    def test_pass2_airline_iata(self):
        assert _map_columns(["airline_iata"])["airline_iata"] == "airline"

    # Pass 3: contains match
    def test_pass3_contains_booking_date(self):
        assert _map_columns(["dep_booking_date_col"])["dep_booking_date_col"] == "booking_date"

    def test_pass3_contains_travel_date(self):
        assert _map_columns(["actual_travel_date_info"])["actual_travel_date_info"] == "travel_date"

    def test_pass3_contains_origin(self):
        assert _map_columns(["port_of_origin"])["port_of_origin"] == "origin"

    def test_pass3_contains_destination(self):
        assert _map_columns(["final_destination_code"])["final_destination_code"] == "destination"

    def test_pass3_contains_airline(self):
        assert _map_columns(["preferred_airline_code"])["preferred_airline_code"] == "airline"

    # Canonical names must not be remapped
    def test_canonical_untouched(self):
        cols = ["airline", "origin", "destination", "booking_date", "travel_date"]
        assert _map_columns(cols) == {}

    # Mixed scenario
    def test_mixed_columns(self):
        cols = ["booking_date_(yyyy-mm-dd)", "pnr", "fare", "carrier"]
        m = _map_columns(cols)
        assert m["booking_date_(yyyy-mm-dd)"] == "booking_date"
        assert m["carrier"] == "airline"
        assert "pnr" not in m
        assert "fare" not in m


# ── load_travel_data integration ──────────────────────────────────────────────

class TestLoadTravelDataFlexibleColumns:

    def test_canonical_columns(self):
        df = _load(["airline", "origin", "destination", "booking_date", "travel_date"])
        for col in ["airline", "origin", "destination", "booking_date", "travel_date"]:
            assert col in df.columns

    def test_verbose_date_columns(self):
        df = _load([
            "airline",
            "origin_(airport_code)",
            "destination_(airport_code)",
            "booking_date_(yyyy-mm-dd)",
            "travel_date_(yyyy-mm-dd)",
        ])
        assert "booking_date" in df.columns
        assert "travel_date" in df.columns
        assert "origin" in df.columns
        assert "destination" in df.columns

    def test_departure_arrival_aliases(self):
        df = _load(["airline", "departure", "arrival", "booking_date", "travel_date"])
        assert "origin" in df.columns
        assert "destination" in df.columns

    def test_carrier_alias(self):
        df = _load(["carrier", "origin", "destination", "booking_date", "travel_date"])
        assert "airline" in df.columns

    def test_contains_match_columns(self):
        # Column names where the keyword is embedded, not a prefix
        df = _load([
            "preferred_airline_code",
            "port_of_origin",
            "final_destination_code",
            "dep_booking_date",
            "actual_travel_date",
        ])
        assert "airline" in df.columns
        assert "origin" in df.columns
        assert "destination" in df.columns
        assert "booking_date" in df.columns
        assert "travel_date" in df.columns

    def test_csv_file(self):
        df = _load(
            ["airline", "origin_(airport_code)", "destination_(airport_code)",
             "booking_date_(yyyy-mm-dd)", "travel_date_(yyyy-mm-dd)"],
            suffix=".csv",
        )
        assert "origin" in df.columns
        assert "destination" in df.columns

    def test_uppercase_column_names_normalized(self):
        df = _load(["AIRLINE", "ORIGIN", "DESTINATION", "BOOKING_DATE", "TRAVEL_DATE"])
        for col in ["airline", "origin", "destination", "booking_date", "travel_date"]:
            assert col in df.columns

    def test_mixed_case_with_spaces(self):
        df = _load([
            "Airline Name",
            "Origin Airport Code",
            "Destination Airport Code",
            "Booking Date (YYYY-MM-DD)",
            "Travel Date (YYYY-MM-DD)",
        ])
        assert "airline" in df.columns
        assert "origin" in df.columns
        assert "destination" in df.columns
        assert "booking_date" in df.columns
        assert "travel_date" in df.columns

    def test_missing_required_column_raises_after_mapping(self):
        with pytest.raises(IngestionError, match="Missing required columns"):
            _load(["airline", "origin", "booking_date", "travel_date"])  # no destination

    def test_downstream_columns_are_standard(self):
        """All downstream modules must receive canonical column names."""
        df = _load([
            "carrier",
            "departure_airport",
            "arrival_airport",
            "booking_date_(yyyy-mm-dd)",
            "travel_date_(yyyy-mm-dd)",
        ])
        assert set(["airline", "origin", "destination", "booking_date", "travel_date"]).issubset(
            set(df.columns)
        )
