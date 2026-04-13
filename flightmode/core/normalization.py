"""Step 2: Normalization — Clean values only, preserve schema.

Contract:
  - normalize_travel() and normalize_loyalty() receive DataFrames
    that already have canonical column names (from ingestion).
  - These functions ONLY clean values (dates, strings, numerics).
  - They NEVER rename, drop, or reorder required columns.
  - They ALWAYS return the same columns they received, plus 'route'
    for travel data.
"""

import pandas as pd
from typing import Optional

REQUIRED_TRAVEL_COLS = ["airline", "booking_date", "travel_date", "origin", "destination"]

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


def _standardize_airline(name) -> str:
    if pd.isna(name):
        return "Unknown"
    key = str(name).strip().lower()
    return AIRLINE_ALIASES.get(key, str(name).strip().title())


def _parse_dates(series: pd.Series, col_name: str) -> pd.Series:
    """
    Parse a Series to datetime64.

    If the Series is already datetime (ingestion pre-converted it), return as-is.
    Otherwise try ISO format first, then dayfirst fallback.
    Uses .where() — CoW-safe for pandas 2.x.
    """
    # Short-circuit: already datetime — no re-parsing needed
    if pd.api.types.is_datetime64_any_dtype(series):
        return series

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
    """
    Clean travel DataFrame values. Schema is preserved — no columns are
    renamed, added (except 'route'), or dropped.

    Raises ValueError immediately if any required column is absent,
    so bugs surface at the normalization boundary rather than as a
    mysterious KeyError inside an analysis module.
    """
    # ── 1. Safety check — fail fast if schema is already broken ──────────────
    for col in REQUIRED_TRAVEL_COLS:
        if col not in df.columns:
            raise ValueError(
                f"Column '{col}' is missing before normalization. "
                f"Columns received: {df.columns.tolist()}"
            )

    df = df.copy()

    # ── 2. Remove exact duplicates ────────────────────────────────────────────
    initial_rows = len(df)
    df.drop_duplicates(inplace=True)
    dropped = initial_rows - len(df)
    if dropped:
        print(f"  [info] Removed {dropped} duplicate rows")

    # ── 3. Clean airline values ───────────────────────────────────────────────
    df["airline"] = df["airline"].apply(_standardize_airline)

    # ── 4. Parse / validate dates ─────────────────────────────────────────────
    df["booking_date"] = _parse_dates(df["booking_date"], "booking_date")
    df["travel_date"]  = _parse_dates(df["travel_date"],  "travel_date")

    # Drop rows where dates could not be parsed — unusable for analysis
    df.dropna(subset=["booking_date", "travel_date"], inplace=True)

    # ── 5. Clean origin / destination strings ─────────────────────────────────
    df["origin"]      = df["origin"].astype(str).str.strip().str.upper()
    df["destination"] = df["destination"].astype(str).str.strip().str.upper()

    # ── 6. Derive route (additive — does not replace any existing column) ─────
    df["route"] = df["origin"] + " → " + df["destination"]

    # ── 7. Clean PNR if present ───────────────────────────────────────────────
    if "pnr" in df.columns:
        df["pnr"] = df["pnr"].astype(str).str.strip().str.upper()

    # ── 8. Sort and reset index ───────────────────────────────────────────────
    df.sort_values("travel_date", inplace=True)
    df.reset_index(drop=True, inplace=True)

    print(f"[Normalization] Travel columns: {df.columns.tolist()}")
    print(f"[Normalization] Travel rows after clean: {len(df)}")
    return df


def normalize_loyalty(df: Optional[pd.DataFrame]) -> Optional[pd.DataFrame]:
    """
    Clean loyalty DataFrame values. Schema is preserved.

    Column names are assumed to be canonical (already normalized by ingestion).
    No renaming is performed here.
    """
    if df is None:
        return None

    df = df.copy()

    # Column names come from ingestion already normalized — do NOT re-normalize.
    # Applying lower/replace here would be a no-op for clean data but could
    # silently corrupt columns if the loyalty sheet had any exotic naming.

    if "airline" in df.columns:
        df["airline"] = df["airline"].apply(_standardize_airline)

    if "flight_date" in df.columns:
        df["flight_date"] = _parse_dates(df["flight_date"], "flight_date")
    elif "travel_date" in df.columns:
        df["travel_date"] = _parse_dates(df["travel_date"], "travel_date")

    if "pnr" in df.columns:
        df["pnr"] = df["pnr"].astype(str).str.strip().str.upper()

    print(f"[Normalization] Loyalty columns: {df.columns.tolist()}")
    print(f"[Normalization] Loyalty rows: {len(df)}")
    return df


def normalize(ingested: dict) -> dict:
    """Normalize both travel and loyalty data (legacy dict-based entry point)."""
    travel_df  = normalize_travel(ingested["travel"])
    loyalty_df = normalize_loyalty(ingested.get("loyalty"))

    return {
        **ingested,
        "travel":    travel_df,
        "loyalty":   loyalty_df,
        "row_count": len(travel_df),
    }
