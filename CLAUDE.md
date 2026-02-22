# research-cli

Automated academic thesis generation from real research data.

## Architecture

```
research_cli/
  main.py              — CLI entry (typer). Commands: init, fetch-data, review, scaffold, draft, present, revise, status
  config.py            — All env vars, rate limits, SOURCES_ENABLED dict
  database.py          — SQLite per-project DB (projects/<name>/research.db). 7 tables.
  llm_client.py        — Multi-provider LLM client (gemini default, also groq/deepseek/openai/anthropic)
  sources/
    __init__.py        — Source registry: get_search_sources() returns enabled (name, search_fn) pairs
    semantic_scholar.py — Search + normalized dicts (origin field)
    openalex.py        — Search, reconstructs abstracts from inverted index
    arxiv.py           — Search (Atom XML) + PDF downloader
    pubmed.py          — Two-step ESearch→EFetch, structured abstract parsing
    core.py            — Requires CORE_API_KEY, gracefully skips without it
    europe_pmc.py      — resulttype must be lowercase, uses cursorMark pagination
    scielo.py          — HTML scraping (no public JSON API), fragile
    doaj.py            — v4 API, bibjson response structure
    scopus.py          — Elsevier API, free tier: no abstracts, uses DOI merge
    crossref.py        — Bibliographic enrichment (not search)
    unpaywall.py       — PDF URL finder (not search)
  commands/
    fetch_cmd.py       — 5-stage pipeline: queries→discovery→dedup→enrich→fulltext→scoring
    init_cmd.py, review_cmd.py, scaffold_cmd.py, draft_cmd.py, present_cmd.py, revise_cmd.py
  content/
    deduplicator.py    — DOI match + title similarity (difflib, 0.85 threshold)
    relevance_scorer.py — LLM batch relevance + citation + recency composite score
    pdf_extractor.py, summarizer.py
  citations/           — BibTeX generation via CrossRef
  generation/          — Section planning + prose generation
  revision/            — Feedback parsing + surgical editing
```

## Key patterns

- All search modules: `search(query, limit, year_range) -> list[dict]` returning normalized paper dicts with `origin` field
- DB upsert deduplicates by DOI first, then by exact title match
- `_select_diverse()` in fetch_cmd.py guarantees minimum representation per source before filling by citation count
- LLM JSON responses may come as `{"key": [...]}` instead of bare lists — always unwrap dicts

## Common tasks

- **Add a new source**: Create `sources/<name>.py` with `search()` function, add to `_SEARCH_MODULES` in `sources/__init__.py`, add rate limit + SOURCES_ENABLED entry in `config.py`
- **Test a single source**: `.venv/bin/python -c "from research_cli.sources.<name> import search; print(search('query', limit=3))"`
- **Run pipeline**: `.venv/bin/research-cli fetch-data <project> --email <email>`
- **Filter sources**: `--sources "semantic_scholar,pubmed,scielo"`

## Known limitations

- SciELO uses HTML scraping — may break if they change layout
- CORE requires free API key (https://core.ac.uk/services/api)
- Semantic Scholar rate-limits aggressively without API key (429s common)
- Europe PMC: `resulttype` param must be lowercase (not camelCase)
- Scopus free tier returns no abstracts — relies on DOI-based merge with other sources
