"""
document_processor.py — Parse and semantically chunk uploaded documents.

Supported formats: PDF (.pdf), plain text (.txt), Word (.docx)

Chunking strategy: LangChain RecursiveCharacterTextSplitter splits on
paragraph → sentence → word → character boundaries, preserving semantic
meaning far better than naive fixed-size splits.
"""

import io
import logging
from pathlib import Path
from typing import List, Dict, Any

from langchain_text_splitters import RecursiveCharacterTextSplitter

import config

logger = logging.getLogger(__name__)


# ── Data model ────────────────────────────────────────────────────────────────

def make_chunk(text: str, source: str, chunk_index: int, page: int = 0) -> Dict[str, Any]:
    """Create a standardised chunk dictionary."""
    return {
        "text": text.strip(),
        "source": source,
        "chunk_index": chunk_index,
        "page": page,
    }


# ── File parsers ──────────────────────────────────────────────────────────────

def _parse_txt(file_bytes: bytes) -> List[Dict[str, Any]]:
    """Parse a plain-text file into raw page-level segments."""
    try:
        text = file_bytes.decode("utf-8", errors="replace")
        if not text.strip():
            raise ValueError("The text file appears to be empty.")
        return [{"text": text, "page": 1}]
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"Failed to read text file: {exc}") from exc


def _parse_pdf(file_bytes: bytes) -> List[Dict[str, Any]]:
    """
    Parse a PDF file page by page.

    Falls back to treating the content as UTF-8 text if the bytes are not
    a valid PDF (e.g. a .txt file that was renamed to .pdf).
    """
    # ── Try proper PDF parsing first ──────────────────────────────────────────
    try:
        import PyPDF2  # lazy import

        reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
        pages = []
        for page_num, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            if text.strip():
                pages.append({"text": text, "page": page_num})

        if pages:
            logger.info("PDF parsed successfully: %d page(s) with text.", len(pages))
            return pages

        # PDF is valid but has no extractable text → raise descriptive error
        raise ValueError(
            "The PDF appears to contain only images or scanned content with no "
            "extractable text. Please use a text-based PDF or convert it first."
        )

    except ValueError:
        raise  # Re-raise our own descriptive errors unchanged

    except Exception as pdf_exc:
        # ── Fallback: maybe this is plain text with a .pdf extension ──────────
        logger.warning(
            "PyPDF2 could not parse file as PDF (%s). "
            "Attempting plain-text fallback…", pdf_exc
        )
        try:
            text = file_bytes.decode("utf-8", errors="replace").strip()
            if text:
                logger.info("Plain-text fallback succeeded (%d chars).", len(text))
                return [{"text": text, "page": 1}]
        except Exception:
            pass

        raise ValueError(
            f"Could not parse this file as a PDF. "
            f"Original error: {pdf_exc}\n\n"
            f"If this is a text file, please rename it with a .txt extension."
        ) from pdf_exc


def _parse_docx(file_bytes: bytes) -> List[Dict[str, Any]]:
    """
    Parse a DOCX file — all paragraphs joined as one segment.
    python-docx does not expose page numbers, so all text is page 1.
    """
    try:
        from docx import Document  # lazy import
    except ImportError as exc:
        raise ImportError(
            "python-docx is required for DOCX support. Run: pip install python-docx"
        ) from exc

    try:
        doc = Document(io.BytesIO(file_bytes))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        text = "\n\n".join(paragraphs)
        if not text.strip():
            raise ValueError("The DOCX file appears to be empty.")
        return [{"text": text, "page": 1}]
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"Failed to parse DOCX: {exc}") from exc


# ── Dispatcher ────────────────────────────────────────────────────────────────

_PARSERS = {
    ".txt":  _parse_txt,
    ".pdf":  _parse_pdf,
    ".docx": _parse_docx,
}

SUPPORTED_EXTENSIONS = list(_PARSERS.keys())


def parse_file(file_bytes: bytes, filename: str) -> List[Dict[str, Any]]:
    """
    Detect file type from extension and parse into page segments.

    Args:
        file_bytes: Raw binary content of the uploaded file.
        filename:   Original filename including extension.

    Returns:
        List of dicts with keys: 'text', 'page'
    """
    ext = Path(filename).suffix.lower()
    parser = _PARSERS.get(ext)
    if parser is None:
        raise ValueError(
            f"Unsupported file type '{ext}'. "
            f"Supported types: {', '.join(SUPPORTED_EXTENSIONS)}"
        )
    logger.info("Parsing '%s' as %s", filename, ext)
    return parser(file_bytes)


# ── Chunker ───────────────────────────────────────────────────────────────────

def chunk_document(file_bytes: bytes, filename: str) -> List[Dict[str, Any]]:
    """
    Full pipeline: parse a file → split into semantic chunks.

    Chunking strategy — RecursiveCharacterTextSplitter splits on:
      1. Double newline  (\\n\\n) — paragraph boundary
      2. Single newline  (\\n)   — line boundary
      3. Period+space   (. )    — sentence boundary
      4. Single space   ( )     — word boundary
      5. Empty string   ("")    — character (last resort)

    Args:
        file_bytes: Raw binary content of the uploaded file.
        filename:   Original filename.

    Returns:
        List of chunk dicts with keys: text, source, chunk_index, page
    """
    pages = parse_file(file_bytes, filename)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.CHUNK_SIZE,
        chunk_overlap=config.CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
        length_function=len,
    )

    all_chunks: List[Dict[str, Any]] = []
    chunk_index = 0

    for page_data in pages:
        page_text = page_data["text"]
        page_num = page_data["page"]

        for split_text in splitter.split_text(page_text):
            if split_text.strip():
                all_chunks.append(make_chunk(
                    text=split_text,
                    source=filename,
                    chunk_index=chunk_index,
                    page=page_num,
                ))
                chunk_index += 1

    if not all_chunks:
        raise ValueError(f"No text content could be extracted from '{filename}'.")

    logger.info(
        "Chunked '%s' → %d chunks across %d page(s).",
        filename, len(all_chunks), len(pages),
    )
    return all_chunks
