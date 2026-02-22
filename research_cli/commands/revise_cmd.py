"""
revise_cmd.py — Phase 6: Feedback-driven revision.

Two modes:
    Without --apply: Parse feedback, analyse gaps, produce revision_plan.md
    With --apply:    Execute the plan — re-fetch, surgically rewrite sections,
                     save as a new version
"""

import os
from rich.console import Console
from rich.panel import Panel

from research_cli.database import (
    get_topic,
    get_current_version,
    get_sections,
    get_sources_for_section,
    increment_version,
    update_section_draft,
    update_phase,
    get_all_bib_entries,
)
from research_cli.revision.feedback_parser import parse_feedback
from research_cli.revision.gap_analyzer import analyze_gaps
from research_cli.revision.surgical_editor import revise_section
from research_cli.citations.bibdb import get_inline_citation_map
from research_cli.generation.post_processor import post_process

console = Console()


def run(project_name: str, feedback_path: str, apply_revisions: bool = False) -> None:
    """Execute the revise phase."""

    # Load current draft
    version = get_current_version(project_name)
    draft_path = os.path.join(
        "projects", project_name, "outputs", f"v{version}", "final_draft.md"
    )
    if not os.path.isfile(draft_path):
        console.print("[red]final_draft.md not found. Run 'research-cli draft' first.[/red]")
        raise SystemExit(1)

    with open(draft_path, "r", encoding="utf-8") as f:
        draft = f.read()

    # Load feedback
    if not os.path.isfile(feedback_path):
        console.print(f"[red]Feedback file not found: {feedback_path}[/red]")
        raise SystemExit(1)

    with open(feedback_path, "r", encoding="utf-8") as f:
        feedback_text = f.read()

    topic = get_topic(project_name) or "(unknown topic)"

    # Get section titles for feedback mapping
    sections = get_sections(project_name, version)
    section_titles = [s.get("section_title", s.get("section_key", "")) for s in sections]

    # Step 1: Parse feedback
    console.print("\n[bold]Parsing feedback...[/bold]")
    feedback_items = parse_feedback(project_name, feedback_text, feedback_path, section_titles)
    console.print(f"  {len(feedback_items)} feedback items identified")

    for item in feedback_items:
        severity = item.get("severity", "minor")
        color = {"critical": "red", "major": "yellow", "minor": "dim"}.get(severity, "white")
        console.print(
            f"  [{color}][{severity.upper()}][/{color}] "
            f"{item.get('target_section', 'general')}: {item.get('item_text', '')[:80]}"
        )

    # Step 2: Analyse gaps
    console.print("\n[bold]Analysing gaps...[/bold]")
    plan = analyze_gaps(feedback_items, draft, topic)

    console.print(Panel(plan.get("summary", ""), title="Revision Summary", border_style="yellow"))

    # Save revision plan
    output_dir = os.path.join("projects", project_name, "outputs", f"v{version}")
    plan_path = os.path.join(output_dir, "revision_plan.md")

    with open(plan_path, "w", encoding="utf-8") as f:
        f.write(f"# Revision Plan (v{version})\n\n")
        f.write(f"## Summary\n{plan.get('summary', '')}\n\n")
        f.write("## Actions\n")
        for action in plan.get("actions", []):
            f.write(
                f"- **[P{action.get('priority', '?')}] {action.get('action_type', '?')}** "
                f"— {action.get('section', '?')}: {action.get('description', '')}\n"
            )
        f.write("\n## Suggested New Queries\n")
        for query in plan.get("new_queries", []):
            f.write(f"- {query}\n")

    console.print(f"  Revision plan saved: {plan_path}")

    if not apply_revisions:
        console.print(
            "\n[dim]To apply revisions automatically, re-run with --apply flag.[/dim]"
        )
        return

    # ── Apply revisions ─────────────────────────────────────────────
    console.print("\n[bold]Applying revisions...[/bold]")

    # Increment version
    new_version = increment_version(project_name)
    new_output_dir = os.path.join("projects", project_name, "outputs", f"v{new_version}")
    os.makedirs(new_output_dir, exist_ok=True)

    citation_map = get_inline_citation_map(project_name)

    # Determine which sections need revision
    sections_to_revise = set()
    for action in plan.get("actions", []):
        section_name = action.get("section", "")
        if section_name:
            sections_to_revise.add(section_name)

    # Copy and revise sections
    revised_parts = []
    for section in sections:
        section_key = section.get("section_key", "")
        section_title = section.get("section_title", "")
        current_content = section.get("draft_content", "")

        if section_key == "references":
            continue

        # Check if this section needs revision
        needs_revision = any(
            section_title in sections_to_revise or section_key in sections_to_revise
            for _ in [None]
        )

        if needs_revision and current_content:
            # Get feedback items targeting this section
            section_feedback = [
                fi for fi in feedback_items
                if fi.get("target_section", "") in (section_title, section_key, "general")
            ]

            # Get any new sources for this section
            new_sources = get_sources_for_section(project_name, section_key)

            console.print(f"  Revising: {section_title}...")
            revised = revise_section(
                topic=topic,
                section_title=section_title,
                section_key=section_key,
                current_content=current_content,
                feedback_items=section_feedback,
                new_sources=new_sources,
                citation_map=citation_map,
            )

            # Save revised section
            update_section_draft(project_name, new_version, section_key, revised)
            revised_parts.append(revised)
        else:
            # Keep unchanged
            revised_parts.append(current_content)

    # Assemble and post-process
    draft_body = "\n\n---\n\n".join(p for p in revised_parts if p)
    result = post_process(project_name, draft_body)

    # Save
    output_path = os.path.join(new_output_dir, "final_draft.md")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(result["draft"])

    update_phase(project_name, "revise")

    console.print(f"\n[bold green]Revised draft saved:[/bold green] {output_path}")
    console.print(f"  Version: v{new_version}")
    console.print(f"  Total words: {result['total_words']}")
