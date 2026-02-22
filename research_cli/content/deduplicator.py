"""
deduplicator.py — Deduplicate academic sources.

Two-pass deduplication:
    1. Exact DOI match (case-insensitive)
    2. Title similarity using difflib (threshold configurable)

When duplicates are found, the record with richer metadata is kept.
"""

import difflib
from research_cli.config import DEDUP_TITLE_THRESHOLD


def _metadata_richness(paper: dict) -> int:
    """Score how much metadata a paper dict has. Higher is richer."""
    score = 0
    if paper.get("doi"):
        score += 3
    if paper.get("abstract"):
        score += 2
    if paper.get("citation_count", 0) > 0:
        score += 2
    if paper.get("pdf_url"):
        score += 2
    if paper.get("journal"):
        score += 1
    if paper.get("authors"):
        score += 1
    if paper.get("tldr"):
        score += 1
    return score


def _merge_papers(primary: dict, secondary: dict) -> dict:
    """Merge two paper dicts, keeping non-empty values from both."""
    merged = dict(primary)
    for key, val in secondary.items():
        if val and not merged.get(key):
            merged[key] = val
    # Always take the higher citation count
    merged["citation_count"] = max(
        primary.get("citation_count", 0),
        secondary.get("citation_count", 0),
    )
    return merged


def _normalize_doi(doi: str) -> str:
    """Normalize a DOI for comparison."""
    return doi.strip().lower().replace("https://doi.org/", "")


def _normalize_title(title: str) -> str:
    """Normalize a title for fuzzy comparison."""
    return title.strip().lower()


def deduplicate(papers: list[dict], title_threshold: float = DEDUP_TITLE_THRESHOLD) -> list[dict]:
    """
    Remove duplicate papers from a combined list.

    Pass 1: exact DOI match
    Pass 2: title similarity (difflib SequenceMatcher)

    Returns a deduplicated list of merged paper dicts.
    """
    # -- Pass 1: DOI dedup --
    doi_map: dict[str, dict] = {}  # normalized_doi -> best paper
    no_doi: list[dict] = []

    for paper in papers:
        doi = paper.get("doi", "")
        if doi:
            norm_doi = _normalize_doi(doi)
            if norm_doi in doi_map:
                existing = doi_map[norm_doi]
                if _metadata_richness(paper) > _metadata_richness(existing):
                    doi_map[norm_doi] = _merge_papers(paper, existing)
                else:
                    doi_map[norm_doi] = _merge_papers(existing, paper)
            else:
                doi_map[norm_doi] = paper
        else:
            no_doi.append(paper)

    deduped = list(doi_map.values())

    # -- Pass 2: Title similarity for papers without DOI --
    existing_titles = [_normalize_title(p.get("title", "")) for p in deduped]

    for paper in no_doi:
        title = _normalize_title(paper.get("title", ""))
        if not title:
            continue

        is_dup = False
        for i, existing_title in enumerate(existing_titles):
            ratio = difflib.SequenceMatcher(None, title, existing_title).ratio()
            if ratio >= title_threshold:
                # Merge into the existing record
                deduped[i] = _merge_papers(deduped[i], paper)
                is_dup = True
                break

        if not is_dup:
            deduped.append(paper)
            existing_titles.append(title)

    removed = len(papers) - len(deduped)
    if removed:
        print(f"  Dedup: removed {removed} duplicates ({len(papers)} → {len(deduped)})")

    return deduped
