"""
feedback_parser.py — Parse free-form colleague feedback into structured items.

Uses Claude to extract individual actionable items from feedback text,
categorize them by severity, and map them to thesis sections.
"""

from research_cli.llm_client import call_claude_json
from research_cli.database import save_feedback_item


def parse_feedback(
    project_name: str,
    feedback_text: str,
    feedback_file: str,
    section_titles: list[str],
) -> list[dict]:
    """
    Parse free-form feedback into structured, actionable items.

    Parameters
    ----------
    project_name : str
        The project name.
    feedback_text : str
        Raw feedback text from colleagues.
    feedback_file : str
        Path to the feedback file (for auditing).
    section_titles : list[str]
        List of section titles in the thesis, used for mapping.

    Returns
    -------
    list[dict]
        List of parsed feedback items with keys:
        item_text, target_section, severity
    """
    sections_str = "\n".join(f"  - {t}" for t in section_titles)

    prompt = f"""Parse this colleague feedback into individual actionable items.

**Thesis sections:**
{sections_str}

**Feedback:**
{feedback_text}

For each item, return a JSON array of objects with:
- "item_text": the specific criticism or suggestion (1-2 sentences)
- "target_section": which thesis section this applies to (use exact section title from above, or "general" if it applies broadly)
- "severity": "critical" (fundamental flaw), "major" (significant gap), or "minor" (style/polish)

Return ONLY the JSON array.
"""

    items = call_claude_json(prompt, max_tokens=2048, temperature=0.1)

    # Store in database
    result = []
    for item in items:
        fid = save_feedback_item(
            project_name,
            feedback_file=feedback_file,
            item_text=item.get("item_text", ""),
            target_section=item.get("target_section", "general"),
            severity=item.get("severity", "minor"),
        )
        item["id"] = fid
        result.append(item)

    return result
