"""
europe_pmc.py — Europe PMC REST API client for biomedical literature.

42M+ abstracts, no authentication required.
Includes direct PDF links for PMC open access articles.
"""

import time
from datetime import datetime

import requests

from research_cli.config import (
    EUROPE_PMC_RATE_LIMIT,
    REQUEST_TIMEOUT,
    USER_AGENT,
)

API_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


def search(query: str, limit: int = 10, year_range: str = "") -> list[dict]:
    """
    Search Europe PMC for papers matching the query.

    Returns normalized paper dicts with the common schema.
    """
    if not year_range:
        current_year = datetime.now().year
        year_range = f"{current_year - 5}-{current_year}"

    min_year, max_year = year_range.split("-") if "-" in year_range else (year_range, year_range)

    # Europe PMC uses Lucene-style queries
    full_query = f"{query} (PUB_YEAR:[{min_year} TO {max_year}])"

    params = {
        "query": full_query,
        "format": "json",
        "pageSize": min(limit * 2, 100),
        "resulttype": "core",  # includes abstracts
        "cursorMark": "*",
    }

    try:
        resp = requests.get(
            API_URL,
            params=params,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        print(f"  [WARN] Europe PMC search failed: {exc}")
        return []

    results = []
    for hit in data.get("resultList", {}).get("result", []):
        abstract = (hit.get("abstractText") or "").strip()
        if not abstract:
            continue

        title = (hit.get("title") or "").strip()
        if not title:
            continue

        # Authors — Europe PMC returns "authorString" as a single string
        authors_str = hit.get("authorString", "")
        authors_list = []
        if authors_str:
            for name in authors_str.split(", "):
                name = name.strip().rstrip(".")
                if name:
                    authors_list.append({"name": name})

        year = str(hit.get("pubYear") or "")
        doi = hit.get("doi") or ""
        journal = hit.get("journalTitle") or ""

        # Build URL
        pmid = hit.get("pmid") or ""
        pmcid = hit.get("pmcid") or ""
        if pmcid:
            url = f"https://europepmc.org/article/PMC/{pmcid}"
        elif pmid:
            url = f"https://europepmc.org/article/MED/{pmid}"
        else:
            url = f"https://doi.org/{doi}" if doi else ""

        # PDF link for PMC articles
        pdf_url = ""
        if pmcid:
            pdf_url = f"https://europepmc.org/backend/ptpmcrender.fcgi?accid={pmcid}&blobtype=pdf"

        is_oa = hit.get("isOpenAccess") == "Y"

        results.append({
            "origin": "europe_pmc",
            "doi": doi,
            "title": title,
            "authors": authors_list,
            "year": year,
            "journal": journal,
            "url": url,
            "pdf_url": pdf_url,
            "abstract": abstract,
            "citation_count": hit.get("citedByCount", 0),
            "is_open_access": 1 if is_oa else 0,
        })

        if len(results) >= limit:
            break

    time.sleep(EUROPE_PMC_RATE_LIMIT)
    print(f"  Europe PMC: {len(results)} papers")
    return results
