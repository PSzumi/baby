"""
init_cmd.py — Phase 1: Project initialisation and topic generation.

Flow:
    1. Create project folder structure on disk.
    2. Initialise the SQLite database (7 tables).
    3. Ask Claude to generate 5 thesis topic suggestions.
    4. User picks a topic (or types their own).
    5. Persist to database, mark phase complete.
"""

import os
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from research_cli.database import init_db, save_topic, update_phase
from research_cli.llm_client import call_claude

console = Console()


def run(project_name: str, context: str = "", location: str = "") -> None:
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
    console.print("[green]Database initialised (7 tables).[/green]")

    # 3. Generate topic suggestions
    prompt_parts = ["Generate exactly 5 specific, researchable thesis topics."]
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

    # 4. User selects a topic
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

    # 5. Persist
    save_topic(project_name, chosen_topic, context=context, location=location)
    update_phase(project_name, "init")

    console.print(f"\n[bold green]Topic saved:[/bold green] {chosen_topic}")
    console.print(
        f"[dim]Next: research-cli fetch-data {project_name} --email your@email.edu[/dim]"
    )
