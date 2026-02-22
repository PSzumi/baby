"""
introduccion.py — Introducción section for USIL thesis.

Generates a multi-paragraph introduction (~600-800 words) covering:
  - Research context and relevance
  - Variable importance
  - Sample description
  - Study contribution
  - Chapter structure overview
"""

from research_cli.llm_client import call_claude, count_tokens
from research_cli.content.summarizer import prepare_source_for_context


INTRODUCCION_SECTIONS = {"introduccion"}


def is_introduccion(section_key: str) -> bool:
    """Return True if section_key is the introduccion section."""
    return section_key in INTRODUCCION_SECTIONS


def _prepare_sources_text(
    sources: list[dict],
    topic: str,
    citation_map: dict[int, str],
    max_total_tokens: int = 5000,
) -> tuple[str, str]:
    """Prepare source material and citation instructions, budget-aware."""
    source_blocks = []
    citation_lines = []
    current_tokens = 0

    for source in sources:
        sid = source["id"]
        cite_str = citation_map.get(sid, f"(Source {sid})")
        citation_lines.append(f"  Source ID {sid}: Cite as {cite_str}")

        block = prepare_source_for_context(
            source, section_key="introduccion", topic=topic
        )
        block_tokens = count_tokens(block)

        if current_tokens + block_tokens > max_total_tokens:
            remaining = max_total_tokens - current_tokens
            if remaining > 200:
                char_limit = remaining * 3
                source_blocks.append(block[:char_limit] + "\n[...truncated...]")
            break

        source_blocks.append(block)
        current_tokens += block_tokens

    return "\n\n".join(source_blocks), "\n".join(citation_lines)


def generate_introduccion(
    section_key: str,
    topic: str,
    meta: dict,
    sources: list[dict],
    citation_map: dict[int, str],
) -> str:
    """Generate the Introducción section.

    Returns formatted markdown (~600-800 words).
    """
    from research_cli.generation.planner import (
        _parse_meta_variable,
        _parse_meta_methodology,
        _build_metadata_block,
    )

    meta_block = _build_metadata_block(meta)
    v1 = _parse_meta_variable(meta.get("variable_1", ""))
    v2 = _parse_meta_variable(meta.get("variable_2", ""))
    v1_name = v1.get("name") or "Variable 1"
    v2_name = v2.get("name") or "Variable 2"
    population = meta.get("population", "la población estudiada")

    if sources:
        sources_text, cite_instructions = _prepare_sources_text(
            sources, topic, citation_map
        )
        source_block = f"""
**Instrucciones de citación — usa estas cadenas EXACTAS:**
{cite_instructions}

**Material de las fuentes (tus ÚNICOS datos — no inventes afirmaciones):**

{sources_text}
"""
    else:
        source_block = ""

    prompt = f"""Redacta la sección de Introducción de una tesis académica USIL.

**Tema:** {topic}
{meta_block}
{source_block}
**Estructura requerida:**
1. **Contexto general** (1-2 párrafos): Presenta la problemática general del tema, su relevancia actual a nivel mundial y en el contexto local. Incluye estadísticas o datos de las fuentes.
2. **Importancia de las variables** (1-2 párrafos): Explica la importancia de estudiar {v1_name} y {v2_name}, y la relación entre ambas.
3. **Descripción de la muestra** (1 párrafo): Describe brevemente a {population} y por qué es relevante estudiar este grupo.
4. **Contribución del estudio** (1 párrafo): Explica qué aporta esta investigación al campo de conocimiento.
5. **Estructura de la tesis** (1 párrafo): Describe brevemente el contenido de cada capítulo:
   - Capítulo 1: Problema de investigación, marco referencial, objetivos e hipótesis.
   - Capítulo 2: Método (tipo, diseño, variables, muestra, instrumentos, procedimiento).
   - Capítulo 3: Resultados, discusión, conclusiones y recomendaciones.

**Formato:**
# Introducción

[contenido]

**REGLAS:**
1. Extensión: 600-800 palabras.
2. Español formal académico, tercera persona.
3. Usa las cadenas de citación proporcionadas si hay fuentes disponibles.
4. NO fabricar datos ni estadísticas que no estén en las fuentes.
5. Incluye el encabezado "# Introducción" como heading markdown.
6. Escribe párrafos sustantivos, no viñetas.
"""

    return call_claude(prompt, max_tokens=4096, temperature=0.3)
