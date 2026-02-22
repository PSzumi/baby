"""
fetch_cmd.py — Phase 2: Multi-source academic data acquisition.

5-stage pipeline:
    1. DISCOVERY — Generate search queries from topic, then hit
       all enabled sources (up to 8 APIs) with multiple queries
    2. DEDUPLICATE — DOI + title similarity
    3. ENRICH — CrossRef bibliographic metadata → BibTeX + APA
    4. FULL-TEXT — Unpaywall/arXiv PDF download + text extraction
    5. RELEVANCE SCORING — composite quality scores
"""

import os
import time
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from research_cli.database import (
    get_topic,
    save_sources_bulk,
    get_all_sources,
    get_sources_with_doi,
    update_source_field,
    update_source_scores,
    update_phase,
)
from research_cli.sources import get_search_sources
from research_cli.sources.unpaywall import find_pdf as unpaywall_find
from research_cli.sources.arxiv import try_download as arxiv_download
from research_cli.content.deduplicator import deduplicate
from research_cli.content.relevance_scorer import score_sources
from research_cli.content.pdf_extractor import download_and_extract
from research_cli.citations.bibdb import build_bibliography, export_bib_file
from research_cli.llm_client import call_claude_json

console = Console()


def _generate_search_queries(topic: str) -> list[str]:
    """
    Use LLM to generate 3-5 broad academic search queries from the topic.

    Academic databases work better with general keyword queries than
    with full thesis statements or brand names.
    """
    prompt = f"""Generate 4 academic search queries for finding peer-reviewed papers related to this research topic:

"{topic}"

CRITICAL RULES:
- Each query should be 3-5 general academic keywords
- DO NOT use company/brand names — use the INDUSTRY instead (e.g. "airline" not "Delta", "coffee shop" not "Starbucks")
- DO NOT include years in queries
- Make queries broad enough to match real paper titles in academic databases
- Cover different angles: theoretical frameworks, methodology, industry context, regional/geographic context
- Return ONLY a JSON array of strings, nothing else

Example for "Customer satisfaction at Starbucks in Asia":
["customer satisfaction coffee shop industry", "service quality food beverage Asia", "SERVQUAL restaurant hospitality", "customer loyalty chain restaurants developing countries"]

Example for "Employee motivation at Toyota manufacturing plants":
["employee motivation manufacturing sector", "job satisfaction automotive industry", "Herzberg motivation theory factory workers", "organizational behavior production workforce"]
"""
    try:
        queries = call_claude_json(prompt, max_tokens=2048, temperature=0.3)
        # LLM may return a list directly or wrap it in a dict
        if isinstance(queries, dict):
            for key in ("queries", "search_queries", "results"):
                if isinstance(queries.get(key), list):
                    queries = queries[key]
                    break
            else:
                # Take the first list value found
                for v in queries.values():
                    if isinstance(v, list):
                        queries = v
                        break
        if isinstance(queries, list) and queries:
            return queries[:5]
    except Exception:
        pass

    # Fallback: use the topic itself split into a simpler query
    return [topic]


