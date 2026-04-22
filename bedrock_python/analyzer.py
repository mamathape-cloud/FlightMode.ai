"""
4-dimension analysis for PDF-extracted data.
Outputs the EXACT same JSON shapes as flightmode/analysis/*.py so that
flightmode/report/generator.py's build_json_report + build_markdown_report
can be used unchanged on Bedrock-extracted data.
"""
from datetime import datetime

FRAGMENTATION_THRESHOLD = 0.60
LAST_MINUTE_DAYS = 3
EARLY_BOOKING_DAYS = 10
MILES_PER_FLIGHT_ESTIMATE = 1500
MILES_VALUE_PER_MILE = 0.5

# Mirrors flightmode/core/normalization.py AIRLINE_ALIASES
_AIRLINE_ALIASES = {
    "air india": "Air India", "ai": "Air India",
    "indigo": "IndiGo", "6e": "IndiGo",
    "go air": "Go Air", "go first": "Go First", "g8": "Go First",
    "spicejet": "SpiceJet", "sg": "SpiceJet",
    "vistara": "Vistara", "uk": "Vistara",
    "akasa": "Akasa Air", "qp": "Akasa Air",
    "air asia": "AirAsia India", "i5": "AirAsia India",
    "emirates": "Emirates", "ek": "Emirates",
    "singapore airlines": "Singapore Airlines", "sq": "Singapore Airlines",
    "british airways": "British Airways", "ba": "British Airways",
    "lufthansa": "Lufthansa", "lh": "Lufthansa",
    "qatar airways": "Qatar Airways", "qr": "Qatar Airways",
    "united airlines": "United Airlines", "ua": "United Airlines",
    "american airlines": "American Airlines", "aa": "American Airlines",
    "delta": "Delta Air Lines", "dl": "Delta Air Lines",
    "air france": "Air France", "af": "Air France",
    "klm": "KLM", "kl": "KLM",
    "etihad": "Etihad Airways", "ey": "Etihad Airways",
}


def _normalize_airline(name: str) -> str:
    key = str(name).strip().lower()
    return _AIRLINE_ALIASES.get(key, str(name).strip().title())


def _parse_date(value):
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except ValueError:
            continue
    return None


# ── Airline Analysis ──────────────────────────────────────────────────────────
# Matches: flightmode/analysis/airline.py → analyze_airline()

def analyze_airline(flights: list) -> dict:
    if not flights:
        return {
            "total_flights": 0,
            "airline_distribution": {},
            "top_airline": None,
            "top_airline_share_pct": 0.0,
            "is_fragmented": False,
            "unique_airlines": 0,
        }

    counts = {}
    for f in flights:
        airline = _normalize_airline(str(f.get("airline") or "Unknown"))
        counts[airline] = counts.get(airline, 0) + 1

    total = len(flights)
    top = max(counts, key=counts.get)
    top_share = counts[top] / total

    distribution = {
        airline: {
            "flights": count,
            "share_pct": round(count / total * 100, 1),
        }
        for airline, count in sorted(counts.items(), key=lambda x: -x[1])
    }

    return {
        "total_flights": total,
        "airline_distribution": distribution,
        "top_airline": top,
        "top_airline_share_pct": round(top_share * 100, 1),
        "is_fragmented": bool(top_share < FRAGMENTATION_THRESHOLD),
        "unique_airlines": len(counts),
    }


# ── Booking Behavior ──────────────────────────────────────────────────────────
# Matches: flightmode/analysis/booking.py → analyze_booking()

