"""Step 2: Normalization - Clean and standardize travel data."""

import pandas as pd
from typing import Optional

AIRLINE_ALIASES = {
    "air india": "Air India",
    "ai": "Air India",
    "indigo": "IndiGo",
    "6e": "IndiGo",
    "go air": "Go Air",
    "go first": "Go First",
    "g8": "Go First",
    "spicejet": "SpiceJet",
    "sg": "SpiceJet",
    "vistara": "Vistara",
    "uk": "Vistara",
    "akasa": "Akasa Air",
    "qp": "Akasa Air",
    "air asia": "AirAsia India",
    "i5": "AirAsia India",
    "emirates": "Emirates",
    "ek": "Emirates",
    "singapore airlines": "Singapore Airlines",
    "sq": "Singapore Airlines",
    "british airways": "British Airways",
    "ba": "British Airways",
    "lufthansa": "Lufthansa",
    "lh": "Lufthansa",
    "qatar airways": "Qatar Airways",
    "qr": "Qatar Airways",
    "united airlines": "United Airlines",
    "ua": "United Airlines",
    "american airlines": "American Airlines",
    "aa": "American Airlines",
    "delta": "Delta Air Lines",
    "dl": "Delta Air Lines",
    "air france": "Air France",
    "af": "Air France",
    "klm": "KLM",
    "kl": "KLM",
    "etihad": "Etihad Airways",
    "ey": "Etihad Airways",
}


def _standardize_airline(name: str) -> str:
    if pd.isna(name):
        return "Unknown"
    key = str(name).strip().lower()
    return AIRLINE_ALIASES.get(key, str(name).strip().title())


def _parse_dates(series: pd.Series, col_name: str) -> pd.Series:
    # Try ISO format first (YYYY-MM-DD), then fall back to dayfirst=True for DD/MM/YYYY.
    # Use .where() to combine results — avoids chained assignment (pandas 2.x CoW safe).
    parsed = pd.to_datetime(series, format="%Y-%m-%d", errors="coerce")
    fallback = pd.to_datetime(series, dayfirst=True, errors="coerce")
    still_null = parsed.isna() & series.notna()
    if still_null.any():
        parsed = parsed.where(~still_null, fallback)
    bad = int(parsed.isna().sum())
    if bad > 0:
        print(f"  [warn] {bad} unparseable dates in '{col_name}' — set to NaT")
    return parsed


def normalize_travel(df: pd.DataFrame) -> pd.DataFrame:
    """Clean and normalize the travel DataFrame."""
    df = df.copy()

    initial_rows = len(df)
    df.drop_duplicates(inplace=True)
    dropped = initial_rows - len(df)
    if dropped:
        print(f"  [info] Removed {dropped} duplicate rows")

    df["airline"] = df["airline"].apply(_standardize_airline)

    df["booking_date"] = _parse_dates(df["booking_date"], "booking_date")
    df["travel_date"] = _parse_dates(df["travel_date"], "travel_date")

    df.dropna(subset=["booking_date", "travel_date"], inplace=True)

    df["origin"] = df["origin"].astype(str).str.strip().str.upper()
    df["destination"] = df["destination"].astype(str).str.strip().str.upper()

    df["route"] = df["origin"] + " → " + df["destination"]

    if "pnr" in df.columns:
        df["pnr"] = df["pnr"].astype(str).str.strip().str.upper()

    df.sort_values("travel_date", inplace=True)
    df.reset_index(drop=True, inplace=True)

    return df


def normalize_loyalty(df: Optional[pd.DataFrame]) -> Optional[pd.DataFrame]:
    """Clean loyalty data if present."""
    if df is None:
        return None
    df = df.copy()
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    if "airline" in df.columns:
        df["airline"] = df["airline"].apply(_standardize_airline)
    if "flight_date" in df.columns:
        df["flight_date"] = _parse_dates(df["flight_date"], "flight_date")
    elif "travel_date" in df.columns:
        df["travel_date"] = _parse_dates(df["travel_date"], "travel_date")
    if "pnr" in df.columns:
        df["pnr"] = df["pnr"].astype(str).str.strip().str.upper()

    return df


def normalize(ingested: dict) -> dict:
    """Normalize both travel and loyalty data."""
    travel_df = normalize_travel(ingested["travel"])
    loyalty_df = normalize_loyalty(ingested.get("loyalty"))

    return {
        **ingested,
        "travel": travel_df,
        "loyalty": loyalty_df,
        "row_count": len(travel_df),
    }
