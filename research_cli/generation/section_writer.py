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


def _expand_short_section(
    draft: str,
    topic: str,
    section_title: str,
    target_words: int,
    current_words: int,
) -> str:
    """Ask LLM to expand a short section while preserving existing content and citations."""
    prompt = f"""The following thesis section is too short ({current_words} words, target: {target_words}).
Expand it to approximately {target_words} words while:
1. Keeping ALL existing content and citations intact — do not remove or change any citation strings.
2. Adding more analysis, explanation, and connections between ideas.
3. Elaborating on key points with more detail from the cited sources.
4. Maintaining formal, third-person academic prose.
5. Including the section heading as a markdown header.

**Topic:** {topic}
**Section:** {section_title}

**Current draft to expand:**
{draft}
"""
    return call_claude(prompt, max_tokens=4096, temperature=0.3)


def _get_previous_section_context(sections: list[dict], current_index: int) -> dict:
    """Get structured context from the previous section for transition coherence.

    Returns dict with:
        title: previous section title
        opening: first non-heading paragraph (up to 500 chars)
        closing: last 1500 chars of the section
    """
    if current_index <= 0:
        return {}
    prev = sections[current_index - 1]
    draft = prev.get("draft_content", "")
    if not draft:
        return {}

    title = prev.get("section_title", "")
    lines = draft.split("\n")

    # Find first non-heading, non-empty paragraph
    opening = ""
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            opening = stripped[:500]
            break

    return {
        "title": title,
        "opening": opening,
        "closing": draft[-1500:],
    }


def _build_research_context(meta: dict | None) -> str:
    """Build a research context block for section writing prompts."""
    if not meta:
        return ""
    from research_cli.generation.planner import _build_metadata_block
    block = _build_metadata_block(meta)
    return f"\n{block}\n" if block else ""


def write_section(
    topic: str,
    section: dict,
    sources: list[dict],
    citation_map: dict[int, str],
    previous_context: dict | None = None,
    meta: dict | None = None,
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
    previous_context : dict or None
        Structured context from previous section (title, opening, closing).
    meta : dict or None
        Project metadata (variables, methodology, population).

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
    if previous_context:
        prev_title = previous_context.get("title", "")
        prev_opening = previous_context.get("opening", "")
        prev_closing = previous_context.get("closing", "")
        transition_note = f"""
**Previous section:** {prev_title}
**Previous section opened with:** {prev_opening}
**Previous section ended with:** ...{prev_closing}

TRANSITION REQUIREMENT: Your opening paragraph MUST connect to the previous section's content.
Use transitional phrases such as "Building on the ... discussed above", "Having established ..., this section turns to",
"While the previous section examined ..., the focus now shifts to", etc.
Do NOT repeat content from the previous section — only reference it to create a bridge.
"""

    # Build research context from metadata
    research_context = _build_research_context(meta)

    # Language instruction
    lang = (meta or {}).get("language", "en")
    lang_rule = "\n9. Write ALL prose in Spanish." if lang == "es" else ""

    prompt = f"""Write the following section of an academic thesis paper.

**Topic:** {topic}
**Section:** {section_title}
{research_context}
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
8. Write substantive paragraphs, not bullet points.{lang_rule}
"""

    result = call_claude(prompt, max_tokens=4096, temperature=0.3)
    return result


def write_all_sections(
    project_name: str,
    topic: str,
    citation_map: dict[int, str],
    meta: dict | None = None,
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

        # Formulaic sections bypass the LLM entirely
        from research_cli.generation.formulaic import is_formulaic, generate_formulaic
        from research_cli.generation.antecedentes import is_antecedentes, generate_antecedentes
        from research_cli.generation.marco_teorico import is_marco_teorico, generate_marco_teorico
        from research_cli.generation.methodology import is_methodology_boilerplate, generate_methodology
        from research_cli.generation.matriz import is_matriz, generate_matriz

        if is_formulaic(section_key):
            draft = generate_formulaic(section_key, topic, meta)
            print(f"    Generated formulaically ({len(draft.split())} words)")
        elif is_antecedentes(section_key):
            sources = get_sources_for_section(project_name, section_key)
            draft = generate_antecedentes(section_key, topic, meta or {}, sources, citation_map)
            print(f"    Generated antecedentes ({len(draft.split())} words, {len(sources)} sources)")
        elif is_marco_teorico(section_key):
            sources = get_sources_for_section(project_name, section_key)
            draft = generate_marco_teorico(section_key, topic, meta or {}, sources, citation_map)
            print(f"    Generated marco teórico ({len(draft.split())} words, {len(sources)} sources)")
        elif is_methodology_boilerplate(section_key):
            sources = get_sources_for_section(project_name, section_key)
            draft = generate_methodology(section_key, topic, meta or {}, sources, citation_map)
            print(f"    Generated methodology ({len(draft.split())} words)")
        elif is_matriz(section_key):
            draft = generate_matriz(section_key, topic, meta or {})
            print(f"    Generated matriz de consistencia")
        else:
            # Get sources assigned to this section
            sources = get_sources_for_section(project_name, section_key)

            # Get previous section context for coherence
            prev_context = _get_previous_section_context(written_sections, len(written_sections))

            # Generate the section
            draft = write_section(
                topic=topic,
                section=section,
                sources=sources,
                citation_map=citation_map,
                previous_context=prev_context,
                meta=meta,
            )

            # Check word count — expand if too short
            word_count = len(draft.split())
            if word_count < 400:
                print(f"    Section too short ({word_count} words), expanding...")
                time.sleep(15)  # rate limit pause
                draft = _expand_short_section(
                    draft, topic, section.get("section_title", ""),
                    target_words=800, current_words=word_count,
                )
                new_wc = len(draft.split())
                print(f"    Expanded: {word_count} → {new_wc} words")

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
