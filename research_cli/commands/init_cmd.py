"""
init_cmd.py — Phase 1: Project initialisation and topic generation.

Flow:
    1. Create project folder structure on disk.
    2. Initialise the SQLite database (7 tables).
    3. Ask language, university, career.
    4. Generate thesis topic suggestions via LLM.
    5. User picks a topic (or types their own).
    6. Collect research variables (name + dimensions).
    7. Collect population, sample size, methodology.
    8. Persist all metadata to database.
    9. Print summary panel.
"""

import json
import os

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from research_cli.config import DEFAULT_LANGUAGE, DEFAULT_METHODOLOGY
from research_cli.database import init_db, save_project_meta, update_phase
from research_cli.llm_client import call_claude

console = Console()


def _ask_variable(label: str, cli_value: str = "") -> dict:
    """Prompt for a variable name and its dimensions. Returns JSON-ready dict."""
    if cli_value:
        # CLI mode: just the name, no dimensions
        return {"name": cli_value, "dimensions": []}

    name = Prompt.ask(f"  Name of {label}")
    dims_raw = Prompt.ask(f"  Dimensions of '{name}' (comma-separated, Enter to skip)", default="")
    dims = [d.strip() for d in dims_raw.split(",") if d.strip()] if dims_raw else []
    return {"name": name, "dimensions": dims}


def _ask_methodology(cli_override: bool = False) -> dict:
    """Prompt for methodology or accept defaults."""
    default = DEFAULT_METHODOLOGY.copy()
    if cli_override:
        return default

    console.print(
        f"\n[bold]Default methodology:[/bold] {default['type']}, "
        f"{default['scope']}, {default['design']}"
    )
    customize = Prompt.ask("  Customize methodology?", choices=["y", "n"], default="n")
    if customize == "n":
        return default

    mtype = Prompt.ask("  Type (cuantitativa/cualitativa/mixta)", default=default["type"])
    scope = Prompt.ask("  Scope (correlacional/descriptivo/explicativo)", default=default["scope"])
    design = Prompt.ask("  Design", default=default["design"])
    return {"type": mtype, "scope": scope, "design": design}


def run(
    project_name: str,
    context: str = "",
    location: str = "",
    language: str = "",
    university: str = "",
    career: str = "",
    variable1: str = "",
    variable2: str = "",
    population: str = "",
    sample_size: int = 0,
) -> None:
    """Execute the init phase."""

    project_dir = os.path.join("projects", project_name)

    # 1. Create folder structure
    if os.path.exists(project_dir):
        console.print(f"[yellow]Project '{project_name}' already exists. Resuming.[/yellow]")
    else:
        for subdir in ("sources/pdfs", "sources/fulltext", "sources/summaries", "outputs/v1"):
            os.makedirs(os.path.join(project_dir, subdir), exist_ok=True)
        console.print(f"[green]Created project:[/green] {project_dir}")

    # 2. Initialise database
    init_db(project_name)
    console.print("[green]Database initialised.[/green]")

    # Detect if running non-interactive (all required fields given via CLI)
    non_interactive = all([variable1, variable2, population])

    # 3. Language
    if not language:
        if non_interactive:
            language = DEFAULT_LANGUAGE
        else:
            language = Prompt.ask("Language", choices=["es", "en"], default=DEFAULT_LANGUAGE)

    # 4. University + career (optional)
    if not non_interactive:
        if not university:
            university = Prompt.ask("University (Enter to skip)", default="")
        if not career:
            career = Prompt.ask("Career / program (Enter to skip)", default="")

    # 5. Generate topic suggestions
    lang_instruction = "in Spanish" if language == "es" else "in English"
    prompt_parts = [f"Generate exactly 5 specific, researchable thesis topics {lang_instruction}."]
    if context:
        prompt_parts.append(f"Academic context / discipline: {context}")
    if location:
        prompt_parts.append(f"Geographic focus: {location}")
    prompt_parts.append(
        "Return ONLY a numbered list (1-5). Each item should be a single, "
        "concise thesis statement that is specific enough to research "
        "with real academic papers."
    )

    console.print("\n[bold]Generating topic suggestions...[/bold]")
    suggestions = call_claude("\n".join(prompt_parts))
    console.print(Panel(suggestions, title="Suggested Topics", border_style="cyan"))

    # 6. User selects a topic
    choice = Prompt.ask(
        "\nEnter the number of your chosen topic, or type a custom topic",
        default="1",
    )

    if choice.strip().isdigit():
        idx = int(choice.strip())
        lines = [
            line.strip().lstrip("0123456789.)- ")
            for line in suggestions.splitlines()
            if line.strip() and line.strip()[0].isdigit()
        ]
        if 1 <= idx <= len(lines):
            chosen_topic = lines[idx - 1]
        else:
            chosen_topic = choice
    else:
        chosen_topic = choice

    # 7. Variables
    if not non_interactive:
        console.print("\n[bold]Research Variables[/bold]")
        console.print("[dim]Each variable needs a name and optional dimensions.[/dim]")
        var1_data = _ask_variable("Variable 1 (independent)", variable1)
        var2_data = _ask_variable("Variable 2 (dependent)", variable2)
    else:
        var1_data = {"name": variable1, "dimensions": []}
        var2_data = {"name": variable2, "dimensions": []}

    # 8. Population + sample
    if not non_interactive:
        if not population:
            population = Prompt.ask("\nPopulation description")
        if sample_size == 0:
            size_raw = Prompt.ask("Sample size (Enter to skip)", default="0")
            try:
                sample_size = int(size_raw)
            except ValueError:
                sample_size = 0

    # 9. Methodology
    meth_data = _ask_methodology(cli_override=non_interactive)

    # 10. Persist
    save_project_meta(
        project_name,
        topic=chosen_topic,
        context=context,
        location=location,
        language=language,
        university=university,
        career=career,
        variable_1=json.dumps(var1_data, ensure_ascii=False),
        variable_2=json.dumps(var2_data, ensure_ascii=False),
        population=population,
        sample_size=sample_size,
        methodology=json.dumps(meth_data, ensure_ascii=False),
    )
    update_phase(project_name, "init")

    # 11. Summary panel
    summary = Table(show_header=False, box=None, padding=(0, 2))
    summary.add_column("Field", style="bold")
    summary.add_column("Value")
    summary.add_row("Topic", chosen_topic)
    summary.add_row("Language", language)
    if university:
        summary.add_row("University", university)
    if career:
        summary.add_row("Career", career)
    summary.add_row("Variable 1", f"{var1_data['name']}  dims={var1_data['dimensions']}")
    summary.add_row("Variable 2", f"{var2_data['name']}  dims={var2_data['dimensions']}")
    summary.add_row("Population", population)
    if sample_size:
        summary.add_row("Sample size", str(sample_size))
    summary.add_row("Methodology", f"{meth_data['type']}, {meth_data['scope']}, {meth_data['design']}")

    console.print()
    console.print(Panel(summary, title="[bold green]Project Initialized[/bold green]", border_style="green"))
    console.print(
        f"[dim]Next: research-cli fetch-data {project_name} --email your@email.edu[/dim]"
    )
