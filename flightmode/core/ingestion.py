"""Step 1: Data Ingestion - Read and validate Excel travel data."""

import re
import pandas as pd
from pathlib import Path
from typing import Optional

REQUIRED_COLUMNS = {"airline", "origin", "destination", "booking_date", "travel_date"}
OPTIONAL_COLUMNS = {"PNR", "pnr", "class", "fare", "loyalty_program", "miles_earned", "passenger_name"}

# Explicit mappings for known column name variations.
# Keys are already lowercased + underscored (post initial normalization).
COLUMN_ALIASES: dict[str, str] = {
    "booking_date_(yyyy-mm-dd)": "booking_date",
    "booking_date_(dd/mm/yyyy)": "booking_date",
    "booking_date_(mm/dd/yyyy)": "booking_date",
    "travel_date_(yyyy-mm-dd)": "travel_date",
    "travel_date_(dd/mm/yyyy)": "travel_date",
    "travel_date_(mm/dd/yyyy)": "travel_date",
    "origin_(airport_code)":     "origin",
    "origin_airport":            "origin",
    "origin_airport_code":       "origin",
    "departure":                 "origin",
    "departure_airport":         "origin",
    "from":                      "origin",
    "from_airport":              "origin",
    "destination_(airport_code)": "destination",
    "destination_airport":       "destination",
    "destination_airport_code":  "destination",
    "arrival":                   "destination",
    "arrival_airport":           "destination",
    "to":                        "destination",
    "to_airport":                "destination",
    "carrier":                   "airline",
    "airline_name":              "airline",
    "operating_carrier":         "airline",
    "flight_date":               "travel_date",
    "date_of_travel":            "travel_date",
    "date_of_booking":           "booking_date",
}


def _normalize_col(raw: str) -> str:
    """Lowercase, strip, collapse whitespace to underscores."""
    return raw.strip().lower().replace(" ", "_")


def _resolve_column_mapping(columns: list[str]) -> dict[str, str]:
    """
    Build a rename mapping from raw (already normalized) column names to
    canonical names. Two-pass resolution:

    Pass 1 — explicit alias table.
    Pass 2 — prefix match: if a column starts with a required name followed
              by a non-alphanumeric character (e.g. '(', '_', ' '), map it.

    Columns that already match a canonical name are left untouched.
    """
    mapping: dict[str, str] = {}
    for col in columns:
        if col in mapping:
            continue

        # Pass 1: explicit alias
        if col in COLUMN_ALIASES:
            mapping[col] = COLUMN_ALIASES[col]
            continue

        # Pass 2: prefix match against required column names
        for canonical in REQUIRED_COLUMNS:
            if col == canonical:
                break  # already correct, no rename needed
            # Match columns like "booking_date_..." or "booking_date(..."
            if re.match(rf"^{re.escape(canonical)}[^a-z0-9]", col):
                mapping[col] = canonical
                break

    return mapping


class IngestionError(Exception):
    pass


def load_travel_data(filepath: str) -> pd.DataFrame:
    """Read the travel sheet from an Excel file and validate required columns."""
    path = Path(filepath)
    if not path.exists():
        raise IngestionError(f"File not found: {filepath}")
    if path.suffix not in (".xlsx", ".xls", ".csv"):
        raise IngestionError(f"Unsupported file format: {path.suffix}. Use .xlsx, .xls, or .csv")

    try:
        if path.suffix == ".csv":
            df = pd.read_csv(filepath)
        else:
            xl = pd.ExcelFile(filepath)
            sheet_names = xl.sheet_names
            travel_sheet = next(
                (s for s in sheet_names if "travel" in s.lower()), sheet_names[0]
            )
            df = xl.parse(travel_sheet)
    except Exception as e:
        raise IngestionError(f"Failed to read file: {e}")

    # Step 1: basic normalization (lowercase, strip, spaces → underscores)
    df.columns = [_normalize_col(c) for c in df.columns]

    # Step 2: flexible column mapping before validation
    mapping = _resolve_column_mapping(list(df.columns))
    if mapping:
        df.rename(columns=mapping, inplace=True)

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise IngestionError(
            f"Missing required columns: {missing}. Found: {list(df.columns)}"
        )

    return df


def load_loyalty_data(filepath: str) -> Optional[pd.DataFrame]:
    """Read the loyalty sheet from an Excel file. Returns None if not present."""
    path = Path(filepath)
    if not path.exists():
        return None
    if path.suffix == ".csv":
        return None

    try:
        xl = pd.ExcelFile(filepath)
        sheet_names = xl.sheet_names
        loyalty_sheet = next(
            (s for s in sheet_names if "loyalty" in s.lower() or "miles" in s.lower()),
            None,
        )
        if loyalty_sheet is None:
            return None
        df = xl.parse(loyalty_sheet)
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
        return df
    except Exception:
        return None


def ingest(filepath: str) -> dict:
    """Main ingestion entry point. Returns dict with travel and loyalty DataFrames."""
    travel_df = load_travel_data(filepath)
    loyalty_df = load_loyalty_data(filepath)

    return {
        "travel": travel_df,
        "loyalty": loyalty_df,
        "source_file": filepath,
        "row_count": len(travel_df),
        "has_loyalty": loyalty_df is not None,
    }
