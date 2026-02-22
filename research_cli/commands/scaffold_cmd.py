"""
scaffold_cmd.py — Phase 3: Section planning and scaffold generation.

Flow:
    1. Load included sources and bibliography.
    2. Use Claude to create a section plan (JSON) mapping sources to sections.
    3. Generate scaffold bullet points for each section.
    4. Save scaffold.md.
"""

import os
from rich.console import Console

from research_cli.database import (
    get_topic,
    get_included_sources,
    get_current_version,
    update_phase,
)
from research_cli.citations.bibdb import get_inline_citation_map
from research_cli.generation.planner import plan_sections, generate_scaffold, DEFAULT_OUTLINE

console = Console()


def run(project_name: str, template_path: str = "") -> None:
    """Execute the scaffold phase."""

    topic = get_topic(project_name)
    if not topic:
        console.print("[red]No topic found. Run 'research-cli init' first.[/red]")
        raise SystemExit(1)

    sources = get_included_sources(project_name)
    if not sources:
        console.print("[red]No included sources. Run 'research-cli fetch-data' and 'review' first.[/red]")
        raise SystemExit(1)

    # Load outline template
    outline = DEFAULT_OUTLINE
    if template_path and os.path.isfile(template_path):
        with open(template_path, "r", encoding="utf-8") as f:
            outline = f.read()
        console.print(f"[green]Using custom outline:[/green] {template_path}")
    else:
        console.print("[yellow]Using default academic outline.[/yellow]")

    # Get citation map
    citation_map = get_inline_citation_map(project_name)
    console.print(f"  {len(citation_map)} citation keys available")

    # Step 1: Plan sections
    console.print("\n[bold]Planning sections...[/bold]")
    section_plans = plan_sections(project_name, topic, sources, outline)

    # Step 2: Generate scaffold
    console.print("[bold]Generating scaffold...[/bold]")
    scaffold = generate_scaffold(project_name, topic, section_plans, sources, citation_map)

    # Save output
    version = get_current_version(project_name)
    output_dir = os.path.join("projects", project_name, "outputs", f"v{version}")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "scaffold.md")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(scaffold)

    update_phase(project_name, "scaffold")

    console.print(f"\n[bold green]Scaffold saved:[/bold green] {output_path}")
    console.print(f"  {len(section_plans)} sections planned")
    console.print(f"  {len(sources)} sources mapped to sections")
    console.print(f"[dim]Next: research-cli draft {project_name}[/dim]")
