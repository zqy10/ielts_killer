#!/usr/bin/env python3
"""SQLite word store: authoritative, globally de-duplicated vocab list.

`vocabulary.tex` is rendered as a readable view from this DB. De-dup key is the
lowercased word (`word_lower`); first occurrence wins (`INSERT OR IGNORE`).
"""

from __future__ import annotations

import re
import sqlite3
import time
from pathlib import Path

from texlib import (
    classify_source_url,
    format_source_block,
    ielts_vocab_dir,
    load_sidecar_meta,
    parse_source_blocks,
)

SECTION_DEFS = {
    "video": {
        "header": r"\section{视频来源 (From Videos)}",
        "markboth": r"\markboth{视频来源}{}",
    },
    "article": {
        "header": r"\section{文章来源 (From Articles)}",
        "markboth": r"\markboth{文章来源}{}",
    },
    "book": {
        "header": r"\section{书籍来源 (From Books)}",
        "markboth": r"\markboth{书籍来源}{}",
    },
    "other": {
        "header": r"\section{其他来源 (Other Sources)}",
        "markboth": r"\markboth{其他来源}{}",
    },
}

CATEGORIES = ("video", "article", "book", "other")
PLACEHOLDER_MARKERS = ("暂无内容", r"\begin{verbatim}")


