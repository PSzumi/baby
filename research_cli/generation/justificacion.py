"""
justificacion.py — Justificación de la Investigación section for USIL thesis.

Generates section 1.1.3 with 4 subsections (~600-800 words total):
  - Teórica (1-3 paragraphs)
  - Metodológica (1-2 paragraphs)
  - Práctica (1-2 paragraphs)
  - Social (1-2 paragraphs)
"""

from research_cli.llm_client import call_claude, count_tokens
from research_cli.content.summarizer import prepare_source_for_context


JUSTIFICACION_SECTIONS = {"justificacion"}


def is_justificacion(section_key: str) -> bool:
    """Return True if section_key is the justificacion section."""
    return section_key in JUSTIFICACION_SECTIONS


def _prepare_sources_text(
    sources: list[dict],
    topic: str,
    citation_map: dict[int, str],
    max_total_tokens: int = 3000,
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
            source, section_key="justificacion", topic=topic
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


def generate_justificacion(
    section_key: str,
    topic: str,
    meta: dict,
    sources: list[dict],
    citation_map: dict[int, str],
) -> str:
    """Generate the Justificación de la Investigación section.

    Returns formatted markdown (~600-800 words).
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

    prompt = f"""Redacta la sección "Justificación de la Investigación" (1.1.3) de una tesis académica USIL.

**Tema:** {topic}
{meta_block}
{source_block}
**Estructura requerida (4 subsecciones):**

### Justificación teórica
(1-3 párrafos) Explica cómo esta investigación contribuye al conocimiento teórico sobre {v1_name} y {v2_name}. Identifica vacíos en la literatura existente que esta investigación busca llenar. Menciona teorías o modelos que se fortalecen o cuestionan.

### Justificación metodológica
(1-2 párrafos) Describe cómo la metodología utilizada aporta al campo de investigación. Explica la utilidad de los instrumentos de medición desarrollados o adaptados para futuras investigaciones.

### Justificación práctica
(1-2 párrafos) Detalla las aplicaciones prácticas de los resultados de esta investigación. Explica cómo beneficia a {population} y a las instituciones o contextos involucrados.

### Justificación social
(1-2 párrafos) Explica la relevancia social de investigar la relación entre {v1_name} y {v2_name}. Describe cómo los hallazgos pueden impactar positivamente en la sociedad.

**Formato:**
## Justificación de la Investigación

[contenido con ### subsecciones]

**REGLAS:**
1. Extensión total: 600-800 palabras.
2. Español formal académico, tercera persona.
3. Usa las cadenas de citación proporcionadas si hay fuentes disponibles.
4. NO fabricar datos ni estadísticas que no estén en las fuentes.
5. Incluye el encabezado "## Justificación de la Investigación" como heading markdown.
6. Escribe párrafos sustantivos, no viñetas.
"""

    return call_claude(prompt, max_tokens=4096, temperature=0.3)
