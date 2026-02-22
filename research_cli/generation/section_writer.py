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


# Section keys that never call the LLM — no rate-limit pause needed
_NO_LLM_SECTIONS = {
    "front_dedicatoria",
    "front_agradecimiento",
    # front_resumen and front_abstract DO use LLM
}

# Sections deferred to end of generation (need body context)
_DEFERRED_SECTIONS = {"front_resumen", "front_abstract"}


def _is_no_llm_section(section_key: str) -> bool:
    """Return True if this section never calls the LLM."""
    from research_cli.generation.formulaic import is_formulaic
    from research_cli.generation.placeholders import is_placeholder
    from research_cli.generation.matriz import is_matriz
    return (
        section_key in _NO_LLM_SECTIONS
        or is_formulaic(section_key)
        or is_placeholder(section_key)
        or is_matriz(section_key)
    )


def _generate_section(
    section_key: str,
    section: dict,
    project_name: str,
    topic: str,
    meta: dict | None,
    citation_map: dict[int, str],
    written_sections: list[dict],
    body_summary: str = "",
) -> tuple[str, bool]:
    """Generate a single section's draft.

    Returns (draft_text, used_llm).
    """
    from research_cli.generation.formulaic import is_formulaic, generate_formulaic
    from research_cli.generation.front_matter import is_front_matter
    from research_cli.generation.front_matter import generate_front_matter
    from research_cli.generation.introduccion import is_introduccion, generate_introduccion
    from research_cli.generation.planteamiento import is_planteamiento, generate_planteamiento
    from research_cli.generation.justificacion import is_justificacion, generate_justificacion
    from research_cli.generation.antecedentes import is_antecedentes, generate_antecedentes
    from research_cli.generation.marco_teorico import is_marco_teorico, generate_marco_teorico
    from research_cli.generation.methodology import is_methodology_boilerplate, generate_methodology
    from research_cli.generation.matriz import is_matriz, generate_matriz
    from research_cli.generation.placeholders import is_placeholder, generate_placeholder

    used_llm = False

    if is_formulaic(section_key):
        draft = generate_formulaic(section_key, topic, meta)
        print(f"    Generated formulaically ({len(draft.split())} words)")
    elif section_key in _DEFERRED_SECTIONS:
        # Resumen / Abstract — generated with body context
        draft = _generate_deferred_front_matter(
            section_key, topic, meta or {}, body_summary
        )
        used_llm = True
        print(f"    Generated front matter with body context ({len(draft.split())} words)")
    elif is_front_matter(section_key):
        draft = generate_front_matter(section_key, topic, meta or {})
        # dedicatoria/agradecimiento are templates, resumen/abstract already handled above
        used_llm = section_key not in _NO_LLM_SECTIONS
        print(f"    Generated front matter ({len(draft.split())} words)")
    elif is_introduccion(section_key):
        sources = get_sources_for_section(project_name, section_key)
        draft = generate_introduccion(section_key, topic, meta or {}, sources, citation_map)
        used_llm = True
        print(f"    Generated introducción ({len(draft.split())} words, {len(sources)} sources)")
    elif is_planteamiento(section_key):
        sources = get_sources_for_section(project_name, section_key)
        draft = generate_planteamiento(section_key, topic, meta or {}, sources, citation_map)
        used_llm = True
        print(f"    Generated planteamiento ({len(draft.split())} words, {len(sources)} sources)")
    elif is_justificacion(section_key):
        sources = get_sources_for_section(project_name, section_key)
        draft = generate_justificacion(section_key, topic, meta or {}, sources, citation_map)
        used_llm = True
        print(f"    Generated justificación ({len(draft.split())} words, {len(sources)} sources)")
    elif is_antecedentes(section_key):
        sources = get_sources_for_section(project_name, section_key)
        draft = generate_antecedentes(section_key, topic, meta or {}, sources, citation_map)
        used_llm = True
        print(f"    Generated antecedentes ({len(draft.split())} words, {len(sources)} sources)")
    elif is_marco_teorico(section_key):
        sources = get_sources_for_section(project_name, section_key)
        draft = generate_marco_teorico(section_key, topic, meta or {}, sources, citation_map)
        used_llm = True
        print(f"    Generated marco teórico ({len(draft.split())} words, {len(sources)} sources)")
    elif is_methodology_boilerplate(section_key):
        sources = get_sources_for_section(project_name, section_key)
        draft = generate_methodology(section_key, topic, meta or {}, sources, citation_map)
        used_llm = True
        print(f"    Generated methodology ({len(draft.split())} words)")
    elif is_matriz(section_key):
        draft = generate_matriz(section_key, topic, meta or {})
        print(f"    Generated matriz de consistencia")
    elif is_placeholder(section_key):
        draft = generate_placeholder(section_key, topic, meta or {})
        print(f"    Generated placeholder ({len(draft.split())} words)")
    else:
        # Generic LLM writer (fallback)
        sources = get_sources_for_section(project_name, section_key)
        prev_context = _get_previous_section_context(written_sections, len(written_sections))
        draft = write_section(
            topic=topic,
            section=section,
            sources=sources,
            citation_map=citation_map,
            previous_context=prev_context,
            meta=meta,
        )
        used_llm = True

        # Check word count — expand if too short
        word_count = len(draft.split())
        if word_count < 400:
            print(f"    Section too short ({word_count} words), expanding...")
            time.sleep(15)
            draft = _expand_short_section(
                draft, topic, section.get("section_title", ""),
                target_words=800, current_words=word_count,
            )
            new_wc = len(draft.split())
            print(f"    Expanded: {word_count} → {new_wc} words")

    return draft, used_llm


