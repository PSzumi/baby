"""
gap_analyzer.py — Map feedback to sections and determine revision actions.

Classifies each feedback item into an action type:
    REWRITE: section needs significant prose changes
    ADD_SOURCES: need additional research
    RESTRUCTURE: section ordering or outline changes
    CITATION_FIX: citation accuracy issues
    STYLE: tone, formatting, wording adjustments
"""

from research_cli.llm_client import call_claude_json


def analyze_gaps(
    feedback_items: list[dict],
    draft_text: str,
    topic: str,
) -> dict:
    """
    Analyze gaps between feedback and the current draft.

    Returns a revision plan dict with:
        actions: list of {section, action_type, description, priority}
        new_queries: list of suggested search queries for data gaps
        summary: human-readable summary
    """
    # Format feedback for the prompt
    feedback_lines = []
    for item in feedback_items:
        feedback_lines.append(
            f"- [{item.get('severity', 'minor').upper()}] "
            f"Section: {item.get('target_section', 'general')} — "
            f"{item.get('item_text', '')}"
        )
    feedback_text = "\n".join(feedback_lines)

    prompt = f"""Analyze this academic paper against colleague feedback and produce a revision plan.

**Topic:** {topic}

**Current Draft:**
{draft_text[:15000]}

**Structured Feedback:**
{feedback_text}

Return a JSON object with:

1. "actions": array of revision actions, each with:
   - "section": which section to modify
   - "action_type": one of "REWRITE", "ADD_SOURCES", "RESTRUCTURE", "CITATION_FIX", "STYLE"
   - "description": what specifically needs to change
   - "priority": 1 (highest) to 5 (lowest)

2. "new_queries": array of 3-5 specific search queries to run if additional
   data sourcing is needed (empty array if not needed)

3. "summary": a 2-3 sentence human-readable summary of the revision scope

Sort actions by priority (1 first).
"""

    plan = call_claude_json(prompt, max_tokens=4096, temperature=0.1)

    # Ensure required keys exist
    plan.setdefault("actions", [])
    plan.setdefault("new_queries", [])
    plan.setdefault("summary", "No revision analysis available.")

    return plan
