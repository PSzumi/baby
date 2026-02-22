"""
config.py — Centralized configuration for research-cli.

Supports multiple LLM providers via LLM_PROVIDER env var:
    gemini (default), groq, deepseek, anthropic, openai

Switch providers by changing LLM_PROVIDER in .env — no code changes needed.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# LLM Provider Configuration
# ---------------------------------------------------------------------------

LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "gemini").lower()

_PROVIDER_CONFIG = {
    "gemini": {
        "api_key_env": "GEMINI_API_KEY",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "default_model": "gemini-2.5-flash-lite",
        "max_tokens": 8192,
    },
    "groq": {
        "api_key_env": "GROQ_API_KEY",
        "base_url": "https://api.groq.com/openai/v1",
        "default_model": "llama-3.3-70b-versatile",
        "max_tokens": 8192,
    },
    "deepseek": {
        "api_key_env": "DEEPSEEK_API_KEY",
        "base_url": "https://api.deepseek.com",
        "default_model": "deepseek-chat",
        "max_tokens": 8192,
    },
    "openai": {
        "api_key_env": "OPENAI_API_KEY",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o",
        "max_tokens": 8192,
    },
    "anthropic": {
        "api_key_env": "ANTHROPIC_API_KEY",
        "base_url": None,  # uses native SDK
        "default_model": "claude-sonnet-4-20250514",
        "max_tokens": 8192,
    },
}

_provider = _PROVIDER_CONFIG.get(LLM_PROVIDER, _PROVIDER_CONFIG["gemini"])

LLM_API_KEY: str = os.getenv(_provider["api_key_env"], "")
LLM_BASE_URL: str | None = _provider["base_url"]
DEFAULT_MODEL: str = os.getenv("LLM_MODEL", _provider["default_model"])
DEFAULT_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", str(_provider["max_tokens"])))
DEFAULT_TEMPERATURE: float = 0.3
SYSTEM_PROMPT: str = "You are an expert academic research assistant."

# ---------------------------------------------------------------------------
# Academic Data API Keys
# ---------------------------------------------------------------------------

SEMANTIC_SCHOLAR_API_KEY: str = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "")
UNPAYWALL_EMAIL: str = os.getenv("UNPAYWALL_EMAIL", "")
CROSSREF_MAILTO: str = os.getenv("CROSSREF_MAILTO", "") or UNPAYWALL_EMAIL
CORE_API_KEY: str = os.getenv("CORE_API_KEY", "")
NCBI_API_KEY: str = os.getenv("NCBI_API_KEY", "")
SCOPUS_API_KEY: str = os.getenv("SCOPUS_API_KEY", "")

# ---------------------------------------------------------------------------
# Rate limits (seconds between requests)
# ---------------------------------------------------------------------------

SS_RATE_LIMIT: float = 1.0 if SEMANTIC_SCHOLAR_API_KEY else 5.0
CROSSREF_RATE_LIMIT: float = 0.05
UNPAYWALL_RATE_LIMIT: float = 0.1
OPENALEX_RATE_LIMIT: float = 0.1
ARXIV_RATE_LIMIT: float = 3.0
PUBMED_RATE_LIMIT: float = 0.1 if NCBI_API_KEY else 0.34
CORE_RATE_LIMIT: float = 0.2
EUROPE_PMC_RATE_LIMIT: float = 0.2
SCIELO_RATE_LIMIT: float = 0.5
DOAJ_RATE_LIMIT: float = 0.2
SCOPUS_RATE_LIMIT: float = 0.1
REQUEST_TIMEOUT: int = 30

# ---------------------------------------------------------------------------
# Content / Source Limits
# ---------------------------------------------------------------------------

MAX_TOKENS_PER_SOURCE: int = 15_000
MAX_SOURCES_PER_SECTION: int = 8
DEFAULT_MAX_SOURCES: int = 40
DEDUP_TITLE_THRESHOLD: float = 0.85

RELEVANCE_WEIGHT: float = 0.5
CITATION_WEIGHT: float = 0.3
RECENCY_WEIGHT: float = 0.2
FULLTEXT_MULTIPLIER: float = 1.5

# ---------------------------------------------------------------------------
# User-Agent for HTTP requests
# ---------------------------------------------------------------------------

USER_AGENT: str = "research-cli/2.0 (academic-automation; mailto:{})".format(
    CROSSREF_MAILTO or "unset"
)

# ---------------------------------------------------------------------------
# Source enable/disable (set DISABLE_<SOURCE>=true to skip)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Thesis / USIL defaults
# ---------------------------------------------------------------------------

DEFAULT_LANGUAGE = "es"
DEFAULT_METHODOLOGY = {
    "type": "cuantitativa",
    "scope": "correlacional",
    "design": "no experimental, transversal",
}

# ---------------------------------------------------------------------------
# Source enable/disable (set DISABLE_<SOURCE>=true to skip)
# ---------------------------------------------------------------------------

SOURCES_ENABLED: dict[str, bool] = {
    "semantic_scholar": os.getenv("DISABLE_SEMANTIC_SCHOLAR", "").lower() != "true",
    "openalex": os.getenv("DISABLE_OPENALEX", "").lower() != "true",
    "arxiv": os.getenv("DISABLE_ARXIV", "").lower() != "true",
    "pubmed": os.getenv("DISABLE_PUBMED", "").lower() != "true",
    "core": os.getenv("DISABLE_CORE", "").lower() != "true",
    "europe_pmc": os.getenv("DISABLE_EUROPE_PMC", "").lower() != "true",
    "scielo": os.getenv("DISABLE_SCIELO", "").lower() != "true",
    "doaj": os.getenv("DISABLE_DOAJ", "").lower() != "true",
    "scopus": os.getenv("DISABLE_SCOPUS", "").lower() != "true",
}
