"""Extract structured travel data from PDFs via AWS Bedrock.

Primary path:  send PDF bytes directly to Bedrock (native document understanding).
Fallback path: extract text with pdfplumber, chunk it, send as text prompts.
               Used when PDF exceeds the 3.3 MB inline limit.
"""
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .bedrock_client import PDF_NATIVE_MAX_BYTES, BedrockError, invoke, invoke_with_pdf
from .prompts import EXTRACTION_PROMPT, EXTRACTION_PROMPT_NATIVE

# Fallback: pages per Bedrock text call
PAGES_PER_CHUNK = 4


@dataclass
class ExtractionResult:
    flights: list = field(default_factory=list)
    loyalty_credits: list = field(default_factory=list)
    source_notes: list = field(default_factory=list)
    total_pdfs_processed: int = 0
    extraction_errors: list = field(default_factory=list)


# ── JSON parsing helpers ──────────────────────────────────────────────────────

def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _parse_bedrock_json(response: str) -> dict | None:
    """Try multiple strategies to extract a JSON object from a Bedrock response.
    Handles complete JSON, partial JSON (truncated due to token limit), and
    malformed responses by salvaging individual complete objects.
    """
    cleaned = _strip_fences(response)

    # Direct parse (happy path)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Find first complete {...} block
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if match:
        try:
            return json.loads(match.group())
        except Exception:
            pass

    # Partial salvage: collect all complete objects from potentially truncated arrays
    data = {}
    for key in ("flights", "loyalty_credits"):
        # Try complete array first
        m = re.search(rf'"{key}"\s*:\s*(\[[\s\S]*?\])\s*[,}}]', cleaned)
        if m:
            try:
                data[key] = json.loads(m.group(1))
                continue
            except Exception:
                pass

        # Truncated array: find array start, collect complete {...} objects
        m2 = re.search(rf'"{key}"\s*:\s*\[', cleaned)
        if m2:
            array_text = cleaned[m2.end():]
            objects = []
            depth = 0
            start = None
            for i, ch in enumerate(array_text):
                if ch == "{":
                    if depth == 0:
                        start = i
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0 and start is not None:
                        try:
                            objects.append(json.loads(array_text[start : i + 1]))
                        except Exception:
                            pass
                        start = None
                elif ch == "]" and depth == 0:
                    break
            if objects:
                data[key] = objects

    return data if data else None


# ── Native PDF path ───────────────────────────────────────────────────────────

def _extract_native(path: str) -> tuple[dict, str]:
    """Send the PDF directly to Bedrock as a document block."""
    pdf_bytes = Path(path).read_bytes()
    try:
        response = invoke_with_pdf(pdf_bytes, EXTRACTION_PROMPT_NATIVE, max_tokens=4096)
    except ValueError as e:
        return {}, str(e)  # PDF too large — caller falls back to text
    except BedrockError as e:
        # "document_unsupported" = model is too old; fall back silently
        return {}, str(e)

    result = _parse_bedrock_json(response)
    if not result:
        return {}, f"{Path(path).name}: Bedrock returned unparseable JSON (native mode)"

    return {
        "flights": result.get("flights") or [],
        "loyalty_credits": result.get("loyalty_credits") or [],
        "source_notes": result.get("source_notes", ""),
        "mode": "native",
    }, ""


# ── Text-extraction fallback path ─────────────────────────────────────────────

def _extract_text_from_pdf(path: str) -> tuple[list[str], int]:
    """Return (list_of_page_texts, page_count) via pdfplumber."""
    import pdfplumber

    pages = []
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""
            if text.strip():
                pages.append(f"--- PAGE {i} ---\n{text.strip()}")
    return pages, len(pages)


def _call_bedrock_chunk(page_texts: list[str]) -> dict:
    pdf_text = "\n\n".join(page_texts)
    prompt = EXTRACTION_PROMPT.format(pdf_text=pdf_text)
    response = invoke(prompt, max_tokens=4096)
    return _parse_bedrock_json(response) or {}


def _extract_text_fallback(path: str) -> tuple[dict, str]:
    """Text-extraction path: pdfplumber → chunk → Bedrock text calls."""
    try:
        page_texts, _ = _extract_text_from_pdf(path)
    except Exception as e:
        return {}, f"Could not read {Path(path).name}: {e}"

    if not page_texts:
        return {}, f"{Path(path).name}: no extractable text (may be a scanned image PDF)"

    chunks = [page_texts[i : i + PAGES_PER_CHUNK] for i in range(0, len(page_texts), PAGES_PER_CHUNK)]
    all_flights, all_credits, source_note, errors = [], [], "", []

    for idx, chunk in enumerate(chunks):
        try:
            chunk_data = _call_bedrock_chunk(chunk)
        except BedrockError as e:
            errors.append(f"chunk {idx + 1}: {e}")
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
        "mode": "text",
    }, ""


# ── Dedup ─────────────────────────────────────────────────────────────────────

def _dedup_flights(flights: list) -> list:
    seen = set()
    result = []
    for f in flights:
        pnr = (f.get("pnr") or "").strip().upper()
        key = pnr if pnr else (
            str(f.get("airline", "")).lower(),
            str(f.get("travel_date", "")),
            str(f.get("origin", "")).upper(),
            str(f.get("destination", "")).upper(),
        )
        if key not in seen:
            seen.add(key)
            result.append(f)
    return result


# ── Public entry point ────────────────────────────────────────────────────────

def _extract_one(path: str) -> tuple[dict, str]:
    """Extract from one PDF: try native first, fall back to text chunking."""
    size = Path(path).stat().st_size

    if size <= PDF_NATIVE_MAX_BYTES:
        data, err = _extract_native(path)
        if not err and (data.get("flights") or data.get("loyalty_credits")):
            return data, ""
        # Native returned no data or had an error — try text fallback
        # (err from _extract_native is informational; text path may succeed)

    return _extract_text_fallback(path)


def extract_from_pdfs(paths: list[str]) -> ExtractionResult:
    """Extract and merge travel data from one or more PDFs."""
    result = ExtractionResult()
    all_flights, all_credits = [], []

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
