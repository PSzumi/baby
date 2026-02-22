"""
review_cmd.py — Phase 2.5: Interactive source review and curation.

Displays all fetched sources in a ranked table and lets the user
include/exclude sources before the scaffold phase.

Optionally asks Claude to identify coverage gaps and suggest
additional search queries.
"""

import os
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt

from research_cli.database import (
    get_topic,
    get_all_sources,
    get_included_sources,
    toggle_source_inclusion,
    get_source_by_id,
    update_phase,
)
from research_cli.llm_client import call_claude

console = Console()


def _display_sources_table(sources: list[dict]) -> None:
    """Display sources in a Rich table."""
    table = Table(title="Fetched Sources (ranked by quality)", show_lines=True)
    table.add_column("#", style="dim", width=4)
    table.add_column("Title", max_width=45)
    table.add_column("Year", width=6)
    table.add_column("Cites", width=6, justify="right")
    table.add_column("Relevance", width=10, justify="right")
    table.add_column("Full Text", width=10, justify="center")
    table.add_column("Included", width=9, justify="center")

    for s in sources:
        sid = s["id"]
        title = (s.get("title") or "Untitled")[:45]
        year = s.get("year", "?")
        cites = str(s.get("citation_count", 0))
        rel = f"{s.get('relevance_score', 0):.2f}"
        ft = "[green]Yes[/green]" if s.get("full_text_path") else "[dim]No[/dim]"
        inc = "[green]Yes[/green]" if s.get("included") else "[red]No[/red]"

        table.add_row(str(sid), title, year, cites, rel, ft, inc)

    console.print(table)


def _check_coverage_gaps(topic: str, sources: list[dict]) -> str:
    """Ask Claude to identify coverage gaps in the source pool."""
    source_list = []
    for s in sources:
        source_list.append(
            f"- \"{s.get('title', 'Untitled')}\" ({s.get('year', '?')}) "
            f"[{s.get('origin', '?')}] — {(s.get('abstract') or '')[:150]}..."
        )

    prompt = f"""Analyze this source pool for an academic thesis on: "{topic}"

**Included Sources ({len(sources)}):**
{chr(10).join(source_list)}

Identify:
1. Are there obvious topical gaps? (aspects of the topic not covered)
2. Is there geographic or methodological diversity?
3. Are there enough recent sources (last 2-3 years)?
4. Suggest 3-5 specific search queries to fill any gaps.

Be concise. Format as bullet points.
"""

    return call_claude(prompt, max_tokens=1024)


def run(project_name: str, auto_approve: bool = False) -> None:
    """Execute the review phase."""

    topic = get_topic(project_name)
    if not topic:
        console.print("[red]No topic found. Run 'research-cli init' first.[/red]")
        raise SystemExit(1)

    sources = get_all_sources(project_name)
    if not sources:
        console.print("[red]No sources found. Run 'research-cli fetch-data' first.[/red]")
        raise SystemExit(1)

    if auto_approve:
        console.print(f"[yellow]Auto-approving all {len(sources)} sources.[/yellow]")
        update_phase(project_name, "review")
        return

    # Display the sources table
    _display_sources_table(sources)

    # Interactive loop
    console.print("\n[bold]Commands:[/bold]")
    console.print("  [cyan]<number>[/cyan]  — Toggle include/exclude for a source")
    console.print("  [cyan]info <n>[/cyan] — Show full abstract for source #n")
    console.print("  [cyan]gaps[/cyan]     — Ask Claude to check for coverage gaps")
    console.print("  [cyan]done[/cyan]     — Proceed to scaffold phase\n")

    while True:
        cmd = Prompt.ask("[bold]review>[/bold]", default="done")
        cmd = cmd.strip().lower()

        if cmd == "done":
            break
        elif cmd == "gaps":
            console.print("\n[bold]Checking coverage gaps...[/bold]")
            included = get_included_sources(project_name)
            analysis = _check_coverage_gaps(topic, included)
            console.print(analysis)
            console.print()
        elif cmd.startswith("info "):
            try:
                sid = int(cmd.split()[1])
                source = get_source_by_id(project_name, sid)
                if source:
                    console.print(f"\n[bold]{source.get('title', 'Untitled')}[/bold]")
                    console.print(f"Authors: {source.get('authors', 'N/A')}")
                    console.print(f"Year: {source.get('year', 'N/A')}")
                    console.print(f"DOI: {source.get('doi', 'N/A')}")
                    console.print(f"Journal: {source.get('journal', 'N/A')}")
                    console.print(f"\n{source.get('abstract', 'No abstract available.')}\n")
                else:
                    console.print(f"[red]Source #{sid} not found.[/red]")
            except (ValueError, IndexError):
                console.print("[red]Usage: info <source_number>[/red]")
        else:
            try:
                sid = int(cmd)
                new_state = toggle_source_inclusion(project_name, sid)
                state_str = "[green]included[/green]" if new_state else "[red]excluded[/red]"
                source = get_source_by_id(project_name, sid)
                title = (source.get("title", "?") if source else "?")[:50]
                console.print(f"  Source #{sid} ({title}): {state_str}")
            except ValueError:
                console.print("[red]Unknown command. Type 'done' to proceed.[/red]")

    # Summary
    included = get_included_sources(project_name)
    console.print(f"\n[bold green]{len(included)} sources included for thesis generation.[/bold green]")

    update_phase(project_name, "review")
    console.print(f"[dim]Next: research-cli scaffold {project_name}[/dim]")
