"""
semantic_scholar.py — Semantic Scholar Graph API client.

Fetches papers with: title, authors, DOI, abstract, citation count,
TLDR summary, open-access PDF link, journal info.
"""

import time
from datetime import datetime

import requests

from research_cli.config import (
    SEMANTIC_SCHOLAR_API_KEY,
    SS_RATE_LIMIT,
    REQUEST_TIMEOUT,
    USER_AGENT,
)

API_BASE = "https://api.semanticscholar.org/graph/v1"
FIELDS = (
    "title,authors,year,abstract,externalIds,citationCount,"
    "tldr,publicationTypes,journal,url,openAccessPdf"
)


def search(query: str, limit: int = 30, year_range: str = "") -> list[dict]:
    """
    Search Semantic Scholar for papers matching the query.

    Returns a list of normalized paper dicts with keys:
        origin, doi, title, authors, year, journal, url, pdf_url,
        abstract, citation_count, is_open_access, tldr
    """
    if not SEMANTIC_SCHOLAR_API_KEY:
        print("  [SKIP] Semantic Scholar: no API key set (set SEMANTIC_SCHOLAR_API_KEY)")
        return []

    if not year_range:
        current_year = datetime.now().year
        year_range = f"{current_year - 5}-{current_year}"

    headers = {"User-Agent": USER_AGENT}
    headers["x-api-key"] = SEMANTIC_SCHOLAR_API_KEY

    results = []
    offset = 0
    per_page = min(limit, 100)  # API max is 100 per request

    while len(results) < limit:
        params = {
            "query": query,
            "limit": per_page,
            "offset": offset,
            "fields": FIELDS,
            "year": year_range,
        }

        try:
            resp = requests.get(
                f"{API_BASE}/paper/search",
                params=params,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            print(f"  [WARN] Semantic Scholar request failed: {exc}")
            break

        papers = data.get("data", [])
        if not papers:
            break

        for paper in papers:
            # Skip papers without abstracts
            if not paper.get("abstract"):
                continue

            # Extract DOI from externalIds
            ext_ids = paper.get("externalIds") or {}
            doi = ext_ids.get("DOI", "")

            # Extract author names
            authors_list = []
            for a in paper.get("authors", []):
                name = a.get("name", "Unknown")
                authors_list.append({"name": name})

            # Journal info
            journal_info = paper.get("journal") or {}
            journal_name = journal_info.get("name", "")

            # Open access PDF
            oa_pdf = paper.get("openAccessPdf") or {}
            pdf_url = oa_pdf.get("url", "")

            # TLDR
            tldr_info = paper.get("tldr") or {}
            tldr_text = tldr_info.get("text", "")

            results.append({
                "origin": "semantic_scholar",
                "doi": doi,
                "title": paper.get("title", "Untitled"),
                "authors": authors_list,
                "year": str(paper.get("year", "")),
                "journal": journal_name,
                "url": paper.get("url", ""),
                "pdf_url": pdf_url,
                "abstract": paper["abstract"],
                "citation_count": paper.get("citationCount", 0),
                "is_open_access": 1 if pdf_url else 0,
                "tldr": tldr_text,
            })

            if len(results) >= limit:
                break

        offset += per_page
        if offset >= data.get("total", 0):
            break

        time.sleep(SS_RATE_LIMIT)

    print(f"  Semantic Scholar: {len(results)} papers")
    return results
