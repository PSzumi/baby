"""
doaj.py — DOAJ (Directory of Open Access Journals) API client.

11M+ open access articles, no authentication required.
Uses the v4 search API with bibjson response structure.
"""

import time
from datetime import datetime

import requests

from research_cli.config import (
    DOAJ_RATE_LIMIT,
    REQUEST_TIMEOUT,
    USER_AGENT,
)

API_URL = "https://doaj.org/api/v4/search/articles"


def search(query: str, limit: int = 10, year_range: str = "") -> list[dict]:
    """
    Search DOAJ for open access articles matching the query.

    Returns normalized paper dicts with the common schema.
    """
    if not year_range:
        current_year = datetime.now().year
        year_range = f"{current_year - 5}-{current_year}"

    min_year, max_year = year_range.split("-") if "-" in year_range else (year_range, year_range)

    # DOAJ search URL format: /api/v4/search/articles/{query}
    search_url = f"{API_URL}/{requests.utils.quote(query)}"

    params = {
        "page": 1,
        "pageSize": min(limit * 2, 50),
    }

    try:
        resp = requests.get(
            search_url,
            params=params,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        print(f"  [WARN] DOAJ search failed: {exc}")
        return []

    results = []
    for item in data.get("results", []):
        bib = item.get("bibjson", {})

        abstract = (bib.get("abstract") or "").strip()
        if not abstract:
            continue

        title = (bib.get("title") or "").strip()
        if not title:
            continue

        # Year from bibjson
        year = str(bib.get("year") or "")
        if not year:
            # Try month field which sometimes has "YYYY-MM" format
            month_str = bib.get("month") or ""
            if len(month_str) >= 4:
                year = month_str[:4]

        try:
            if year and not (int(min_year) <= int(year) <= int(max_year)):
                continue
        except ValueError:
            pass

        # Authors
        authors_list = []
        for author in bib.get("author", []):
            name = author.get("name", "").strip()
            if name:
                authors_list.append({"name": name})

        # DOI from identifiers
        doi = ""
        for ident in bib.get("identifier", []):
            if ident.get("type") == "doi":
                doi = ident.get("id", "")
                break

        # Journal
        journal_info = bib.get("journal", {})
        journal = journal_info.get("title", "") if isinstance(journal_info, dict) else ""

        # Links — find fulltext URL
        url = ""
        pdf_url = ""
        for link in bib.get("link", []):
            link_url = link.get("url", "")
            link_type = link.get("type", "")
            content_type = link.get("content_type", "")
            if content_type == "application/pdf" or (link_type == "fulltext" and link_url.endswith(".pdf")):
                pdf_url = link_url
            elif link_type == "fulltext":
                url = link_url

        if not url and doi:
            url = f"https://doi.org/{doi}"

        results.append({
            "origin": "doaj",
            "doi": doi,
            "title": title,
            "authors": authors_list,
            "year": year,
            "journal": journal,
            "url": url,
            "pdf_url": pdf_url,
            "abstract": abstract,
            "citation_count": 0,
            "is_open_access": 1,
        })

        if len(results) >= limit:
            break

    time.sleep(DOAJ_RATE_LIMIT)
    print(f"  DOAJ: {len(results)} papers")
    return results