def analyze_booking(flights: list) -> dict:
    gaps = []
    for f in flights:
        bd = _parse_date(f.get("booking_date"))
        td = _parse_date(f.get("travel_date"))
        if not bd or not td:
            continue
        delta = (td - bd).days
        if delta >= 0:
            gaps.append(delta)

    empty = {
        "total_bookings": 0,
        "avg_booking_gap_days": None,
        "median_booking_gap_days": None,
        "min_booking_gap_days": None,
        "max_booking_gap_days": None,
        "last_minute_count": 0,
        "last_minute_pct": 0.0,
        "early_booking_count": 0,
        "early_booking_pct": 0.0,
        "gap_distribution": {},
    }

    if not gaps:
        return empty

    total = len(gaps)
    last_minute = sum(1 for g in gaps if g <= LAST_MINUTE_DAYS)
    early = sum(1 for g in gaps if g >= EARLY_BOOKING_DAYS)
    gaps_sorted = sorted(gaps)
    n = len(gaps_sorted)
    median = gaps_sorted[n // 2] if n % 2 else (gaps_sorted[n // 2 - 1] + gaps_sorted[n // 2]) / 2

    buckets = [
        ("0-3 days (last minute)", 0, 3),
        ("4-7 days", 4, 7),
        ("8-14 days", 8, 14),
        ("15-30 days", 15, 30),
        ("31+ days (planned)", 31, 99999),
    ]
    gap_distribution = {}
    for label, lo, hi in buckets:
        count = sum(1 for g in gaps if lo <= g <= hi)
        gap_distribution[label] = {"count": count, "pct": round(count / total * 100, 1)}

    return {
        "total_bookings": total,
        "avg_booking_gap_days": round(sum(gaps) / total, 1),
        "median_booking_gap_days": round(median, 1),
        "min_booking_gap_days": min(gaps),
        "max_booking_gap_days": max(gaps),
        "last_minute_count": last_minute,
        "last_minute_pct": round(last_minute / total * 100, 1),
        "early_booking_count": early,
        "early_booking_pct": round(early / total * 100, 1),
        "gap_distribution": gap_distribution,
    }


# ── Route Analysis ────────────────────────────────────────────────────────────
# Matches: flightmode/analysis/route.py → analyze_routes()

def analyze_routes(flights: list) -> dict:
    if not flights:
        return {
            "total_routes_flown": 0,
            "unique_routes": 0,
            "repeated_route_pct": 0.0,
            "top_routes": [],
            "route_distribution": {},
        }

    route_counts = {}
    for f in flights:
        origin = str(f.get("origin") or "?").strip().upper()
        dest = str(f.get("destination") or "?").strip().upper()
        route = f"{origin} → {dest}"
        route_counts[route] = route_counts.get(route, 0) + 1

    total = len(flights)
    sorted_routes = sorted(route_counts.items(), key=lambda x: -x[1])

    repeated_flights = sum(c for c in route_counts.values() if c > 1)
    repeated_pct = round(repeated_flights / total * 100, 1) if total else 0.0

    top_routes = [
        {"route": route, "count": count, "share_pct": round(count / total * 100, 1)}
        for route, count in sorted_routes[:10]
    ]

    route_distribution = {
        route: {"count": count, "share_pct": round(count / total * 100, 1)}
        for route, count in sorted_routes
    }

    top = sorted_routes[0][0] if sorted_routes else None
    top_count = sorted_routes[0][1] if sorted_routes else 0

    return {
        "total_routes_flown": total,
        "unique_routes": len(route_counts),
        "most_frequent_route": top,
        "most_frequent_route_count": top_count,
        "repeated_route_pct": repeated_pct,
        "top_routes": top_routes,
        "route_distribution": route_distribution,
    }


# ── Loyalty Analysis ──────────────────────────────────────────────────────────
# Matches: flightmode/analysis/loyalty.py → analyze_loyalty()

def analyze_loyalty(flights: list, loyalty_credits: list) -> dict:
    total_flights = len(flights)
    flight_pnrs = {str(f.get("pnr") or "").strip().upper() for f in flights if f.get("pnr")}
    credit_pnrs = {str(c.get("pnr") or "").strip().upper() for c in loyalty_credits if c.get("pnr")}

    credited = flight_pnrs & credit_pnrs
    missing_pnrs = flight_pnrs - credit_pnrs

    credited_count = len(credited)
    missing_count = len(missing_pnrs)
    missing_pct = round(missing_count / total_flights * 100, 1) if total_flights else 0.0

    miles_earned = sum(float(c.get("miles_earned") or 0) for c in loyalty_credits)
    estimated_miles_lost = missing_count * MILES_PER_FLIGHT_ESTIMATE

    return {
        "loyalty_data_available": bool(loyalty_credits),
        "total_flights": total_flights,
        "credited_flights": credited_count,
        "missing_credits": missing_count,
        "missing_credit_pct": missing_pct,
        "miles_already_earned": int(miles_earned),
        "estimated_miles_lost": estimated_miles_lost,
        "estimated_inr_value": round(estimated_miles_lost * MILES_VALUE_PER_MILE, 0),
        "missing_pnrs": list(missing_pnrs)[:20],
    }


# ── Date range helper ─────────────────────────────────────────────────────────

def get_date_range(flights: list) -> str | None:
    dates = []
    for f in flights:
        d = _parse_date(f.get("travel_date"))
        if d:
            dates.append(d)
    if not dates:
        return None
    return f"{min(dates)} to {max(dates)}"


# ── Combined ──────────────────────────────────────────────────────────────────

def run_all(flights: list, loyalty_credits: list) -> dict:
    return {
        "airline": analyze_airline(flights),
        "booking": analyze_booking(flights),
        "routes": analyze_routes(flights),
        "loyalty": analyze_loyalty(flights, loyalty_credits),
        "date_range": get_date_range(flights),
    }
