"""Tests for flexible column mapping in the ingestion layer."""

import pandas as pd
import pytest
import tempfile
import os
from datetime import datetime

from flightmode.core.ingestion import (
    _normalize_col,
    _resolve_column_mapping,
    load_travel_data,
    IngestionError,
)


def _make_excel(columns: list[str], output_path: str) -> str:
    """Write a minimal Excel file with the given column names and one data row."""
    row = {
        c: "IndiGo" if "airline" in c.lower() or c.lower() in ("carrier", "airline_name", "operating_carrier")
        else ("DEL" if any(k in c.lower() for k in ("origin", "departure", "from"))
              else ("BOM" if any(k in c.lower() for k in ("destination", "arrival", "to"))
                    else "2024-06-01"))
        for c in columns
    }
    df = pd.DataFrame([row])
    df.to_excel(output_path, index=False, sheet_name="Travel Data")
    return output_path


# ── _normalize_col ────────────────────────────────────────────────────────────

class TestNormalizeCol:
    def test_strips_and_lowercases(self):
        assert _normalize_col("  Booking_Date  ") == "booking_date"

    def test_spaces_become_underscores(self):
        assert _normalize_col("Travel Date") == "travel_date"

    def test_already_clean(self):
        assert _normalize_col("airline") == "airline"


# ── _resolve_column_mapping ───────────────────────────────────────────────────

class TestResolveColumnMapping:
    def test_explicit_alias_booking_date(self):
        mapping = _resolve_column_mapping(["booking_date_(yyyy-mm-dd)"])
        assert mapping["booking_date_(yyyy-mm-dd)"] == "booking_date"

    def test_explicit_alias_travel_date(self):
        mapping = _resolve_column_mapping(["travel_date_(yyyy-mm-dd)"])
        assert mapping["travel_date_(yyyy-mm-dd)"] == "travel_date"

    def test_explicit_alias_origin(self):
        mapping = _resolve_column_mapping(["origin_(airport_code)"])
        assert mapping["origin_(airport_code)"] == "origin"

    def test_explicit_alias_destination(self):
        mapping = _resolve_column_mapping(["destination_(airport_code)"])
        assert mapping["destination_(airport_code)"] == "destination"

    def test_prefix_match_booking_date(self):
        mapping = _resolve_column_mapping(["booking_date_(custom_format)"])
        assert mapping["booking_date_(custom_format)"] == "booking_date"

    def test_prefix_match_travel_date(self):
        mapping = _resolve_column_mapping(["travel_date_utc"])
        assert mapping["travel_date_utc"] == "travel_date"

    def test_prefix_match_origin(self):
        mapping = _resolve_column_mapping(["origin_code"])
        assert mapping["origin_code"] == "origin"

    def test_canonical_names_not_remapped(self):
        cols = ["airline", "origin", "destination", "booking_date", "travel_date"]
        mapping = _resolve_column_mapping(cols)
        assert mapping == {}

    def test_departure_alias(self):
        mapping = _resolve_column_mapping(["departure"])
        assert mapping["departure"] == "origin"

    def test_arrival_alias(self):
        mapping = _resolve_column_mapping(["arrival"])
        assert mapping["arrival"] == "destination"

    def test_carrier_alias(self):
        mapping = _resolve_column_mapping(["carrier"])
        assert mapping["carrier"] == "airline"

    def test_mixed_known_and_unknown_columns(self):
        cols = ["booking_date_(yyyy-mm-dd)", "pnr", "fare"]
        mapping = _resolve_column_mapping(cols)
        assert mapping["booking_date_(yyyy-mm-dd)"] == "booking_date"
        assert "pnr" not in mapping
        assert "fare" not in mapping


# ── Full load_travel_data integration ────────────────────────────────────────

class TestLoadTravelDataFlexibleColumns:
    def _run(self, columns):
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            path = f.name
        try:
            _make_excel(columns, path)
            return load_travel_data(path)
        finally:
            os.unlink(path)

    def test_canonical_columns_pass(self):
        df = self._run(["airline", "origin", "destination", "booking_date", "travel_date"])
        assert set(["airline", "origin", "destination", "booking_date", "travel_date"]).issubset(df.columns)

    def test_verbose_date_columns_pass(self):
        df = self._run([
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

    def test_alternative_origin_destination(self):
        df = self._run(["airline", "departure", "arrival", "booking_date", "travel_date"])
        assert "origin" in df.columns
        assert "destination" in df.columns

    def test_carrier_alias(self):
        df = self._run(["carrier", "origin", "destination", "booking_date", "travel_date"])
        assert "airline" in df.columns

    def test_missing_required_column_raises(self):
        with pytest.raises(IngestionError, match="Missing required columns"):
            self._run(["airline", "origin", "booking_date", "travel_date"])
