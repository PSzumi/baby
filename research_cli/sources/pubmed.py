"""
pubmed.py — PubMed/NCBI API client for biomedical literature search.

Two-step process:
    1. ESearch — get PMIDs matching query (JSON)
    2. EFetch — get full records for those PMIDs (XML)

42M+ papers. Optional NCBI_API_KEY for higher rate limits (3→10 req/s).
"""

import time
import xml.etree.ElementTree as ET
from datetime import datetime

import requests

from research_cli.config import (
    NCBI_API_KEY,
    PUBMED_RATE_LIMIT,
    REQUEST_TIMEOUT,
    USER_AGENT,
)

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


def _parse_abstract(article: ET.Element) -> str:
    """
    Parse PubMed abstract, handling structured abstracts
    (Background/Methods/Results/Conclusions labels).
    """
    abstract_elem = article.find(".//Abstract")
    if abstract_elem is None:
        return ""

    parts = []
    for text_elem in abstract_elem.findall("AbstractText"):
        label = text_elem.get("Label", "")
        text = text_elem.text or ""
        text = text.strip()
        if not text:
            continue
        if label:
            parts.append(f"{label}: {text}")
        else:
            parts.append(text)

    return " ".join(parts)


def search(query: str, limit: int = 10, year_range: str = "") -> list[dict]:
    """
    Search PubMed for papers matching the query.

    Returns normalized paper dicts with the common schema.
    """
    if not year_range:
        current_year = datetime.now().year
        year_range = f"{current_year - 5}-{current_year}"

    min_year, max_year = year_range.split("-") if "-" in year_range else (year_range, year_range)

    # Step 1: ESearch — get PMIDs
    esearch_params = {
        "db": "pubmed",
        "term": query,
        "retmax": min(limit * 2, 100),  # fetch extra since some may lack abstracts
        "retmode": "json",
        "sort": "relevance",
        "mindate": f"{min_year}/01/01",
        "maxdate": f"{max_year}/12/31",
        "datetype": "pdat",
    }
    if NCBI_API_KEY:
        esearch_params["api_key"] = NCBI_API_KEY

    try:
        resp = requests.get(
            ESEARCH_URL,
            params=esearch_params,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        print(f"  [WARN] PubMed ESearch failed: {exc}")
        return []

    pmids = data.get("esearchresult", {}).get("idlist", [])
    if not pmids:
        print("  PubMed: 0 papers")
        return []

    time.sleep(PUBMED_RATE_LIMIT)

    # Step 2: EFetch — get full records as XML
    efetch_params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml",
    }
    if NCBI_API_KEY:
        efetch_params["api_key"] = NCBI_API_KEY

    try:
        resp = requests.get(
            EFETCH_URL,
            params=efetch_params,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"  [WARN] PubMed EFetch failed: {exc}")
        return []

    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError as exc:
        print(f"  [WARN] PubMed XML parse error: {exc}")
        return []

    results = []
    for article_wrap in root.findall(".//PubmedArticle"):
        article = article_wrap.find(".//MedlineCitation/Article")
        if article is None:
            continue

        abstract = _parse_abstract(article)
        if not abstract:
            continue

        title = (article.findtext("ArticleTitle") or "").strip()
        if not title:
            continue

        # Authors
        authors_list = []
        author_list = article.find("AuthorList")
        if author_list is not None:
            for author in author_list.findall("Author"):
                last = author.findtext("LastName") or ""
                fore = author.findtext("ForeName") or ""
                name = f"{fore} {last}".strip() or "Unknown"
                authors_list.append({"name": name})

        # Year
        pub_date = article.find(".//Journal/JournalIssue/PubDate")
        year = ""
        if pub_date is not None:
            year = pub_date.findtext("Year") or ""
            if not year:
                medline_date = pub_date.findtext("MedlineDate") or ""
                if medline_date:
                    year = medline_date[:4]

        # Journal
        journal = article.findtext(".//Journal/Title") or ""

        # DOI
        doi = ""
        for eid in article_wrap.findall(".//PubmedData/ArticleIdList/ArticleId"):
            if eid.get("IdType") == "doi":
                doi = (eid.text or "").strip()
                break

        # PMID for URL
        pmid = article_wrap.findtext(".//MedlineCitation/PMID") or ""
        url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""

        # PMC PDF link
        pdf_url = ""
        for eid in article_wrap.findall(".//PubmedData/ArticleIdList/ArticleId"):
            if eid.get("IdType") == "pmc":
                pmc_id = (eid.text or "").strip()
                if pmc_id:
                    pdf_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmc_id}/pdf/"
                break

        results.append({
            "origin": "pubmed",
            "doi": doi,
            "title": title,
            "authors": authors_list,
            "year": year,
            "journal": journal,
            "url": url,
            "pdf_url": pdf_url,
            "abstract": abstract,
            "citation_count": 0,
            "is_open_access": 1 if pdf_url else 0,
        })

        if len(results) >= limit:
            break

    time.sleep(PUBMED_RATE_LIMIT)
    print(f"  PubMed: {len(results)} papers")
    return results
