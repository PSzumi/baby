"""
formulaic.py — Deterministic section generators for USIL thesis.

Sections like Formulación del problema, Objetivos, Hipótesis, and parts of
Metodología follow strict formulas derived from research variables, dimensions,
and methodology metadata.  No LLM needed — pure string interpolation.
"""

import json

from research_cli.generation.planner import _parse_meta_variable, _parse_meta_methodology


FORMULAIC_SECTIONS = {
    "problem_formulation",
    "research_objectives",
    "hypothesis",
    "tipo_investigacion",
    "diseno_investigacion",
    "variables_def",
    "muestra",
}


def is_formulaic(section_key: str) -> bool:
    """Return True if section_key should be generated formulaically."""
    return section_key in FORMULAIC_SECTIONS


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _vars_and_pop(meta: dict) -> tuple[dict, dict, str]:
    """Extract parsed V1, V2, and population from metadata."""
    v1 = _parse_meta_variable(meta.get("variable_1", ""))
    v2 = _parse_meta_variable(meta.get("variable_2", ""))
    population = meta.get("population", "la población estudiada")
    return v1, v2, population


# ---------------------------------------------------------------------------
# Generator: Formulación del problema (1.1.2)
# ---------------------------------------------------------------------------

def _gen_problem_formulation(topic: str, meta: dict) -> str:
    v1, v2, population = _vars_and_pop(meta)
    v1_name = v1.get("name") or "Variable 1"
    v2_name = v2.get("name") or "Variable 2"
    v2_dims = v2.get("dimensions") or []

    lines = [
        "## Formulación del Problema",
        "",
        "### Problema general",
        "",
        f"¿Cuál es la relación entre {v1_name} y {v2_name} en {population}?",
        "",
        "### Problemas específicos",
        "",
    ]

    if v2_dims:
        for i, dim in enumerate(v2_dims, 1):
            lines.append(
                f"{i}. ¿Cuál es la relación entre {v1_name} y {dim} de "
                f"{v2_name} en {population}?"
            )
    else:
        lines.append(
            f"1. ¿Cuál es la relación entre {v1_name} y las dimensiones de "
            f"{v2_name} en {population}?"
        )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Generator: Objetivos (1.3.1)
# ---------------------------------------------------------------------------

def _gen_research_objectives(topic: str, meta: dict) -> str:
    v1, v2, population = _vars_and_pop(meta)
    v1_name = v1.get("name") or "Variable 1"
    v2_name = v2.get("name") or "Variable 2"
    v2_dims = v2.get("dimensions") or []

    lines = [
        "## Objetivos",
        "",
        "### Objetivo general",
        "",
        f"Determinar la relación entre {v1_name} y {v2_name} en {population}.",
        "",
        "### Objetivos específicos",
        "",
    ]

    if v2_dims:
        for i, dim in enumerate(v2_dims, 1):
            lines.append(
                f"{i}. Determinar la relación entre {v1_name} y {dim} de "
                f"{v2_name} en {population}."
            )
    else:
        lines.append(
            f"1. Determinar la relación entre {v1_name} y las dimensiones de "
            f"{v2_name} en {population}."
        )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Generator: Hipótesis (1.3.2)
# ---------------------------------------------------------------------------

def _gen_hypothesis(topic: str, meta: dict) -> str:
    v1, v2, population = _vars_and_pop(meta)
    v1_name = v1.get("name") or "Variable 1"
    v2_name = v2.get("name") or "Variable 2"
    v2_dims = v2.get("dimensions") or []

    lines = [
        "## Hipótesis",
        "",
        "### Hipótesis general",
        "",
        f"Existe una relación significativa entre {v1_name} y {v2_name} en {population}.",
        "",
        "### Hipótesis específicas",
        "",
    ]

    if v2_dims:
        for i, dim in enumerate(v2_dims, 1):
            lines.append(
                f"{i}. Existe una relación significativa entre {v1_name} y "
                f"{dim} de {v2_name} en {population}."
            )
    else:
        lines.append(
            f"1. Existe una relación significativa entre {v1_name} y las "
            f"dimensiones de {v2_name} en {population}."
        )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Generator: Tipo de Investigación (2.1.1)
# ---------------------------------------------------------------------------

