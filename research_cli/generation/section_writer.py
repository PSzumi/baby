"""
section_writer.py — Write thesis sections one at a time.

Each section is generated independently with:
    - Only its assigned sources (full text or summary)
    - Its scaffold bullet points
    - The tail of the previous section (for coherence)
    - A citation map with exact inline citation strings

Citations are validated per-section immediately after generation.
"""

import json
import time

from research_cli.llm_client import call_claude
from research_cli.content.summarizer import prepare_source_for_context
from research_cli.citations.validator import validate_draft, extract_inline_citations
from research_cli.database import (
    get_sections,
    get_sources_for_section,
    update_section_draft,
    get_current_version,
    get_all_bib_entries,
)


def _get_previous_section_tail(sections: list[dict], current_index: int, chars: int = 1500) -> str:
    """Get the last ~chars characters of the previous section for transition coherence."""
    if current_index <= 0:
        return ""
    prev = sections[current_index - 1]
    draft = prev.get("draft_content", "")
    if not draft:
        return ""
    return draft[-chars:]


def write_section(
    topic: str,
    section: dict,
    sources: list[dict],
    citation_map: dict[int, str],
    previous_tail: str = "",
) -> str:
    """
    Generate prose for a single thesis section.

    Parameters
    ----------
    topic : str
        The thesis topic.
    section : dict
        Section metadata from the sections table.
    sources : list[dict]
        Sources assigned to this section (from source_sections table).
    citation_map : dict[int, str]
        Mapping of source_id -> inline citation string.
    previous_tail : str
        Last ~500 words of the previous section for transitions.

    Returns
    -------
    str
        Generated section prose in markdown.
    """
    section_title = section.get("section_title", "")
    section_key = section.get("section_key", "")
    scaffold_raw = section.get("scaffold_content", "")
    target_words = 800  # default

    # Parse scaffold content
    try:
        key_points = json.loads(scaffold_raw)
        if isinstance(key_points, list):
            scaffold_text = "\n".join(f"- {p}" for p in key_points)
        else:
            scaffold_text = scaffold_raw
    except (json.JSONDecodeError, TypeError):
        scaffold_text = scaffold_raw

    # Prepare source material
    source_blocks = []
    citation_instructions = []
    for source in sources:
        sid = source["id"]
        cite_str = citation_map.get(sid, f"(Source {sid})")

        # Prepare content (full text or abstract)
        content_block = prepare_source_for_context(
            source, section_key=section_key, topic=topic
        )
        source_blocks.append(content_block)
        citation_instructions.append(
            f"  Source ID {sid}: Cite as {cite_str}"
        )

    # Budget source material to fit within model context limits
    # Groq free tier has 12K TPM — keep total prompt under ~8K tokens
    from research_cli.llm_client import count_tokens
    max_source_tokens = 5000  # leave room for prompt, scaffold, instructions
    current_tokens = 0
    trimmed_blocks = []
    for block in source_blocks:
        block_tokens = count_tokens(block)
        if current_tokens + block_tokens > max_source_tokens:
            # Truncate this block to fit remaining budget
            remaining = max_source_tokens - current_tokens
            if remaining > 200:  # only include if we have reasonable space
                char_limit = remaining * 3
                trimmed_blocks.append(block[:char_limit] + "\n[...truncated...]")
            break
        trimmed_blocks.append(block)
        current_tokens += block_tokens

    sources_text = "\n\n".join(trimmed_blocks)
    cite_instructions = "\n".join(citation_instructions)

    # Build transition context
    transition_note = ""
    if previous_tail:
        transition_note = f"""
**Previous section ended with:**
...{previous_tail}

Ensure a smooth transition from the previous section.
"""

    prompt = f"""Write the following section of an academic thesis paper.

**Topic:** {topic}
**Section:** {section_title}

**Scaffold / Key Points:**
{scaffold_text}

**Citation Instructions — use these EXACT strings when citing:**
{cite_instructions}

**Source Material (your ONLY data — do not invent any claims):**

{sources_text}
{transition_note}
**RULES:**
1. Write formal, third-person academic prose.
2. Target approximately {target_words} words.
3. Use ONLY the citation strings listed above. Do NOT invent or modify citations.
4. Every factual claim must have an inline citation.
5. Do NOT fabricate data, statistics, or findings not in the sources.
6. If the sources are insufficient for a point, write:
   "[Further research is needed to establish...]"
7. Include the section heading as a markdown header.
8. Write substantive paragraphs, not bullet points.
"""

    result = call_claude(prompt, max_tokens=4096, temperature=0.3)
    return result


def write_all_sections(
    project_name: str,
    topic: str,
    citation_map: dict[int, str],
) -> str:
    """
    Orchestrate writing all sections in order.

    Returns the complete assembled draft.
    """
    version = get_current_version(project_name)
    sections = get_sections(project_name, version)

    # Get bibliography entries for validation
    bib_entries = get_all_bib_entries(project_name)

    written_sections = []

    for i, section in enumerate(sections):
        section_key = section.get("section_key", "")

        # Skip references section — generated programmatically
        if section_key == "references":
            continue

        # Skip already-drafted sections
        if section.get("status") == "drafted" and section.get("draft_content"):
            written_sections.append(section)
            print(f"  [{i+1}/{len(sections)}] {section.get('section_title', '')} — already drafted")
            continue

        print(f"  [{i+1}/{len(sections)}] Writing: {section.get('section_title', '')}...")

        # Get sources assigned to this section
        sources = get_sources_for_section(project_name, section_key)

        # Get previous section tail for coherence
        prev_tail = _get_previous_section_tail(written_sections, len(written_sections))

        # Generate the section
        draft = write_section(
            topic=topic,
            section=section,
            sources=sources,
            citation_map=citation_map,
            previous_tail=prev_tail,
        )

        # Validate citations in this section
        report = validate_draft(draft, bib_entries)
        if report.orphan_citations:
            print(f"    [WARN] {len(report.orphan_citations)} orphan citations in this section")

        # Save to database
        update_section_draft(project_name, version, section_key, draft)
        section["draft_content"] = draft
        section["status"] = "drafted"
        written_sections.append(section)

        # Rate limit pause between sections (Groq free tier: 12K TPM)
        time.sleep(15)

    # Assemble the complete draft
    draft_parts = [s.get("draft_content", "") for s in written_sections if s.get("draft_content")]
    return "\n\n---\n\n".join(draft_parts)
