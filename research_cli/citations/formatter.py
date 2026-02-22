"""
formatter.py — APA 7th edition citation formatting.

Produces both:
    - Full reference list entries (e.g. for the References section)
    - Inline citation strings (e.g. "(Smith & Jones, 2024)")

All formatting is done from structured data (CrossRef metadata),
never by the LLM.
"""


def _format_author_apa(author: dict) -> str:
    """
    Format a single author in APA style: Family, G. I.

    Handles cases where only 'name' is available (no given/family split).
    """
    family = author.get("family", "")
    given = author.get("given", "")

    if family and given:
        # Initials from given name
        initials = " ".join(f"{part[0]}." for part in given.split() if part)
        return f"{family}, {initials}"
    elif family:
        return family
    elif author.get("name"):
        # Try to split "First Last" into initials
        parts = author["name"].split()
        if len(parts) >= 2:
            family = parts[-1]
            initials = " ".join(f"{p[0]}." for p in parts[:-1])
            return f"{family}, {initials}"
        return parts[0] if parts else "Unknown"
    return "Unknown"


def _format_authors_apa(authors: list[dict]) -> str:
    """Format the author list according to APA 7th edition rules."""
    if not authors:
        return "Unknown"

    formatted = [_format_author_apa(a) for a in authors]

    if len(formatted) == 1:
        return formatted[0]
    elif len(formatted) == 2:
        return f"{formatted[0]}, & {formatted[1]}"
    elif len(formatted) <= 20:
        return ", ".join(formatted[:-1]) + f", & {formatted[-1]}"
    else:
        # APA 7: list first 19, then ... then last
        return ", ".join(formatted[:19]) + f", ... {formatted[-1]}"


def format_apa7(bib_data: dict) -> str:
    """
    Format a complete APA 7th edition reference entry.

    Expected keys in bib_data:
        authors (list of dicts), year, title, journal, volume, issue,
        pages, doi, url, publisher
    """
    authors = bib_data.get("authors", [])
    year = bib_data.get("year", "n.d.")
    title = bib_data.get("title", "Untitled")
    journal = bib_data.get("journal", "")
    volume = bib_data.get("volume", "")
    issue = bib_data.get("issue", "")
    pages = bib_data.get("pages", "")
    doi = bib_data.get("doi", "")
    publisher = bib_data.get("publisher", "")

    # Author block
    author_str = _format_authors_apa(authors)

    # Year
    year_str = f"({year})" if year else "(n.d.)"

    # Title (sentence case — APA requires it, but we keep original case
    # since we're working with real metadata)
    title_str = title.rstrip(".")

    parts = [f"{author_str} {year_str}. {title_str}."]

    # Journal article format
    if journal:
        journal_part = f"*{journal}*"
        if volume:
            journal_part += f", *{volume}*"
            if issue:
                journal_part += f"({issue})"
        if pages:
            journal_part += f", {pages}"
        journal_part += "."
        parts.append(journal_part)
    elif publisher:
        parts.append(f"{publisher}.")

    # DOI
    if doi:
        parts.append(f"https://doi.org/{doi}")

    return " ".join(parts)


def format_inline_citation(authors: list[dict], year: str) -> str:
    """
    Format an inline citation: (Author, Year)

    Rules:
        1 author:  (Smith, 2024)
        2 authors: (Smith & Jones, 2024)
        3+ authors: (Smith et al., 2024)
    """
    if not authors:
        return f"(Unknown, {year})"

    # Get family names
    names = []
    for a in authors:
        family = a.get("family", "")
        if not family and a.get("name"):
            parts = a["name"].split()
            family = parts[-1] if parts else "Unknown"
        names.append(family or "Unknown")

    if len(names) == 1:
        return f"({names[0]}, {year})"
    elif len(names) == 2:
        return f"({names[0]} & {names[1]}, {year})"
    else:
        return f"({names[0]} et al., {year})"
