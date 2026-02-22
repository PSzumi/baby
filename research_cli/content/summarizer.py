"""
summarizer.py — Claude-based source summarization for context budget management.

When a paper's full text exceeds the per-source token budget, this module
extracts the most relevant excerpts for a given thesis section.

Summaries are cached to avoid re-extraction on retry or revision.
"""

import os

from research_cli.llm_client import call_claude, count_tokens
from research_cli.config import MAX_TOKENS_PER_SOURCE


def prepare_source_for_context(
    source: dict,
    section_key: str,
    topic: str,
    max_tokens: int = MAX_TOKENS_PER_SOURCE,
) -> str:
    """
    Prepare a source's content for inclusion in a generation prompt.

    Strategy:
        1. If the source has full text and it fits within max_tokens, use it.
        2. If the full text is too large, use Claude to extract relevant excerpts.
        3. If only abstract is available, use abstract + TLDR (if available).

    Returns a formatted string ready for prompt inclusion.
    """
    full_text_path = source.get("full_text_path", "")
    abstract = source.get("abstract", "")
    summary = source.get("summary", "")
    tldr = source.get("tldr", "")

    # If we have a cached summary for this section, use it
    if summary:
        token_count = count_tokens(summary)
        if token_count <= max_tokens:
            return _format_source_context(source, summary)

    # Try full text
    if full_text_path and os.path.isfile(full_text_path):
        with open(full_text_path, "r", encoding="utf-8", errors="ignore") as f:
            full_text = f.read()

        token_count = count_tokens(full_text)

        if token_count <= max_tokens:
            return _format_source_context(source, full_text)

        # Full text is too long — use simple truncation
        # Take intro/abstract portion + conclusion portion to stay within budget
        char_budget = max_tokens * 3  # rough token-to-char
        if len(full_text) > char_budget:
            first = full_text[:int(char_budget * 0.6)]
            last = full_text[-int(char_budget * 0.3):]
            full_text = first + "\n\n[...middle sections omitted...]\n\n" + last
        return _format_source_context(source, full_text)

    # Abstract-only fallback
    content = abstract
    if tldr:
        content += f"\n\nTLDR: {tldr}"

    return _format_source_context(source, content, abstract_only=True)


def _extract_relevant_excerpts(
    full_text: str,
    section_key: str,
    topic: str,
    max_tokens: int,
) -> str:
    """
    Use Claude to extract the most relevant portions of a paper
    for a specific thesis section.
    """
    # Truncate input to fit in Claude's context window
    # Leave room for the prompt and response
    input_budget = 150_000  # tokens for the paper text
    if count_tokens(full_text) > input_budget:
        # Rough truncation: take first ~70% and last ~30%
        chars = input_budget * 3  # rough token-to-char conversion
        first_part = full_text[:int(chars * 0.7)]
        last_part = full_text[-int(chars * 0.3):]
        full_text = first_part + "\n\n[...middle sections omitted...]\n\n" + last_part

    prompt = f"""Extract the sections and paragraphs from this academic paper that are
most relevant to writing about "{section_key}" in a thesis about "{topic}".

Include:
- Exact quotes and key data points with their context
- Methodology details if relevant to this section
- Results and findings that support or challenge the topic
- Author conclusions related to this section

Keep your extraction under {max_tokens} tokens. Include section headers
from the original paper to maintain context.

PAPER:
{full_text}
"""

    excerpt = call_claude(prompt, max_tokens=min(max_tokens, 8192))
    return excerpt


def _format_source_context(source: dict, content: str, abstract_only: bool = False) -> str:
    """Format a source's content for inclusion in a generation prompt."""
    title = source.get("title", "Untitled")
    year = source.get("year", "")
    doi = source.get("doi", "")
    tag = "[ABSTRACT ONLY]" if abstract_only else "[FULL TEXT]"

    return f"""--- SOURCE {tag} ---
Title: {title}
Year: {year}
DOI: {doi}
Content:
{content}
--- END SOURCE ---"""
