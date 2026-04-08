# FlightMode.ai

**Deterministic Travel Intelligence System — Phase 1 POC**

FlightMode.ai analyzes structured Excel travel data and produces a premium diagnostic report with actionable insights. It is **not a chatbot** — all analytics are deterministic Python logic; LLM is only used (optionally) for prose formatting and grounded chat responses.

---

## Architecture

```
Excel File
    │
    ▼
┌─────────────────────────────────────────────────────┐
│ Step 1: Ingestion     (core/ingestion.py)            │
│   - Read .xlsx / .xls / .csv                        │
│   - Validate required columns                        │
│   - Load travel + loyalty sheets                     │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│ Step 2: Normalization (core/normalization.py)        │
│   - Standardize airline names (alias map)            │
│   - Parse & normalize date formats                   │
│   - Remove duplicates, handle missing values         │
│   - Build route column (ORIGIN → DEST)               │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│ Step 3: Analysis Modules (analysis/)                 │
│   A. Airline     – distribution, fragmentation rule  │
│   B. Booking     – gap metrics, last-minute rate     │
│   C. Routes      – frequent routes, repetition       │
│   D. Loyalty     – PNR cross-reference, miles lost   │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│ Step 4: Insight Engine (analysis/insights.py)        │
│   - 5+ structured insights per report                │
│   - Each: observation / implication /                │
│           recommendation / impact (₹)               │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│ Steps 5-6: Report Generation (report/generator.py)   │
│   - JSON report  (machine-readable)                  │
│   - Markdown report (7 sections, premium format)     │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│ Step 7: Chat Layer (chat/qa.py)                      │
│   - ask_question(question, report_context)           │
│   - Deterministic keyword-based lookup               │
│   - Optional OpenAI path (grounded, no hallucination)│
│   - Out-of-scope → "not available in the report"     │
└─────────────────────────────────────────────────────┘
```

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the demo (generates sample data + full report)

```bash
python3 -m flightmode.main --demo
```

Output files written to `output/`:
- `sample_report.md` — Markdown diagnostic report
- `sample_report.json` — Structured JSON output

### 3. Run on your own data

```bash
python3 -m flightmode.main /path/to/your/travel_data.xlsx
```

### 4. Ask a question via chat

```bash
python3 -m flightmode.main /path/to/travel_data.xlsx "What is my top airline?"
```

### 5. Use programmatically

```python
from flightmode.pipeline import run_pipeline
from flightmode.chat.qa import ask_question

result = run_pipeline("travel_data.xlsx")

# JSON report
print(result["json_report"]["airline_analysis"])

# Markdown report
print(result["markdown_report"])

# Chat
answer = ask_question("Is my travel fragmented?", result["json_report"])
print(answer)
```

---

## Input Format

Excel file (`.xlsx` / `.xls`) or CSV with these columns:

| Column | Required | Description |
|---|---|---|
| `airline` | ✅ | Airline name or IATA code (e.g., `6E`, `IndiGo`) |
| `origin` | ✅ | Origin airport code (e.g., `DEL`) |
| `destination` | ✅ | Destination airport code (e.g., `BOM`) |
| `booking_date` | ✅ | Date booking was made |
| `travel_date` | ✅ | Actual travel date |
| `PNR` | Optional | Booking reference (enables loyalty cross-reference) |

**Loyalty sheet** (optional second sheet named "Loyalty Data"):

| Column | Description |
|---|---|
| `PNR` | Booking reference to match against travel |
| `miles_earned` | Miles credited for this flight |
| `loyalty_program` | Program name |

---

## Report Sections

1. **Executive Summary** — Key flags and total recoverable value
2. **Travel Overview** — High-level metrics table
3. **Airline Utilization** — Distribution table + fragmentation status
4. **Booking Behavior** — Gap metrics + window distribution
5. **Loyalty Leakage** — Missing credits + estimated miles lost
6. **Optimization Strategy** — Prioritized action table
7. **Action Plan** — Numbered 7-day / 14-day / 30-day steps

---

## Chat Layer Rules

```python
from flightmode.chat.qa import ask_question

answer = ask_question("What is my top airline?", json_report)
# → "Your top airline is IndiGo, accounting for 50% of your flights."

answer = ask_question("What is the weather in Mumbai?", json_report)
# → "This data is not available in the report."
```

- **Deterministic by default** — no LLM required
- **LLM-enhanced** if `OPENAI_API_KEY` is set (grounded, `temperature=0`)
- Out-of-scope questions always return: `"This data is not available in the report."`

---

## Key Business Rules

| Rule | Threshold | Consequence |
|---|---|---|
| Airline fragmentation | Top airline share < 60% | Loyalty status forfeited |
| Last-minute booking | ≤ 3 days before travel | 30–80% fare premium |
| Early booking target | ≥ 10 days domestic | Optimal fare window |
| Loyalty leakage | Uncredited PNRs | ~1,500 miles/flight estimated |

---

## Running Tests

```bash
python3 -m pytest flightmode/tests/ -v
```

20 tests covering all analysis modules, normalization, insight engine.

---

## Project Structure

```
flightmode/
├── core/
│   ├── ingestion.py        # Step 1: Read & validate Excel
│   └── normalization.py    # Step 2: Clean & standardize
├── analysis/
│   ├── airline.py          # Step 3A: Airline distribution
│   ├── booking.py          # Step 3B: Booking gap metrics
│   ├── route.py            # Step 3C: Route analysis
│   ├── loyalty.py          # Step 3D: Loyalty leakage
│   └── insights.py         # Step 4: Insight engine
├── report/
│   └── generator.py        # Steps 5-6: JSON + Markdown reports
├── chat/
│   └── qa.py               # Step 7: Grounded chat layer
├── data/
│   └── generate_sample.py  # Sample dataset generator
├── tests/
│   └── test_analysis.py    # 20 unit tests
├── pipeline.py             # Main orchestrator
└── main.py                 # CLI entry point
```
