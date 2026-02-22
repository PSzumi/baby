"""
front_matter.py — Front matter sections for USIL thesis.

Generates:
  Dedicatoria  — placeholder template (user fills in)
  Agradecimiento — placeholder template (user fills in)
  Resumen — LLM-generated ~250-word Spanish summary + Palabras clave
  Abstract — LLM-generated English translation + Keywords
"""

from research_cli.llm_client import call_claude


FRONT_MATTER_SECTIONS = {
    "front_dedicatoria",
    "front_agradecimiento",
    "front_resumen",
    "front_abstract",
}


def is_front_matter(section_key: str) -> bool:
    """Return True if section_key is a front matter section."""
    return section_key in FRONT_MATTER_SECTIONS


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------

def _gen_dedicatoria(topic: str, meta: dict) -> str:
    return (
        "# Dedicatoria\n\n"
        "[Escriba aquí su dedicatoria personal. "
        "Ejemplo: A mis padres, por su apoyo incondicional...]"
    )


def _gen_agradecimiento(topic: str, meta: dict) -> str:
    return (
        "# Agradecimiento\n\n"
        "[Escriba aquí sus agradecimientos. "
        "Ejemplo: A mi asesor(a) de tesis, por su guía y orientación...]"
    )


def _gen_resumen(topic: str, meta: dict) -> str:
    """Generate ~250-word Spanish abstract via LLM."""
    from research_cli.generation.planner import (
        _parse_meta_variable,
        _parse_meta_methodology,
        _build_metadata_block,
    )

    meta_block = _build_metadata_block(meta)

    prompt = f"""Redacta el Resumen de una tesis académica USIL.

**Tema:** {topic}
{meta_block}

**Estructura requerida (un solo párrafo):**
1. Contexto y propósito de la investigación (2-3 oraciones)
2. Metodología empleada: tipo, diseño, muestra, instrumento (2-3 oraciones)
3. Principales resultados esperados (1-2 oraciones)
4. Conclusión general (1 oración)

**Formato final:**
# Resumen

[párrafo de ~250 palabras]

**Palabras clave:** [5-6 palabras clave separadas por comas]

**REGLAS:**
- Extensión: 200-300 palabras.
- Español formal académico, tercera persona.
- NO incluir citas bibliográficas en el resumen.
- Terminar con "Palabras clave:" en línea aparte.
"""

    return call_claude(prompt, max_tokens=1500, temperature=0.3)


def _gen_abstract(topic: str, meta: dict) -> str:
    """Generate English abstract via LLM."""
    from research_cli.generation.planner import (
        _parse_meta_variable,
        _parse_meta_methodology,
        _build_metadata_block,
    )

    meta_block = _build_metadata_block(meta)

    prompt = f"""Write the Abstract for a USIL academic thesis (English translation of the Resumen).

**Topic:** {topic}
{meta_block}

**Required structure (single paragraph):**
1. Context and research purpose (2-3 sentences)
2. Methodology: type, design, sample, instrument (2-3 sentences)
3. Expected main results (1-2 sentences)
4. General conclusion (1 sentence)

**Final format:**
# Abstract

[paragraph of ~250 words]

**Keywords:** [5-6 keywords separated by commas]

**RULES:**
- Length: 200-300 words.
- Formal academic English, third person.
- Do NOT include bibliographic citations.
- End with "Keywords:" on a separate line.
"""

    return call_claude(prompt, max_tokens=1500, temperature=0.3)


# ---------------------------------------------------------------------------
# Public dispatcher
# ---------------------------------------------------------------------------

_GENERATORS = {
    "front_dedicatoria": _gen_dedicatoria,
    "front_agradecimiento": _gen_agradecimiento,
    "front_resumen": _gen_resumen,
    "front_abstract": _gen_abstract,
}


def generate_front_matter(section_key: str, topic: str, meta: dict) -> str:
    """Dispatch to the appropriate front matter generator.

    Returns the generated markdown string.
    """
    gen = _GENERATORS.get(section_key)
    if gen is None:
        return ""
    return gen(topic, meta or {})
