"""
main.py — CLI entry point for research-cli v2.

8 commands mapping to the research workflow:
    init        -> Phase 1:   Project setup + topic generation
    fetch-data  -> Phase 2:   5-API data acquisition pipeline
    review      -> Phase 2.5: Interactive source curation
    scaffold    -> Phase 3:   Section planning + outline population
    draft       -> Phase 4:   Section-by-section prose generation
    present     -> Phase 5:   Executive summary, slides, Q&A guide
    revise      -> Phase 6:   Feedback analysis + executable revisions
    status      -> Utility:   Show project state
"""

import typer

app = typer.Typer(
    name="research-cli",
    help="Automated academic thesis generation from real research data.",
    add_completion=False,
)


# ── Phase 1: init ──────────────────────────────────────────────────────

@app.command()
def init(
    project_name: str = typer.Argument(..., help="Name for the new research project."),
    context: str = typer.Option("", "--context", "-c", help="Academic discipline."),
    location: str = typer.Option("", "--location", "-l", help="Geographic focus."),
) -> None:
    """Phase 1: Create a project and generate thesis topics."""
    from research_cli.commands.init_cmd import run
    run(project_name, context=context, location=location)


# ── Phase 2: fetch-data ───────────────────────────────────────────────

@app.command("fetch-data")
def fetch_data(
    project_name: str = typer.Argument(..., help="Existing project name."),
    email: str = typer.Option("", "--email", "-e", help="Email for Unpaywall API (enables PDF downloads)."),
    skip_fulltext: bool = typer.Option(False, "--skip-fulltext", help="Skip PDF downloads."),
    max_sources: int = typer.Option(40, "--max-sources", help="Max sources to keep after dedup."),
    sources: str = typer.Option("", "--sources", "-s", help="Comma-separated list of sources (e.g. 'semantic_scholar,pubmed,scielo'). Default: all enabled."),
) -> None:
    """Phase 2: Fetch academic sources from up to 8 databases (Semantic Scholar, OpenAlex, arXiv, PubMed, CORE, Europe PMC, SciELO, DOAJ)."""
    from research_cli.commands.fetch_cmd import run
    run(project_name, skip_fulltext=skip_fulltext, max_sources=max_sources, email=email, sources_filter=sources)


# ── Phase 2.5: review ─────────────────────────────────────────────────

@app.command()
def review(
    project_name: str = typer.Argument(..., help="Existing project name."),
    auto: bool = typer.Option(False, "--auto", help="Skip interactive review, include all sources."),
) -> None:
    """Phase 2.5: Interactively review and curate fetched sources."""
    from research_cli.commands.review_cmd import run
    run(project_name, auto_approve=auto)


# ── Phase 3: scaffold ─────────────────────────────────────────────────

@app.command()
def scaffold(
    project_name: str = typer.Argument(..., help="Existing project name."),
    template: str = typer.Option("", "--template", "-t", help="Path to a custom outline file."),
) -> None:
    """Phase 3: Plan sections and generate a research scaffold."""
    from research_cli.commands.scaffold_cmd import run
    run(project_name, template_path=template)


# ── Phase 4: draft ────────────────────────────────────────────────────

@app.command()
def draft(
    project_name: str = typer.Argument(..., help="Existing project name."),
) -> None:
    """Phase 4: Generate the full thesis paper section-by-section."""
    from research_cli.commands.draft_cmd import run
    run(project_name)


# ── Phase 5: present ──────────────────────────────────────────────────

@app.command()
def present(
    project_name: str = typer.Argument(..., help="Existing project name."),
) -> None:
    """Phase 5: Generate executive summary, slide deck, and Q&A defense guide."""
    from research_cli.commands.present_cmd import run
    run(project_name)


# ── Phase 6: revise ───────────────────────────────────────────────────

@app.command()
def revise(
    project_name: str = typer.Argument(..., help="Existing project name."),
    feedback: str = typer.Option(..., "--feedback", "-f", help="Path to feedback text file."),
    apply: bool = typer.Option(False, "--apply", help="Execute revisions automatically."),
) -> None:
    """Phase 6: Analyse feedback and produce a revision plan (optionally apply it)."""
    from research_cli.commands.revise_cmd import run
    run(project_name, feedback_path=feedback, apply_revisions=apply)


# ── Status utility ────────────────────────────────────────────────────

@app.command()
def status(
    project_name: str = typer.Argument(..., help="Existing project name."),
) -> None:
    """Show project state: topic, phase, source counts, versions."""
    import os
    from rich.console import Console
    from rich.table import Table
    from research_cli.database import get_meta, get_all_sources, get_current_version

    console = Console()
    meta = get_meta(project_name)
    if not meta:
        console.print(f"[red]Project '{project_name}' not found.[/red]")
        raise SystemExit(1)

    sources = get_all_sources(project_name)
    version = get_current_version(project_name)

    table = Table(title=f"Project: {project_name}", show_header=False)
    table.add_column("Field", style="bold")
    table.add_column("Value")
    table.add_row("Topic", meta.get("topic", "-"))
    table.add_row("Context", meta.get("context", "-") or "-")
    table.add_row("Location", meta.get("location", "-") or "-")
    table.add_row("Current Phase", meta.get("phase", "-"))
    table.add_row("Current Version", f"v{version}")
    table.add_row("Total Sources", str(len(sources)))
    table.add_row("Included Sources", str(sum(1 for s in sources if s.get("included"))))
    table.add_row("With Full Text", str(sum(1 for s in sources if s.get("full_text_path"))))
    table.add_row("With DOI", str(sum(1 for s in sources if s.get("doi"))))

    # Source breakdown by origin
    origins = {}
    for s in sources:
        o = s.get("origin", "unknown")
        origins[o] = origins.get(o, 0) + 1
    for origin, count in sorted(origins.items()):
        table.add_row(f"  {origin}", str(count))

    # Check for output files
    output_dir = os.path.join("projects", project_name, "outputs", f"v{version}")
    for fname in ("scaffold.md", "final_draft.md", "presentation_guide.md", "revision_plan.md"):
        fpath = os.path.join(output_dir, fname)
        exists = "[green]Yes[/green]" if os.path.isfile(fpath) else "[dim]No[/dim]"
        table.add_row(f"  {fname}", exists)

    table.add_row("Created", meta.get("created_at", "-"))
    table.add_row("Updated", meta.get("updated_at", "-"))
    console.print(table)


# ── Entry point ───────────────────────────────────────────────────────

def main() -> None:
    app()


if __name__ == "__main__":
    main()
