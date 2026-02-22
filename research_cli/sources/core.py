"""
core.py — CORE API v3 client for open access research outputs.

125M+ open access outputs. Requires a free API key from
https://core.ac.uk/services/api — gracefully skips if not set.
"""

import time
from datetime import datetime

import requests

from research_cli.config import (
    CORE_API_KEY,
    CORE_RATE_LIMIT,
    REQUEST_TIMEOUT,
    USER_AGENT,
)

API_URL = "https://api.core.ac.uk/v3/search/works"


def search(query: str, limit: int = 10, year_range: str = "") -> list[dict]:
    """
    Search CORE for open access works matching the query.

    Returns normalized paper dicts. Skips silently if CORE_API_KEY is not set.
    """
    if not CORE_API_KEY:
        print("  [SKIP] CORE: no API key set (set CORE_API_KEY)")
        return []

    if not year_range:
        current_year = datetime.now().year
        year_range = f"{current_year - 5}-{current_year}"

    min_year, max_year = year_range.split("-") if "-" in year_range else (year_range, year_range)

    headers = {
        "User-Agent": USER_AGENT,
        "Authorization": f"Bearer {CORE_API_KEY}",
    }

    params = {
        "q": query,
        "limit": min(limit * 2, 100),
        "offset": 0,
    }

    try:
        resp = requests.get(
            API_URL,
            params=params,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        print(f"  [WARN] CORE search failed: {exc}")
        return []

    results = []
    for work in data.get("results", []):
        abstract = (work.get("abstract") or "").strip()
        if not abstract:
            continue

        title = (work.get("title") or "").strip()
        if not title:
            continue

        year = str(work.get("yearPublished") or "")
        try:
            if year and not (int(min_year) <= int(year) <= int(max_year)):
                continue
        except ValueError:
            pass

        # Authors
        authors_list = []
        for author in work.get("authors", []):
            name = author.get("name", "").strip()
            if name:
                authors_list.append({"name": name})

        # DOI
        doi = ""
        for identifier in work.get("identifiers", []):
            if isinstance(identifier, str) and identifier.startswith("10."):
                doi = identifier
                break

        # Links
        download_url = work.get("downloadUrl") or ""
        source_url = work.get("sourceFulltextUrls") or []
        url = work.get("links", [{}])[0].get("url", "") if work.get("links") else ""

        # Journal
        journal = ""
        journal_info = work.get("journals", [])
        if journal_info and isinstance(journal_info, list):
            journal = journal_info[0].get("title", "") if journal_info[0] else ""

        results.append({
            "origin": "core",
            "doi": doi,
            "title": title,
            "authors": authors_list,
            "year": year,
            "journal": journal,
            "url": url or (source_url[0] if source_url else ""),
            "pdf_url": download_url,
            "abstract": abstract,
            "citation_count": work.get("citationCount", 0),
            "is_open_access": 1,
        })

        if len(results) >= limit:
            break

    time.sleep(CORE_RATE_LIMIT)
    print(f"  CORE: {len(results)} papers")
    return results