def _compile_sources_file(sources: list[dict], output_path: str) -> None:
    """Write all sources to a human-readable text file."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"COMPILED ACADEMIC SOURCES ({len(sources)} total)\n")
        f.write("=" * 72 + "\n\n")
        for i, s in enumerate(sources, 1):
            f.write(f"--- Source #{i} [{s.get('origin', '?')}] ---\n")
            f.write(f"Title   : {s.get('title', 'N/A')}\n")
            f.write(f"Authors : {s.get('authors', 'N/A')}\n")
            f.write(f"Year    : {s.get('year', 'N/A')}\n")
            f.write(f"DOI     : {s.get('doi', 'N/A')}\n")
            f.write(f"Journal : {s.get('journal', 'N/A')}\n")
            f.write(f"URL     : {s.get('url', 'N/A')}\n")
            f.write(f"Citations: {s.get('citation_count', 0)}\n")
            f.write(f"Quality : {s.get('quality_score', 0):.3f}\n")
            f.write(f"Full text: {'Yes' if s.get('full_text_path') else 'No'}\n")
            f.write(f"Abstract:\n{s.get('abstract', 'N/A')}\n\n")


def _select_diverse(papers: list[dict], max_total: int) -> list[dict]:
    """
    Select up to *max_total* papers ensuring source diversity.

    Strategy:
        1. Group papers by origin, sort each group by citation_count desc.
        2. Guarantee each source gets at least *min_per_source* slots
           (or all its papers if it has fewer).
        3. Fill remaining slots from all sources by citation_count desc.
    """
    # Group by origin
    by_origin: dict[str, list[dict]] = {}
    for p in papers:
        origin = p.get("origin", "unknown")
        by_origin.setdefault(origin, []).append(p)

    # Sort each group by citation count (best first)
    for origin in by_origin:
        by_origin[origin].sort(
            key=lambda p: p.get("citation_count", 0), reverse=True,
        )

    n_sources = len(by_origin)
    # Each source gets at least this many guaranteed slots
    min_per_source = max(3, max_total // (n_sources * 2))

    selected: list[dict] = []
    selected_ids: set[int] = set()  # track by id() to avoid dupes
    remaining: list[dict] = []

    # Phase 1: take top min_per_source from each origin
    for origin, group in by_origin.items():
        for p in group[:min_per_source]:
            selected.append(p)
            selected_ids.add(id(p))
        for p in group[min_per_source:]:
            remaining.append(p)

    # Phase 2: fill remaining slots by citation count
    if len(selected) < max_total:
        remaining.sort(
            key=lambda p: p.get("citation_count", 0), reverse=True,
        )
        for p in remaining:
            if len(selected) >= max_total:
                break
            if id(p) not in selected_ids:
                selected.append(p)

    return selected[:max_total]


def run(
    project_name: str,
    skip_fulltext: bool = False,
    max_sources: int = 40,
    email: str = "",
    sources_filter: str = "",
) -> None:
    """Execute the fetch-data phase."""

    topic = get_topic(project_name)
    if not topic:
        console.print("[red]No topic found. Run 'research-cli init' first.[/red]")
        raise SystemExit(1)

    console.print(f"[bold]Fetching sources for:[/bold] {topic}\n")

    # Resolve which sources to use
    selected = None
    if sources_filter:
        selected = [s.strip() for s in sources_filter.split(",") if s.strip()]

    search_sources = get_search_sources(selected)
    source_names = [name for name, _ in search_sources]
    console.print(f"[bold]Active sources:[/bold] {', '.join(source_names)}\n")

    project_dir = os.path.join("projects", project_name)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:

        # ── Stage 0: Generate search queries ────────────────────────
        task = progress.add_task("Stage 0: Generating search queries...", total=None)
        queries = _generate_search_queries(topic)
        progress.update(task, description=f"Stage 0: {len(queries)} search queries generated")
        progress.update(task, completed=True)

        for i, q in enumerate(queries):
            console.print(f"  Query {i+1}: {q}")

        # ── Stage 1: Discovery ──────────────────────────────────────
        task = progress.add_task("Stage 1: Discovering papers...", total=None)

        all_papers = []
        per_query_limit = max(8, 30 // len(queries))

        for q in queries:
            for source_name, search_fn in search_sources:
                if source_name == "semantic_scholar":
                    # Semantic Scholar gets retry on 429
                    for attempt in range(3):
                        results = search_fn(q, limit=per_query_limit)
                        if results:
                            all_papers.extend(results)
                            break
                        if attempt < 2:
                            wait = (attempt + 1) * 10
                            console.print(f"  [dim]SS rate limited, waiting {wait}s...[/dim]")
                            time.sleep(wait)
                else:
                    try:
                        results = search_fn(q, limit=per_query_limit)
                        all_papers.extend(results)
                    except Exception as exc:
                        console.print(f"  [dim][SKIP] {source_name}: {exc}[/dim]")

            time.sleep(1)  # brief pause between queries

        progress.update(task, description=f"Stage 1: Found {len(all_papers)} papers")
        progress.update(task, completed=True)

        if not all_papers:
            console.print("[red]No papers found from any API.[/red]")
            console.print("[yellow]Try a broader topic or check your internet connection.[/yellow]")
            raise SystemExit(1)

        # ── Stage 2: Deduplicate ────────────────────────────────────
        task = progress.add_task("Stage 2: Deduplicating...", total=None)

        deduped = deduplicate(all_papers)
        if len(deduped) > max_sources:
            deduped = _select_diverse(deduped, max_sources)

        progress.update(task, description=f"Stage 2: {len(deduped)} unique papers")
        progress.update(task, completed=True)

        # Save to database
        save_sources_bulk(project_name, deduped)

        # ── Stage 3: Bibliographic Enrichment ───────────────────────
        task = progress.add_task("Stage 3: Enriching bibliography (CrossRef)...", total=None)

        bib_count = build_bibliography(project_name)

        progress.update(task, description=f"Stage 3: {bib_count} bibliography entries")
        progress.update(task, completed=True)

        # ── Stage 4: Full-Text Acquisition ──────────────────────────
        if not skip_fulltext:
            task = progress.add_task("Stage 4: Downloading full-text PDFs...", total=None)

            sources = get_sources_with_doi(project_name)
            pdf_dir = os.path.join(project_dir, "sources", "pdfs")
            fulltext_dir = os.path.join(project_dir, "sources", "fulltext")
            pdf_count = 0

            for source in sources:
                doi = source.get("doi", "")
                url = source.get("url", "")
                sid = source["id"]

                if source.get("full_text_path"):
                    pdf_count += 1
                    continue

                pdf_url = source.get("pdf_url", "")

                # Try Unpaywall
                if not pdf_url and email:
                    found = unpaywall_find(doi)
                    if found:
                        pdf_url = found
                        update_source_field(project_name, sid, "pdf_url", pdf_url)

                # Try arXiv
                if not pdf_url:
                    arxiv_path = arxiv_download(doi, url, pdf_dir)
                    if arxiv_path:
                        from research_cli.content.pdf_extractor import extract_text
                        text = extract_text(arxiv_path)
                        if text:
                            ft_path = os.path.join(fulltext_dir, f"{sid}.txt")
                            os.makedirs(fulltext_dir, exist_ok=True)
                            with open(ft_path, "w", encoding="utf-8") as f:
                                f.write(text)
                            update_source_field(project_name, sid, "full_text_path", ft_path)
                            pdf_count += 1
                        continue

                # Download PDF from URL
                if pdf_url:
                    filename = f"{sid}.pdf"
                    pdf_path, text = download_and_extract(pdf_url, pdf_dir, filename)
                    if text:
                        ft_path = os.path.join(fulltext_dir, f"{sid}.txt")
                        os.makedirs(fulltext_dir, exist_ok=True)
                        with open(ft_path, "w", encoding="utf-8") as f:
                            f.write(text)
                        update_source_field(project_name, sid, "full_text_path", ft_path)
                        pdf_count += 1

            progress.update(task, description=f"Stage 4: {pdf_count} full-text papers")
            progress.update(task, completed=True)
        else:
            console.print("  [yellow]Skipping full-text download (--skip-fulltext)[/yellow]")

        # ── Stage 5: Relevance Scoring ──────────────────────────────
        task = progress.add_task("Stage 5: Scoring relevance...", total=None)

        all_sources = get_all_sources(project_name)
        scored = score_sources(topic, all_sources)

        for s in scored:
            update_source_scores(
                project_name, s["id"],
                s.get("relevance_score", 0),
                s.get("quality_score", 0),
            )

        progress.update(task, description=f"Stage 5: Scored {len(scored)} sources")
        progress.update(task, completed=True)

    # ── Save output files ───────────────────────────────────────────
    sources_file = os.path.join(project_dir, "sources", "compiled_sources.txt")
    _compile_sources_file(get_all_sources(project_name), sources_file)

    bib_file = os.path.join(project_dir, "sources", "bibliography.bib")
    export_bib_file(project_name, bib_file)

    update_phase(project_name, "fetch-data")

    # Summary
    final_sources = get_all_sources(project_name)
    ft_count = sum(1 for s in final_sources if s.get("full_text_path"))

    console.print(f"\n[bold green]Done![/bold green]")
    console.print(f"  Total sources: {len(final_sources)}")
    console.print(f"  With full text: {ft_count}")
    console.print(f"  Bibliography entries: {bib_count}")
    console.print(f"\n[dim]Next: research-cli review {project_name}[/dim]")
