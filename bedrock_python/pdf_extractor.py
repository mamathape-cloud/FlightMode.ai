"""Extract text from PDFs with pdfplumber, then use Bedrock to parse structured data."""
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .bedrock_client import BedrockError, invoke
from .prompts import EXTRACTION_PROMPT

# Pages per Bedrock call — keeps response well under the 4096-token output limit
PAGES_PER_CHUNK = 8


@dataclass
class ExtractionResult:
    flights: list = field(default_factory=list)
    loyalty_credits: list = field(default_factory=list)
    source_notes: list = field(default_factory=list)
    total_pdfs_processed: int = 0
    extraction_errors: list = field(default_factory=list)


def extract_text_from_pdf(path: str) -> tuple[list[str], int]:
    """Return (list_of_page_texts, page_count) from a PDF using pdfplumber."""
    import pdfplumber

    pages = []
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""
            if text.strip():
                pages.append(f"--- PAGE {i} ---\n{text.strip()}")
    return pages, len(pages)


def _strip_fences(text: str) -> str:
    """Remove markdown code fences Bedrock sometimes adds despite instructions."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _parse_bedrock_json(response: str) -> dict | None:
    """Try multiple strategies to extract a JSON object from a Bedrock response."""
    cleaned = _strip_fences(response)
    # Direct parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    # Find first complete JSON object
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if match:
        try:
            return json.loads(match.group())
        except Exception:
            pass
    # Partial salvage: grab flights/loyalty arrays individually
    data = {}
    for key in ("flights", "loyalty_credits"):
        m = re.search(rf'"{key}"\s*:\s*(\[[\s\S]*?\])\s*[,}}]', cleaned)
        if m:
            try:
                data[key] = json.loads(m.group(1))
            except Exception:
                pass
    return data if data else None


def _call_bedrock_chunk(page_texts: list[str]) -> dict:
    """Send one chunk of page texts to Bedrock for extraction."""
    pdf_text = "\n\n".join(page_texts)
    prompt = EXTRACTION_PROMPT.format(pdf_text=pdf_text)
    response = invoke(prompt, max_tokens=4096)
    result = _parse_bedrock_json(response)
    return result or {}


def _extract_one(path: str) -> tuple[dict, str]:
    """Extract structured data from a single PDF (chunked). Returns (data_dict, error_msg)."""
    try:
        page_texts, page_count = extract_text_from_pdf(path)
    except Exception as e:
        return {}, f"Could not read {Path(path).name}: {e}"

    if not page_texts:
        return {}, f"{Path(path).name}: no extractable text (may be a scanned image PDF)"

    # Split into chunks to stay within Haiku's 4096-token output limit
    chunks = [page_texts[i:i + PAGES_PER_CHUNK] for i in range(0, len(page_texts), PAGES_PER_CHUNK)]
    all_flights = []
    all_credits = []
    source_note = ""
    errors = []

    for idx, chunk in enumerate(chunks):
        try:
            chunk_data = _call_bedrock_chunk(chunk)
        except BedrockError as e:
            errors.append(f"chunk {idx+1}: {e}")
            continue
        all_flights.extend(chunk_data.get("flights") or [])
        all_credits.extend(chunk_data.get("loyalty_credits") or [])
        if not source_note:
            source_note = chunk_data.get("source_notes", "")

    if errors and not all_flights and not all_credits:
        return {}, f"All chunks failed for {Path(path).name}: {'; '.join(errors)}"

    return {
        "flights": all_flights,
        "loyalty_credits": all_credits,
        "source_notes": source_note,
    }, ""


def _dedup_flights(flights: list) -> list:
    """Deduplicate by PNR; fall back to (airline, travel_date, origin, dest) composite key."""
    seen = set()
    result = []
    for f in flights:
        pnr = (f.get("pnr") or "").strip().upper()
        if pnr:
            key = pnr
        else:
            key = (
                str(f.get("airline", "")).lower(),
                str(f.get("travel_date", "")),
                str(f.get("origin", "")).upper(),
                str(f.get("destination", "")).upper(),
            )
        if key not in seen:
            seen.add(key)
            result.append(f)
    return result


def extract_from_pdfs(paths: list[str]) -> ExtractionResult:
    """Extract and merge data from multiple PDFs."""
    result = ExtractionResult()
    all_flights = []
    all_credits = []

    for path in paths:
        name = Path(path).name
        data, err = _extract_one(path)
        if err:
            result.extraction_errors.append(err)
            continue
        result.total_pdfs_processed += 1
        all_flights.extend(data.get("flights") or [])
        all_credits.extend(data.get("loyalty_credits") or [])
        note = data.get("source_notes", "")
        if note:
            result.source_notes.append(f"{name}: {note}")

    result.flights = _dedup_flights(all_flights)
    result.loyalty_credits = all_credits
    return result