def _generate_deferred_front_matter(
    section_key: str,
    topic: str,
    meta: dict,
    body_summary: str,
) -> str:
    """Generate Resumen or Abstract with context from the completed thesis body."""
    from research_cli.generation.planner import _build_metadata_block

    meta_block = _build_metadata_block(meta)

    if section_key == "front_resumen":
        prompt = f"""Redacta el Resumen de una tesis académica USIL.

**Tema:** {topic}
{meta_block}

**Resumen del contenido de la tesis (secciones ya redactadas):**
{body_summary}

**Estructura requerida (un solo párrafo):**
1. Contexto y propósito de la investigación (2-3 oraciones)
2. Metodología empleada: tipo, diseño, muestra, instrumento (2-3 oraciones)
3. Principales resultados esperados (1-2 oraciones)
4. Conclusión general (1 oración)

**Formato final:**
# Resumen

[párrafo de ~250 palabras]

**Palabras clave:** [5-6 palabras clave separadas por comas]

**REGLAS:**
- Extensión: 200-300 palabras.
- Español formal académico, tercera persona.
- NO incluir citas bibliográficas en el resumen.
- Basa el contenido en las secciones ya redactadas.
- Terminar con "Palabras clave:" en línea aparte.
"""
    else:  # front_abstract
        prompt = f"""Write the Abstract for a USIL academic thesis (English translation of the Resumen).

**Topic:** {topic}
{meta_block}

**Summary of thesis content (sections already drafted):**
{body_summary}

**Required structure (single paragraph):**
1. Context and research purpose (2-3 sentences)
2. Methodology: type, design, sample, instrument (2-3 sentences)
3. Expected main results (1-2 sentences)
4. General conclusion (1 sentence)

**Final format:**
# Abstract

[paragraph of ~250 words]

**Keywords:** [5-6 keywords separated by commas]

**RULES:**
- Length: 200-300 words.
- Formal academic English, third person.
- Do NOT include bibliographic citations.
- Base the content on the sections already drafted.
- End with "Keywords:" on a separate line.
"""

    from research_cli.llm_client import call_claude
    return call_claude(prompt, max_tokens=1500, temperature=0.3)


def _build_body_summary(written_sections: list[dict]) -> str:
    """Build a compact summary of all drafted body sections for Resumen/Abstract context."""
    parts = []
    for section in written_sections:
        key = section.get("section_key", "")
        title = section.get("section_title", key)
        draft = section.get("draft_content", "")
        if not draft or key in ("front_dedicatoria", "front_agradecimiento"):
            continue
        # Take first 300 chars of content (skip heading lines)
        lines = draft.split("\n")
        content_lines = [l for l in lines if l.strip() and not l.strip().startswith("#")]
        preview = " ".join(content_lines)[:300]
        wc = len(draft.split())
        parts.append(f"- **{title}** ({wc} words): {preview}...")
    return "\n".join(parts)


