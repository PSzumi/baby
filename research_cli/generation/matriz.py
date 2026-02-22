"""
matriz.py — Matriz de consistencia generator for USIL thesis.

Generates the consistency matrix table for the Anexos (Appendix) section.
Pure Python — no LLM needed.  All data comes from project metadata
collected during init (variables, dimensions, population, methodology).

The matrix has 6 columns:
    PROBLEMAS | OBJETIVOS | HIPÓTESIS | VARIABLES | DIMENSIONES | METODOLOGÍA

Rows scale dynamically based on the number of V2 dimensions (one specific
problem/objective/hypothesis per dimension).
"""

import json

from research_cli.generation.planner import _parse_meta_variable, _parse_meta_methodology


MATRIZ_SECTIONS = {"matriz_consistencia"}


def is_matriz(section_key: str) -> bool:
    """Return True if section_key is the consistency matrix."""
    return section_key in MATRIZ_SECTIONS


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_problems(v1_name: str, v2_name: str, v2_dims: list[str], population: str) -> list[str]:
    """Build general + specific problem questions."""
    general = (
        f"¿Cuál es la relación entre {v1_name} y {v2_name} "
        f"en {population}?"
    )
    specifics = []
    if v2_dims:
        for dim in v2_dims:
            specifics.append(
                f"¿Cuál es la relación entre {v1_name} y {dim} "
                f"de {v2_name} en {population}?"
            )
    else:
        specifics.append(
            f"¿Cuál es la relación entre {v1_name} y las dimensiones "
            f"de {v2_name} en {population}?"
        )
    return [general] + specifics


def _build_objectives(v1_name: str, v2_name: str, v2_dims: list[str], population: str) -> list[str]:
    """Build general + specific objectives."""
    general = (
        f"Determinar la relación entre {v1_name} y {v2_name} "
        f"en {population}."
    )
    specifics = []
    if v2_dims:
        for dim in v2_dims:
            specifics.append(
                f"Determinar la relación entre {v1_name} y {dim} "
                f"de {v2_name} en {population}."
            )
    else:
        specifics.append(
            f"Determinar la relación entre {v1_name} y las dimensiones "
            f"de {v2_name} en {population}."
        )
    return [general] + specifics


def _build_hypotheses(v1_name: str, v2_name: str, v2_dims: list[str], population: str) -> list[str]:
    """Build general + specific hypotheses."""
    general = (
        f"Existe una relación significativa entre {v1_name} y "
        f"{v2_name} en {population}."
    )
    specifics = []
    if v2_dims:
        for dim in v2_dims:
            specifics.append(
                f"Existe una relación significativa entre {v1_name} y "
                f"{dim} de {v2_name} en {population}."
            )
    else:
        specifics.append(
            f"Existe una relación significativa entre {v1_name} y las "
            f"dimensiones de {v2_name} en {population}."
        )
    return [general] + specifics


def _build_methodology_cell(meth: dict, population: str, sample_size: int) -> str:
    """Build the methodology column content as a multi-line string."""
    mtype = meth.get("type", "cuantitativa")
    scope = meth.get("scope", "correlacional")
    design = meth.get("design", "no experimental, transversal")

    lines = [
        f"1. Tipo: Básico, {mtype}",
        f"2. Alcance: {scope.capitalize()}",
        f"3. Diseño: {design.capitalize()}",
    ]

    if sample_size:
        lines.append(f"4. Muestra: {sample_size} participantes de {population}")
    else:
        lines.append(f"4. Población: {population}")

    lines.append("5. Técnica: Encuesta")
    lines.append("6. Instrumento: Cuestionario tipo Likert")

    return " / ".join(lines)


def _build_variables_cells(
    v1_name: str, v1_dims: list[str],
    v2_name: str, v2_dims: list[str],
    num_rows: int,
) -> list[tuple[str, str]]:
    """Build (variable, dimension) pairs for each row of the matrix.

    Returns list of (variable_text, dimension_text) tuples.
    """
    all_dims = []

    # First row: general — both variables, all dimensions summarized
    v1_dims_text = ", ".join(v1_dims) if v1_dims else "Por definir"
    v2_dims_text = ", ".join(v2_dims) if v2_dims else "Por definir"
    general_var = f"V1: {v1_name} / V2: {v2_name}"
    general_dim = f"V1: {v1_dims_text} / V2: {v2_dims_text}"
    all_dims.append((general_var, general_dim))

    # Specific rows: one per V2 dimension
    if v2_dims:
        for dim in v2_dims:
            all_dims.append((f"V1: {v1_name} / V2: {v2_name}", dim))
    else:
        all_dims.append((f"V1: {v1_name} / V2: {v2_name}", "Por definir"))

    # Pad if needed
    while len(all_dims) < num_rows:
        all_dims.append(("", ""))

    return all_dims[:num_rows]


# ---------------------------------------------------------------------------
# Public generator
# ---------------------------------------------------------------------------

def generate_matriz(section_key: str, topic: str, meta: dict) -> str:
    """Generate the Matriz de consistencia as a markdown table.

    Parameters
    ----------
    section_key : str
        Must be "matriz_consistencia".
    topic : str
        The thesis topic.
    meta : dict
        Project metadata from database.

    Returns
    -------
    str
        Formatted markdown with heading and table.
    """
    v1 = _parse_meta_variable(meta.get("variable_1", ""))
    v2 = _parse_meta_variable(meta.get("variable_2", ""))
    meth = _parse_meta_methodology(meta.get("methodology", ""))

    v1_name = v1.get("name") or "Variable 1"
    v2_name = v2.get("name") or "Variable 2"
    v1_dims = v1.get("dimensions") or []
    v2_dims = v2.get("dimensions") or []
    population = meta.get("population", "la población estudiada")
    sample_size = meta.get("sample_size", 0)
    if isinstance(sample_size, str):
        try:
            sample_size = int(sample_size)
        except ValueError:
            sample_size = 0

    # Build column data
    problems = _build_problems(v1_name, v2_name, v2_dims, population)
    objectives = _build_objectives(v1_name, v2_name, v2_dims, population)
    hypotheses = _build_hypotheses(v1_name, v2_name, v2_dims, population)
    num_rows = len(problems)

    var_dim_pairs = _build_variables_cells(
        v1_name, v1_dims, v2_name, v2_dims, num_rows
    )
    methodology_text = _build_methodology_cell(meth, population, sample_size)

    # Build markdown table
    lines = [
        "## Anexo: Matriz de consistencia",
        "",
        "| Problemas | Objetivos | Hipótesis | Variables | Dimensiones | Metodología |",
        "|-----------|-----------|-----------|-----------|-------------|-------------|",
    ]

    for i in range(num_rows):
        prob = problems[i] if i < len(problems) else ""
        obj = objectives[i] if i < len(objectives) else ""
        hyp = hypotheses[i] if i < len(hypotheses) else ""
        var_text, dim_text = var_dim_pairs[i] if i < len(var_dim_pairs) else ("", "")
        # Methodology only in first row (spans conceptually)
        meth_text = methodology_text if i == 0 else ""

        # Label rows
        if i == 0:
            prob = f"**General:** {prob}"
            obj = f"**General:** {obj}"
            hyp = f"**General:** {hyp}"
        else:
            prob = f"**PE{i}:** {prob}"
            obj = f"**OE{i}:** {obj}"
            hyp = f"**HE{i}:** {hyp}"

        lines.append(
            f"| {prob} | {obj} | {hyp} | {var_text} | {dim_text} | {meth_text} |"
        )

    return "\n".join(lines)
