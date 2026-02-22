"""
surgical_editor.py — Targeted section rewrites addressing specific feedback.

Revises individual sections without touching the rest of the draft.
New sources can be incorporated during revision.
"""

from research_cli.llm_client import call_claude
from research_cli.content.summarizer import prepare_source_for_context


def revise_section(
    topic: str,
    section_title: str,
    section_key: str,
    current_content: str,
    feedback_items: list[dict],
    new_sources: list[dict],
    citation_map: dict[int, str],
) -> str:
    """
    Rewrite a specific section addressing feedback.

    Parameters
    ----------
    topic : str
        The thesis topic.
    section_title : str
        Title of the section being revised.
    section_key : str
        Section key for source context preparation.
    current_content : str
        The current draft text of this section.
    feedback_items : list[dict]
        Feedback items targeting this section.
    new_sources : list[dict]
        Any newly fetched sources to incorporate.
    citation_map : dict[int, str]
        source_id -> inline citation string.

    Returns
    -------
    str
        The revised section text.
    """
    # Format feedback
    feedback_lines = []
    for item in feedback_items:
        severity = item.get("severity", "minor").upper()
        text = item.get("item_text", "")
        feedback_lines.append(f"  [{severity}] {text}")
    feedback_text = "\n".join(feedback_lines)

    # Prepare new source material
    source_blocks = []
    cite_instructions = []
    for source in new_sources:
        sid = source["id"]
        cite_str = citation_map.get(sid, f"(Source {sid})")
        block = prepare_source_for_context(source, section_key, topic)
        source_blocks.append(block)
        cite_instructions.append(f"  Source ID {sid}: Cite as {cite_str}")

    new_sources_text = "\n\n".join(source_blocks) if source_blocks else "(No new sources)"
    cite_text = "\n".join(cite_instructions) if cite_instructions else "(No new citations)"

    prompt = f"""Revise this section of an academic thesis to address colleague feedback.

**Topic:** {topic}
**Section:** {section_title}

**Current Section Text:**
{current_content}

**Feedback to Address:**
{feedback_text}

**New Sources Available (if any):**
{new_sources_text}

**New Citation Instructions:**
{cite_text}

**RULES:**
1. Preserve parts of the section that are NOT criticized.
2. Address every feedback item marked CRITICAL or MAJOR.
3. Address MINOR items if they are easy to fix.
4. If new sources are provided, incorporate them naturally with citations.
5. Use EXACT citation strings from the instructions.
6. Maintain formal academic tone.
7. Do NOT remove existing valid citations.
8. Output the complete revised section with its heading.
"""

    return call_claude(prompt, max_tokens=4096, temperature=0.3)
