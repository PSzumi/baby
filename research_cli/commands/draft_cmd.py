"""
draft_cmd.py — Phase 4: Section-by-section full prose generation.

Flow:
    1. Load section plans from database.
    2. Write each section independently with its assigned sources.
    3. Validate citations per-section.
    4. Assemble complete draft.
    5. Generate References section programmatically (never via LLM).
    6. Run post-processor quality checks.
    7. Save as versioned output.
"""

import os
from rich.console import Console

from research_cli.database import (
    get_topic,
    get_current_version,
    update_phase,
)
from research_cli.citations.bibdb import get_inline_citation_map
from research_cli.generation.section_writer import write_all_sections
from research_cli.generation.post_processor import post_process

console = Console()


def run(project_name: str) -> None:
    """Execute the draft phase."""

    topic = get_topic(project_name)
    if not topic:
        console.print("[red]No topic found. Run 'research-cli init' first.[/red]")
        raise SystemExit(1)

    # Get citation map
    citation_map = get_inline_citation_map(project_name)
    if not citation_map:
        console.print("[red]No bibliography entries. Run 'research-cli fetch-data' first.[/red]")
        raise SystemExit(1)

    console.print(f"[bold]Generating thesis draft for:[/bold] {topic}")
    console.print(f"  {len(citation_map)} citation keys available\n")

    # Write all sections
    console.print("[bold]Writing sections...[/bold]")
    draft_body = write_all_sections(project_name, topic, citation_map)

    # Post-process
    console.print("\n[bold]Running quality checks...[/bold]")
    result = post_process(project_name, draft_body)

    # Report
    report = result["citation_report"]
    console.print(f"  Total words: {result['total_words']}")
    console.print(f"  Citations matched: {len(report.matched)}")

    if report.orphan_citations:
        console.print(f"  [yellow]Orphan citations: {len(report.orphan_citations)}[/yellow]")
        for c in report.orphan_citations[:5]:
            console.print(f"    - {c}")
    if report.uncited_entries:
        console.print(f"  [yellow]Uncited bibliography entries: {len(report.uncited_entries)}[/yellow]")

    for warning in result["word_count_warnings"]:
        console.print(f"  [yellow]{warning}[/yellow]")

    # Save output
    version = get_current_version(project_name)
    output_dir = os.path.join("projects", project_name, "outputs", f"v{version}")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "final_draft.md")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(result["draft"])

    update_phase(project_name, "draft")

    console.print(f"\n[bold green]Draft saved:[/bold green] {output_path}")
    console.print(f"[dim]Next: research-cli present {project_name}[/dim]")
