"""Tests for the ingestion layer.

Covers:
  - _normalize_col()
  - _map_columns() — all three passes
  - load_sheets() — sheet discovery, missing sheets, flexible column names
  - ingest() — end-to-end dict output
  - Backward-compatible helpers load_travel_data() / load_loyalty_data()
"""

import os
import tempfile

import pandas as pd
import pytest

from flightmode.core.ingestion import (
    _normalize_col,
    _map_columns,
    load_sheets,
    load_travel_data,
    load_loyalty_data,
    ingest,
    IngestionError,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

TRAVEL_COLS = ["airline", "origin", "destination", "booking_date", "travel_date"]
TRAVEL_ROW  = {
    "airline": "IndiGo", "origin": "DEL", "destination": "BOM",
    "booking_date": "2024-06-01", "travel_date": "2024-06-10",
}
LOYALTY_COLS = ["PNR", "airline", "loyalty_program", "miles_earned"]
LOYALTY_ROW  = {"PNR": "FM123", "airline": "IndiGo", "loyalty_program": "6E Rewards", "miles_earned": 800}


def _make_excel(
    travel_cols: list[str] = None,
    travel_rows: list[dict] = None,
    loyalty_cols: list[str] = None,
    loyalty_rows: list[dict] = None,
    travel_sheet: str = "Travel_Data",
    loyalty_sheet: str = "Loyalty_Data",
    include_loyalty: bool = True,
) -> str:
    """Write a temp Excel file and return its path."""
    travel_cols = travel_cols or TRAVEL_COLS
    travel_rows = travel_rows or [TRAVEL_ROW]
    loyalty_rows = loyalty_rows or [LOYALTY_ROW]

    t_df = pd.DataFrame(travel_rows, columns=travel_cols)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as f:
        path = f.name

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        t_df.to_excel(writer, sheet_name=travel_sheet, index=False)
        if include_loyalty:
            l_df = pd.DataFrame(loyalty_rows, columns=loyalty_cols or LOYALTY_COLS)
            l_df.to_excel(writer, sheet_name=loyalty_sheet, index=False)

    return path


def _make_csv(cols: list[str] = None, rows: list[dict] = None) -> str:
    cols = cols or TRAVEL_COLS
    rows = rows or [TRAVEL_ROW]
    df = pd.DataFrame(rows, columns=cols)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv", mode="w") as f:
        path = f.name
    df.to_csv(path, index=False)
    return path


# ── _normalize_col ────────────────────────────────────────────────────────────

class TestNormalizeCol:
    def test_strips_and_lowercases(self):
        assert _normalize_col("  Booking_Date  ") == "booking_date"

    def test_spaces_to_underscores(self):
        assert _normalize_col("Travel Date") == "travel_date"

    def test_multiple_spaces_collapsed(self):
        assert _normalize_col("Origin  Airport") == "origin_airport"

    def test_already_clean(self):
        assert _normalize_col("airline") == "airline"

    def test_mixed_case(self):
        assert _normalize_col("Destination_(Airport_Code)") == "destination_(airport_code)"


# ── _map_columns ──────────────────────────────────────────────────────────────

class TestMapColumns:

    # Pass 1: exact alias
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

    def test_canonical_untouched(self):
        cols = ["airline", "origin", "destination", "booking_date", "travel_date"]
        assert _map_columns(cols) == {}

    def test_mixed_columns(self):
        cols = ["booking_date_(yyyy-mm-dd)", "pnr", "fare", "carrier"]
        m = _map_columns(cols)
        assert m["booking_date_(yyyy-mm-dd)"] == "booking_date"
        assert m["carrier"] == "airline"
        assert "pnr" not in m
        assert "fare" not in m


# ── load_sheets ───────────────────────────────────────────────────────────────

class TestLoadSheets:

    # ── Happy paths ────────────────────────────────────────────────────────────

    def test_both_sheets_present(self):
        path = _make_excel()
        try:
            travel, loyalty = load_sheets(path)
            assert travel is not None
            assert loyalty is not None
            for col in ["airline", "origin", "destination", "booking_date", "travel_date"]:
                assert col in travel.columns
        finally:
            os.unlink(path)

    def test_travel_only_no_loyalty_sheet(self):
        path = _make_excel(include_loyalty=False)
        try:
            travel, loyalty = load_sheets(path)
            assert travel is not None
            assert loyalty is None
        finally:
            os.unlink(path)

    def test_csv_travel_only(self):
        path = _make_csv()
        try:
            travel, loyalty = load_sheets(path)
            assert travel is not None
            assert loyalty is None
        finally:
            os.unlink(path)

    def test_canonical_columns_pass(self):
        path = _make_excel()
        try:
            travel, _ = load_sheets(path)
            assert set(TRAVEL_COLS).issubset(set(travel.columns))
        finally:
            os.unlink(path)

    # ── Sheet name variants ────────────────────────────────────────────────────

    def test_travel_data_underscore_sheet_name(self):
        path = _make_excel(travel_sheet="Travel_Data", loyalty_sheet="Loyalty_Data")
        try:
            travel, loyalty = load_sheets(path)
            assert travel is not None
            assert loyalty is not None
        finally:
            os.unlink(path)

    def test_travel_data_space_sheet_name(self):
        path = _make_excel(travel_sheet="Travel Data", loyalty_sheet="Loyalty Data")
        try:
            travel, loyalty = load_sheets(path)
            assert travel is not None
        finally:
            os.unlink(path)

    def test_lowercase_sheet_names(self):
        path = _make_excel(travel_sheet="travel_data", loyalty_sheet="loyalty_data")
        try:
            travel, loyalty = load_sheets(path)
            assert travel is not None
        finally:
            os.unlink(path)

    # ── Flexible column names ──────────────────────────────────────────────────

    def test_verbose_date_column_names(self):
        cols = [
            "airline",
            "origin_(airport_code)",
            "destination_(airport_code)",
            "booking_date_(yyyy-mm-dd)",
            "travel_date_(yyyy-mm-dd)",
        ]
        rows = [{
            "airline": "IndiGo",
            "origin_(airport_code)": "DEL",
            "destination_(airport_code)": "BOM",
            "booking_date_(yyyy-mm-dd)": "2024-06-01",
            "travel_date_(yyyy-mm-dd)": "2024-06-10",
        }]
        path = _make_excel(travel_cols=cols, travel_rows=rows)
        try:
            travel, _ = load_sheets(path)
            assert "booking_date" in travel.columns
            assert "travel_date" in travel.columns
            assert "origin" in travel.columns
            assert "destination" in travel.columns
        finally:
            os.unlink(path)

    def test_departure_arrival_column_names(self):
        cols = ["airline", "departure", "arrival", "booking_date", "travel_date"]
        rows = [{"airline": "IndiGo", "departure": "DEL", "arrival": "BOM",
                 "booking_date": "2024-06-01", "travel_date": "2024-06-10"}]
        path = _make_excel(travel_cols=cols, travel_rows=rows)
        try:
            travel, _ = load_sheets(path)
            assert "origin" in travel.columns
            assert "destination" in travel.columns
        finally:
            os.unlink(path)

    def test_uppercase_column_names(self):
        cols = ["AIRLINE", "ORIGIN", "DESTINATION", "BOOKING_DATE", "TRAVEL_DATE"]
        rows = [{"AIRLINE": "IndiGo", "ORIGIN": "DEL", "DESTINATION": "BOM",
                 "BOOKING_DATE": "2024-06-01", "TRAVEL_DATE": "2024-06-10"}]
        path = _make_excel(travel_cols=cols, travel_rows=rows)
        try:
            travel, _ = load_sheets(path)
            for col in ["airline", "origin", "destination", "booking_date", "travel_date"]:
                assert col in travel.columns
        finally:
            os.unlink(path)

    def test_columns_with_spaces(self):
        cols = ["Airline Name", "Origin Airport", "Destination Airport",
                "Booking Date (YYYY-MM-DD)", "Travel Date (YYYY-MM-DD)"]
        rows = [{"Airline Name": "IndiGo", "Origin Airport": "DEL",
                 "Destination Airport": "BOM",
                 "Booking Date (YYYY-MM-DD)": "2024-06-01",
                 "Travel Date (YYYY-MM-DD)": "2024-06-10"}]
        path = _make_excel(travel_cols=cols, travel_rows=rows)
        try:
            travel, _ = load_sheets(path)
            assert "airline" in travel.columns
            assert "origin" in travel.columns
            assert "destination" in travel.columns
            assert "booking_date" in travel.columns
            assert "travel_date" in travel.columns
        finally:
            os.unlink(path)

    # ── Error paths ────────────────────────────────────────────────────────────

    def test_missing_travel_data_sheet_raises(self):
        """No Travel_Data or recognizable travel sheet → IngestionError."""
        t_df = pd.DataFrame([TRAVEL_ROW], columns=TRAVEL_COLS)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as f:
            path = f.name
        try:
            with pd.ExcelWriter(path, engine="openpyxl") as writer:
                t_df.to_excel(writer, sheet_name="Sheet1", index=False)
            with pytest.raises(IngestionError, match="Travel_Data.*sheet is required"):
                load_sheets(path)
        finally:
            os.unlink(path)

    def test_missing_required_travel_column_raises(self):
        """Travel_Data sheet present but missing 'destination' → IngestionError."""
        cols = ["airline", "origin", "booking_date", "travel_date"]  # no destination
        rows = [{"airline": "IndiGo", "origin": "DEL",
                 "booking_date": "2024-06-01", "travel_date": "2024-06-10"}]
        path = _make_excel(travel_cols=cols, travel_rows=rows, include_loyalty=False)
        try:
            with pytest.raises(IngestionError, match="missing required columns"):
                load_sheets(path)
        finally:
            os.unlink(path)

    def test_file_not_found_raises(self):
        with pytest.raises(IngestionError, match="File not found"):
            load_sheets("/nonexistent/path/file.xlsx")

    def test_unsupported_format_raises(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as f:
            f.write(b"{}")
            path = f.name
        try:
            with pytest.raises(IngestionError, match="Unsupported file format"):
                load_sheets(path)
        finally:
            os.unlink(path)

    # ── Graceful handling ──────────────────────────────────────────────────────

    def test_empty_loyalty_sheet_treated_as_none(self):
        """An empty Loyalty_Data sheet → loyalty_df is None (not empty DataFrame)."""
        t_df = pd.DataFrame([TRAVEL_ROW], columns=TRAVEL_COLS)
        l_df = pd.DataFrame(columns=LOYALTY_COLS)  # empty
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as f:
            path = f.name
        try:
            with pd.ExcelWriter(path, engine="openpyxl") as writer:
                t_df.to_excel(writer, sheet_name="Travel_Data", index=False)
                l_df.to_excel(writer, sheet_name="Loyalty_Data", index=False)
            _, loyalty = load_sheets(path)
            assert loyalty is None
        finally:
            os.unlink(path)

    def test_downstream_columns_are_canonical(self):
        """After load_sheets(), all required columns use canonical names."""
        cols = ["carrier", "departure_airport", "arrival_airport",
                "booking_date_(yyyy-mm-dd)", "travel_date_(yyyy-mm-dd)"]
        rows = [{"carrier": "IndiGo", "departure_airport": "DEL",
                 "arrival_airport": "BOM",
                 "booking_date_(yyyy-mm-dd)": "2024-06-01",
                 "travel_date_(yyyy-mm-dd)": "2024-06-10"}]
        path = _make_excel(travel_cols=cols, travel_rows=rows, include_loyalty=False)
        try:
            travel, _ = load_sheets(path)
            assert set(["airline", "origin", "destination", "booking_date", "travel_date"]).issubset(
                set(travel.columns)
            )
        finally:
            os.unlink(path)


# ── ingest() dict output ──────────────────────────────────────────────────────

class TestIngest:

    def test_returns_required_keys(self):
        path = _make_excel()
        try:
            result = ingest(path)
            assert "travel" in result
            assert "loyalty" in result
            assert "source_file" in result
            assert "row_count" in result
            assert "has_loyalty" in result
        finally:
            os.unlink(path)

    def test_has_loyalty_true_when_sheet_present(self):
        path = _make_excel(include_loyalty=True)
        try:
            result = ingest(path)
            assert result["has_loyalty"] is True
            assert result["loyalty"] is not None
        finally:
            os.unlink(path)

    def test_has_loyalty_false_when_sheet_absent(self):
        path = _make_excel(include_loyalty=False)
        try:
            result = ingest(path)
            assert result["has_loyalty"] is False
            assert result["loyalty"] is None
        finally:
            os.unlink(path)

    def test_row_count_matches_travel_rows(self):
        path = _make_excel(travel_rows=[TRAVEL_ROW, TRAVEL_ROW])
        try:
            result = ingest(path)
            assert result["row_count"] == 2
        finally:
            os.unlink(path)


# ── Backward-compatible helpers ───────────────────────────────────────────────

class TestBackwardCompatHelpers:

    def test_load_travel_data_returns_dataframe(self):
        path = _make_excel()
        try:
            df = load_travel_data(path)
            assert isinstance(df, pd.DataFrame)
            assert "airline" in df.columns
        finally:
            os.unlink(path)

    def test_load_loyalty_data_returns_dataframe(self):
        path = _make_excel(include_loyalty=True)
        try:
            df = load_loyalty_data(path)
            assert isinstance(df, pd.DataFrame)
        finally:
            os.unlink(path)

    def test_load_loyalty_data_returns_none_when_absent(self):
        path = _make_excel(include_loyalty=False)
        try:
            df = load_loyalty_data(path)
            assert df is None
        finally:
            os.unlink(path)
