"""sources/ — Academic data acquisition from multiple APIs."""

import importlib

from research_cli.config import SOURCES_ENABLED

# Modules that expose a search(query, limit, year_range) function
_SEARCH_MODULES = [
    "semantic_scholar",
    "openalex",
    "arxiv",
    "pubmed",
    "core",
    "europe_pmc",
    "scielo",
    "doaj",
    "scopus",
]


def get_search_sources(selected: list[str] | None = None) -> list[tuple[str, callable]]:
    """
    Return a list of (name, search_fn) for all enabled source modules.

    If *selected* is given, only those sources are returned (still respecting
    SOURCES_ENABLED and module availability).
    """
    sources = []
    for name in _SEARCH_MODULES:
        if selected and name not in selected:
            continue
        if not SOURCES_ENABLED.get(name, True):
            continue
        try:
            mod = importlib.import_module(f"research_cli.sources.{name}")
            fn = getattr(mod, "search", None)
            if fn is not None:
                sources.append((name, fn))
        except Exception as exc:
            print(f"  [WARN] Could not load source '{name}': {exc}")
    return sources
