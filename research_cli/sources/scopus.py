"""
scopus.py — Scopus (Elsevier) API client for academic literature search.

Largest curated abstract and citation database (90M+ records).
Requires a free API key from https://dev.elsevier.com/

Free tier returns titles, DOIs, citation counts, and journal info but
NOT abstracts. Papers are merged with other sources during dedup to
fill in abstracts via DOI matching.
"""

import time
from datetime import datetime

import requests

from research_cli.config import (
    SCOPUS_API_KEY,
    SCOPUS_RATE_LIMIT,
    REQUEST_TIMEOUT,
)

API_URL = "https://api.elsevier.com/content/search/scopus"


def search(query: str, limit: int = 10, year_range: str = "") -> list[dict]:
    """
    Search Scopus for papers matching the query.

    Returns normalized paper dicts. Abstracts may be empty (free tier);
    the deduplicator will fill them in from other sources via DOI matching.
    """
    if not SCOPUS_API_KEY:
        print("  [SKIP] Scopus: no API key set (set SCOPUS_API_KEY)")
        return []

    if not year_range:
        current_year = datetime.now().year
        year_range = f"{current_year - 5}-{current_year}"

    min_year, max_year = year_range.split("-") if "-" in year_range else (year_range, year_range)

    # Scopus uses its own query syntax
    scopus_query = f"TITLE-ABS-KEY({query}) AND PUBYEAR > {int(min_year) - 1} AND PUBYEAR < {int(max_year) + 1}"

    headers = {
        "X-ELS-APIKey": SCOPUS_API_KEY,
        "Accept": "application/json",
    }

    params = {
        "query": scopus_query,
        "count": min(limit * 2, 50),
        "sort": "citedby-count",
        "field": (
            "dc:title,dc:creator,prism:coverDate,prism:doi,"
            "citedby-count,dc:description,prism:publicationName,"
            "subtypeDescription,openaccess,eid,prism:url"
        ),
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
        print(f"  [WARN] Scopus search failed: {exc}")
        return []

    entries = data.get("search-results", {}).get("entry", [])
    if not entries:
        print("  Scopus: 0 papers")
        return []

    # Check for API error entries
    if len(entries) == 1 and entries[0].get("error"):
        print(f"  [WARN] Scopus: {entries[0]['error']}")
        return []

    results = []
    for entry in entries:
        title = (entry.get("dc:title") or "").strip()
        if not title:
            continue

        doi = entry.get("prism:doi") or ""

        # We need either a DOI (for merge) or an abstract to be useful
        abstract = (entry.get("dc:description") or "").strip()
        if not doi and not abstract:
            continue

        # Year from coverDate (format: "2023-05-01")
        cover_date = entry.get("prism:coverDate") or ""
        year = cover_date[:4] if len(cover_date) >= 4 else ""

        # Author — Scopus returns only first author in search
        author_name = entry.get("dc:creator") or ""
        authors_list = [{"name": author_name}] if author_name else []

        journal = entry.get("prism:publicationName") or ""
        citation_count = int(entry.get("citedby-count") or 0)

        url = entry.get("prism:url") or ""
        if not url and doi:
            url = f"https://doi.org/{doi}"

        is_oa = entry.get("openaccess") == "1"

        results.append({
            "origin": "scopus",
            "doi": doi,
            "title": title,
            "authors": authors_list,
            "year": year,
            "journal": journal,
            "url": url,
            "pdf_url": "",
            "abstract": abstract,
            "citation_count": citation_count,
            "is_open_access": 1 if is_oa else 0,
        })

        if len(results) >= limit:
            break

    time.sleep(SCOPUS_RATE_LIMIT)
    print(f"  Scopus: {len(results)} papers")
    return results
