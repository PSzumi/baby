"""
marco_teorico.py — Bases teóricas for USIL thesis (Marco Teórico, section 1.2.2).

Generates:
  1.2.2.1 Bases teóricas — Variable 1 (conceptualization organized by dimension)
  1.2.2.2 Bases teóricas — Variable 2 (same structure)

Each bases_teoricas section gets a single LLM call that produces:
  1. 8 conceptual definitions from different authors (~400 words)
  2. Estado del Arte table (20 theories/models/approaches)
  3. Theory selection paragraph (which theory adopted and why)
  4. Dimension definitions (8 lines each with citations)

Target: ~1500-2000 words per variable.
"""

import json

from research_cli.llm_client import call_claude, count_tokens
from research_cli.content.summarizer import prepare_source_for_context
from research_cli.generation.planner import _parse_meta_variable


MARCO_TEORICO_SECTIONS = {
    "bases_teoricas_v1",
    "bases_teoricas_v2",
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

**Estructura requerida (en este orden):**

### 1. Definiciones conceptuales (~400 palabras)
Presenta al menos 8 definiciones de "{var_name}" de diferentes autores, cada una en un párrafo breve (2-3 oraciones). Usa el formato:
"Según [Autor] ([Año]), [variable] se define como..."
Varía los verbos: define, conceptualiza, plantea, establece, señala, argumenta, propone, sostiene.

### 2. Estado del Arte — Tabla de teorías/modelos
Presenta una tabla markdown con al menos 15 teorías, modelos o enfoques relacionados con "{var_name}":
| N° | Autor(es) | Año | Teoría/Modelo/Enfoque | Descripción breve |

### 3. Teoría adoptada (~150 palabras)
Selecciona la teoría o modelo que se adopta en esta investigación y justifica la elección explicando por qué es la más pertinente para estudiar "{var_name}" en el contexto del estudio.

### 4. Definición de dimensiones
{dim_instruction}

Para cada dimensión escribe al menos 8 líneas de contenido (~200 palabras por dimensión):
- Definición conceptual con 2-3 autores diferentes
- Relevancia para la variable principal
- Indicadores asociados según la literatura

**Instrucciones de citación — usa estas cadenas EXACTAS:**
{cite_instructions}

**Material de las fuentes (tus ÚNICOS datos — no inventes afirmaciones):**

{sources_text}

**REGLAS:**
1. Redacción formal académica en español, tercera persona.
2. Extensión aproximada: 1500-2000 palabras.
3. Usa SOLO las cadenas de citación listadas arriba. NO inventes citas.
4. Toda afirmación fáctica debe tener una cita en línea.
5. NO fabricar datos, estadísticas o hallazgos que no estén en las fuentes.
6. Si las fuentes son insuficientes para un punto, escribe:
   "[Se requiere mayor investigación para establecer...]"
7. Incluye el encabezado de la variable como heading markdown (##).
8. Escribe párrafos sustantivos, no viñetas (excepto en la tabla).
9. Para cada dimensión usa heading ### (o #### si hay muchas).
"""

    result = call_claude(prompt, max_tokens=8192, temperature=0.3)
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
    """Generate a marco teórico section (bases teóricas).

    Returns formatted markdown.
    """
    if section_key in ("bases_teoricas_v1", "bases_teoricas_v2"):
        return _generate_bases_teoricas(
            section_key, topic, meta, sources, citation_map
        )
    else:
        return ""
