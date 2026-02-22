"""
antecedentes.py — Structured antecedentes generators for USIL thesis.

USIL theses require "Antecedentes de la investigación" sections (2.1.1
internacionales, 2.1.2 nacionales) with rigid per-paper paragraphs:

    [Author] ([Year]) en su investigación titulada "[Title]", tuvo como
    objetivo [objective]. La investigación fue de enfoque [methodology].
    Los resultados evidenciaron que [findings]. Se concluyó que [conclusions].

This is a hybrid: LLM extracts structured data from abstracts/full text,
then a template formats each paragraph deterministically.
"""

import json

from research_cli.llm_client import call_claude_json, count_tokens
from research_cli.content.summarizer import prepare_source_for_context


ANTECEDENTES_SECTIONS = {"antecedentes_internacionales", "antecedentes_nacionales"}


def is_antecedentes(section_key: str) -> bool:
    """Return True if section_key is an antecedentes section."""
    return section_key in ANTECEDENTES_SECTIONS


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_author_display(source: dict) -> str:
    """Parse authors field into display format for prose.

    Returns:
        Single author  → "Apellido"
        Two authors    → "Apellido y Apellido"
        Three or more  → "Apellido et al."
        Missing        → "Autor desconocido"
    """
    raw = source.get("authors", "")
    if not raw:
        return "Autor desconocido"

    # Try JSON list first
    names = []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            for entry in parsed:
                if isinstance(entry, dict):
                    name = entry.get("name", "")
                elif isinstance(entry, str):
                    name = entry
                else:
                    continue
                if name:
                    # Extract surname (before comma or first word)
                    surname = name.split(",")[0].strip()
                    names.append(surname)
    except (json.JSONDecodeError, TypeError):
        # Plain string — treat as single author
        surname = raw.split(",")[0].strip()
        if surname:
            names.append(surname)

    if not names:
        return "Autor desconocido"
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} y {names[1]}"
    return f"{names[0]} et al."


def _prepare_sources_for_extraction(
    sources: list[dict],
    section_key: str,
    topic: str,
    max_total_tokens: int = 5000,
) -> str:
    """Prepare source material for the LLM extraction prompt, budget-aware."""
    blocks = []
    current_tokens = 0

    for source in sources:
        block = prepare_source_for_context(
            source, section_key=section_key, topic=topic
        )
        block_tokens = count_tokens(block)

        if current_tokens + block_tokens > max_total_tokens:
            remaining = max_total_tokens - current_tokens
            if remaining > 200:
                char_limit = remaining * 3
                blocks.append(block[:char_limit] + "\n[...truncated...]")
            break

        blocks.append(block)
        current_tokens += block_tokens

    return "\n\n".join(blocks)


def _batch_extract(
    sources: list[dict],
    source_material: str,
    topic: str,
) -> dict[int, dict]:
    """Single LLM call to extract structured data from all sources.

    Returns dict mapping source_id -> {objective, methodology, findings, conclusions}.
    """
    source_ids_info = []
    for s in sources:
        source_ids_info.append(
            f"  - source_id={s['id']}: \"{s.get('title', 'Sin título')}\" "
            f"({s.get('year', 's.f.')})"
        )
    ids_text = "\n".join(source_ids_info)

    prompt = f"""Analyze the following academic source material and extract structured information for each paper.

**Topic:** {topic}

**Papers to extract from:**
{ids_text}

**Source material:**
{source_material}

For EACH paper listed above, extract:
- "source_id": the integer ID of the paper
- "objective": the main research objective (1-2 sentences, in Spanish)
- "methodology": the research approach/methodology (1 sentence, in Spanish)
- "findings": key results/findings (1-2 sentences, in Spanish)
- "conclusions": main conclusions (1-2 sentences, in Spanish)

Return a JSON array of objects. If you cannot determine a field from the available text, use null for that field.

Return ONLY the JSON array.
"""

    try:
        result = call_claude_json(prompt, max_tokens=3000)
    except Exception:
        return {}

    # Unwrap dict wrapper if present (e.g. {"papers": [...]})
    if isinstance(result, dict):
        for v in result.values():
            if isinstance(v, list):
                result = v
                break
        else:
            return {}

    if not isinstance(result, list):
        return {}

    # Build lookup by source_id
    extracted = {}
    for item in result:
        if not isinstance(item, dict):
            continue
        sid = item.get("source_id")
        if sid is not None:
            try:
                sid = int(sid)
            except (ValueError, TypeError):
                continue
            extracted[sid] = {
                "objective": item.get("objective"),
                "methodology": item.get("methodology"),
                "findings": item.get("findings"),
                "conclusions": item.get("conclusions"),
            }

    return extracted


def _format_antecedent(
    source: dict,
    extraction: dict,
    citation_map: dict[int, str],
) -> str:
    """Format a single antecedent paragraph using the USIL template."""
    sid = source["id"]
    title = source.get("title", "Sin título")
    year = source.get("year", "") or "s.f."
    author = _get_author_display(source)

    fallback = "[datos insuficientes]"
    objective = extraction.get("objective") or fallback
    methodology = extraction.get("methodology") or fallback
    findings = extraction.get("findings") or fallback
    conclusions = extraction.get("conclusions") or fallback

    cite = citation_map.get(sid, f"({author}, {year})")

    paragraph = (
        f"{author} ({year}) en su investigación titulada \"{title}\", "
        f"tuvo como objetivo {objective} "
        f"La investigación fue de enfoque {methodology} "
        f"Los resultados evidenciaron que {findings} "
        f"Se concluyó que {conclusions} "
        f"{cite}"
    )

    return paragraph


# ---------------------------------------------------------------------------
# Public dispatcher
# ---------------------------------------------------------------------------

def generate_antecedentes(
    section_key: str,
    topic: str,
    meta: dict,
    sources: list[dict],
    citation_map: dict[int, str],
) -> str:
    """Generate an antecedentes section (internacionales or nacionales).

    Returns formatted markdown with heading and one paragraph per source.
    """
    if section_key == "antecedentes_internacionales":
        heading = "## Antecedentes internacionales"
    elif section_key == "antecedentes_nacionales":
        heading = "## Antecedentes nacionales"
    else:
        heading = f"## {section_key}"

    if not sources:
        return f"{heading}\n\nNo se encontraron antecedentes para esta sección."

    # Stage 1: Prepare source material (budget-trimmed)
    source_material = _prepare_sources_for_extraction(
        sources, section_key=section_key, topic=topic
    )

    # Stage 2: Batch LLM extraction
    extracted = _batch_extract(sources, source_material, topic)

    # Stage 3: Template formatting
    paragraphs = []
    for source in sources:
        sid = source["id"]
        extraction = extracted.get(sid, {})
        paragraph = _format_antecedent(source, extraction, citation_map)
        paragraphs.append(paragraph)

    body = "\n\n".join(paragraphs)
    return f"{heading}\n\n{body}"
