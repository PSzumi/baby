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
from research_cli.sources.unpaywall import batch_find_pdfs as unpaywall_batch
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

    # ── Stats tracking ──────────────────────────────────────────────
    stats = {
        "source_errors": [],           # (source_name, query, error_msg)
        "papers_discovered": 0,
        "papers_after_dedup": 0,
        "bib_entries": 0,
        "unpaywall_found": 0,
        "unpaywall_total": 0,
        "pdf_downloads_attempted": 0,
        "pdf_downloads_succeeded": 0,
        "pdf_downloads_failed": 0,
        "fulltext_extracted": 0,
        "sources_scored": 0,
    }

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
                        stats["source_errors"].append((source_name, q, "rate limited after 3 attempts"))
                else:
                    try:
                        results = search_fn(q, limit=per_query_limit)
                        all_papers.extend(results)
                    except Exception as exc:
                        console.print(f"  [dim][SKIP] {source_name}: {exc}[/dim]")
                        stats["source_errors"].append((source_name, q, str(exc)))

            time.sleep(1)  # brief pause between queries

        stats["papers_discovered"] = len(all_papers)
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

        stats["papers_after_dedup"] = len(deduped)
        progress.update(task, description=f"Stage 2: {len(deduped)} unique papers")
        progress.update(task, completed=True)

        # Save to database
        save_sources_bulk(project_name, deduped)

        # ── Stage 3: Bibliographic Enrichment ───────────────────────
        task = progress.add_task("Stage 3: Enriching bibliography (CrossRef)...", total=None)

        bib_count = build_bibliography(project_name)
        stats["bib_entries"] = bib_count

        progress.update(task, description=f"Stage 3: {bib_count} bibliography entries")
        progress.update(task, completed=True)

        # ── Stage 4: Full-Text Acquisition ──────────────────────────
        if not skip_fulltext:
            task = progress.add_task("Stage 4: Downloading full-text PDFs...", total=None)

            sources = get_sources_with_doi(project_name)
            pdf_dir = os.path.join(project_dir, "sources", "pdfs")
            fulltext_dir = os.path.join(project_dir, "sources", "fulltext")
            pdf_count = 0

            # Batch Unpaywall lookup for all DOIs missing pdf_url
            if email:
                dois_needing_urls = [
                    s["doi"] for s in sources
                    if s.get("doi") and not s.get("pdf_url") and not s.get("full_text_path")
                ]
                if dois_needing_urls:
                    stats["unpaywall_total"] = len(dois_needing_urls)
                    unpaywall_results = unpaywall_batch(dois_needing_urls)
                    stats["unpaywall_found"] = len(unpaywall_results)
                    # Update pdf_url for matched sources
                    doi_to_sid = {s["doi"]: s["id"] for s in sources if s.get("doi")}
                    for doi, pdf_url in unpaywall_results.items():
                        sid = doi_to_sid.get(doi)
                        if sid:
                            update_source_field(project_name, sid, "pdf_url", pdf_url)
                            # Also update in-memory list
                            for s in sources:
                                if s.get("doi") == doi:
                                    s["pdf_url"] = pdf_url
                                    break

            for source in sources:
                doi = source.get("doi", "")
                url = source.get("url", "")
                sid = source["id"]

                if source.get("full_text_path"):
                    pdf_count += 1
                    continue

                pdf_url = source.get("pdf_url", "")

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
                            stats["fulltext_extracted"] += 1
                        continue

                # Download PDF from URL
                if pdf_url:
                    stats["pdf_downloads_attempted"] += 1
                    filename = f"{sid}.pdf"
                    pdf_path, text = download_and_extract(pdf_url, pdf_dir, filename)
                    if text:
                        ft_path = os.path.join(fulltext_dir, f"{sid}.txt")
                        os.makedirs(fulltext_dir, exist_ok=True)
                        with open(ft_path, "w", encoding="utf-8") as f:
                            f.write(text)
                        update_source_field(project_name, sid, "full_text_path", ft_path)
                        pdf_count += 1
                        stats["pdf_downloads_succeeded"] += 1
                        stats["fulltext_extracted"] += 1
                    else:
                        stats["pdf_downloads_failed"] += 1

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

        stats["sources_scored"] = len(scored)
        progress.update(task, description=f"Stage 5: Scored {len(scored)} sources")
        progress.update(task, completed=True)

    # ── Save output files ───────────────────────────────────────────
    sources_file = os.path.join(project_dir, "sources", "compiled_sources.txt")
    _compile_sources_file(get_all_sources(project_name), sources_file)

    bib_file = os.path.join(project_dir, "sources", "bibliography.bib")
    export_bib_file(project_name, bib_file)

    update_phase(project_name, "fetch-data")

    # ── Summary Report ──────────────────────────────────────────────
    final_sources = get_all_sources(project_name)
    ft_count = sum(1 for s in final_sources if s.get("full_text_path"))

    from rich.panel import Panel
    from rich.table import Table

    summary = Table(show_header=False, box=None, padding=(0, 2))
    summary.add_column("label", style="bold")
    summary.add_column("value")

    summary.add_row("Papers discovered", str(stats["papers_discovered"]))
    summary.add_row("After dedup", str(stats["papers_after_dedup"]))
    summary.add_row("Bibliography entries", str(stats["bib_entries"]))

    if not skip_fulltext:
        summary.add_row("Unpaywall hits", f"{stats['unpaywall_found']}/{stats['unpaywall_total']}")
        summary.add_row("PDF downloads", f"{stats['pdf_downloads_succeeded']}/{stats['pdf_downloads_attempted']} succeeded, {stats['pdf_downloads_failed']} failed")
        summary.add_row("Full text extracted", str(ft_count))

    summary.add_row("Sources scored", str(stats["sources_scored"]))

    if stats["source_errors"]:
        # Group errors by source
        error_counts: dict[str, int] = {}
        for src, _q, _msg in stats["source_errors"]:
            error_counts[src] = error_counts.get(src, 0) + 1
        error_summary = ", ".join(f"{src}: {cnt}" for src, cnt in sorted(error_counts.items()))
        summary.add_row("Source errors", f"{len(stats['source_errors'])} ({error_summary})")

    console.print()
    console.print(Panel(summary, title="[bold green]Fetch Complete[/bold green]", border_style="green"))
    console.print(f"\n[dim]Next: research-cli review {project_name}[/dim]")
