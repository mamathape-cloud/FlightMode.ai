"""Step 1: Data Ingestion

Standard input format: one Excel file with two sheets:
  - "Travel_Data"  (required)
  - "Loyalty_Data" (optional)

CSV is also accepted (travel data only, no loyalty sheet).

Column resolution order applied to BOTH sheets before any validation:
  1. Normalize  — lowercase, strip whitespace, spaces/parens → underscores
  2. Alias map  — exact match against known variant names
  3. Prefix     — canonical name at start followed by non-alphanumeric char
  4. Contains   — canonical keyword appears anywhere in the column name
  5. Validate   — raise IngestionError only after all mapping is exhausted
"""

import re
import pandas as pd
from pathlib import Path
from typing import Optional

# ── Constants ─────────────────────────────────────────────────────────────────

TRAVEL_SHEET_NAMES = ["Travel_Data", "Travel Data", "travel_data", "travel data", "Travel"]
LOYALTY_SHEET_NAMES = ["Loyalty_Data", "Loyalty Data", "loyalty_data", "loyalty data", "Loyalty", "Miles"]

REQUIRED_COLUMNS = {"airline", "origin", "destination", "booking_date", "travel_date"}
OPTIONAL_COLUMNS = {"pnr", "class", "fare", "loyalty_program", "miles_earned", "passenger_name"}

COLUMN_ALIASES: dict[str, str] = {
    # booking_date
    "booking_date_(yyyy-mm-dd)": "booking_date",
    "booking_date_(dd/mm/yyyy)": "booking_date",
    "booking_date_(mm/dd/yyyy)": "booking_date",
    "date_of_booking":           "booking_date",
    "booked_date":               "booking_date",
    "reservation_date":          "booking_date",
    # travel_date
    "travel_date_(yyyy-mm-dd)":  "travel_date",
    "travel_date_(dd/mm/yyyy)":  "travel_date",
    "travel_date_(mm/dd/yyyy)":  "travel_date",
    "flight_date":               "travel_date",
    "date_of_travel":            "travel_date",
    "departure_date":            "travel_date",
    "journey_date":              "travel_date",
    # origin
    "origin_(airport_code)":     "origin",
    "origin_airport":            "origin",
    "origin_airport_code":       "origin",
    "departure":                 "origin",
    "departure_airport":         "origin",
    "from":                      "origin",
    "from_airport":              "origin",
    "source":                    "origin",
    "source_airport":            "origin",
    # destination
    "destination_(airport_code)": "destination",
    "destination_airport":        "destination",
    "destination_airport_code":   "destination",
    "arrival":                    "destination",
    "arrival_airport":            "destination",
    "to":                         "destination",
    "to_airport":                 "destination",
    # airline
    "carrier":                   "airline",
    "airline_name":              "airline",
    "operating_carrier":         "airline",
    "airline_code":              "airline",
    "flight_carrier":            "airline",
}

# Ordered most-specific → least-specific to avoid false matches
CONTAINS_MAP: list[tuple[str, str]] = [
    ("booking_date", "booking_date"),
    ("travel_date",  "travel_date"),
    ("destination",  "destination"),
    ("origin",       "origin"),
    ("airline",      "airline"),
]


# ── Exceptions ────────────────────────────────────────────────────────────────

class IngestionError(Exception):
    pass


# ── Column helpers (public so tests can import them) ──────────────────────────

def _normalize_col(raw: str) -> str:
    """
    Normalize a column name to a clean lowercase underscore identifier.

    Steps (in order):
      1. Strip outer whitespace
      2. Remove parenthesised content, e.g. "(YYYY-MM-DD)" → ""
      3. Insert underscore between CamelCase word boundaries so that
         "BookingDate" → "Booking_Date" and "TravelDate" → "Travel_Date"
         before lowercasing, enabling consistent matching regardless of
         whether the user used CamelCase, Title_Case, or lowercase.
      4. Lowercase the whole string
      5. Replace every run of non-alphanumeric characters with a single underscore
      6. Collapse multiple underscores and strip leading/trailing ones
    """
    col = raw.strip()
    col = re.sub(r"\(.*?\)", "", col)                      # remove bracket content
    col = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", col)     # camelCase → camel_Case
    col = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", col)  # ABCDef → ABC_Def
    col = col.lower()
    col = re.sub(r"[^a-z0-9]+", "_", col)                 # special chars → underscore
    col = re.sub(r"_+", "_", col)                          # collapse underscores
    return col.strip("_")