def _gen_tipo_investigacion(topic: str, meta: dict) -> str:
    meth = _parse_meta_methodology(meta.get("methodology", ""))
    mtype = meth.get("type", "cuantitativa")
    scope = meth.get("scope", "correlacional")

    lines = [
        "## Tipo de Investigación",
        "",
        f"La presente investigación es de enfoque **{mtype}**, dado que se "
        f"recolectan y analizan datos numéricos para probar las hipótesis "
        f"planteadas mediante el uso de técnicas estadísticas. Según "
        f"Hernández-Sampieri et al. (2014), el enfoque cuantitativo utiliza la "
        f"recolección de datos para probar hipótesis con base en la medición "
        f"numérica y el análisis estadístico, con el fin de establecer pautas "
        f"de comportamiento y probar teorías.",
        "",
        f"Asimismo, la investigación es de tipo **básica**, ya que busca "
        f"ampliar el conocimiento teórico existente sobre las variables de "
        f"estudio sin perseguir una aplicación práctica inmediata. La "
        f"investigación básica tiene como propósito producir conocimiento y "
        f"teorías (Hernández-Sampieri et al., 2014).",
        "",
        f"El alcance del estudio es **{scope}**, ya que tiene como propósito "
        f"medir el grado de relación existente entre las variables de "
        f"investigación en un contexto determinado. Los estudios "
        f"correlacionales tienen como finalidad conocer la relación o grado "
        f"de asociación que exista entre dos o más conceptos, categorías o "
        f"variables en una muestra o contexto en particular "
        f"(Hernández-Sampieri et al., 2014).",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Generator: Diseño de Investigación (2.1.2)
# ---------------------------------------------------------------------------

def _gen_diseno_investigacion(topic: str, meta: dict) -> str:
    meth = _parse_meta_methodology(meta.get("methodology", ""))
    design = meth.get("design", "no experimental, transversal")

    lines = [
        "## Diseño de Investigación",
        "",
        f"El diseño de la investigación es **no experimental**, puesto que no se "
        f"manipulan deliberadamente las variables de estudio. Según "
        f"Hernández-Sampieri et al. (2014), en la investigación no experimental "
        f"se observan los fenómenos tal como se dan en su contexto natural, "
        f"para posteriormente analizarlos.",
        "",
        f"Asimismo, es de corte **transversal**, ya que los datos se recolectan "
        f"en un solo momento temporal, en un tiempo único. Su propósito es "
        f"describir variables y analizar su incidencia e interrelación en un "
        f"momento dado. Es como tomar una fotografía de algo que sucede "
        f"(Hernández-Sampieri et al., 2014).",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Generator: Variables (2.1.3)
# ---------------------------------------------------------------------------

def _gen_variables_def(topic: str, meta: dict) -> str:
    v1 = _parse_meta_variable(meta.get("variable_1", ""))
    v2 = _parse_meta_variable(meta.get("variable_2", ""))
    v1_name = v1.get("name") or "Variable 1"
    v2_name = v2.get("name") or "Variable 2"
    v1_dims = v1.get("dimensions") or []
    v2_dims = v2.get("dimensions") or []

    lines = [
        "## Variables",
        "",
        "### Definición conceptual",
        "",
        f"**{v1_name} (Variable independiente):** [Insertar definición conceptual "
        f"de {v1_name} según autor de referencia, con cita].",
        "",
        f"**{v2_name} (Variable dependiente):** [Insertar definición conceptual "
        f"de {v2_name} según autor de referencia, con cita].",
        "",
        "### Definición operacional",
        "",
        f"**{v1_name}:** Se mide a través de un cuestionario tipo Likert que "
        f"evalúa las dimensiones: {', '.join(v1_dims) if v1_dims else '[por definir]'}.",
        "",
        f"**{v2_name}:** Se mide a través de un cuestionario tipo Likert que "
        f"evalúa las dimensiones: {', '.join(v2_dims) if v2_dims else '[por definir]'}.",
        "",
        "### Operacionalización de variables",
        "",
        "| Variable | Dimensiones | Indicadores | Escala |",
        "|----------|-------------|-------------|--------|",
    ]

    for var, var_name in ((v1, v1_name), (v2, v2_name)):
        dims = var.get("dimensions") or []
        if dims:
            for j, dim in enumerate(dims):
                var_cell = var_name if j == 0 else ""
                lines.append(f"| {var_cell} | {dim} | Ítems del instrumento | Ordinal (Likert) |")
        else:
            lines.append(f"| {var_name} | Por definir | Ítems del instrumento | Ordinal (Likert) |")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Generator: Muestra (2.1.4)
# ---------------------------------------------------------------------------

def _gen_muestra(topic: str, meta: dict) -> str:
    population = meta.get("population", "la población estudiada")
    sample_size = meta.get("sample_size", 0)

    lines = [
        "## Muestra",
        "",
        "### Población",
        "",
        f"La población de la presente investigación está constituida por {population}.",
        "",
        "### Muestra",
        "",
    ]

    if sample_size:
        lines.append(
            f"La muestra está conformada por **{sample_size}** participantes, "
            f"seleccionados mediante muestreo probabilístico aleatorio simple. "
            f"El tamaño de muestra se determinó utilizando la fórmula para "
            f"poblaciones infinitas con un nivel de confianza del 95% y un "
            f"margen de error del 5%."
        )
    else:
        lines.append(
            "El tamaño de muestra se determinará utilizando la fórmula para "
            "poblaciones infinitas con un nivel de confianza del 95% y un "
            "margen de error del 5%."
        )

    lines.extend([
        "",
        "### Criterios de selección",
        "",
        "**Criterios de inclusión:**",
        "",
        f"- Pertenecer a {population}.",
        "- Participación voluntaria con consentimiento informado.",
        "- Haber completado el cuestionario en su totalidad.",
        "",
        "**Criterios de exclusión:**",
        "",
        "- No cumplir con los criterios de inclusión.",
        "- Cuestionarios con respuestas incompletas o inconsistentes.",
        "- Negativa a participar en la investigación.",
    ])

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public dispatcher
# ---------------------------------------------------------------------------

_GENERATORS = {
    "problem_formulation": _gen_problem_formulation,
    "research_objectives": _gen_research_objectives,
    "hypothesis": _gen_hypothesis,
    "tipo_investigacion": _gen_tipo_investigacion,
    "diseno_investigacion": _gen_diseno_investigacion,
    "variables_def": _gen_variables_def,
    "muestra": _gen_muestra,
}


def generate_formulaic(section_key: str, topic: str, meta: dict) -> str:
    """Dispatch to the appropriate formulaic generator.

    Returns the generated markdown string, or an empty string if the key
    is not a formulaic section.
    """
    gen = _GENERATORS.get(section_key)
    if gen is None:
        return ""
    return gen(topic, meta or {})
