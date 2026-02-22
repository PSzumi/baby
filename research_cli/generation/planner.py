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


def _parse_meta_variable(raw: str) -> dict:
    """Parse a JSON-encoded variable string, returning {'name': ..., 'dimensions': [...]}."""
    if not raw:
        return {"name": "", "dimensions": []}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {"name": raw, "dimensions": []}


def _parse_meta_methodology(raw: str) -> dict:
    """Parse JSON-encoded methodology string."""
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


def _build_metadata_block(meta: dict) -> str:
    """Build a metadata context block for LLM prompts from project metadata."""
    if not meta:
        return ""

    parts = []
    var1 = _parse_meta_variable(meta.get("variable_1", ""))
    var2 = _parse_meta_variable(meta.get("variable_2", ""))

    if var1.get("name") or var2.get("name"):
        parts.append("**Research Variables:**")
        if var1.get("name"):
            dims = ", ".join(var1["dimensions"]) if var1["dimensions"] else "not specified"
            parts.append(f"- Variable 1 (independent): {var1['name']} — Dimensions: {dims}")
        if var2.get("name"):
            dims = ", ".join(var2["dimensions"]) if var2["dimensions"] else "not specified"
            parts.append(f"- Variable 2 (dependent): {var2['name']} — Dimensions: {dims}")

    population = meta.get("population", "")
    if population:
        parts.append(f"**Population:** {population}")

    sample_size = meta.get("sample_size", 0)
    if sample_size:
        parts.append(f"**Sample size:** {sample_size}")

    meth = _parse_meta_methodology(meta.get("methodology", ""))
    if meth:
        parts.append(
            f"**Methodology:** {meth.get('type', '')}, {meth.get('scope', '')}, "
            f"{meth.get('design', '')}"
        )

    return "\n".join(parts)


def get_usil_outline(meta: dict | None = None) -> str:
    """Return USIL thesis outline with variable names interpolated from metadata."""
    var1 = _parse_meta_variable((meta or {}).get("variable_1", ""))
    var2 = _parse_meta_variable((meta or {}).get("variable_2", ""))
    var1_name = var1.get("name") or "Variable 1"
    var2_name = var2.get("name") or "Variable 2"

    return f"""Dedicatoria
Agradecimiento
Resumen
Abstract
Introducción
Capítulo 1
  1.1. Problema de Investigación
    1.1.1. Planteamiento del Problema
    1.1.2. Formulación del Problema
    1.1.3. Justificación de la Investigación
  1.2. Marco Referencial
    1.2.1. Antecedentes (internacionales + nacionales)
    1.2.2. Marco Teórico
      1.2.2.1. {var1_name}
      1.2.2.2. {var2_name}
  1.3. Objetivos e Hipótesis
    1.3.1. Objetivos
    1.3.2. Hipótesis
Capítulo 2
  2.1. Método
    2.1.1. Tipo de Investigación
    2.1.2. Diseño de Investigación
    2.1.3. Variables
    2.1.4. Muestra
    2.1.5. Instrumentos de Investigación
    2.1.6. Procedimientos de Recolección de Datos
Capítulo 3
  3.1. Resultados
    3.1.1. Presentación de Resultados
    3.1.2. Discusión
    3.1.3. Conclusiones
    3.1.4. Recomendaciones
Referencias Bibliográficas
Anexos"""


# ---------------------------------------------------------------------------
# Canonical section ordering — guarantees correct USIL structure regardless
# of what order_index the LLM assigns.
# ---------------------------------------------------------------------------

CANONICAL_ORDER: dict[str, int] = {
    "front_dedicatoria": 0,
    "front_agradecimiento": 1,
    "front_resumen": 2,
    "front_abstract": 3,
    "introduccion": 4,
    "planteamiento_problema": 5,
    "problem_formulation": 6,
    "justificacion": 7,
    "antecedentes_internacionales": 8,
    "antecedentes_nacionales": 9,
    "bases_teoricas_v1": 10,
    "bases_teoricas_v2": 11,
    "research_objectives": 12,
    "hypothesis": 13,
    "tipo_investigacion": 14,
    "diseno_investigacion": 15,
    "variables_def": 16,
    "muestra": 17,
    "instrumentos_investigacion": 18,
    "procedimiento_recoleccion": 19,
    "resultados_placeholder": 20,
    "discusion_placeholder": 21,
    "conclusiones_placeholder": 22,
    "recomendaciones_placeholder": 23,
    "references": 24,
    "matriz_consistencia": 25,
}


# ---------------------------------------------------------------------------
# Heading number prefixes — applied during draft assembly to produce
# USIL-compliant numbered headings (e.g. "## 1.1.1. Planteamiento del Problema").
# Keys with empty strings get no prefix (front matter, references, etc.).
# ---------------------------------------------------------------------------

