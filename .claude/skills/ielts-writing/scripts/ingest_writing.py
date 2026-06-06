#!/usr/bin/env python3
"""Ingest pending essay JSON into the DB and regenerate writing.tex.

Runs with NO human gate (mirrors the vocab skill). Each `ielts-writing/pending/*.json`
describes one prompt + one generated essay (and optionally the full sample text,
analysis, highlights, and the URLs that were searched). For each file we:

  1. upsert the prompt (de-duplicated by a hash of the prompt text),
  2. insert the essay row,
  3. log every listed source URL (so future runs skip re-searching),

then regenerate writing.tex from the DB and delete the ingested pending files
(the DB is the authoritative store).
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

from writing_db import (
    connect,
    db_path,
    find_repo_root,
    insert_essay,
    log_source,
    pending_dir,
    render_writing_tex,
    tex_path,
    upsert_prompt,
)


def _ingest_file(conn: sqlite3.Connection, path: Path) -> int:
    rec = json.loads(path.read_text(encoding="utf-8"))
    items = rec if isinstance(rec, list) else [rec]
    count = 0
    for item in items:
        if not item.get("essay_text") or not item.get("prompt_text"):
            print(f"  skip (missing prompt_text/essay_text): {path.name}", file=sys.stderr)
            continue
        prompt_id = upsert_prompt(conn, item)
        insert_essay(conn, prompt_id, item)
        for s in item.get("sources", []) or []:
            log_source(
                conn,
                url=s.get("url", ""),
                kind=s.get("kind", "search"),
                query=s.get("query", ""),
                task_type=s.get("task_type", item.get("task_type", "")),
                theme=s.get("theme", item.get("theme", "")),
                title=s.get("title", ""),
            )
        # The sample essay's own source counts as a visited URL too.
        if item.get("sample_source_url"):
            log_source(
                conn,
                url=item["sample_source_url"],
                kind="sample_essay",
                query=item.get("theme", ""),
                task_type=item.get("task_type", ""),
                theme=item.get("theme", ""),
            )
        count += 1
    return count


def ingest(pending: Path, vocabulary: Path, database: Path) -> int:
    conn = connect(database)
    ingested_files: list[Path] = []
    total = 0
    try:
        for jf in sorted(pending.glob("*.json")):
            total += _ingest_file(conn, jf)
            ingested_files.append(jf)
        render_writing_tex(conn, vocabulary)
    finally:
        conn.close()
    for f in ingested_files:
        f.unlink()
    return total


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ingest pending essay JSON into the DB and regenerate writing.tex"
    )
    parser.add_argument("--pending-dir", type=Path, default=None)
    parser.add_argument("--tex", type=Path, default=None)
    parser.add_argument("--db", type=Path, default=None)
    args = parser.parse_args()

    repo = find_repo_root()
    pending = (args.pending_dir or pending_dir(repo)).resolve()
    vocabulary = (args.tex or tex_path(repo)).resolve()
    database = (args.db or db_path(repo)).resolve()

    if not vocabulary.exists():
        print(f"writing.tex not found: {vocabulary}", file=sys.stderr)
        return 1

    total = ingest(pending, vocabulary, database)
    print(
        f"Ingested {total} essay(s) into {database}; "
        f"regenerated {vocabulary}; pending cleared."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