def _map_columns(columns: list[str]) -> dict[str, str]:
    """
    Build a rename dict: raw normalized column name → canonical name.

    Pass 1 — exact alias table
    Pass 2 — prefix regex  (booking_date_utc → booking_date)
    Pass 3 — contains      (dep_booking_date → booking_date)

    Canonical names are never remapped. First match wins.
    """
    canonical_set = REQUIRED_COLUMNS | OPTIONAL_COLUMNS
    mapping: dict[str, str] = {}

    for col in columns:
        if col in canonical_set:
            continue

        if col in COLUMN_ALIASES:
            mapping[col] = COLUMN_ALIASES[col]
            continue

        matched = False
        for canonical in REQUIRED_COLUMNS:
            if re.match(rf"^{re.escape(canonical)}[^a-z0-9]", col):
                mapping[col] = canonical
                matched = True
                break
        if matched:
            continue

        for keyword, canonical in CONTAINS_MAP:
            if keyword in col:
                mapping[col] = canonical
                break

    return mapping


def _prepare_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize column names, apply flexible mapping, normalize values,
    and ensure all required columns exist.
    """
    df = df.copy()

    # 1. Normalize column names
    df.columns = [_normalize_col(c) for c in df.columns]

    # 2. Map variant names → canonical names
    mapping = _map_columns(list(df.columns))
    if mapping:
        df.rename(columns=mapping, inplace=True)

    # 3. Normalize values (safe — only applied when column is present)
    if "airline" in df.columns:
        df["airline"] = df["airline"].astype(str).str.strip().str.title()

    if "booking_date" in df.columns:
        df["booking_date"] = pd.to_datetime(df["booking_date"], errors="coerce")

    if "travel_date" in df.columns:
        df["travel_date"] = pd.to_datetime(df["travel_date"], errors="coerce")

    if "amount" in df.columns:
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")

    # 4. Guarantee required columns exist — prevents KeyError downstream
    for col in ["airline", "origin", "destination", "booking_date", "travel_date"]:
        if col not in df.columns:
            df[col] = None

    return df


# ── Sheet resolution ──────────────────────────────────────────────────────────

def _find_sheet(sheet_names: list[str], candidates: list[str]) -> Optional[str]:
    """Return the first sheet name that matches any candidate (case-insensitive)."""
    lower_map = {s.lower(): s for s in sheet_names}
    for candidate in candidates:
        match = lower_map.get(candidate.lower())
        if match:
            return match
    # Fallback: any sheet whose name contains a candidate substring
    for sheet in sheet_names:
        sl = sheet.lower()
        for candidate in candidates:
            if candidate.lower().split("_")[0] in sl:
                return sheet
    return None


# ── Public ingestion API ──────────────────────────────────────────────────────

def load_sheets(filepath: str) -> tuple[pd.DataFrame, Optional[pd.DataFrame]]:
    """
    Read an Excel file and return (travel_df, loyalty_df).

    - Reads ALL sheets in one pass with sheet_name=None.
    - Looks for "Travel_Data" sheet (required) and "Loyalty_Data" sheet (optional).
    - Applies normalize → map → validate before returning.
    - CSV files are also accepted (travel only, loyalty = None).

    Returns:
        (travel_df, loyalty_df)  where loyalty_df may be None.

    Raises:
        IngestionError if the file cannot be read, Travel_Data sheet is missing,
        or required columns are absent after all mapping.
    """
    path = Path(filepath)
    if not path.exists():
        raise IngestionError(f"File not found: {filepath}")
    if path.suffix not in (".xlsx", ".xls", ".csv"):
        raise IngestionError(
            f"Unsupported file format: {path.suffix}. Use .xlsx, .xls, or .csv"
        )

    # ── CSV path (travel only) ────────────────────────────────────────────────
    if path.suffix == ".csv":
        try:
            raw_travel = pd.read_csv(filepath)
        except Exception as e:
            raise IngestionError(f"Failed to read CSV: {e}")
        travel_df = _prepare_df(raw_travel)
        travel_df = travel_df.dropna(
            subset=["booking_date", "travel_date", "origin", "destination"]
        )
        _validate_travel(travel_df)
        print(f"[Ingestion] Final columns: {travel_df.columns.tolist()}")
        print(f"[Ingestion] Rows loaded: {len(travel_df)}")
        return travel_df, None

    # ── Excel path ────────────────────────────────────────────────────────────
    try:
        sheets: dict[str, pd.DataFrame] = pd.read_excel(filepath, sheet_name=None)
    except Exception as e:
        raise IngestionError(f"Failed to read Excel file: {e}")

    sheet_names = list(sheets.keys())

    # Resolve Travel_Data sheet
    travel_sheet = _find_sheet(sheet_names, TRAVEL_SHEET_NAMES)
    if travel_sheet is None:
        raise IngestionError(
            f"'Travel_Data' sheet is required but not found. "
            f"Available sheets: {sheet_names}"
        )

    # Resolve Loyalty_Data sheet (optional)
    loyalty_sheet = _find_sheet(sheet_names, LOYALTY_SHEET_NAMES)

    # Prepare travel DataFrame
    travel_df = _prepare_df(sheets[travel_sheet])
    travel_df = travel_df.dropna(
        subset=["booking_date", "travel_date", "origin", "destination"]
    )
    _validate_travel(travel_df)

    # Prepare loyalty DataFrame (None if sheet absent or empty)
    loyalty_df: Optional[pd.DataFrame] = None
    if loyalty_sheet and loyalty_sheet != travel_sheet:
        raw_loyalty = sheets[loyalty_sheet]
        if not raw_loyalty.empty:
            loyalty_df = _prepare_df(raw_loyalty)

    print(f"[Ingestion] Final columns: {travel_df.columns.tolist()}")
    print(f"[Ingestion] Rows loaded: {len(travel_df)}")
    return travel_df, loyalty_df


def _validate_travel(df: pd.DataFrame) -> None:
    """Raise IngestionError if any required column is missing after mapping."""
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise IngestionError(
            f"Missing required fields after processing: {sorted(missing)}.\n"
            f"Detected columns: {sorted(df.columns.tolist())}\n"
            f"Please check column names in your Excel file."
        )


def ingest(filepath: str) -> dict:
    """
    Main ingestion entry point.

    Returns a dict compatible with the existing normalization + pipeline steps:
      {
        "travel":      pd.DataFrame,
        "loyalty":     pd.DataFrame | None,
        "source_file": str,
        "row_count":   int,
        "has_loyalty": bool,
      }
    """
    travel_df, loyalty_df = load_sheets(filepath)
    return {
        "travel":      travel_df,
        "loyalty":     loyalty_df,
        "source_file": filepath,
        "row_count":   len(travel_df),
        "has_loyalty": loyalty_df is not None,
    }


# ── Legacy helpers kept for backward compatibility with existing tests ─────────

def load_travel_data(filepath: str) -> pd.DataFrame:
    """Backward-compatible wrapper — returns travel DataFrame only."""
    travel_df, _ = load_sheets(filepath)
    return travel_df


def load_loyalty_data(filepath: str) -> Optional[pd.DataFrame]:
    """Backward-compatible wrapper — returns loyalty DataFrame or None."""
    _, loyalty_df = load_sheets(filepath)
    return loyalty_df
