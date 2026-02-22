"""
relevance_scorer.py — Score and rank academic sources by quality and relevance.

Composite score = weighted combination of:
    - Semantic relevance to topic (0.5 weight, Claude-scored)
    - Citation count (0.3 weight, log-normalized)
    - Recency (0.2 weight, linear decay over 10 years)

Sources with full text get a 1.5x quality multiplier.
"""

import math
from datetime import datetime

from research_cli.config import (
    RELEVANCE_WEIGHT,
    CITATION_WEIGHT,
    RECENCY_WEIGHT,
    FULLTEXT_MULTIPLIER,
)
from research_cli.llm_client import call_claude_json


def _recency_score(year_str: str) -> float:
    """Calculate recency score: 1.0 for current year, decaying to 0.0 over 10 years."""
    try:
        pub_year = int(year_str)
    except (ValueError, TypeError):
        return 0.3  # default for unknown year

    current_year = datetime.now().year
    age = current_year - pub_year
    return max(0.0, 1.0 - age / 10.0)


def _citation_score(citation_count: int, max_citations: int) -> float:
    """Log-normalized citation score. Papers with 0 citations get a neutral
    baseline (0.3) since many sources don't report citation data."""
    if max_citations <= 0:
        return 0.3
    if citation_count == 0:
        return 0.3  # neutral baseline for unknown/zero citations
    return math.log(1 + citation_count) / math.log(1 + max_citations)


def score_relevance_batch(topic: str, papers: list[dict]) -> dict[int, float]:
    """
    Use Claude to batch-score semantic relevance of papers to the topic.

    Papers are identified by their list index. Returns {index: score (0-1)}.
    """
    if not papers:
        return {}

    # Build a compact list for Claude
    paper_list = []
    for i, p in enumerate(papers):
        title = p.get("title", "Untitled")
        abstract = (p.get("abstract") or "")[:300]  # truncate for batch efficiency
        paper_list.append(f"{i}. \"{title}\" — {abstract}")

    prompt = f"""Rate each paper's relevance to this research topic on a scale of 0-10.
Topic: "{topic}"

Papers:
{chr(10).join(paper_list)}

Return a JSON object mapping paper number to relevance score (0-10).
Example: {{"0": 8, "1": 3, "2": 9}}
"""

    try:
        scores = call_claude_json(prompt, max_tokens=1024, temperature=0.1)
        # Normalize to 0-1
        return {int(k): float(v) / 10.0 for k, v in scores.items()}
    except (ValueError, KeyError, TypeError):
        # Default to moderate relevance on failure
        print(f"  [WARN] LLM relevance scoring failed for batch of {len(papers)} papers — using 0.5 defaults")
        return {i: 0.5 for i in range(len(papers))}


def score_sources(
    topic: str,
    sources: list[dict],
    batch_size: int = 20,
) -> list[dict]:
    """
    Score all sources and add relevance_score and quality_score fields.

    Sources are scored in batches to fit within context limits.
    Returns the same list with scores populated.
    """
    if not sources:
        return sources

    # Find max citation count for normalization
    max_citations = max(s.get("citation_count", 0) for s in sources)

    # Score relevance in batches
    all_relevance: dict[int, float] = {}
    for batch_start in range(0, len(sources), batch_size):
        batch = sources[batch_start:batch_start + batch_size]
        batch_scores = score_relevance_batch(topic, batch)
        for local_idx, score in batch_scores.items():
            all_relevance[batch_start + local_idx] = score

    # Compute composite scores
    for i, source in enumerate(sources):
        rel = all_relevance.get(i, 0.5)
        cit = _citation_score(source.get("citation_count", 0), max_citations)
        rec = _recency_score(source.get("year", ""))

        # Weighted composite
        composite = (
            RELEVANCE_WEIGHT * rel
            + CITATION_WEIGHT * cit
            + RECENCY_WEIGHT * rec
        )

        # Full-text multiplier
        has_fulltext = bool(source.get("full_text_path"))
        quality = composite * (FULLTEXT_MULTIPLIER if has_fulltext else 1.0)

        source["relevance_score"] = round(rel, 3)
        source["quality_score"] = round(quality, 3)

    # Sort by quality descending
    sources.sort(key=lambda s: s.get("quality_score", 0), reverse=True)

    print(f"  Scored {len(sources)} sources (top score: {sources[0].get('quality_score', 0):.3f})")
    return sources
