"""
marco_teorico.py — Bases teóricas and definición de términos for USIL thesis.

Generates Chapter II sections 2.2 and 2.3:
  2.2.1 Bases teóricas — Variable 1 (conceptualization organized by dimension)
  2.2.2 Bases teóricas — Variable 2 (same structure)
  2.3   Definición de términos básicos (brief academic definitions)

Each bases_teoricas section gets a single LLM call that produces structured
prose per dimension, citing assigned sources.  Definición de términos extracts
key terms from both variables and their dimensions and generates concise
definitions with citations.
"""

import json

from research_cli.llm_client import call_claude, count_tokens
from research_cli.content.summarizer import prepare_source_for_context
from research_cli.generation.planner import _parse_meta_variable


MARCO_TEORICO_SECTIONS = {
    "bases_teoricas_v1",
    "bases_teoricas_v2",
    "definicion_terminos",
}


def is_marco_teorico(section_key: str) -> bool:
    """Return True if section_key is a marco teórico section."""
    return section_key in MARCO_TEORICO_SECTIONS


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _prepare_sources_text(
    sources: list[dict],
    section_key: str,
    topic: str,
    citation_map: dict[int, str],
    max_total_tokens: int = 5000,
) -> tuple[str, str]:
    """Prepare source material and citation instructions, budget-aware.

    Returns (sources_text, cite_instructions).
    """
    source_blocks = []
    citation_lines = []
    current_tokens = 0

    for source in sources:
        sid = source["id"]
        cite_str = citation_map.get(sid, f"(Source {sid})")
        citation_lines.append(f"  Source ID {sid}: Cite as {cite_str}")

        block = prepare_source_for_context(
            source, section_key=section_key, topic=topic
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


def _generate_bases_teoricas(
    variable_key: str,
    topic: str,
    meta: dict,
    sources: list[dict],
    citation_map: dict[int, str],
) -> str:
    """Generate bases teóricas section for one variable.

    Uses a single LLM call to produce conceptualization organized by dimension.
    """
    # Determine which variable (1 or 2)
    if variable_key == "bases_teoricas_v1":
        var_data = _parse_meta_variable(meta.get("variable_1", ""))
        var_label = "Variable 1 (independiente)"
    else:
        var_data = _parse_meta_variable(meta.get("variable_2", ""))
        var_label = "Variable 2 (dependiente)"

    var_name = var_data.get("name") or var_label
    dimensions = var_data.get("dimensions") or []

    if not sources:
        heading = f"## {var_name}"
        return f"{heading}\n\nNo se asignaron fuentes para esta sección."

    # Prepare source material
    sources_text, cite_instructions = _prepare_sources_text(
        sources, variable_key, topic, citation_map
    )

    # Build dimension instructions
    if dimensions:
        dims_text = "\n".join(f"  - {dim}" for dim in dimensions)
        dim_instruction = f"""Organiza el contenido con las siguientes dimensiones como subsecciones:
{dims_text}

Para cada dimensión:
1. Define la dimensión conceptualmente con citas académicas.
2. Explica su relevancia para la variable principal.
3. Describe los indicadores asociados según la literatura."""
    else:
        dim_instruction = (
            "No se han definido dimensiones específicas. Organiza el contenido "
            "por los aspectos conceptuales más relevantes de la variable según "
            "las fuentes proporcionadas."
        )

    prompt = f"""Redacta la sección de Bases Teóricas para la variable "{var_name}" de una tesis académica USIL.

**Tema de investigación:** {topic}
**Variable:** {var_name} ({var_label})

**Estructura requerida:**
1. Definición general de la variable (~200 palabras, con citas)
2. Subsecciones por dimensión (~200 palabras cada una, con citas)
3. Síntesis de la relación entre dimensiones (~100 palabras)

{dim_instruction}

**Instrucciones de citación — usa estas cadenas EXACTAS:**
{cite_instructions}

**Material de las fuentes (tus ÚNICOS datos — no inventes afirmaciones):**

{sources_text}

**REGLAS:**
1. Redacción formal académica en español, tercera persona.
2. Extensión aproximada: 800 palabras.
3. Usa SOLO las cadenas de citación listadas arriba. NO inventes citas.
4. Toda afirmación fáctica debe tener una cita en línea.
5. NO fabricar datos, estadísticas o hallazgos que no estén en las fuentes.
6. Si las fuentes son insuficientes para un punto, escribe:
   "[Se requiere mayor investigación para establecer...]"
7. Incluye el encabezado de la variable como heading markdown (##).
8. Escribe párrafos sustantivos, no viñetas.
9. Para cada dimensión usa heading ### (o #### si hay muchas).
"""

    result = call_claude(prompt, max_tokens=4096, temperature=0.3)
    return result


def _generate_definicion_terminos(
    topic: str,
    meta: dict,
    sources: list[dict],
    citation_map: dict[int, str],
) -> str:
    """Generate the 'Definición de términos básicos' section.

    Extracts key terms from variables and dimensions, generates concise
    academic definitions with citations.
    """
    v1 = _parse_meta_variable(meta.get("variable_1", ""))
    v2 = _parse_meta_variable(meta.get("variable_2", ""))

    # Collect terms: variable names + all dimensions
    terms = []
    v1_name = v1.get("name", "")
    v2_name = v2.get("name", "")
    if v1_name:
        terms.append(v1_name)
        terms.extend(v1.get("dimensions") or [])
    if v2_name:
        terms.append(v2_name)
        terms.extend(v2.get("dimensions") or [])

    if not terms:
        return (
            "## Definición de términos básicos\n\n"
            "No se definieron variables para generar los términos básicos."
        )

    terms_list = "\n".join(f"  - {t}" for t in terms)

    # Prepare source material (lighter budget — definitions are brief)
    if sources:
        sources_text, cite_instructions = _prepare_sources_text(
            sources, "definicion_terminos", topic, citation_map,
            max_total_tokens=3000,
        )
    else:
        sources_text = "(Sin fuentes asignadas)"
        cite_instructions = "(Sin instrucciones de citación)"

    prompt = f"""Redacta la sección "Definición de términos básicos" de una tesis académica USIL.

**Tema:** {topic}

**Términos a definir:**
{terms_list}

**Instrucciones de citación:**
{cite_instructions}

**Material de las fuentes:**

{sources_text}

**REGLAS:**
1. Para cada término, escribe una definición concisa (2-3 oraciones) en español formal académico.
2. Cada definición debe incluir al menos una cita en línea de las fuentes proporcionadas.
3. Si no hay fuente disponible para un término, proporciona una definición conceptual e indica
   "[definición operacional propuesta por el investigador]".
4. Formato: lista con el término en **negrita** seguido de su definición.
5. Incluye el encabezado "## Definición de términos básicos".
6. NO inventar citas ni referencias.
7. Ordena los términos: primero las variables principales, luego sus dimensiones.
"""

    result = call_claude(prompt, max_tokens=2048, temperature=0.3)
    return result


# ---------------------------------------------------------------------------
# Public dispatcher
# ---------------------------------------------------------------------------

def generate_marco_teorico(
    section_key: str,
    topic: str,
    meta: dict,
    sources: list[dict],
    citation_map: dict[int, str],
) -> str:
    """Generate a marco teórico section (bases teóricas or definición de términos).

    Returns formatted markdown.
    """
    if section_key in ("bases_teoricas_v1", "bases_teoricas_v2"):
        return _generate_bases_teoricas(
            section_key, topic, meta, sources, citation_map
        )
    elif section_key == "definicion_terminos":
        return _generate_definicion_terminos(topic, meta, sources, citation_map)
    else:
        return ""
