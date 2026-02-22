"""
placeholders.py — Chapter 3 placeholder sections for USIL thesis.

Generates template placeholders for sections that require empirical data:
  3.1.1 Presentación de Resultados
  3.1.2 Discusión
  3.1.3 Conclusiones
  3.1.4 Recomendaciones

Pure templates, 0 LLM calls — placeholder text explaining what goes in
each section once data is collected.
"""

from research_cli.generation.planner import _parse_meta_variable, _parse_meta_methodology


PLACEHOLDER_SECTIONS = {
    "resultados_placeholder",
    "discusion_placeholder",
    "conclusiones_placeholder",
    "recomendaciones_placeholder",
}


def is_placeholder(section_key: str) -> bool:
    """Return True if section_key is a Chapter 3 placeholder section."""
    return section_key in PLACEHOLDER_SECTIONS


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------

def _gen_resultados(topic: str, meta: dict) -> str:
    v1 = _parse_meta_variable(meta.get("variable_1", ""))
    v2 = _parse_meta_variable(meta.get("variable_2", ""))
    v1_name = v1.get("name") or "Variable 1"
    v2_name = v2.get("name") or "Variable 2"
    v2_dims = v2.get("dimensions") or []
    meth = _parse_meta_methodology(meta.get("methodology", ""))
    scope = meth.get("scope", "correlacional")

    lines = [
        "## Presentación de Resultados",
        "",
        "*[Esta sección se completará una vez recolectados y analizados los datos empíricos.]*",
        "",
        "### Resultados descriptivos",
        "",
        f"Presentar las tablas de frecuencia y estadísticos descriptivos (media, desviación estándar) para las variables {v1_name} y {v2_name} y sus dimensiones.",
        "",
        "### Prueba de normalidad",
        "",
        "Incluir los resultados de la prueba de Kolmogorov-Smirnov para determinar la distribución de los datos y justificar la selección de la prueba estadística.",
        "",
        "### Contrastación de hipótesis",
        "",
        "**Hipótesis general**",
        "",
        f"Presentar la tabla de correlación entre {v1_name} y {v2_name} (coeficiente, p-valor, nivel de significancia).",
        "",
        "**Hipótesis específicas**",
        "",
    ]

    if v2_dims:
        for i, dim in enumerate(v2_dims, 1):
            lines.append(f"- **HE{i}**: Correlación entre {v1_name} y {dim} de {v2_name}.")
    else:
        lines.append(f"- Presentar correlaciones entre {v1_name} y cada dimensión de {v2_name}.")

    return "\n".join(lines)


def _gen_discusion(topic: str, meta: dict) -> str:
    v1 = _parse_meta_variable(meta.get("variable_1", ""))
    v2 = _parse_meta_variable(meta.get("variable_2", ""))
    v1_name = v1.get("name") or "Variable 1"
    v2_name = v2.get("name") or "Variable 2"

    return f"""## Discusión

*[Esta sección se completará una vez obtenidos los resultados.]*

La discusión debe abordar los siguientes puntos:

1. **Interpretación de resultados**: Comparar los resultados obtenidos con los antecedentes internacionales y nacionales presentados en el Capítulo 1. Identificar coincidencias y discrepancias con estudios previos sobre {v1_name} y {v2_name}.

2. **Contraste con el marco teórico**: Analizar cómo los hallazgos se alinean o divergen de las teorías presentadas en las bases teóricas. Explicar posibles razones para las discrepancias.

3. **Análisis de hipótesis**: Para cada hipótesis (general y específicas), discutir si fue aceptada o rechazada y las posibles explicaciones.

4. **Limitaciones del estudio**: Identificar las limitaciones metodológicas, de muestra o de contexto que podrían haber influido en los resultados.

5. **Implicaciones**: Describir las implicaciones teóricas y prácticas de los hallazgos."""


def _gen_conclusiones(topic: str, meta: dict) -> str:
    v1 = _parse_meta_variable(meta.get("variable_1", ""))
    v2 = _parse_meta_variable(meta.get("variable_2", ""))
    v1_name = v1.get("name") or "Variable 1"
    v2_name = v2.get("name") or "Variable 2"
    v2_dims = v2.get("dimensions") or []

    lines = [
        "## Conclusiones",
        "",
        "*[Esta sección se completará una vez finalizada la discusión.]*",
        "",
        "Las conclusiones deben responder directamente a los objetivos planteados:",
        "",
        f"1. **Conclusión general**: Respecto a la relación entre {v1_name} y {v2_name} en la muestra estudiada.",
        "",
    ]

    if v2_dims:
        for i, dim in enumerate(v2_dims, 1):
            lines.append(
                f"{i+1}. **Conclusión específica {i}**: Respecto a la relación entre "
                f"{v1_name} y {dim} de {v2_name}."
            )
            lines.append("")

    lines.append("Cada conclusión debe ser breve, directa y basada exclusivamente en los resultados obtenidos.")

    return "\n".join(lines)


def _gen_recomendaciones(topic: str, meta: dict) -> str:
    v1 = _parse_meta_variable(meta.get("variable_1", ""))
    v2 = _parse_meta_variable(meta.get("variable_2", ""))
    v1_name = v1.get("name") or "Variable 1"
    v2_name = v2.get("name") or "Variable 2"
    population = meta.get("population", "la población estudiada")

    return f"""## Recomendaciones

*[Esta sección se completará una vez formuladas las conclusiones.]*

Las recomendaciones deben organizarse en:

1. **Recomendaciones para la práctica**: Sugerencias específicas para {population} e instituciones involucradas, basadas en los hallazgos sobre {v1_name} y {v2_name}.

2. **Recomendaciones para futuras investigaciones**:
   - Ampliar la muestra a otros contextos o poblaciones.
   - Utilizar diseños experimentales o longitudinales.
   - Incorporar variables mediadoras o moderadoras.
   - Emplear instrumentos adicionales o métodos mixtos.

3. **Recomendaciones metodológicas**: Sugerencias para mejorar los procesos de medición e investigación en el campo."""


# ---------------------------------------------------------------------------
# Public dispatcher
# ---------------------------------------------------------------------------

_GENERATORS = {
    "resultados_placeholder": _gen_resultados,
    "discusion_placeholder": _gen_discusion,
    "conclusiones_placeholder": _gen_conclusiones,
    "recomendaciones_placeholder": _gen_recomendaciones,
}


def generate_placeholder(section_key: str, topic: str, meta: dict) -> str:
    """Dispatch to the appropriate placeholder generator.

    Returns the generated markdown string.
    """
    gen = _GENERATORS.get(section_key)
    if gen is None:
        return ""
    return gen(topic, meta or {})
