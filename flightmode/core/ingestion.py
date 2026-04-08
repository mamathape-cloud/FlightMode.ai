"""Step 1: Data Ingestion - Read and validate Excel travel data."""

import pandas as pd
from pathlib import Path
from typing import Optional

REQUIRED_COLUMNS = {"airline", "origin", "destination", "booking_date", "travel_date"}
OPTIONAL_COLUMNS = {"PNR", "pnr", "class", "fare", "loyalty_program", "miles_earned", "passenger_name"}


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

    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

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
