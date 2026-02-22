"""
pdf_extractor.py — Download PDFs and extract text.

Primary extractor: PyMuPDF (fitz)
Fallback: pdfplumber (better for some scanned documents)

Extracted text is cleaned: headers/footers stripped, whitespace normalized.
"""

import os
import re

import requests

from research_cli.config import REQUEST_TIMEOUT, USER_AGENT


def download_pdf(url: str, dest_path: str) -> bool:
    """
    Download a PDF from a URL to dest_path.
    Returns True on success, False on failure.
    """
    if os.path.isfile(dest_path):
        return True  # already downloaded

    os.makedirs(os.path.dirname(dest_path), exist_ok=True)

    try:
        resp = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT * 2,
            stream=True,
        )
        resp.raise_for_status()

        # Verify it looks like a PDF
        content_type = resp.headers.get("Content-Type", "")
        first_bytes = b""

        with open(dest_path, "wb") as f:
            for i, chunk in enumerate(resp.iter_content(chunk_size=8192)):
                if i == 0:
                    first_bytes = chunk[:5]
                f.write(chunk)

        # Check if it's actually a PDF
        if not first_bytes.startswith(b"%PDF"):
            os.remove(dest_path)
            return False

        return True

    except (requests.RequestException, OSError):
        # Clean up partial downloads
        if os.path.isfile(dest_path):
            os.remove(dest_path)
        return False


def extract_text_pymupdf(pdf_path: str) -> str | None:
    """Extract text from a PDF using PyMuPDF (fitz)."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return None

    try:
        doc = fitz.open(pdf_path)
        pages = []
        for page in doc:
            text = page.get_text()
            if text.strip():
                pages.append(text)
        doc.close()
        return "\n\n".join(pages) if pages else None
    except Exception:
        return None


def extract_text_pdfplumber(pdf_path: str) -> str | None:
    """Extract text from a PDF using pdfplumber (fallback)."""
    try:
        import pdfplumber
    except ImportError:
        return None

    try:
        pages = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text and text.strip():
                    pages.append(text)
        return "\n\n".join(pages) if pages else None
    except Exception:
        return None


def _clean_text(text: str) -> str:
    """Clean extracted PDF text: normalize whitespace, remove artifacts."""
    # Collapse multiple blank lines into two
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Remove page numbers standing alone on a line
    text = re.sub(r"^\s*\d{1,4}\s*$", "", text, flags=re.MULTILINE)
    # Fix hyphenated line breaks (word- \n continuation)
    text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)
    # Normalize whitespace within lines
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def extract_text(pdf_path: str) -> str | None:
    """
    Extract text from a PDF file using PyMuPDF (primary) or pdfplumber (fallback).
    Returns cleaned text or None if extraction fails.
    """
    if not os.path.isfile(pdf_path):
        return None

    # Try PyMuPDF first
    text = extract_text_pymupdf(pdf_path)
    if not text:
        # Fallback to pdfplumber
        text = extract_text_pdfplumber(pdf_path)

    if text:
        return _clean_text(text)
    return None


def download_and_extract(url: str, dest_dir: str, filename: str) -> tuple[str | None, str | None]:
    """
    Download a PDF and extract its text.

    Returns (pdf_path, extracted_text) — either or both may be None.
    """
    pdf_path = os.path.join(dest_dir, filename)

    if not download_pdf(url, pdf_path):
        return None, None

    text = extract_text(pdf_path)
    return pdf_path, text
