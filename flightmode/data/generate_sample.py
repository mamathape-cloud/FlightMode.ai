"""Generate a realistic 24-month sample Excel dataset for FlightMode.ai POC."""

import pandas as pd
import random
from datetime import datetime, timedelta
from pathlib import Path

random.seed(42)

AIRLINES = [
    ("IndiGo", 52),
    ("Air India", 20),
    ("Vistara", 12),
    ("SpiceJet", 8),
    ("Emirates", 5),
    ("Singapore Airlines", 3),
]

ROUTES = [
    ("DEL", "BOM"),
    ("BOM", "DEL"),
    ("DEL", "BLR"),
    ("BLR", "DEL"),
    ("BOM", "HYD"),
    ("HYD", "BOM"),
    ("DEL", "MAA"),
    ("MAA", "DEL"),
    ("BLR", "BOM"),
    ("BOM", "BLR"),
    ("DEL", "DXB"),
    ("BOM", "SIN"),
    ("HYD", "BLR"),
    ("DEL", "CCU"),
    ("BOM", "GOI"),
]

ROUTE_WEIGHTS = [18, 17, 12, 11, 8, 7, 6, 5, 4, 4, 3, 2, 1, 1, 1]


def pick_airline(weights):
    names = [a[0] for a in weights]
    wts = [a[1] for a in weights]
    return random.choices(names, weights=wts, k=1)[0]


def pick_route():
    return random.choices(ROUTES, weights=ROUTE_WEIGHTS, k=1)[0]


def random_date(start: datetime, end: datetime) -> datetime:
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))


def generate_travel_data(n: int = 120) -> pd.DataFrame:
    start = datetime(2024, 1, 1)
    end = datetime(2025, 12, 31)

    records = []
    for i in range(n):
        travel_date = random_date(start, end)

        booking_gap_profile = random.choices(
            ["last_minute", "moderate", "planned"],
            weights=[35, 40, 25],
            k=1,
        )[0]

        if booking_gap_profile == "last_minute":
            gap = random.randint(0, 3)
        elif booking_gap_profile == "moderate":
            gap = random.randint(4, 14)
        else:
            gap = random.randint(15, 45)

        booking_date = travel_date - timedelta(days=gap)

        origin, destination = pick_route()
        airline = pick_airline(AIRLINES)

        pnr = f"FM{random.randint(100000, 999999)}"

        records.append({
            "PNR": pnr,
            "airline": airline,
            "origin": origin,
            "destination": destination,
            "booking_date": booking_date.strftime("%Y-%m-%d"),
            "travel_date": travel_date.strftime("%Y-%m-%d"),
            "passenger_name": "Rajesh Kumar",
        })

    df = pd.DataFrame(records).sort_values("travel_date").reset_index(drop=True)
    return df


def generate_loyalty_data(travel_df: pd.DataFrame) -> pd.DataFrame:
    """Simulate loyalty data — only 70% of flights are credited."""
    sampled = travel_df.sample(frac=0.70, random_state=42).copy()
    sampled["miles_earned"] = sampled["airline"].apply(
        lambda a: random.randint(800, 2500) if a in ("Emirates", "Singapore Airlines") else random.randint(300, 1200)
    )
    sampled["loyalty_program"] = sampled["airline"].apply(
        lambda a: {
            "IndiGo": "6E Rewards",
            "Air India": "Flying Returns",
            "Vistara": "Club Vistara",
            "SpiceJet": "SpiceClub",
            "Emirates": "Skywards",
            "Singapore Airlines": "KrisFlyer",
        }.get(a, "Unknown")
    )
    return sampled[["PNR", "airline", "loyalty_program", "miles_earned"]].reset_index(drop=True)


def create_sample_excel(output_path: str = None) -> str:
    if output_path is None:
        here = Path(__file__).parent
        output_path = str(here / "sample_travel_data.xlsx")

    travel_df = generate_travel_data(120)
    loyalty_df = generate_loyalty_data(travel_df)

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        travel_df.to_excel(writer, sheet_name="Travel_Data", index=False)
        loyalty_df.to_excel(writer, sheet_name="Loyalty_Data", index=False)

    print(f"Sample dataset written to: {output_path}")
    print(f"  Travel rows: {len(travel_df)}, Loyalty rows: {len(loyalty_df)}")
    return output_path


if __name__ == "__main__":
    create_sample_excel()
