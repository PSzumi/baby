"""
planteamiento.py — Planteamiento del Problema section for USIL thesis.

Generates section 1.1.1 with a global→LATAM→Peru funnel structure:
  - 2 paragraphs per geographic level with statistics/citations
  - Problem statement connecting both research variables
  - Uses meta["location"] for local context level
"""

from research_cli.llm_client import call_claude, count_tokens
from research_cli.content.summarizer import prepare_source_for_context


PLANTEAMIENTO_SECTIONS = {"planteamiento_problema"}


def is_planteamiento(section_key: str) -> bool:
    """Return True if section_key is the planteamiento section."""
    return section_key in PLANTEAMIENTO_SECTIONS


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
            source, section_key="planteamiento_problema", topic=topic
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


def generate_planteamiento(
    section_key: str,
    topic: str,
    meta: dict,
    sources: list[dict],
    citation_map: dict[int, str],
) -> str:
    """Generate the Planteamiento del Problema section.

    Returns formatted markdown (~800-1000 words) with geographic funnel.
    """
    from research_cli.generation.planner import (
        _parse_meta_variable,
        _build_metadata_block,
    )

    meta_block = _build_metadata_block(meta)
    v1 = _parse_meta_variable(meta.get("variable_1", ""))
    v2 = _parse_meta_variable(meta.get("variable_2", ""))
    v1_name = v1.get("name") or "Variable 1"
    v2_name = v2.get("name") or "Variable 2"
    location = meta.get("location", "Perú")
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

    prompt = f"""Redacta la sección "Planteamiento del Problema" (1.1.1) de una tesis académica USIL.

**Tema:** {topic}
{meta_block}
{source_block}
**Estructura requerida (embudo geográfico):**

1. **Nivel mundial** (2 párrafos): Presenta la problemática de {v1_name} y {v2_name} a nivel global. Incluye estadísticas internacionales, datos de organismos como OMS, UNESCO, OCDE u otras fuentes. Describe cómo afecta este problema en diferentes contextos.

2. **Nivel Latinoamérica** (2 párrafos): Describe la situación en América Latina. Incluye datos regionales, estudios comparativos entre países de la región, cifras de organismos regionales.

3. **Nivel local — {location}** (2 párrafos): Presenta la problemática específica en {location}. Incluye estadísticas nacionales, datos del INEI, MINEDU u organismos locales relevantes. Relaciona directamente con {population}.

4. **Enunciado del problema** (1 párrafo): Conecta ambas variables ({v1_name} y {v2_name}) y plantea explícitamente el problema de investigación. Justifica por qué es necesario investigar esta relación en {population}.

**Formato:**
## Planteamiento del Problema

[contenido]

**REGLAS:**
1. Extensión: 800-1000 palabras.
2. Español formal académico, tercera persona.
3. Usa las cadenas de citación proporcionadas si hay fuentes disponibles.
4. NO fabricar datos, estadísticas o cifras que no estén en las fuentes.
5. Si no hay datos para un nivel geográfico, indica "[Se requieren datos de...]".
6. Incluye el encabezado como heading markdown (##).
7. Escribe párrafos sustantivos, no viñetas.
"""

    return call_claude(prompt, max_tokens=4096, temperature=0.3)
