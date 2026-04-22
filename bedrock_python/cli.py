"""CLI entry point for the Bedrock PDF Analyzer."""
import argparse
import io
import os
import sys
from pathlib import Path

# Force UTF-8 output on Windows terminals
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from dotenv import load_dotenv

load_dotenv()

# Default PDFs in project root
ROOT = Path(__file__).parent.parent
DEFAULT_PDFS = [
    ROOT / "Club_Vistara_Activities_311602482_2026-04-16.pdf",
    ROOT / "AI report April 2024 to March 2025.pdf",
    ROOT / "AI report April 2025 to March 2026.pdf",
]

W = 62  # display width


def _hr(char="="):
    print(char * W)


def _header(title):
    _hr()
    print(f"  {title}")
    _hr()


def _table(rows: list[tuple[str, str]]):
    if not rows:
        return
    col1 = max(len(r[0]) for r in rows)
    sep = f"  +{'-' * (col1 + 2)}+{'-' * 18}+"
    print(sep)
    for label, value in rows:
        print(f"  | {label:<{col1}} | {str(value):<16} |")
    print(sep)


def _print_insight(insight: dict):
    idx = insight.get("id", "?")
    print(f"\n  #{idx}")
    print(f"  {'─' * (W - 4)}")
    for key in ("observation", "implication", "recommendation", "impact"):
        label = key.capitalize()
        value = insight.get(key, "")
        # Word-wrap long values
        words = value.split()
        line = ""
        first = True
        for word in words:
            if len(line) + len(word) + 1 > W - 20:
                indent = f"  {label + ':':<16}" if first else " " * 18
                print(f"{indent}{line}")
                line = word
                first = False
            else:
                line = (line + " " + word).strip()
        if line:
            indent = f"  {label + ':':<16}" if first else " " * 18
            print(f"{indent}{line}")


def _fmt_pct(val) -> str:
    if val is None:
        return "N/A"
    return f"{val * 100:.1f}%"


def _fmt_inr(val) -> str:
    if val is None:
        return "N/A"
    return f"₹{int(val):,}"


def main():
    parser = argparse.ArgumentParser(
        description="FlightMode.ai — Bedrock PDF Analyzer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "pdfs",
        nargs="*",
        help="PDF file paths to analyse (default: all PDFs in project root)",
    )
    parser.add_argument(
        "--no-insights",
        action="store_true",
        help="Skip the Bedrock insights generation step",
    )
    args = parser.parse_args()

    # Resolve PDF paths
    if args.pdfs:
        pdf_paths = [str(Path(p).resolve()) for p in args.pdfs]
    else:
        pdf_paths = [str(p) for p in DEFAULT_PDFS if p.exists()]
        if not pdf_paths:
            print("No PDFs found in project root. Pass file paths as arguments.")
            sys.exit(1)

    _header("FlightMode.ai — Bedrock PDF Analyzer")
    print(f"  Model : {os.environ.get('BEDROCK_MODEL_ID', '(not set)')}")
    print(f"  Region: {os.environ.get('AWS_REGION', '(not set)')}")
    print()

    # Step 1 — Extract text
    print(f"[1/4] Extracting text from {len(pdf_paths)} PDF(s)...")
    from .pdf_extractor import extract_text_from_pdf

    for path in pdf_paths:
        name = Path(path).name
        try:
            _, page_count = extract_text_from_pdf(path)
            print(f"  - {name[:50]:<50}  {page_count} pages")
        except Exception as e:
            print(f"  - {name[:50]:<50}  ERROR: {e}")

    print()

    # Step 2 — Bedrock extraction
    print(f"[2/4] Sending to Bedrock for structured data extraction...")
    from .pdf_extractor import extract_from_pdfs

    extraction = extract_from_pdfs(pdf_paths)

    if extraction.extraction_errors:
        for err in extraction.extraction_errors:
            print(f"  Warning: {err}")

    print(f"  Extracted : {len(extraction.flights)} flights, {len(extraction.loyalty_credits)} loyalty activities")
    print(f"  PDFs OK   : {extraction.total_pdfs_processed}/{len(pdf_paths)}")
    if extraction.source_notes:
        for note in extraction.source_notes:
            print(f"  Note      : {note}")
    print()

    # Step 3 — Analytics
    print("[3/4] Running analytics...")
    from .analyzer import run_all

    metrics = run_all(extraction.flights, extraction.loyalty_credits)
    a = metrics["airline"]
    b = metrics["booking"]
    r = metrics["routes"]
    ly = metrics["loyalty"]

    lm_pct = f"{b.get('last_minute_pct', 0)}%" if b.get("avg_booking_gap_days") is not None else "N/A"
    early_pct = f"{b.get('early_booking_pct', 0)}%" if b.get("avg_booking_gap_days") is not None else "N/A"
    rows = [
        ("Total Flights Extracted", a["total_flights"]),
        ("Unique Airlines", a["unique_airlines"]),
        ("Top Airline", a.get("top_airline") or "N/A"),
        ("Top Airline Share", f"{a.get('top_airline_share_pct', 0)}%"),
        ("Fragmented?", "Yes" if a.get("is_fragmented") else "No"),
        ("Avg Booking Lead (days)", b.get("avg_booking_gap_days") or "N/A"),
        ("Last-Minute Bookings", lm_pct),
        ("Early Bookings (>=10d)", early_pct),
        ("Unique Routes", r["unique_routes"]),
        ("Top Route", r.get("most_frequent_route") or "N/A"),
        ("Loyalty Activities", len(extraction.loyalty_credits)),
        ("Total Miles Earned", f"{ly.get('miles_already_earned', 0):,}"),
        ("Miles Value (est.)", _fmt_inr(ly.get("miles_already_earned", 0) * 0.5)),
        ("Uncredited Flights", ly.get("missing_credits", 0)),
        ("Loyalty Leakage (est.)", _fmt_inr(ly.get("estimated_inr_value", 0))),
    ]
    print()
    _table(rows)
    print()

    if args.no_insights:
        print("Insights skipped (--no-insights).")
        return

    # Step 4 — Insights
    print("[4/4] Generating insights via Bedrock...")
    from .insights_generator import generate

    insights = generate(extraction.flights, extraction.loyalty_credits, metrics)
    print(f"  Generated {len(insights)} insights")

    print()
    _hr("=")
    print("  INSIGHTS")
    _hr("=")

    for insight in insights:
        _print_insight(insight)

    print()
    _hr()
    print(f"  Done. {len(extraction.flights)} flights analysed, {len(insights)} insights generated.")
    _hr()


if __name__ == "__main__":
    main()