def _apply_heading_numbers(content: str, section_key: str) -> str:
    """Prefix the first markdown heading in content with its USIL number, if mapped."""
    from research_cli.generation.planner import HEADING_NUMBERS

    prefix = HEADING_NUMBERS.get(section_key)
    if not prefix:
        return content

    import re
    # Match the first heading line (# or ## or ###)
    def _add_prefix(m: re.Match) -> str:
        hashes = m.group(1)
        text = m.group(2).strip()
        # Don't double-number if already starts with the prefix
        if text.startswith(prefix):
            return m.group(0)
        return f"{hashes} {prefix} {text}"

    return re.sub(r"^(#{1,4})\s+(.*)", _add_prefix, content, count=1, flags=re.MULTILINE)


def write_all_sections(
    project_name: str,
    topic: str,
    citation_map: dict[int, str],
    meta: dict | None = None,
) -> str:
    """
    Orchestrate writing all sections in order.

    Resumen and Abstract are deferred to the end so they can summarize
    the completed thesis body. Non-LLM sections skip the rate-limit pause.

    Returns the complete assembled draft.
    """
    version = get_current_version(project_name)
    sections = get_sections(project_name, version)

    # Get bibliography entries for validation
    bib_entries = get_all_bib_entries(project_name)

    written_sections = []
    deferred_sections = []  # (index, section) tuples for Resumen/Abstract

    # --- Pass 1: generate all sections except deferred ones ---
    for i, section in enumerate(sections):
        section_key = section.get("section_key", "")

        # Skip references section — generated programmatically
        if section_key == "references":
            continue

        # Defer Resumen/Abstract to after body is complete
        if section_key in _DEFERRED_SECTIONS:
            if section.get("status") == "drafted" and section.get("draft_content"):
                written_sections.append(section)
                print(f"  [{i+1}/{len(sections)}] {section.get('section_title', '')} — already drafted")
            else:
                deferred_sections.append((i, section))
                print(f"  [{i+1}/{len(sections)}] {section.get('section_title', '')} — deferred to end")
            continue

        # Skip already-drafted sections
        if section.get("status") == "drafted" and section.get("draft_content"):
            written_sections.append(section)
            print(f"  [{i+1}/{len(sections)}] {section.get('section_title', '')} — already drafted")
            continue

        print(f"  [{i+1}/{len(sections)}] Writing: {section.get('section_title', '')}...")

        draft, used_llm = _generate_section(
            section_key, section, project_name, topic,
            meta, citation_map, written_sections,
        )

        # Validate citations
        report = validate_draft(draft, bib_entries)
        if report.orphan_citations:
            print(f"    [WARN] {len(report.orphan_citations)} orphan citations in this section")

        # Save to database
        update_section_draft(project_name, version, section_key, draft)
        section["draft_content"] = draft
        section["status"] = "drafted"
        written_sections.append(section)

        # Rate limit pause only after LLM calls
        if used_llm:
            time.sleep(15)

    # --- Pass 2: generate deferred sections (Resumen/Abstract) with body context ---
    if deferred_sections:
        body_summary = _build_body_summary(written_sections)
        print(f"\n  Generating deferred front matter with {len(written_sections)} body sections as context...")

        for i, section in deferred_sections:
            section_key = section.get("section_key", "")
            print(f"  [{i+1}/{len(sections)}] Writing: {section.get('section_title', '')}...")

            draft, used_llm = _generate_section(
                section_key, section, project_name, topic,
                meta, citation_map, written_sections,
                body_summary=body_summary,
            )

            report = validate_draft(draft, bib_entries)
            if report.orphan_citations:
                print(f"    [WARN] {len(report.orphan_citations)} orphan citations in this section")

            update_section_draft(project_name, version, section_key, draft)
            section["draft_content"] = draft
            section["status"] = "drafted"
            written_sections.append(section)

            if used_llm:
                time.sleep(15)

    # --- Sort written sections back into canonical order for assembly ---
    section_order = {s.get("section_key", ""): s.get("order_index", 999) for s in sections}
    written_sections.sort(key=lambda s: section_order.get(s.get("section_key", ""), 999))

    # Assemble the complete draft
    from research_cli.generation.planner import HEADING_NUMBERS
    draft_parts = []
    for s in written_sections:
        content = s.get("draft_content", "")
        if not content:
            continue
        key = s.get("section_key", "")
        content = _apply_heading_numbers(content, key)
        draft_parts.append(content)

    return "\n\n---\n\n".join(draft_parts)
