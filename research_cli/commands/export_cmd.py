"""
export_cmd.py — Export thesis draft to USIL-formatted .docx.

Reads the latest final_draft.md and converts it to a Word document
with proper USIL formatting (Times New Roman, headings, tables, margins).
"""

import os
from rich.console import Console

from research_cli.database import get_current_version, get_meta
from research_cli.export.docx_exporter import markdown_to_docx

console = Console()


def run(project_name: str) -> None:
    """Execute the export phase."""

    version = get_current_version(project_name)
    output_dir = os.path.join("projects", project_name, "outputs", f"v{version}")
    draft_path = os.path.join(output_dir, "final_draft.md")

    if not os.path.isfile(draft_path):
        console.print("[red]final_draft.md not found. Run 'research-cli draft' first.[/red]")
        raise SystemExit(1)

    with open(draft_path, "r", encoding="utf-8") as f:
        markdown_text = f.read()

    console.print(f"[bold]Exporting thesis to DOCX...[/bold]")
    console.print(f"  Source: {draft_path}")

    docx_path = os.path.join(output_dir, "thesis.docx")
    markdown_to_docx(markdown_text, docx_path)

    # Report stats
    word_count = len(markdown_text.split())
    meta = get_meta(project_name)
    lang = (meta or {}).get("language", "en")

    console.print(f"  Words: {word_count}")
    console.print(f"  Language: {lang}")
    console.print(f"\n[bold green]DOCX saved:[/bold green] {docx_path}")
