"""
FlightMode.ai — CLI entry point

Usage:
  python -m flightmode.main <path-to-excel>
  python -m flightmode.main --demo
"""

import json
import sys
from pathlib import Path

from flightmode.pipeline import run_pipeline
from flightmode.chat.qa import ask_question


DEMO_QUESTIONS = [
    "What is my top airline?",
    "Is my travel fragmented?",
    "What is my average booking lead time?",
    "What percentage of bookings are last-minute?",
    "What is my most frequent route?",
    "How many miles have I lost to loyalty leakage?",
    "What are the key recommendations?",
    "How many unique routes did I fly?",
    "What is the weather in Mumbai?",
]


def run_demo():
    from flightmode.data.generate_sample import create_sample_excel

    print("=" * 60)
    print("  FlightMode.ai — Phase 1 POC Demo")
    print("=" * 60)

    sample_path = create_sample_excel()
    result = run_pipeline(sample_path)

    report_dir = Path(__file__).parent.parent / "output"
    report_dir.mkdir(exist_ok=True)

    md_path = report_dir / "sample_report.md"
    json_path = report_dir / "sample_report.json"

    md_path.write_text(result["markdown_report"], encoding="utf-8")
    json_path.write_text(
        json.dumps(result["json_report"], indent=2, default=str), encoding="utf-8"
    )

    print(f"\n[Output] Markdown report → {md_path}")
    print(f"[Output] JSON report     → {json_path}")

    print("\n" + "=" * 60)
    print("  CHAT LAYER DEMO")
    print("=" * 60)
    for q in DEMO_QUESTIONS:
        print(f"\n Q: {q}")
        answer = ask_question(q, result["json_report"])
        print(f" A: {answer}")

    print("\n" + "=" * 60)
    print("  SAMPLE MARKDOWN REPORT (truncated)")
    print("=" * 60)
    lines = result["markdown_report"].split("\n")
    print("\n".join(lines[:80]))
    if len(lines) > 80:
        print(f"\n... [{len(lines) - 80} more lines — see {md_path}]")

    return result


def main():
    if len(sys.argv) == 1 or (len(sys.argv) == 2 and sys.argv[1] == "--demo"):
        run_demo()
        return

    filepath = sys.argv[1]
    if not Path(filepath).exists():
        print(f"Error: File not found: {filepath}")
        sys.exit(1)

    result = run_pipeline(filepath)

    output_dir = Path(filepath).parent / "output"
    output_dir.mkdir(exist_ok=True)

    stem = Path(filepath).stem
    md_path = output_dir / f"{stem}_report.md"
    json_path = output_dir / f"{stem}_report.json"

    md_path.write_text(result["markdown_report"], encoding="utf-8")
    json_path.write_text(
        json.dumps(result["json_report"], indent=2, default=str), encoding="utf-8"
    )

    print(f"\n[Output] Markdown report → {md_path}")
    print(f"[Output] JSON report     → {json_path}")

    if len(sys.argv) >= 3:
        question = " ".join(sys.argv[2:])
        print(f"\n[Chat] Q: {question}")
        print(f"[Chat] A: {ask_question(question, result['json_report'])}")

import tempfile

def run_analysis(file):
    """
    Wrapper for Streamlit UI
    """

    # Save uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        tmp.write(file.read())
        temp_path = tmp.name

    result = run_pipeline(temp_path)

    report = {
        "executive_summary": result.get("markdown_report", "No summary available"),
        "top_insights": result.get("json_report", {}).get("insights", []),
        "full_report": result.get("markdown_report", "No report generated")
    }

    context = result

    return report, context


def ask_question_streamlit(question, context):
    """
    Wrapper for chat (uses existing ask_question)
    """
    try:
        return ask_question(question, context.get("json_report", {}))
    except:
        return "Unable to answer from report"

if __name__ == "__main__":
    main()
