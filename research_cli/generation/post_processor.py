"""
post_processor.py — Post-processing and quality checks for generated drafts.

Checks:
    1. Citation consistency (every inline citation has a reference entry)
    2. Source coverage (every included source is cited at least once)
    3. Section word counts (flag thin or bloated sections)
    4. Programmatic reference list generation
"""

import os
import re

from research_cli.database import (
    get_all_bib_entries,
    get_included_sources,
    get_sections,
    get_current_version,
)
from research_cli.citations.validator import validate_draft, ValidationReport
from research_cli.citations.formatter import format_apa7


def generate_references_section(project_name: str) -> str:
    """
    Generate the References section programmatically from the bibliography table.

    This is NEVER done by Claude — references are built from real CrossRef data.
    """
    entries = get_all_bib_entries(project_name)
    if not entries:
        return "# References\n\nNo bibliography entries found."

    # Sort by APA formatted string (alphabetical by first author)
    sorted_entries = sorted(entries, key=lambda e: e.get("apa_formatted", "").lower())

    lines = ["# References\n"]
    for entry in sorted_entries:
        apa = entry.get("apa_formatted", "")
        if apa:
            lines.append(apa)
            lines.append("")  # blank line between entries

    return "\n".join(lines)


def check_section_word_counts(project_name: str) -> list[str]:
    """Check word counts per section and flag issues."""
    version = get_current_version(project_name)
    sections = get_sections(project_name, version)
    warnings = []

    for section in sections:
        key = section.get("section_key", "")
        if key == "references":
            continue
        wc = section.get("word_count", 0)
        title = section.get("section_title", key)

        if wc < 150:
            warnings.append(f"Section '{title}' is thin ({wc} words)")
        elif wc > 2000:
            warnings.append(f"Section '{title}' may be too long ({wc} words)")

    return warnings


def post_process(project_name: str, draft_text: str) -> dict:
    """
    Run all quality checks on a completed draft.

    Returns a dict with:
        draft: the final draft text with references appended
        citation_report: ValidationReport
        word_count_warnings: list of warnings
        total_words: total word count
    """
    # 1. Generate references section
    references = generate_references_section(project_name)

    # 2. Combine draft with references
    full_draft = draft_text + "\n\n---\n\n" + references

    # 3. Citation validation
    bib_entries = get_all_bib_entries(project_name)
    citation_report = validate_draft(full_draft, bib_entries)

    # 4. Word count checks
    word_count_warnings = check_section_word_counts(project_name)

    # 5. Total word count
    total_words = len(draft_text.split())

    return {
        "draft": full_draft,
        "citation_report": citation_report,
        "word_count_warnings": word_count_warnings,
        "total_words": total_words,
    }
