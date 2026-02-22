"""
openalex.py — OpenAlex API client.

Fetches papers with: title, authors, DOI, abstract (reconstructed from
inverted index), citation count, open-access status, journal info.
"""

import time
from datetime import datetime

import requests

from research_cli.config import (
    CROSSREF_MAILTO,
    OPENALEX_RATE_LIMIT,
    REQUEST_TIMEOUT,
    USER_AGENT,
)

API_BASE = "https://api.openalex.org"


def _reconstruct_abstract(inverted_index: dict) -> str:
    """
    OpenAlex stores abstracts as inverted indexes:
        {"word": [position1, position2], ...}
    Reconstruct into a readable string.
    """
    if not inverted_index:
        return ""
    position_word = []
    for word, positions in inverted_index.items():
        for pos in positions:
            position_word.append((pos, word))
    position_word.sort(key=lambda x: x[0])
    return " ".join(w for _, w in position_word)


def search(query: str, limit: int = 30, year_range: str = "") -> list[dict]:
    """
    Search OpenAlex for works matching the query.

    Returns normalized paper dicts matching the common schema.
    """
    if not year_range:
        current_year = datetime.now().year
        year_range = f"{current_year - 5}-{current_year}"

    headers = {"User-Agent": USER_AGENT}
    params = {
        "search": query,
        "per_page": min(limit, 50),  # API max is 50 for search
        "filter": f"publication_year:{year_range},type:article|review,is_paratext:false",
        "select": (
            "id,doi,title,authorships,publication_year,cited_by_count,"
            "primary_location,open_access,abstract_inverted_index"
        ),
    }
    if CROSSREF_MAILTO:
        params["mailto"] = CROSSREF_MAILTO

    results = []
    page = 1

    while len(results) < limit:
        params["page"] = page
        try:
            resp = requests.get(
                f"{API_BASE}/works",
                params=params,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            print(f"  [WARN] OpenAlex request failed: {exc}")
            break

        works = data.get("results", [])
        if not works:
            break

        for work in works:
            # Reconstruct abstract from inverted index
            abstract = _reconstruct_abstract(
                work.get("abstract_inverted_index") or {}
            )
            if not abstract:
                continue

            # Extract DOI (strip "https://doi.org/" prefix)
            doi_raw = work.get("doi", "") or ""
            doi = doi_raw.replace("https://doi.org/", "").strip()

            # Authors
            authors_list = []
            for authorship in work.get("authorships", []):
                author = authorship.get("author", {})
                name = author.get("display_name", "Unknown")
                authors_list.append({"name": name})

            # Journal / source info
            primary_loc = work.get("primary_location") or {}
            source = primary_loc.get("source") or {}
            journal_name = source.get("display_name", "")

            # Open access
            oa_info = work.get("open_access") or {}
            oa_url = oa_info.get("oa_url", "")
            is_oa = oa_info.get("is_oa", False)

            results.append({
                "origin": "openalex",
                "doi": doi,
                "title": work.get("title", "Untitled"),
                "authors": authors_list,
                "year": str(work.get("publication_year", "")),
                "journal": journal_name,
                "url": doi_raw or work.get("id", ""),
                "pdf_url": oa_url if is_oa else "",
                "abstract": abstract,
                "citation_count": work.get("cited_by_count", 0),
                "is_open_access": 1 if is_oa else 0,
            })

            if len(results) >= limit:
                break

        page += 1
        time.sleep(OPENALEX_RATE_LIMIT)

    print(f"  OpenAlex: {len(results)} papers")
    return results
