"""
bibdb.py — BibTeX database management.

Builds BibTeX entries from CrossRef data and manages the citation key
namespace. Citation keys are generated as "authorfamily2024" with
disambiguation suffixes (a, b, c) for collisions.
"""

import json
import os
import re

from research_cli.database import (
    get_sources_with_doi,
    get_source_by_id,
    save_bib_entry,
    get_all_bib_entries,
    get_bib_entry,
)
from research_cli.sources.crossref import enrich_by_doi
from research_cli.citations.formatter import format_apa7, format_inline_citation


def _generate_bibtex_key(authors: list[dict], year: str, existing_keys: set[str]) -> str:
    """
    Generate a unique BibTeX key from author surname and year.

    Format: lastname2024, lastname2024a, lastname2024b, etc.
    """
    # Get first author's family name
    if authors:
        family = authors[0].get("family", "")
        if not family:
            # Try to extract from "name" field
            name = authors[0].get("name", "unknown")
            parts = name.split()
            family = parts[-1] if parts else "unknown"
    else:
        family = "unknown"

    # Clean the name: lowercase, ascii only
    clean = re.sub(r"[^a-z]", "", family.lower())
    if not clean:
        clean = "unknown"

    base_key = f"{clean}{year}"

    if base_key not in existing_keys:
        return base_key

    # Disambiguate with suffix
    for suffix_char in "abcdefghijklmnopqrstuvwxyz":
        candidate = f"{base_key}{suffix_char}"
        if candidate not in existing_keys:
            return candidate

    return f"{base_key}_{len(existing_keys)}"


def _format_bibtex_entry(key: str, bib_type: str, data: dict) -> str:
    """Format a BibTeX entry string."""
    fields = []

    field_map = {
        "title": data.get("title", ""),
        "author": " and ".join(
            f"{a.get('family', '')}{{,}} {a.get('given', '')}"
            for a in data.get("authors", [])
        ),
        "year": data.get("year", ""),
        "journal": data.get("journal", ""),
        "volume": data.get("volume", ""),
        "number": data.get("issue", ""),
        "pages": data.get("pages", ""),
        "publisher": data.get("publisher", ""),
        "doi": data.get("doi", ""),
        "url": data.get("url", ""),
    }

    for field_name, value in field_map.items():
        if value:
            # Escape special LaTeX characters in values
            escaped = value.replace("&", r"\&").replace("_", r"\_")
            fields.append(f"  {field_name} = {{{escaped}}}")

    fields_str = ",\n".join(fields)
    return f"@{bib_type}{{{key},\n{fields_str}\n}}"


def build_bibliography(project_name: str) -> int:
    """
    Build the bibliography database for all sources with DOIs.

    For each source:
        1. Fetch metadata from CrossRef
        2. Generate a unique BibTeX key
        3. Format BibTeX entry and APA reference
        4. Store in bibliography table

    Returns the number of entries created.
    """
    sources = get_sources_with_doi(project_name)
    if not sources:
        print("  No sources with DOIs found.")
        return 0

    # Collect existing keys to avoid collisions
    existing_entries = get_all_bib_entries(project_name)
    existing_keys = {e["bibtex_key"] for e in existing_entries}

    count = 0
    for source in sources:
        # Skip if already in bibliography
        if get_bib_entry(project_name, source["id"]):
            count += 1
            continue

        doi = source["doi"]

        # Fetch CrossRef metadata
        cr_data = enrich_by_doi(doi)

        if cr_data:
            authors = cr_data.get("authors", [])
            year = cr_data.get("year", source.get("year", ""))
            bib_type = cr_data.get("bibtex_type", "article")
        else:
            # Fall back to source's own metadata
            authors_raw = source.get("authors", "")
            if isinstance(authors_raw, str):
                try:
                    authors = json.loads(authors_raw)
                except (json.JSONDecodeError, TypeError):
                    authors = [{"name": authors_raw, "family": authors_raw.split()[-1] if authors_raw else "unknown"}]
            else:
                authors = authors_raw or []
            year = source.get("year", "")
            bib_type = "article"
            cr_data = {
                "title": source.get("title", ""),
                "authors": authors,
                "year": year,
                "journal": source.get("journal", ""),
                "volume": source.get("volume", ""),
                "issue": source.get("issue", ""),
                "pages": source.get("pages", ""),
                "doi": doi,
                "url": source.get("url", ""),
            }

        # Generate unique key
        key = _generate_bibtex_key(authors, year, existing_keys)
        existing_keys.add(key)

        # Format entries
        bibtex_raw = _format_bibtex_entry(key, bib_type, cr_data)
        apa_formatted = format_apa7(cr_data)

        # Save to DB
        save_bib_entry(
            project_name,
            source_id=source["id"],
            bibtex_key=key,
            bibtex_type=bib_type,
            bibtex_raw=bibtex_raw,
            apa_formatted=apa_formatted,
        )
        count += 1

    print(f"  Bibliography: {count} entries")
    return count


def export_bib_file(project_name: str, output_path: str) -> None:
    """Write all BibTeX entries to a .bib file."""
    entries = get_all_bib_entries(project_name)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        for entry in entries:
            f.write(entry["bibtex_raw"])
            f.write("\n\n")

    print(f"  Exported {len(entries)} entries to {output_path}")


def get_inline_citation_map(project_name: str) -> dict[int, str]:
    """
    Build a mapping of source_id -> inline citation string.

    Example: {3: "(Smith & Jones, 2024)", 7: "(Chen et al., 2023)"}
    """
    entries = get_all_bib_entries(project_name)
    citation_map = {}

    for entry in entries:
        source_id = entry["source_id"]
        source = get_source_by_id(project_name, source_id)
        if source:
            authors_raw = source.get("authors", "")
            if isinstance(authors_raw, str):
                try:
                    authors = json.loads(authors_raw)
                except (json.JSONDecodeError, TypeError):
                    authors = [{"name": authors_raw}]
            else:
                authors = authors_raw or []

            year = source.get("year", entry.get("year", ""))
            citation_map[source_id] = format_inline_citation(authors, year)

    return citation_map
