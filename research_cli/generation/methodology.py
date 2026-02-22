"""
methodology.py — Boilerplate methodology sections for USIL thesis (Chapter III).

Generates sections 3.4, 3.5, and 3.6 which are NOT already handled by formulaic.py:
  3.4 Técnicas e instrumentos de recolección de datos
  3.5 Procedimiento de recolección de datos
  3.6 Métodos de análisis de datos

These are heavily template-driven with variable interpolation from project
metadata.  Each section makes a single LLM call to enrich the boilerplate
with academic definitions and citations from assigned sources.
"""

import json

from research_cli.llm_client import call_claude, count_tokens
from research_cli.content.summarizer import prepare_source_for_context
from research_cli.generation.planner import _parse_meta_variable, _parse_meta_methodology


METHODOLOGY_SECTIONS = {
    "tecnicas_instrumentos",
    "procedimiento_recoleccion",
    "metodos_analisis",
}


def is_methodology_boilerplate(section_key: str) -> bool:
    """Return True if section_key is a methodology boilerplate section."""
    return section_key in METHODOLOGY_SECTIONS


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _prepare_sources_text(
    sources: list[dict],
    section_key: str,
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


def _build_variable_instrument_table(meta: dict) -> str:
    """Build a markdown table mapping variables to instrument dimensions."""
    v1 = _parse_meta_variable(meta.get("variable_1", ""))
    v2 = _parse_meta_variable(meta.get("variable_2", ""))

    lines = [
        "| Variable | Dimensiones | Ítems |",
        "|----------|-------------|-------|",
    ]

    for var in (v1, v2):
        name = var.get("name") or "—"
        dims = var.get("dimensions") or []
        if dims:
            for j, dim in enumerate(dims):
                var_cell = name if j == 0 else ""
                lines.append(f"| {var_cell} | {dim} | Por definir |")
        else:
            lines.append(f"| {name} | Por definir | Por definir |")

    return "\n".join(lines)


def _select_statistical_test(meth: dict) -> dict:
    """Select appropriate statistical tests based on methodology metadata."""
    scope = meth.get("scope", "correlacional").lower()
    mtype = meth.get("type", "cuantitativa").lower()

    if "correlacional" in scope:
        return {
            "test_name": "coeficiente de correlación de Spearman",
            "test_justification": (
                "dado que se busca determinar la relación entre las variables "
                "y los datos provienen de escalas ordinales (tipo Likert)"
            ),
            "normality_test": "prueba de Kolmogorov-Smirnov",
            "descriptive": "frecuencias, porcentajes, medias y desviaciones estándar",
        }
    elif "explicativo" in scope or "causal" in scope:
        return {
            "test_name": "regresión lineal múltiple",
            "test_justification": (
                "dado que se busca determinar la influencia de la variable "
                "independiente sobre la dependiente"
            ),
            "normality_test": "prueba de Kolmogorov-Smirnov",
            "descriptive": "frecuencias, porcentajes, medias y desviaciones estándar",
        }
    else:  # descriptivo or other
        return {
            "test_name": "estadística descriptiva",
            "test_justification": (
                "dado que se busca describir las características de las "
                "variables de estudio"
            ),
            "normality_test": "prueba de Kolmogorov-Smirnov",
            "descriptive": "frecuencias, porcentajes, medias y desviaciones estándar",
        }


# ---------------------------------------------------------------------------
# Section generators
# ---------------------------------------------------------------------------

def _gen_tecnicas_instrumentos(
    topic: str,
    meta: dict,
    sources: list[dict],
    citation_map: dict[int, str],
) -> str:
    """Generate section 3.4: Técnicas e instrumentos de recolección de datos."""
    v1 = _parse_meta_variable(meta.get("variable_1", ""))
    v2 = _parse_meta_variable(meta.get("variable_2", ""))
    v1_name = v1.get("name") or "Variable 1"
    v2_name = v2.get("name") or "Variable 2"
    population = meta.get("population", "la población estudiada")

    instrument_table = _build_variable_instrument_table(meta)

    # Template body
    template = f"""## Técnicas e instrumentos de recolección de datos

### Técnica

La técnica empleada para la recolección de datos en la presente investigación fue la **encuesta**, la cual permite obtener información de los sujetos de estudio a través de un conjunto estructurado de preguntas.

{{definition_encuesta}}

### Instrumento

El instrumento utilizado fue el **cuestionario** estructurado con escala de medición tipo **Likert** de cinco puntos (1 = Totalmente en desacuerdo, 2 = En desacuerdo, 3 = Ni de acuerdo ni en desacuerdo, 4 = De acuerdo, 5 = Totalmente de acuerdo).

{{definition_cuestionario}}

Se diseñaron dos cuestionarios:

1. **Cuestionario de {v1_name}**: orientado a medir la variable independiente y sus dimensiones en {population}.
2. **Cuestionario de {v2_name}**: orientado a medir la variable dependiente y sus dimensiones en {population}.

### Estructura del instrumento

{instrument_table}

### Validez y confiabilidad

La **validez de contenido** del instrumento fue evaluada mediante el juicio de expertos, quienes verificaron la pertinencia, relevancia y claridad de cada ítem.

La **confiabilidad** del instrumento se determinó mediante el coeficiente **Alfa de Cronbach**, considerándose aceptables valores superiores a 0.70.

{{definition_validez}}"""

    # LLM call to fill definition placeholders with academic citations
    if sources:
        sources_text, cite_instructions = _prepare_sources_text(
            sources, "tecnicas_instrumentos", topic, citation_map
        )
        enrichment_context = f"""
**Instrucciones de citación:**
{cite_instructions}

**Fuentes disponibles:**
{sources_text}"""
    else:
        enrichment_context = ""
        cite_instructions = ""

    prompt = f"""Genera tres párrafos breves en español académico formal para insertar en una sección de metodología de tesis USIL.

1. **definition_encuesta**: Define qué es la técnica de la encuesta según la literatura metodológica (2-3 oraciones con cita).
2. **definition_cuestionario**: Define qué es un cuestionario con escala Likert según la literatura (2-3 oraciones con cita).
3. **definition_validez**: Define brevemente validez de contenido y Alfa de Cronbach según la literatura (2-3 oraciones con cita).
{enrichment_context}

REGLAS:
- Escribe en tercera persona, español formal académico.
- Si hay fuentes disponibles, usa las cadenas de citación proporcionadas.
- Si no hay fuentes de metodología disponibles, usa referencias generales como (Hernández-Sampieri et al., 2014) para metodología de investigación.
- Cada definición debe ser un párrafo independiente de 2-3 oraciones.

Devuelve EXACTAMENTE en este formato (3 bloques separados por líneas vacías):
DEFINITION_ENCUESTA:
[texto]

DEFINITION_CUESTIONARIO:
[texto]

DEFINITION_VALIDEZ:
[texto]
"""

    try:
        llm_output = call_claude(prompt, max_tokens=1500, temperature=0.2)
        definitions = _parse_definitions(llm_output)
    except Exception:
        definitions = {}

    result = template.replace(
        "{definition_encuesta}",
        definitions.get("definition_encuesta", "")
    ).replace(
        "{definition_cuestionario}",
        definitions.get("definition_cuestionario", "")
    ).replace(
        "{definition_validez}",
        definitions.get("definition_validez", "")
    )

    return result


def _gen_procedimiento_recoleccion(
    topic: str,
    meta: dict,
    sources: list[dict],
    citation_map: dict[int, str],
) -> str:
    """Generate section 3.5: Procedimiento de recolección de datos."""
    population = meta.get("population", "la población estudiada")
    university = meta.get("university", "")
    location = meta.get("location", "")

    institution_ref = ""
    if university:
        institution_ref = f" de {university}"
    elif location:
        institution_ref = f" en {location}"

    template = f"""## Procedimiento de recolección de datos

El procedimiento de recolección de datos se realizó siguiendo las etapas que se describen a continuación:

1. **Coordinación institucional**: Se solicitó la autorización correspondiente a las autoridades{institution_ref} para la aplicación del instrumento de investigación a {population}.

2. **Consentimiento informado**: Se informó a los participantes sobre los objetivos de la investigación, la naturaleza voluntaria de su participación y la confidencialidad de sus respuestas. Se obtuvo el consentimiento informado de cada participante.

3. **Aplicación del instrumento**: Se procedió a la aplicación de los cuestionarios a {population}. El tiempo aproximado de aplicación fue de 15 a 20 minutos por participante.

4. **Control de calidad**: Se revisaron los cuestionarios completados para identificar respuestas incompletas o inconsistentes, descartando aquellos que no cumplieran con los criterios de inclusión.

5. **Tabulación de datos**: Los datos recolectados fueron tabulados y organizados en una base de datos utilizando el programa Microsoft Excel para su posterior análisis estadístico.

{{definition_etica}}"""

    # LLM call for ethical considerations definition
    if sources:
        sources_text, cite_instructions = _prepare_sources_text(
            sources, "procedimiento_recoleccion", topic, citation_map
        )
        enrichment_context = f"""
**Instrucciones de citación:**
{cite_instructions}

**Fuentes disponibles:**
{sources_text}"""
    else:
        enrichment_context = ""

    prompt = f"""Genera un párrafo breve en español académico formal sobre las consideraciones éticas en la recolección de datos para una tesis USIL.

El párrafo debe mencionar:
- El respeto a la autonomía de los participantes
- La confidencialidad y anonimato de los datos
- El cumplimiento de principios éticos de investigación
{enrichment_context}

REGLAS:
- 3-4 oraciones en tercera persona.
- Si hay fuentes disponibles, cita las cadenas proporcionadas.
- Si no, usa una referencia general como (Noreña et al., 2012) para principios éticos.

Devuelve SOLO el párrafo, sin encabezados.
"""

    try:
        llm_output = call_claude(prompt, max_tokens=500, temperature=0.2)
        ethics_paragraph = llm_output.strip()
    except Exception:
        ethics_paragraph = ""

    return template.replace("{definition_etica}", ethics_paragraph)


def _gen_metodos_analisis(
    topic: str,
    meta: dict,
    sources: list[dict],
    citation_map: dict[int, str],
) -> str:
    """Generate section 3.6: Métodos de análisis de datos."""
    meth = _parse_meta_methodology(meta.get("methodology", ""))
    stats = _select_statistical_test(meth)
    v1 = _parse_meta_variable(meta.get("variable_1", ""))
    v2 = _parse_meta_variable(meta.get("variable_2", ""))
    v1_name = v1.get("name") or "Variable 1"
    v2_name = v2.get("name") or "Variable 2"

    template = f"""## Métodos de análisis de datos

El análisis de los datos recolectados se realizó utilizando el programa estadístico **SPSS** (Statistical Package for the Social Sciences) versión 26.

### Estadística descriptiva

Para el análisis descriptivo de los datos se utilizaron {stats['descriptive']}, lo cual permitió caracterizar el comportamiento de las variables {v1_name} y {v2_name} y sus respectivas dimensiones.

### Estadística inferencial

Para la contrastación de las hipótesis de investigación se empleó el **{stats['test_name']}**, {stats['test_justification']}.

Previamente, se aplicó la **{stats['normality_test']}** para determinar la distribución de los datos y seleccionar la prueba estadística más adecuada.

Se consideró un nivel de significancia de **α = 0.05** para la toma de decisiones estadísticas. El criterio de decisión fue:
- Si p-valor < 0.05: se rechaza la hipótesis nula (H₀).
- Si p-valor ≥ 0.05: no se rechaza la hipótesis nula (H₀).

{{definition_test}}"""

    # LLM call for test definition
    if sources:
        sources_text, cite_instructions = _prepare_sources_text(
            sources, "metodos_analisis", topic, citation_map
        )
        enrichment_context = f"""
**Instrucciones de citación:**
{cite_instructions}

**Fuentes disponibles:**
{sources_text}"""
    else:
        enrichment_context = ""

    prompt = f"""Genera un párrafo breve en español académico formal que defina el {stats['test_name']} y justifique su uso en una investigación {meth.get('type', 'cuantitativa')} de alcance {meth.get('scope', 'correlacional')}.
{enrichment_context}

REGLAS:
- 2-3 oraciones en tercera persona.
- Si hay fuentes disponibles, cita las cadenas proporcionadas.
- Si no, usa una referencia general como (Hernández-Sampieri et al., 2014).

Devuelve SOLO el párrafo, sin encabezados.
"""

    try:
        llm_output = call_claude(prompt, max_tokens=500, temperature=0.2)
        test_paragraph = llm_output.strip()
    except Exception:
        test_paragraph = ""

    return template.replace("{definition_test}", test_paragraph)


def _parse_definitions(llm_output: str) -> dict:
    """Parse labeled definition blocks from LLM output."""
    definitions = {}
    current_key = None
    current_lines = []

    for line in llm_output.split("\n"):
        upper = line.strip().upper()
        if upper.startswith("DEFINITION_ENCUESTA"):
            if current_key:
                definitions[current_key] = "\n".join(current_lines).strip()
            current_key = "definition_encuesta"
            current_lines = []
            # Check if content is on the same line after ':'
            after_colon = line.split(":", 1)[1].strip() if ":" in line else ""
            if after_colon:
                current_lines.append(after_colon)
        elif upper.startswith("DEFINITION_CUESTIONARIO"):
            if current_key:
                definitions[current_key] = "\n".join(current_lines).strip()
            current_key = "definition_cuestionario"
            current_lines = []
            after_colon = line.split(":", 1)[1].strip() if ":" in line else ""
            if after_colon:
                current_lines.append(after_colon)
        elif upper.startswith("DEFINITION_VALIDEZ"):
            if current_key:
                definitions[current_key] = "\n".join(current_lines).strip()
            current_key = "definition_validez"
            current_lines = []
            after_colon = line.split(":", 1)[1].strip() if ":" in line else ""
            if after_colon:
                current_lines.append(after_colon)
        else:
            if current_key and line.strip():
                current_lines.append(line.strip())

    if current_key:
        definitions[current_key] = "\n".join(current_lines).strip()

    return definitions


# ---------------------------------------------------------------------------
# Public dispatcher
# ---------------------------------------------------------------------------

def generate_methodology(
    section_key: str,
    topic: str,
    meta: dict,
    sources: list[dict],
    citation_map: dict[int, str],
) -> str:
    """Generate a methodology boilerplate section.

    Returns formatted markdown.
    """
    if section_key == "tecnicas_instrumentos":
        return _gen_tecnicas_instrumentos(topic, meta, sources, citation_map)
    elif section_key == "procedimiento_recoleccion":
        return _gen_procedimiento_recoleccion(topic, meta, sources, citation_map)
    elif section_key == "metodos_analisis":
        return _gen_metodos_analisis(topic, meta, sources, citation_map)
    else:
        return ""
