"""
scielo.py — SciELO search client for Latin American journals.

1200+ Latin American, Caribbean, and Iberian journals.
All content is open access. Parses search.scielo.org HTML results
since SciELO doesn't expose a public JSON search API.
"""

import html
import re
import time
from datetime import datetime

import requests

from research_cli.config import (
    SCIELO_RATE_LIMIT,
    REQUEST_TIMEOUT,
)

SEARCH_URL = "https://search.scielo.org/"


def _parse_items(raw_html: str, limit: int) -> list[dict]:
    """Parse article items from SciELO search result HTML."""
    results = []

    # Split by item divs: <div id="PID-collection" class="item">
    item_splits = re.split(r'<div\s+id="([^"]+)"\s+class="item">', raw_html)
    # item_splits[0] is before the first item, then alternating: pid, content
    if len(item_splits) < 3:
        return []

    for i in range(1, len(item_splits), 2):
        if len(results) >= limit:
            break

        pid = item_splits[i]
        block = item_splits[i + 1] if i + 1 < len(item_splits) else ""

        # Title: <strong class="title" id="title-PID">...</strong>
        title_match = re.search(
            r'<strong\s+class="title"[^>]*>(.*?)</strong>',
            block, re.DOTALL,
        )
        if not title_match:
            continue
        title = html.unescape(re.sub(r'<[^>]+>', '', title_match.group(1))).strip()
        if not title:
            continue

        # Abstract: <div id="PID_en" class="abstract" ...>text</div>
        # Prefer English, fall back to any language
        abstract = ""
        for lang in ("en", "es", "pt"):
            abs_match = re.search(
                rf'<div\s+id="[^"]*_{lang}"\s+class="abstract"[^>]*>\s*(.*?)\s*</div>',
                block, re.DOTALL,
            )
            if abs_match:
                raw = abs_match.group(1).strip()
                # Remove the label prefix (Abstract, Resumen, Resumo)
                raw = re.sub(r'^(Abstract|Resumen|Resumo)\s*', '', raw)
                abstract = html.unescape(re.sub(r'<[^>]+>', '', raw)).strip()
                if abstract:
                    break
        if not abstract:
            continue

        # Authors: <a ... class="author">Name</a>
        authors_list = []
        for m in re.finditer(r'class="author"[^>]*>(.*?)</a>', block):
            name = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if name:
                authors_list.append({"name": name})

        # Journal: inside <div class="line source"> ... journal name in <a>
        journal = ""
        source_match = re.search(
            r'class="line source">(.*?)</div>\s*</div>',
            block, re.DOTALL,
        )
        if source_match:
            # First link text in source section is the journal
            j_match = re.search(
                r'data-original-title="Metrics">\s*(.*?)\s*</a>',
                source_match.group(1), re.DOTALL,
            )
            if j_match:
                journal = re.sub(r'<[^>]+>', '', j_match.group(1)).strip()

        # Year: look for year pattern in source section
        year = ""
        year_match = re.search(r'(\d{4}),\s*</span>', block)
        if year_match:
            year = year_match.group(1)

        # DOI: from the DOIResults span
        doi = ""
        doi_match = re.search(r'doi\.org/(10\.[^\s"<]+)', block)
        if doi_match:
            doi = doi_match.group(1).rstrip('.')

        # Article URL
        url_match = re.search(
            r'href="(https?://[^"]*scielo[^"]*script=sci_arttext[^"]*)"',
            block,
        )
        url = url_match.group(1) if url_match else ""
        if not url and doi:
            url = f"https://doi.org/{doi}"

        # PDF URL
        pdf_url = ""
        pdf_match = re.search(
            r'href="(https?://[^"]*script=sci_pdf[^"]*)"',
            block,
        )
        if pdf_match:
            pdf_url = pdf_match.group(1)

        results.append({
            "origin": "scielo",
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

    return results


def search(query: str, limit: int = 10, year_range: str = "") -> list[dict]:
    """
    Search SciELO for papers matching the query.

    Returns normalized paper dicts. Gracefully skips if the search
    interface is unavailable (SciELO articles are also found via OpenAlex).
    """
    if not year_range:
        current_year = datetime.now().year
        year_range = f"{current_year - 5}-{current_year}"

    params = {
        "q": query,
        "count": min(limit * 3, 50),
        "from": 0,
        "lang": "en",
        "page": 1,
        "format": "summary",
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    try:
        resp = requests.get(
            SEARCH_URL,
            params=params,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"  [SKIP] SciELO: search unavailable ({exc})")
        return []

    results = _parse_items(resp.text, limit)

    time.sleep(SCIELO_RATE_LIMIT)
    print(f"  SciELO: {len(results)} papers")
    return results