HEADING_NUMBERS: dict[str, str] = {
    "front_dedicatoria": "",
    "front_agradecimiento": "",
    "front_resumen": "",
    "front_abstract": "",
    "introduccion": "",
    "planteamiento_problema": "1.1.1.",
    "problem_formulation": "1.1.2.",
    "justificacion": "1.1.3.",
    "antecedentes_internacionales": "1.2.1.",
    "antecedentes_nacionales": "1.2.1.",
    "bases_teoricas_v1": "1.2.2.",
    "bases_teoricas_v2": "1.2.2.",
    "research_objectives": "1.3.1.",
    "hypothesis": "1.3.2.",
    "tipo_investigacion": "2.1.1.",
    "diseno_investigacion": "2.1.2.",
    "variables_def": "2.1.3.",
    "muestra": "2.1.4.",
    "instrumentos_investigacion": "2.1.5.",
    "procedimiento_recoleccion": "2.1.6.",
    "resultados_placeholder": "3.1.1.",
    "discusion_placeholder": "3.1.2.",
    "conclusiones_placeholder": "3.1.3.",
    "recomendaciones_placeholder": "3.1.4.",
    "references": "",
    "matriz_consistencia": "",
}


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
    meta: dict | None = None,
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

    # Build metadata context if available
    meta_block = _build_metadata_block(meta)
    meta_section = f"\n{meta_block}\n" if meta_block else ""

    # Determine language for instructions
    lang = (meta or {}).get("language", "en")
    lang_instruction = (
        "\n- Write ALL section titles and key_points in Spanish."
        if lang == "es" else ""
    )

    # Pin USIL formulaic + antecedentes section keys for deterministic detection
    usil_keys = ""
    location = (meta or {}).get("location", "Peru")
    if lang == "es":
        usil_keys = f"""
- Use these EXACT section_keys for front matter sections (empty source_ids):
  "front_dedicatoria" for Dedicatoria
  "front_agradecimiento" for Agradecimiento
  "front_resumen" for Resumen
  "front_abstract" for Abstract
- Use this EXACT section_key for the introduction (5-8 source_ids):
  "introduccion" for Introducción
- Use these EXACT section_keys for Problema de Investigación:
  "planteamiento_problema" for 1.1.1 Planteamiento del Problema (5-8 source_ids)
  "problem_formulation" for 1.1.2 Formulación del Problema (empty source_ids — formulaic)
  "justificacion" for 1.1.3 Justificación de la Investigación (3-5 source_ids)
- Use these EXACT section_keys for antecedentes sections:
  "antecedentes_internacionales" for Antecedentes internacionales
  "antecedentes_nacionales" for Antecedentes nacionales
- Antecedentes sections need 5-8 source_ids each, classified geographically:
  Papers from {location} → antecedentes_nacionales
  All other papers → antecedentes_internacionales
  If country of origin is unclear → antecedentes_internacionales
- Use these EXACT section_keys for marco teórico sections:
  "bases_teoricas_v1" for Bases teóricas of Variable 1
  "bases_teoricas_v2" for Bases teóricas of Variable 2
- These sections need 5-8 source_ids each (sources most relevant to the variable's conceptualization).
- Use these EXACT section_keys for formulaic sections (empty source_ids):
  "research_objectives" for 1.3.1 Objetivos
  "hypothesis" for 1.3.2 Hipótesis
  "tipo_investigacion" for 2.1.1 Tipo de Investigación
  "diseno_investigacion" for 2.1.2 Diseño de Investigación
  "variables_def" for 2.1.3 Variables
  "muestra" for 2.1.4 Muestra
- Use these EXACT section_keys for methodology sections (empty source_ids):
  "instrumentos_investigacion" for 2.1.5 Instrumentos de Investigación
  "procedimiento_recoleccion" for 2.1.6 Procedimientos de Recolección de Datos
- Use these EXACT section_keys for Chapter 3 placeholders (empty source_ids):
  "resultados_placeholder" for 3.1.1 Presentación de Resultados
  "discusion_placeholder" for 3.1.2 Discusión
  "conclusiones_placeholder" for 3.1.3 Conclusiones
  "recomendaciones_placeholder" for 3.1.4 Recomendaciones
- Use this EXACT section_key for the consistency matrix:
  "matriz_consistencia" for Matriz de consistencia (placed in Anexos after References)
- This section needs an empty source_ids array (generated formulaically from metadata)."""

    prompt = f"""You are planning the structure of an academic thesis paper.

**Topic:** {topic}
{meta_section}
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
- Do NOT include sources that are irrelevant to a section.{lang_instruction}{usil_keys}

Return ONLY the JSON array.
"""

    plans = call_claude_json(prompt, max_tokens=4096)

    # --- Enforce canonical ordering ---
    # Override LLM-assigned order_index with deterministic values
    plans_by_key = {}
    for plan in plans:
        key = plan.get("section_key", "")
        if key:
            plans_by_key[key] = plan

    # Inject any missing required USIL sections (empty source_ids, default title)
    _DEFAULT_TITLES = {
        "front_dedicatoria": "Dedicatoria",
        "front_agradecimiento": "Agradecimiento",
        "front_resumen": "Resumen",
        "front_abstract": "Abstract",
        "introduccion": "Introducción",
        "planteamiento_problema": "Planteamiento del Problema",
        "problem_formulation": "Formulación del Problema",
        "justificacion": "Justificación de la Investigación",
        "antecedentes_internacionales": "Antecedentes internacionales",
        "antecedentes_nacionales": "Antecedentes nacionales",
        "bases_teoricas_v1": "Bases teóricas — Variable 1",
        "bases_teoricas_v2": "Bases teóricas — Variable 2",
        "research_objectives": "Objetivos",
        "hypothesis": "Hipótesis",
        "tipo_investigacion": "Tipo de Investigación",
        "diseno_investigacion": "Diseño de Investigación",
        "variables_def": "Variables",
        "muestra": "Muestra",
        "instrumentos_investigacion": "Instrumentos de Investigación",
        "procedimiento_recoleccion": "Procedimientos de Recolección de Datos",
        "resultados_placeholder": "Presentación de Resultados",
        "discusion_placeholder": "Discusión",
        "conclusiones_placeholder": "Conclusiones",
        "recomendaciones_placeholder": "Recomendaciones",
        "references": "Referencias Bibliográficas",
        "matriz_consistencia": "Matriz de consistencia",
    }

    if lang == "es":
        for key in CANONICAL_ORDER:
            if key not in plans_by_key:
                plans_by_key[key] = {
                    "section_key": key,
                    "section_title": _DEFAULT_TITLES.get(key, key),
                    "source_ids": [],
                    "key_points": [],
                }
                print(f"    [AUTO] Injected missing section: {key}")

    # Apply canonical order_index to all plans
    for key, plan in plans_by_key.items():
        plan["order_index"] = CANONICAL_ORDER.get(key, 999)

    # Rebuild sorted plan list
    plans = sorted(plans_by_key.values(), key=lambda p: p.get("order_index", 999))

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
    meta: dict | None = None,
) -> str:
    """
    Generate the scaffold (detailed outline with bullet points and citations)
    for all sections in a single LLM call.

    Returns the complete scaffold as markdown.
    """
    from research_cli.llm_client import call_claude

    sources_by_id = {s["id"]: s for s in sources}

    # Build combined section descriptions for one mega-prompt
    section_blocks = []
    for plan in section_plans:
        section_key = plan.get("section_key", "")
        if section_key == "references":
            continue

        section_title = plan.get("section_title", section_key)
        key_points = plan.get("key_points", [])
        source_ids = plan.get("source_ids", [])

        # Gather source snippets (truncated to 200 chars each)
        section_sources = []
        for sid in source_ids:
            s = sources_by_id.get(sid)
            if s:
                cite = citation_map.get(sid, f"(Source {sid})")
                abstract_snip = (s.get("abstract") or "")[:200]
                section_sources.append(f"  - [{cite}] \"{s.get('title', '')}\": {abstract_snip}")

        points_text = "\n".join(f"  - {p}" for p in key_points)
        sources_text = "\n".join(section_sources) if section_sources else "  (no sources assigned)"

        section_blocks.append(
            f"### {section_title}\n"
            f"Key points:\n{points_text}\n"
            f"Sources:\n{sources_text}"
        )

    combined_sections = "\n\n".join(section_blocks)

    # Build metadata context
    meta_block = _build_metadata_block(meta)
    meta_section = f"\n{meta_block}\n" if meta_block else ""

    # Language instruction
    lang = (meta or {}).get("language", "en")
    lang_rule = "\n7. Write ALL content in Spanish." if lang == "es" else ""

    prompt = f"""Generate a detailed scaffold (outline with bullet points and citations) for ALL sections of this academic thesis in one response.

**Topic:** {topic}
{meta_section}
**Sections to scaffold:**

{combined_sections}

Rules:
1. For EACH section above, write a markdown heading followed by 5-10 detailed bullet points per subsection.
2. Each bullet should reference a specific source using the EXACT citation string shown in brackets.
3. Map which findings come from which sources.
4. Note agreements and disagreements between sources.
5. Mark any gaps with [NEEDS MORE DATA].
6. Output all sections in order, each starting with a markdown heading.{lang_rule}
"""

    scaffold = call_claude(prompt, max_tokens=8192)

    # Append references placeholder
    scaffold += "\n\n# References\n\n[Auto-generated from bibliography]\n"

    return scaffold
