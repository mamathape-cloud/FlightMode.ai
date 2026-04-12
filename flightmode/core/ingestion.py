"""Step 1: Data Ingestion - Read and validate Excel travel data.

Column resolution order (applied before validation):
  1. Normalize  — lowercase, strip whitespace, spaces → underscores
  2. Alias map  — exact match against known variant names
  3. Contains   — if a required keyword appears anywhere in the column name,
                  map it (e.g. "dep_booking_date_utc" → "booking_date")
  4. Validate   — raise IngestionError only after all mapping is exhausted
"""

import re
import pandas as pd
from pathlib import Path
from typing import Optional

REQUIRED_COLUMNS = {"airline", "origin", "destination", "booking_date", "travel_date"}
OPTIONAL_COLUMNS = {"pnr", "class", "fare", "loyalty_program", "miles_earned", "passenger_name"}

# Exact alias table (keys: already normalized — lowercase, underscores).
COLUMN_ALIASES: dict[str, str] = {
    # booking_date variants
    "booking_date_(yyyy-mm-dd)": "booking_date",
    "booking_date_(dd/mm/yyyy)": "booking_date",
    "booking_date_(mm/dd/yyyy)": "booking_date",
    "date_of_booking":           "booking_date",
    "booked_date":               "booking_date",
    "reservation_date":          "booking_date",
    # travel_date variants
    "travel_date_(yyyy-mm-dd)":  "travel_date",
    "travel_date_(dd/mm/yyyy)":  "travel_date",
    "travel_date_(mm/dd/yyyy)":  "travel_date",
    "flight_date":               "travel_date",
    "date_of_travel":            "travel_date",
    "departure_date":            "travel_date",
    "journey_date":              "travel_date",
    # origin variants
    "origin_(airport_code)":     "origin",
    "origin_airport":            "origin",
    "origin_airport_code":       "origin",
    "departure":                 "origin",
    "departure_airport":         "origin",
    "from":                      "origin",
    "from_airport":              "origin",
    "source":                    "origin",
    "source_airport":            "origin",
    # destination variants
    "destination_(airport_code)": "destination",
    "destination_airport":        "destination",
    "destination_airport_code":   "destination",
    "arrival":                    "destination",
    "arrival_airport":            "destination",
    "to":                         "destination",
    "to_airport":                 "destination",
    # airline variants
    "carrier":                   "airline",
    "airline_name":              "airline",
    "operating_carrier":         "airline",
    "airline_code":              "airline",
    "flight_carrier":            "airline",
}

# For contains-based matching: maps substring → canonical column.
# Ordered from most specific to least specific to avoid false matches.
CONTAINS_MAP: list[tuple[str, str]] = [
    ("booking_date", "booking_date"),
    ("travel_date",  "travel_date"),
    ("destination",  "destination"),
    ("origin",       "origin"),
    ("airline",      "airline"),
]


class IngestionError(Exception):
    pass


def _normalize_col(raw: str) -> str:
    """Lowercase, strip outer whitespace, collapse internal whitespace to underscores."""
    return re.sub(r"\s+", "_", raw.strip().lower())


def _map_columns(columns: list[str]) -> dict[str, str]:
    """
    Build a rename dict for any column that is not already canonical.

    Resolution order:
      Pass 1 — exact alias table lookup
      Pass 2 — prefix match  (e.g. "booking_date_utc"  → "booking_date")
      Pass 3 — contains match (e.g. "dep_booking_date"  → "booking_date")

    A column that already equals a canonical name is left untouched.
    The first match wins; later passes are skipped for that column.
    """
    canonical_set = REQUIRED_COLUMNS | OPTIONAL_COLUMNS
    mapping: dict[str, str] = {}

    for col in columns:
        # Already canonical — nothing to do
        if col in canonical_set:
            continue

        # Pass 1: exact alias
        if col in COLUMN_ALIASES:
            mapping[col] = COLUMN_ALIASES[col]
            continue

        # Pass 2: prefix match — canonical name at the start followed by
        # a non-alphanumeric character (handles "booking_date_(fmt)", "origin_code" …)
        matched = False
        for canonical in REQUIRED_COLUMNS:
            if re.match(rf"^{re.escape(canonical)}[^a-z0-9]", col):
                mapping[col] = canonical
                matched = True
                break
        if matched:
            continue

        # Pass 3: contains match — canonical keyword appears anywhere in name
        for keyword, canonical in CONTAINS_MAP:
            if keyword in col:
                mapping[col] = canonical
                break

    return mapping


def load_travel_data(filepath: str) -> pd.DataFrame:
    """
    Load travel data from Excel or CSV.

    Execution order:
      1. Read raw file
      2. Normalize column names
      3. Apply column mapping (alias → prefix → contains)
      4. Validate required columns
    """
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

    # Step 1: normalize
    df.columns = [_normalize_col(c) for c in df.columns]

    # Step 2 & 3: map flexible names → canonical names
    mapping = _map_columns(list(df.columns))
    if mapping:
        df.rename(columns=mapping, inplace=True)

    # Step 4: validate — only after mapping is fully applied
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise IngestionError(
            f"Missing required columns: {missing}. "
            f"Found after mapping: {sorted(df.columns.tolist())}"
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
        df.columns = [_normalize_col(c) for c in df.columns]
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
