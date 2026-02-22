"""
unpaywall.py — Unpaywall API client for finding open-access PDF links.

Given a DOI, returns the best available OA PDF URL.
Requires an email address (configured via UNPAYWALL_EMAIL).
"""

import time

import requests

from research_cli.config import (
    UNPAYWALL_EMAIL,
    UNPAYWALL_RATE_LIMIT,
    REQUEST_TIMEOUT,
    USER_AGENT,
)

API_BASE = "https://api.unpaywall.org/v2"


def find_pdf(doi: str) -> str | None:
    """
    Look up a DOI on Unpaywall and return the best OA PDF URL.
    Returns None if no OA version is available or the request fails.
    """
    if not doi or not UNPAYWALL_EMAIL:
        return None

    try:
        resp = requests.get(
            f"{API_BASE}/{doi}",
            params={"email": UNPAYWALL_EMAIL},
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException:
        return None

    # Try best OA location first
    best = data.get("best_oa_location") or {}
    pdf_url = best.get("url_for_pdf") or best.get("url")

    if pdf_url:
        return pdf_url

    # Fall back to any OA location with a PDF
    for loc in data.get("oa_locations", []):
        url = loc.get("url_for_pdf")
        if url:
            return url

    return None


def batch_find_pdfs(dois: list[str]) -> dict[str, str]:
    """
    Look up OA PDF URLs for a batch of DOIs.

    Returns a dict mapping DOI -> PDF URL (only for DOIs with results).
    """
    results = {}
    for doi in dois:
        url = find_pdf(doi)
        if url:
            results[doi] = url
        time.sleep(UNPAYWALL_RATE_LIMIT)

    print(f"  Unpaywall: found PDFs for {len(results)}/{len(dois)} DOIs")
    return results
