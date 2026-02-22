"""
database.py — SQLite state management for research-cli v2.

Each project gets its own SQLite database at:
    ./projects/<project_name>/state.db

Tables (7):
    project_meta    — single-row: topic, context, location, phase, version.
    sources         — one row per academic paper with full metadata + quality scores.
    source_sections — maps sources to thesis sections they're relevant for.
    bibliography    — BibTeX entries built from CrossRef data.
    sections        — thesis section plans and draft content.
    phases          — audit log of completed workflow phases.
    feedback_items  — structured feedback from colleagues.
"""

import json
import sqlite3
import os
from datetime import datetime, timezone
from typing import Optional


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _db_path(project_name: str) -> str:
    return os.path.join("projects", project_name, "state.db")


def get_connection(project_name: str) -> sqlite3.Connection:
    """Open (or create) the project database and return a connection."""
    path = _db_path(project_name)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _migrate_db(conn: sqlite3.Connection) -> None:
    """Add new columns to project_meta if they don't exist (cheap on every call)."""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(project_meta)")}
    new_cols = {
        "language": "TEXT DEFAULT 'es'",
        "university": "TEXT DEFAULT ''",
        "career": "TEXT DEFAULT ''",
        "variable_1": "TEXT DEFAULT ''",
        "variable_2": "TEXT DEFAULT ''",
        "population": "TEXT DEFAULT ''",
        "sample_size": "INTEGER DEFAULT 0",
        "methodology": "TEXT DEFAULT ''",
    }
    added = False
    for col, typedef in new_cols.items():
        if col not in existing:
            conn.execute(f"ALTER TABLE project_meta ADD COLUMN {col} {typedef}")
            added = True
    if added:
        conn.commit()


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS project_meta (
    id              INTEGER PRIMARY KEY CHECK (id = 1),
    topic           TEXT,
    context         TEXT,
    location        TEXT,
    phase           TEXT DEFAULT 'init',
    current_version INTEGER DEFAULT 1,
    created_at      TEXT,
    updated_at      TEXT,
    language        TEXT DEFAULT 'es',
    university      TEXT DEFAULT '',
    career          TEXT DEFAULT '',
    variable_1      TEXT DEFAULT '',
    variable_2      TEXT DEFAULT '',
    population      TEXT DEFAULT '',
    sample_size     INTEGER DEFAULT 0,
    methodology     TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS sources (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    origin          TEXT NOT NULL,
    doi             TEXT,
    title           TEXT,
    authors         TEXT,
    year            TEXT,
    journal         TEXT,
    volume          TEXT,
    issue           TEXT,
    pages           TEXT,
    url             TEXT,
    pdf_url         TEXT,
    abstract        TEXT,
    full_text_path  TEXT,
    summary         TEXT,
    citation_count  INTEGER DEFAULT 0,
    relevance_score REAL DEFAULT 0.0,
    quality_score   REAL DEFAULT 0.0,
    is_open_access  INTEGER DEFAULT 0,
    included        INTEGER DEFAULT 1,
    fetched_at      TEXT,
    UNIQUE(doi)
);

CREATE TABLE IF NOT EXISTS source_sections (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id   INTEGER REFERENCES sources(id),
    section_key TEXT NOT NULL,
    relevance   REAL DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS bibliography (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id     INTEGER REFERENCES sources(id),
    bibtex_key    TEXT UNIQUE NOT NULL,
    bibtex_type   TEXT DEFAULT 'article',
    bibtex_raw    TEXT NOT NULL,
    apa_formatted TEXT,
    verified      INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sections (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    version          INTEGER DEFAULT 1,
    section_key      TEXT NOT NULL,
    section_title    TEXT,
    order_index      INTEGER,
    scaffold_content TEXT,
    draft_content    TEXT,
    word_count       INTEGER DEFAULT 0,
    status           TEXT DEFAULT 'pending',
    generated_at     TEXT,
    UNIQUE(version, section_key)
);

CREATE TABLE IF NOT EXISTS phases (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    phase_name   TEXT NOT NULL,
    version      INTEGER DEFAULT 1,
    completed    INTEGER DEFAULT 0,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS feedback_items (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    feedback_file  TEXT,
    item_text      TEXT,
    target_section TEXT,
    severity       TEXT,
    status         TEXT DEFAULT 'open',
    created_at     TEXT
);
"""


def init_db(project_name: str) -> None:
    """Create all tables if they don't already exist."""
    conn = get_connection(project_name)
    conn.executescript(_SCHEMA)
    conn.commit()
    _migrate_db(conn)  # add new columns to existing DBs
    conn.close()


# ---------------------------------------------------------------------------
# Project metadata
# ---------------------------------------------------------------------------

def save_project_meta(
    project_name: str,
    topic: str,
    context: str = "",
    location: str = "",
    language: str = "es",
    university: str = "",
    career: str = "",
    variable_1: str = "",
    variable_2: str = "",
    population: str = "",
    sample_size: int = 0,
    methodology: str = "",
) -> None:
    """Save all project metadata (full USIL thesis fields)."""
    conn = get_connection(project_name)
    _migrate_db(conn)
    now = _now()
    conn.execute(
        """INSERT INTO project_meta
               (id, topic, context, location, language, university, career,
                variable_1, variable_2, population, sample_size, methodology,
                created_at, updated_at)
           VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(id) DO UPDATE SET
               topic = excluded.topic, context = excluded.context,
               location = excluded.location, language = excluded.language,
               university = excluded.university, career = excluded.career,
               variable_1 = excluded.variable_1, variable_2 = excluded.variable_2,
               population = excluded.population, sample_size = excluded.sample_size,
               methodology = excluded.methodology, updated_at = ?""",
        (topic, context, location, language, university, career,
         variable_1, variable_2, population, sample_size, methodology,
         now, now, now),
    )
    conn.commit()
    conn.close()


def save_topic(project_name: str, topic: str, context: str = "", location: str = "") -> None:
    """Backward-compatible wrapper — saves only topic/context/location."""
    save_project_meta(project_name, topic, context=context, location=location)


def get_topic(project_name: str) -> Optional[str]:
    conn = get_connection(project_name)
    row = conn.execute("SELECT topic FROM project_meta WHERE id = 1").fetchone()
    conn.close()
    return row["topic"] if row else None


def get_meta(project_name: str) -> Optional[dict]:
    conn = get_connection(project_name)
    _migrate_db(conn)
    row = conn.execute("SELECT * FROM project_meta WHERE id = 1").fetchone()
    conn.close()
    return dict(row) if row else None


def get_current_version(project_name: str) -> int:
    conn = get_connection(project_name)
    row = conn.execute("SELECT current_version FROM project_meta WHERE id = 1").fetchone()
    conn.close()
    return row["current_version"] if row else 1


def increment_version(project_name: str) -> int:
    conn = get_connection(project_name)
    conn.execute(
        "UPDATE project_meta SET current_version = current_version + 1, updated_at = ? WHERE id = 1",
        (_now(),),
    )
    conn.commit()
    row = conn.execute("SELECT current_version FROM project_meta WHERE id = 1").fetchone()
    conn.close()
    return row["current_version"]


def update_phase(project_name: str, phase: str) -> None:
    conn = get_connection(project_name)
    now = _now()
    version = get_current_version(project_name)
    conn.execute("UPDATE project_meta SET phase = ?, updated_at = ? WHERE id = 1", (phase, now))
    conn.execute(
        "INSERT INTO phases (phase_name, version, completed, completed_at) VALUES (?, ?, 1, ?)",
        (phase, version, now),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

def upsert_source(project_name: str, source: dict) -> int:
    """
    Insert or update a source. If DOI exists, update with richer data.
    Returns the source id.
    """
    conn = get_connection(project_name)
    now = _now()

    doi = source.get("doi")
    title = source.get("title", "")

    # Check for existing source by DOI, or by exact title if no DOI
    existing = None
    if doi:
        existing = conn.execute("SELECT id FROM sources WHERE doi = ?", (doi,)).fetchone()
    if not existing and title:
        existing = conn.execute(
            "SELECT id FROM sources WHERE LOWER(title) = LOWER(?)", (title,)
        ).fetchone()

    if existing:
        # Update with any new fields that are non-empty
        source_id = existing["id"]
        updates = []
        params = []
        for field in (
            "title", "authors", "year", "journal", "volume", "issue",
            "pages", "url", "pdf_url", "abstract", "full_text_path",
            "summary",
        ):
            val = source.get(field)
            if val:
                updates.append(f"{field} = ?")
                params.append(val)
        # Numeric fields: update if non-zero
        for field in ("citation_count", "is_open_access"):
            val = source.get(field)
            if val:
                updates.append(f"{field} = ?")
                params.append(val)
        if updates:
            params.append(source_id)
            conn.execute(
                f"UPDATE sources SET {', '.join(updates)} WHERE id = ?",
                params,
            )
            conn.commit()
        conn.close()
        return source_id

    # Authors: serialize to JSON if it's a list
    authors = source.get("authors", "")
    if isinstance(authors, list):
        authors = json.dumps(authors)

    cur = conn.execute(
        """INSERT INTO sources
           (origin, doi, title, authors, year, journal, volume, issue, pages,
            url, pdf_url, abstract, full_text_path, summary,
            citation_count, relevance_score, quality_score,
            is_open_access, included, fetched_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)""",
        (
            source.get("origin", "unknown"),
            doi,
            source.get("title", ""),
            authors,
            source.get("year", ""),
            source.get("journal", ""),
            source.get("volume", ""),
            source.get("issue", ""),
            source.get("pages", ""),
            source.get("url", ""),
            source.get("pdf_url", ""),
            source.get("abstract", ""),
            source.get("full_text_path", ""),
            source.get("summary", ""),
            source.get("citation_count", 0),
            source.get("relevance_score", 0.0),
            source.get("quality_score", 0.0),
            source.get("is_open_access", 0),
            now,
        ),
    )
    conn.commit()
    source_id = cur.lastrowid
    conn.close()
    return source_id


def save_sources_bulk(project_name: str, sources: list[dict]) -> int:
    """Insert multiple sources, skipping DOI duplicates. Returns count inserted."""
    count = 0
    for s in sources:
        try:
            upsert_source(project_name, s)
            count += 1
        except sqlite3.IntegrityError:
            pass  # DOI duplicate
    return count


def get_all_sources(project_name: str) -> list[dict]:
    conn = get_connection(project_name)
    rows = conn.execute("SELECT * FROM sources ORDER BY quality_score DESC, id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_included_sources(project_name: str) -> list[dict]:
    conn = get_connection(project_name)
    rows = conn.execute(
        "SELECT * FROM sources WHERE included = 1 ORDER BY quality_score DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def toggle_source_inclusion(project_name: str, source_id: int) -> bool:
    """Toggle the included flag. Returns the new value."""
    conn = get_connection(project_name)
    conn.execute(
        "UPDATE sources SET included = CASE WHEN included = 1 THEN 0 ELSE 1 END WHERE id = ?",
        (source_id,),
    )
    conn.commit()
    row = conn.execute("SELECT included FROM sources WHERE id = ?", (source_id,)).fetchone()
    conn.close()
    return bool(row["included"]) if row else False


def update_source_field(project_name: str, source_id: int, field: str, value) -> None:
    conn = get_connection(project_name)
    conn.execute(f"UPDATE sources SET {field} = ? WHERE id = ?", (value, source_id))
    conn.commit()
    conn.close()


def update_source_scores(project_name: str, source_id: int,
                         relevance: float, quality: float) -> None:
    conn = get_connection(project_name)
    conn.execute(
        "UPDATE sources SET relevance_score = ?, quality_score = ? WHERE id = ?",
        (relevance, quality, source_id),
    )
    conn.commit()
    conn.close()


def get_source_by_id(project_name: str, source_id: int) -> Optional[dict]:
    conn = get_connection(project_name)
    row = conn.execute("SELECT * FROM sources WHERE id = ?", (source_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_sources_with_doi(project_name: str) -> list[dict]:
    conn = get_connection(project_name)
    rows = conn.execute(
        "SELECT * FROM sources WHERE doi IS NOT NULL AND doi != ''"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Source-Section mappings
# ---------------------------------------------------------------------------

def save_source_section(project_name: str, source_id: int,
                        section_key: str, relevance: float = 0.0) -> None:
    conn = get_connection(project_name)
    conn.execute(
        """INSERT OR REPLACE INTO source_sections (source_id, section_key, relevance)
           VALUES (?, ?, ?)""",
        (source_id, section_key, relevance),
    )
    conn.commit()
    conn.close()


def get_sources_for_section(project_name: str, section_key: str) -> list[dict]:
    conn = get_connection(project_name)
    rows = conn.execute(
        """SELECT s.* FROM sources s
           JOIN source_sections ss ON s.id = ss.source_id
           WHERE ss.section_key = ? AND s.included = 1
           ORDER BY ss.relevance DESC""",
        (section_key,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Bibliography
# ---------------------------------------------------------------------------

def save_bib_entry(project_name: str, source_id: int, bibtex_key: str,
                   bibtex_type: str, bibtex_raw: str, apa_formatted: str = "") -> None:
    conn = get_connection(project_name)
    conn.execute(
        """INSERT OR REPLACE INTO bibliography
           (source_id, bibtex_key, bibtex_type, bibtex_raw, apa_formatted, verified)
           VALUES (?, ?, ?, ?, ?, 1)""",
        (source_id, bibtex_key, bibtex_type, bibtex_raw, apa_formatted),
    )
    conn.commit()
    conn.close()


def get_bib_entry(project_name: str, source_id: int) -> Optional[dict]:
    conn = get_connection(project_name)
    row = conn.execute(
        "SELECT * FROM bibliography WHERE source_id = ?", (source_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_bib_entries(project_name: str) -> list[dict]:
    conn = get_connection(project_name)
    rows = conn.execute(
        "SELECT b.*, s.title, s.year FROM bibliography b JOIN sources s ON b.source_id = s.id"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_citation_map(project_name: str) -> dict[int, str]:
    """Return {source_id: '(Author, Year)'} for inline citations."""
    conn = get_connection(project_name)
    rows = conn.execute(
        "SELECT source_id, bibtex_key FROM bibliography"
    ).fetchall()
    conn.close()

    result = {}
    for row in rows:
        # Parse the bibtex_key (e.g., "smith2024") into "(Smith, 2024)"
        key = row["bibtex_key"]
        # We need author info from sources table for proper formatting
        # This is handled by citations/formatter.py — store the key for now
        result[row["source_id"]] = key
    return result


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------

def save_section(project_name: str, version: int, section_key: str,
                 section_title: str, order_index: int,
                 scaffold_content: str = "", draft_content: str = "",
                 status: str = "pending") -> None:
    conn = get_connection(project_name)
    word_count = len(draft_content.split()) if draft_content else 0
    conn.execute(
        """INSERT OR REPLACE INTO sections
           (version, section_key, section_title, order_index,
            scaffold_content, draft_content, word_count, status, generated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (version, section_key, section_title, order_index,
         scaffold_content, draft_content, word_count, status, _now()),
    )
    conn.commit()
    conn.close()


def get_sections(project_name: str, version: int) -> list[dict]:
    conn = get_connection(project_name)
    rows = conn.execute(
        "SELECT * FROM sections WHERE version = ? ORDER BY order_index",
        (version,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_section(project_name: str, version: int, section_key: str) -> Optional[dict]:
    conn = get_connection(project_name)
    row = conn.execute(
        "SELECT * FROM sections WHERE version = ? AND section_key = ?",
        (version, section_key),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_section_draft(project_name: str, version: int, section_key: str,
                         draft_content: str) -> None:
    conn = get_connection(project_name)
    word_count = len(draft_content.split())
    conn.execute(
        """UPDATE sections SET draft_content = ?, word_count = ?,
           status = 'drafted', generated_at = ?
           WHERE version = ? AND section_key = ?""",
        (draft_content, word_count, _now(), version, section_key),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------

def save_feedback_item(project_name: str, feedback_file: str, item_text: str,
                       target_section: str = "", severity: str = "minor") -> int:
    conn = get_connection(project_name)
    cur = conn.execute(
        """INSERT INTO feedback_items (feedback_file, item_text, target_section, severity, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (feedback_file, item_text, target_section, severity, _now()),
    )
    conn.commit()
    fid = cur.lastrowid
    conn.close()
    return fid


def get_feedback_items(project_name: str, status: str = "open") -> list[dict]:
    conn = get_connection(project_name)
    rows = conn.execute(
        "SELECT * FROM feedback_items WHERE status = ? ORDER BY id", (status,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_feedback_status(project_name: str, item_id: int, status: str) -> None:
    conn = get_connection(project_name)
    conn.execute("UPDATE feedback_items SET status = ? WHERE id = ?", (status, item_id))
    conn.commit()
    conn.close()
