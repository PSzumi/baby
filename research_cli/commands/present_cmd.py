"""
present_cmd.py — Phase 5: Presentation materials generation.

Generates:
    a. 1-page Executive Summary
    b. Slide Deck outline (10-12 slides)
    c. Q&A Defense Guide (8-10 anticipated questions)
"""

import os
from rich.console import Console

from research_cli.database import get_topic, get_current_version, update_phase
from research_cli.llm_client import call_claude

console = Console()


def run(project_name: str) -> None:
    """Execute the presentation phase."""

    # Find the latest draft
    version = get_current_version(project_name)
    draft_path = os.path.join(
        "projects", project_name, "outputs", f"v{version}", "final_draft.md"
    )
    if not os.path.isfile(draft_path):
        console.print("[red]final_draft.md not found. Run 'research-cli draft' first.[/red]")
        raise SystemExit(1)

    with open(draft_path, "r", encoding="utf-8") as f:
        draft = f.read()

    topic = get_topic(project_name) or "(unknown topic)"

    prompt = f"""Based on the following completed research paper, generate
three presentation deliverables.

**Topic:** {topic}

**FULL DRAFT:**
{draft}

Generate the following three sections in a single Markdown document:

---

# 1. EXECUTIVE SUMMARY (~400 words)
- Research objective and significance
- Methodology overview
- Key findings (3-5 bullet points)
- Primary recommendations
- Limitations and future research

# 2. SLIDE DECK OUTLINE (10-12 slides)
For each slide:
- **Slide title**
- **Key points** (3-4 bullets)
- **Speaker notes** (1-2 sentences)

Structure: Title -> Problem -> Literature -> Methodology -> Findings (3 slides) ->
Analysis -> Discussion -> Recommendations -> Limitations -> Q&A

# 3. Q&A DEFENSE GUIDE (8-10 questions)
For each:
- The anticipated question
- Suggested response (2-3 sentences grounded in the paper's data)
- Which section/source to reference

---

Output in clean Markdown.
"""

    console.print("\n[bold]Generating presentation materials...[/bold]")
    result = call_claude(prompt, max_tokens=8192)

    output_dir = os.path.join("projects", project_name, "outputs", f"v{version}")
    output_path = os.path.join(output_dir, "presentation_guide.md")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(result)

    update_phase(project_name, "present")

    console.print(f"\n[bold green]Presentation guide saved:[/bold green] {output_path}")
    console.print(
        f"[dim]Next (optional): research-cli revise {project_name} "
        f"--feedback path/to/feedback.txt[/dim]"
    )
