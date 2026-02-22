"""
planner.py — Section planning with source allocation.

Uses Claude to decompose the thesis outline into a structured section plan,
mapping specific sources to specific sections based on relevance.

The plan is stored in the sections table and source_sections table.
"""

import json

from research_cli.llm_client import call_claude_json
from research_cli.database import (
    save_section,
    save_source_section,
    get_current_version,
)


# Default academic outline used when no template is provided
DEFAULT_OUTLINE = """
I. Introduction
   A. Background and Context
   B. Problem Statement
   C. Research Objectives
   D. Significance of the Study

II. Literature Review
   A. Global Perspectives
   B. Regional / Local Perspectives
   C. Theoretical Framework
   D. Research Gap

III. Methodology
   A. Research Design
   B. Data Sources
   C. Analytical Approach

IV. Findings and Analysis
   A. Key Findings from Global Literature
   B. Key Findings from Local/Regional Literature
   C. Comparative Analysis

V. Discussion
   A. Interpretation of Findings
   B. Implications
   C. Limitations

VI. Conclusion and Recommendations

VII. References
""".strip()


def plan_sections(
    project_name: str,
    topic: str,
    sources: list[dict],
    outline: str = "",
) -> list[dict]:
    """
    Use Claude to create a structured section plan.

    Each section gets assigned specific sources from the pool.
    The plan is stored in the database.

    Returns the list of section plans as dicts.
    """
    if not outline:
        outline = DEFAULT_OUTLINE

    # Build a compact source summary table for Claude
    source_table = []
    for s in sources:
        abstract_preview = (s.get("abstract") or "")[:200]
        source_table.append(
            f"  ID={s['id']}: \"{s.get('title', 'Untitled')}\" "
            f"({s.get('year', '?')}) — {abstract_preview}..."
        )
    sources_text = "\n".join(source_table)

    prompt = f"""You are planning the structure of an academic thesis paper.

**Topic:** {topic}

**Outline Template:**
{outline}

**Available Sources (ID, Title, Year, Abstract preview):**
{sources_text}

Create a section plan as a JSON array. For each section:
- "section_key": a short snake_case identifier (e.g., "introduction", "lit_review_global", "methodology")
- "section_title": the full section heading (e.g., "I. Introduction")
- "order_index": integer ordering (0, 1, 2, ...)
- "source_ids": array of source IDs (from the list above) most relevant to this section (3-8 per section)
- "target_word_count": recommended word count for this section
- "key_points": array of 3-5 specific points to cover, grounded in the assigned sources

Rules:
- The References section should have section_key "references" with an empty source_ids array.
- Each source should appear in at least one section's source_ids.
- Literature review sections should have the most sources (6-8 each).
- Introduction and conclusion can share sources with other sections.
- Do NOT include sources that are irrelevant to a section.

Return ONLY the JSON array.
"""

    plans = call_claude_json(prompt, max_tokens=4096)

    # Validate and store
    version = get_current_version(project_name)

    for plan in plans:
        section_key = plan.get("section_key", "")
        if not section_key:
            continue

        # Save section plan
        save_section(
            project_name,
            version=version,
            section_key=section_key,
            section_title=plan.get("section_title", section_key),
            order_index=plan.get("order_index", 0),
            scaffold_content=json.dumps(plan.get("key_points", [])),
            status="planned",
        )

        # Save source-section mappings
        for i, source_id in enumerate(plan.get("source_ids", [])):
            relevance = 1.0 - (i * 0.1)  # decreasing relevance by order
            save_source_section(
                project_name,
                source_id=source_id,
                section_key=section_key,
                relevance=max(relevance, 0.1),
            )

    print(f"  Planned {len(plans)} sections with source assignments")
    return plans


def generate_scaffold(
    project_name: str,
    topic: str,
    section_plans: list[dict],
    sources: list[dict],
    citation_map: dict[int, str],
) -> str:
    """
    Generate the scaffold (detailed outline with bullet points and citations)
    for all sections.

    Returns the complete scaffold as markdown.
    """
    from research_cli.llm_client import call_claude

    scaffold_parts = []
    sources_by_id = {s["id"]: s for s in sources}

    for plan in section_plans:
        section_key = plan.get("section_key", "")
        section_title = plan.get("section_title", section_key)
        key_points = plan.get("key_points", [])
        source_ids = plan.get("source_ids", [])

        # Skip references section
        if section_key == "references":
            scaffold_parts.append(f"\n# {section_title}\n\n[Auto-generated from bibliography]\n")
            continue

        # Gather source snippets for this section
        section_sources = []
        for sid in source_ids:
            s = sources_by_id.get(sid)
            if s:
                cite = citation_map.get(sid, f"(Source {sid})")
                section_sources.append(
                    f"- [{cite}] \"{s.get('title', '')}\": {(s.get('abstract') or '')[:300]}"
                )

        prompt = f"""Generate detailed scaffold bullet points for this thesis section.

**Topic:** {topic}
**Section:** {section_title}

**Key points to cover:**
{json.dumps(key_points, indent=2)}

**Sources assigned to this section (use ONLY these, cite with the exact strings shown):**
{chr(10).join(section_sources)}

Rules:
1. Write 5-10 detailed bullet points per subsection.
2. Each bullet should reference a specific source using the EXACT citation string shown.
3. Map which findings come from which sources.
4. Note agreements and disagreements between sources.
5. Mark any gaps with [NEEDS MORE DATA].
6. Output in markdown with the section heading.
"""

        section_scaffold = call_claude(prompt, max_tokens=2048)
        scaffold_parts.append(section_scaffold)

    return "\n\n".join(scaffold_parts)
