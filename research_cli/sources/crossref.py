"""
crossref.py — CrossRef API client for bibliographic enrichment.

Given a DOI, fetches complete bibliographic metadata:
    journal name, volume, issue, pages, publisher, full author names.
Produces BibTeX entries and APA-formatted reference strings.
"""

import time

import requests

from research_cli.config import (
    CROSSREF_MAILTO,
    CROSSREF_RATE_LIMIT,
    REQUEST_TIMEOUT,
    USER_AGENT,
)

API_BASE = "https://api.crossref.org/works"


def enrich_by_doi(doi: str) -> dict | None:
    """
    Fetch full bibliographic metadata from CrossRef for a single DOI.

    Returns a dict with keys:
        title, authors (list of {given, family}), year, journal,
        volume, issue, pages, publisher, doi, bibtex_type, url
    Or None if the DOI is not found / request fails.
    """
    if not doi:
        return None

    headers = {"User-Agent": USER_AGENT}
    if CROSSREF_MAILTO:
        headers["User-Agent"] += f" (mailto:{CROSSREF_MAILTO})"

    try:
        resp = requests.get(
            f"{API_BASE}/{doi}",
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException:
        return None

    msg = data.get("message", {})

    # Title
    titles = msg.get("title", [])
    title = titles[0] if titles else ""

    # Authors with given/family names
    authors = []
    for author in msg.get("author", []):
        authors.append({
            "given": author.get("given", ""),
            "family": author.get("family", ""),
            "name": f"{author.get('given', '')} {author.get('family', '')}".strip(),
        })

    # Publication date
    date_parts = msg.get("published-print", msg.get("published-online", {}))
    parts = date_parts.get("date-parts", [[]])[0] if date_parts else []
    year = str(parts[0]) if parts else ""

    # Journal
    containers = msg.get("container-title", [])
    journal = containers[0] if containers else ""

    # Volume, issue, pages
    volume = msg.get("volume", "")
    issue = msg.get("issue", "")
    pages = msg.get("page", "")

    # Publisher
    publisher = msg.get("publisher", "")

    # Type mapping
    cr_type = msg.get("type", "journal-article")
    bibtex_type_map = {
        "journal-article": "article",
        "proceedings-article": "inproceedings",
        "book-chapter": "incollection",
        "book": "book",
        "monograph": "book",
        "dissertation": "phdthesis",
    }
    bibtex_type = bibtex_type_map.get(cr_type, "article")

    return {
        "title": title,
        "authors": authors,
        "year": year,
        "journal": journal,
        "volume": volume,
        "issue": issue,
        "pages": pages,
        "publisher": publisher,
        "doi": doi,
        "bibtex_type": bibtex_type,
        "url": f"https://doi.org/{doi}",
    }


def batch_enrich(dois: list[str]) -> list[dict]:
    """
    Fetch CrossRef metadata for a batch of DOIs with rate limiting.

    Returns list of enrichment dicts (skips failures silently).
    """
    results = []
    for doi in dois:
        result = enrich_by_doi(doi)
        if result:
            results.append(result)
        time.sleep(CROSSREF_RATE_LIMIT)

    print(f"  CrossRef: enriched {len(results)}/{len(dois)} DOIs")
    return results