def db_path(repo_root: Path | None = None) -> Path:
    return ielts_vocab_dir(repo_root) / "vocab.db"


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS sources (
            url        TEXT PRIMARY KEY,
            title      TEXT,
            date       TEXT,
            category   TEXT,
            first_seen INTEGER
        );
        CREATE TABLE IF NOT EXISTS words (
            word_lower TEXT PRIMARY KEY,
            word       TEXT,
            pos        TEXT,
            ipa        TEXT,
            gloss_zh   TEXT,
            example    TEXT,
            synonyms   TEXT,
            antonyms   TEXT,
            source_url TEXT,
            added_at   INTEGER,
            ord        INTEGER
        );
        """
    )
    conn.commit()


def _next_ord(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COALESCE(MAX(ord), 0) FROM words").fetchone()
    return (row[0] or 0) + 1


def _next_first_seen(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COALESCE(MAX(first_seen), 0) FROM sources").fetchone()
    return (row[0] or 0) + 1


def ingest_blocks(
    conn: sqlite3.Connection,
    blocks: list[dict],
    default_meta: dict | None = None,
) -> int:
    """Upsert sources and de-duplicated words. Returns count of new words."""
    new_words = 0
    ord_counter = _next_ord(conn)
    for block in blocks:
        url = block.get("url", "")
        category = classify_source_url(url, default_meta)
        # Register the source once (first-wins on first_seen ordering).
        if url:
            existing = conn.execute(
                "SELECT url FROM sources WHERE url = ?", (url,)
            ).fetchone()
            if existing is None:
                conn.execute(
                    "INSERT INTO sources (url, title, date, category, first_seen) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        url,
                        block.get("title", ""),
                        block.get("date", ""),
                        category,
                        _next_first_seen(conn),
                    ),
                )
        for e in block.get("entries", []):
            word = e.get("word", "")
            wl = word.strip().lower()
            if not wl:
                continue
            cur = conn.execute(
                "INSERT OR IGNORE INTO words "
                "(word_lower, word, pos, ipa, gloss_zh, example, synonyms, "
                " antonyms, source_url, added_at, ord) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    wl,
                    word,
                    e.get("pos", ""),
                    e.get("ipa", ""),
                    e.get("gloss_zh", ""),
                    e.get("example", ""),
                    e.get("synonyms", ""),
                    e.get("antonyms", ""),
                    url,
                    int(time.time()),
                    ord_counter,
                ),
            )
            if cur.rowcount:
                new_words += 1
                ord_counter += 1
    conn.commit()
    return new_words


def migrate_from_tex(conn: sqlite3.Connection, vocabulary_path: Path) -> int:
    """Seed the DB from existing vocabulary.tex. Idempotent (INSERT OR IGNORE)."""
    if not vocabulary_path.exists():
        return 0
    text = vocabulary_path.read_text(encoding="utf-8")
    _prefix, sections, _suffix = split_vocabulary_tex(text)
    total = 0
    for cat in CATEGORIES:
        content = sections.get(cat, "")
        if section_is_placeholder(content):
            continue
        total += ingest_blocks(conn, parse_source_blocks(content))
    return total


def import_pending(conn: sqlite3.Connection, pending: Path) -> int:
    """Ingest pending/*.tex into the DB (de-duplicated by lowercased word)."""
    total = 0
    for tex_path in sorted(pending.glob("*.tex")):
        content = tex_path.read_text(encoding="utf-8")
        meta = load_sidecar_meta(tex_path)
        total += ingest_blocks(conn, parse_source_blocks(content), meta)
    return total


# ---- vocabulary.tex rendering -------------------------------------------------


def split_vocabulary_tex(text: str) -> tuple[str, dict[str, str], str]:
    """Return prefix (through toc), section bodies by key, appendix suffix."""
    appendix_split = re.split(r"(\\newpage\s*\n\\section\*\{附录)", text, maxsplit=1)
    if len(appendix_split) == 3:
        main, appendix_start, appendix_rest = appendix_split
        suffix = appendix_start + appendix_rest
    else:
        main = text
        suffix = ""

    first_section = re.search(r"\\section\{视频来源", main)
    if not first_section:
        raise ValueError("vocabulary.tex: missing 视频来源 section")

    prefix = main[: first_section.start()]
    body = main[first_section.start() :]

    sections: dict[str, str] = {}
    patterns = [
        ("video", r"\\section\{视频来源"),
        ("article", r"\\section\{文章来源"),
        ("book", r"\\section\{书籍来源"),
        ("other", r"\\section\{其他来源"),
    ]
    for idx, (key, pat) in enumerate(patterns):
        m = re.search(pat, body)
        if not m:
            sections[key] = ""
            continue
        if idx + 1 < len(patterns):
            m2 = re.search(patterns[idx + 1][1], body)
            end = m2.start() if m2 else len(body)
        else:
            end = len(body)
        chunk = body[m.start() : end]
        header_end = chunk.find("\n", chunk.find("}")) + 1
        sections[key] = chunk[header_end:].strip()

    return prefix, sections, suffix


def section_is_placeholder(content: str) -> bool:
    if not content.strip():
        return True
    return any(m in content for m in PLACEHOLDER_MARKERS)


def _blocks_for_category(conn: sqlite3.Connection, category: str) -> list[dict]:
    sources = conn.execute(
        "SELECT url, title, date FROM sources WHERE category = ? ORDER BY first_seen",
        (category,),
    ).fetchall()
    blocks: list[dict] = []
    for url, title, date in sources:
        rows = conn.execute(
            "SELECT word, pos, ipa, gloss_zh, example, synonyms, antonyms "
            "FROM words WHERE source_url = ? ORDER BY ord",
            (url,),
        ).fetchall()
        if not rows:
            continue
        entries = [
            {
                "word": r[0],
                "pos": r[1],
                "ipa": r[2],
                "gloss_zh": r[3],
                "example": r[4],
                "synonyms": r[5],
                "antonyms": r[6],
            }
            for r in rows
        ]
        blocks.append(
            {
                "source_line": f"\\vocabsource{{{title}}}{{{url}}}{{{date}}}",
                "entries": entries,
            }
        )
    return blocks


def _render_section(category: str, blocks: list[dict]) -> str:
    lines = [SECTION_DEFS[category]["header"], SECTION_DEFS[category]["markboth"], ""]
    if not blocks:
        lines.append("\\textit{暂无内容}")
        return "\n".join(lines).rstrip() + "\n"
    for block in blocks:
        lines.append(format_source_block(block).rstrip())
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_vocabulary_tex(conn: sqlite3.Connection, vocabulary_path: Path) -> None:
    text = vocabulary_path.read_text(encoding="utf-8")
    prefix, _sections, suffix = split_vocabulary_tex(text)

    out_sections = {
        cat: _render_section(cat, _blocks_for_category(conn, cat))
        for cat in CATEGORIES
    }
    body = "\n\n".join(out_sections[cat] for cat in CATEGORIES)
    if suffix and not suffix.startswith("\n"):
        suffix = "\n" + suffix
    vocabulary_path.write_text(prefix + body + suffix, encoding="utf-8")
