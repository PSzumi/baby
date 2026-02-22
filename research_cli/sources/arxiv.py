"""
arxiv.py — arXiv API client for preprint search and PDF downloads.

Search: Queries the arXiv Atom API, returns normalized paper dicts.
Download: Detects arXiv papers from DOI patterns or external IDs,
downloads PDFs to the project's pdfs/ directory.
"""

import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime

import requests

from research_cli.config import (
    ARXIV_RATE_LIMIT,
    REQUEST_TIMEOUT,
    USER_AGENT,
)

ARXIV_API_URL = "https://export.arxiv.org/api/query"
_ATOM_NS = "{http://www.w3.org/2005/Atom}"

# Regex to extract arXiv IDs from DOIs or URLs
ARXIV_DOI_PATTERN = re.compile(r"10\.48550/arXiv\.(\d{4}\.\d{4,5})")
ARXIV_URL_PATTERN = re.compile(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})")
ARXIV_ID_PATTERN = re.compile(r"^(\d{4}\.\d{4,5})(v\d+)?$")


def extract_arxiv_id(doi: str = "", url: str = "") -> str | None:
    """Extract an arXiv ID from a DOI or URL string."""
    if doi:
        match = ARXIV_DOI_PATTERN.search(doi)
        if match:
            return match.group(1)
    if url:
        match = ARXIV_URL_PATTERN.search(url)
        if match:
            return match.group(1)
    return None


def download_pdf(arxiv_id: str, dest_dir: str) -> str | None:
    """
    Download a PDF from arXiv.

    Returns the path to the saved PDF file, or None on failure.
    """
    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    dest_path = os.path.join(dest_dir, f"arxiv_{arxiv_id.replace('.', '_')}.pdf")

    # Skip if already downloaded
    if os.path.isfile(dest_path):
        return dest_path

    os.makedirs(dest_dir, exist_ok=True)

    try:
        resp = requests.get(
            pdf_url,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT * 2,  # longer timeout for PDF downloads
            stream=True,
        )
        resp.raise_for_status()

        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        time.sleep(ARXIV_RATE_LIMIT)
        return dest_path

    except requests.RequestException as exc:
        print(f"  [WARN] arXiv PDF download failed for {arxiv_id}: {exc}")
        return None


def try_download(doi: str, url: str, dest_dir: str) -> str | None:
    """
    Attempt to download a PDF from arXiv if the paper has an arXiv ID.
    Returns the PDF path or None.
    """
    arxiv_id = extract_arxiv_id(doi=doi, url=url)
    if arxiv_id:
        return download_pdf(arxiv_id, dest_dir)
    return None


def search(query: str, limit: int = 10, year_range: str = "") -> list[dict]:
    """
    Search arXiv for papers matching the query.

    Returns normalized paper dicts with the common schema.
    arXiv API doesn't support year filtering, so we post-filter.
    """
    # Parse year range for post-filtering
    min_year, max_year = 0, 9999
    if year_range:
        parts = year_range.split("-")
        if len(parts) == 2:
            min_year, max_year = int(parts[0]), int(parts[1])
    else:
        max_year = datetime.now().year
        min_year = max_year - 5

    # Fetch more than needed since we'll post-filter by year
    fetch_limit = min(limit * 3, 100)
    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": fetch_limit,
        "sortBy": "relevance",
        "sortOrder": "descending",
    }

    try:
        resp = requests.get(
            ARXIV_API_URL,
            params=params,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"  [WARN] arXiv search failed: {exc}")
        return []

    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError as exc:
        print(f"  [WARN] arXiv XML parse error: {exc}")
        return []

    results = []
    for entry in root.findall(f"{_ATOM_NS}entry"):
        title = (entry.findtext(f"{_ATOM_NS}title") or "").strip().replace("\n", " ")
        if not title or title == "Error":
            continue

        abstract = (entry.findtext(f"{_ATOM_NS}summary") or "").strip().replace("\n", " ")
        if not abstract:
            continue

        # Extract year from published date (e.g. "2023-05-15T...")
        published = entry.findtext(f"{_ATOM_NS}published") or ""
        year = published[:4] if len(published) >= 4 else ""
        try:
            if year and not (min_year <= int(year) <= max_year):
                continue
        except ValueError:
            pass

        # Authors
        authors_list = []
        for author in entry.findall(f"{_ATOM_NS}author"):
            name = author.findtext(f"{_ATOM_NS}name") or "Unknown"
            authors_list.append({"name": name.strip()})

        # Extract DOI and PDF link
        doi = ""
        pdf_url = ""
        abs_url = ""
        for link in entry.findall(f"{_ATOM_NS}link"):
            href = link.get("href", "")
            link_type = link.get("type", "")
            rel = link.get("rel", "")
            if link_type == "application/pdf":
                pdf_url = href
            elif rel == "alternate":
                abs_url = href

        # Check for DOI in arxiv:doi element
        doi_elem = entry.find("{http://arxiv.org/schemas/atom}doi")
        if doi_elem is not None and doi_elem.text:
            doi = doi_elem.text.strip()

        # Journal ref
        journal_elem = entry.find("{http://arxiv.org/schemas/atom}journal_ref")
        journal = journal_elem.text.strip() if journal_elem is not None and journal_elem.text else ""

        results.append({
            "origin": "arxiv",
            "doi": doi,
            "title": title,
            "authors": authors_list,
            "year": year,
            "journal": journal or "arXiv preprint",
            "url": abs_url,
            "pdf_url": pdf_url,
            "abstract": abstract,
            "citation_count": 0,
            "is_open_access": 1,
        })

        if len(results) >= limit:
            break

    time.sleep(ARXIV_RATE_LIMIT)
    print(f"  arXiv: {len(results)} papers")
    return results
