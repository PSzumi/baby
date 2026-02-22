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
    "methodology_type_design",
    "population_sample",
    "variable_operationalization",
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
# Generator: Formulación del problema
# ---------------------------------------------------------------------------

def _gen_problem_formulation(topic: str, meta: dict) -> str:
    v1, v2, population = _vars_and_pop(meta)
    v1_name = v1.get("name") or "Variable 1"
    v2_name = v2.get("name") or "Variable 2"
    v2_dims = v2.get("dimensions") or []

    lines = [
        "## Formulación del problema",
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
# Generator: Objetivos de la investigación
# ---------------------------------------------------------------------------

def _gen_research_objectives(topic: str, meta: dict) -> str:
    v1, v2, population = _vars_and_pop(meta)
    v1_name = v1.get("name") or "Variable 1"
    v2_name = v2.get("name") or "Variable 2"
    v2_dims = v2.get("dimensions") or []

    lines = [
        "## Objetivos de la investigación",
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
# Generator: Hipótesis
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
# Generator: Tipo y diseño de investigación
# ---------------------------------------------------------------------------

def _gen_methodology_type_design(topic: str, meta: dict) -> str:
    meth = _parse_meta_methodology(meta.get("methodology", ""))
    mtype = meth.get("type", "cuantitativa")
    scope = meth.get("scope", "correlacional")
    design = meth.get("design", "no experimental, transversal")

    lines = [
        "## Tipo y diseño de investigación",
        "",
        f"La presente investigación es de enfoque **{mtype}**, dado que se "
        f"recolectan y analizan datos numéricos para probar las hipótesis "
        f"planteadas mediante el uso de técnicas estadísticas.",
        "",
        f"El alcance del estudio es **{scope}**, ya que tiene como propósito "
        f"medir el grado de relación existente entre las variables de "
        f"investigación en un contexto determinado.",
        "",
        f"El diseño de la investigación es **{design}**, puesto que no se "
        f"manipulan deliberadamente las variables y los datos se recolectan "
        f"en un solo momento temporal.",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Generator: Población y muestra
# ---------------------------------------------------------------------------

def _gen_population_sample(topic: str, meta: dict) -> str:
    population = meta.get("population", "la población estudiada")
    sample_size = meta.get("sample_size", 0)

    lines = [
        "## Población y muestra",
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

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Generator: Operacionalización de variables
# ---------------------------------------------------------------------------

def _gen_variable_operationalization(topic: str, meta: dict) -> str:
    v1 = _parse_meta_variable(meta.get("variable_1", ""))
    v2 = _parse_meta_variable(meta.get("variable_2", ""))

    lines = [
        "## Operacionalización de variables",
        "",
        "| Variable | Dimensiones | Indicadores |",
        "|----------|-------------|-------------|",
    ]

    for var in (v1, v2):
        name = var.get("name") or "—"
        dims = var.get("dimensions") or []
        if dims:
            for j, dim in enumerate(dims):
                var_cell = name if j == 0 else ""
                lines.append(f"| {var_cell} | {dim} | Ítems del instrumento |")
        else:
            lines.append(f"| {name} | Por definir | Ítems del instrumento |")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public dispatcher
# ---------------------------------------------------------------------------

_GENERATORS = {
    "problem_formulation": _gen_problem_formulation,
    "research_objectives": _gen_research_objectives,
    "hypothesis": _gen_hypothesis,
    "methodology_type_design": _gen_methodology_type_design,
    "population_sample": _gen_population_sample,
    "variable_operationalization": _gen_variable_operationalization,
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
