"""
validator.py — Validate inline citations against the bibliography.

Checks:
    1. Every inline (Author, Year) citation has a matching bibliography entry.
    2. Every bibliography entry is cited at least once in the text.
    3. Reports orphan citations, uncited entries, and potential mismatches.
"""

import re
from dataclasses import dataclass, field


@dataclass
class ValidationReport:
    """Results of citation validation."""
    matched: list[str] = field(default_factory=list)
    orphan_citations: list[str] = field(default_factory=list)  # in text but not in bibliography
    uncited_entries: list[str] = field(default_factory=list)    # in bibliography but not cited
    warnings: list[str] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return not self.orphan_citations and not self.uncited_entries

    def summary(self) -> str:
        lines = [f"Citations matched: {len(self.matched)}"]
        if self.orphan_citations:
            lines.append(f"Orphan citations (not in bibliography): {len(self.orphan_citations)}")
            for c in self.orphan_citations:
                lines.append(f"  - {c}")
        if self.uncited_entries:
            lines.append(f"Uncited bibliography entries: {len(self.uncited_entries)}")
            for e in self.uncited_entries:
                lines.append(f"  - {e}")
        if self.warnings:
            lines.append(f"Warnings: {len(self.warnings)}")
            for w in self.warnings:
                lines.append(f"  - {w}")
        return "\n".join(lines)


# Pattern to match inline citations: (Author, Year) or (Author et al., Year)
# Also matches (Author & Author, Year)
_CITATION_PATTERN = re.compile(
    r"\(([A-Z][a-zA-Zà-ÿ\-']+(?:\s*(?:&|and)\s*[A-Z][a-zA-Zà-ÿ\-']+)?(?:\s+et\s+al\.)?),\s*(\d{4}[a-z]?)\)"
)


def extract_inline_citations(text: str) -> list[tuple[str, str]]:
    """
    Extract all inline citations from text.

    Returns list of (author_part, year) tuples.
    E.g., [("Smith", "2024"), ("Smith & Jones", "2023"), ("Chen et al.", "2022")]
    """
    matches = _CITATION_PATTERN.findall(text)
    return [(m[0].strip(), m[1].strip()) for m in matches]


def _normalize_citation(author_part: str, year: str) -> str:
    """Normalize a citation for comparison: lowercase, stripped."""
    return f"{author_part.lower().strip()}, {year}"


def validate_draft(
    draft_text: str,
    bibliography_entries: list[dict],
) -> ValidationReport:
    """
    Validate all inline citations in a draft against the bibliography.

    Parameters
    ----------
    draft_text : str
        The full draft text to check.
    bibliography_entries : list[dict]
        List of bibliography entries, each with keys:
        source_id, bibtex_key, apa_formatted, and source metadata.
    """
    report = ValidationReport()

    # Extract all inline citations from text
    inline_citations = extract_inline_citations(draft_text)

    # Build a lookup from bibliography entries
    # We need to match "(Smith, 2024)" against bibliography entries
    bib_lookup: dict[str, dict] = {}
    for entry in bibliography_entries:
        apa = entry.get("apa_formatted", "")
        key = entry.get("bibtex_key", "")
        # Extract author surname and year from bibtex_key pattern: smith2024
        # Also try to match from APA formatted string
        bib_lookup[key] = entry

    # Track which bib entries are cited
    cited_keys: set[str] = set()

    for author_part, year in inline_citations:
        citation_str = f"({author_part}, {year})"

        # Try to match against bibliography
        matched = False

        # Extract first author surname from the citation
        first_author = author_part.split("&")[0].split(" et al.")[0].strip().lower()

        for key, entry in bib_lookup.items():
            # Match: bibtex_key starts with author surname and contains year
            key_lower = key.lower()
            if first_author in key_lower and year in key_lower:
                report.matched.append(citation_str)
                cited_keys.add(key)
                matched = True
                break

        if not matched:
            # Try fuzzy: check if the APA string contains both author and year
            for key, entry in bib_lookup.items():
                apa = entry.get("apa_formatted", "").lower()
                if first_author in apa and year in apa:
                    report.matched.append(citation_str)
                    cited_keys.add(key)
                    matched = True
                    break

        if not matched:
            report.orphan_citations.append(citation_str)

    # Check for uncited bibliography entries
    for key, entry in bib_lookup.items():
        if key not in cited_keys:
            apa = entry.get("apa_formatted", key)
            report.uncited_entries.append(apa[:100])

    return report
