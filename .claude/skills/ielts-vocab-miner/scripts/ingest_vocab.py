#!/usr/bin/env python3
"""Generation workflow: ingest pending .tex into the DB and regenerate vocabulary.tex.

Runs with NO human gate. Pending blocks are merged into the SQLite word store as
*unreviewed* words (reviewed=0); words on the hard reject list are skipped. After
a successful render, the pending source files are deleted (the DB is the
authoritative store). Human review happens separately via review_vocab.py.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

from learner import find_repo_root, ielts_vocab_dir, load_preferences, pending_dir
from vocab_db import (
    db_path,
    import_pending,
    init_db,
    migrate_from_tex,
    render_vocabulary_tex,
)


def ingest_vocabulary(vocabulary_path: Path, pending: Path, database: Path) -> int:
    """Merge pending/*.tex into the DB, regenerate vocabulary.tex, clear pending.

    Returns the count of new (unreviewed) words ingested.
    """
    conn = sqlite3.connect(database)
    try:
        init_db(conn)
        # Seed from existing tex (idempotent, reviewed=1) so manual edits and
        # pre-DB content are absorbed, then ingest fresh pending as unreviewed.
        migrate_from_tex(conn, vocabulary_path)
        reject = set(load_preferences().get("reject_lemmas") or [])
        new_words = import_pending(conn, pending, reject)
        render_vocabulary_tex(conn, vocabulary_path)
    finally:
        conn.close()

    # Render succeeded → drop the pending source files (DB is authoritative).
    for f in pending.glob("*.tex"):
        f.unlink()
    for f in pending.glob("*.meta.json"):
        f.unlink()
    return new_words


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ingest pending tex into the DB and regenerate vocabulary.tex"
    )
    parser.add_argument("--vocabulary", type=Path, help="Path to vocabulary.tex")
    parser.add_argument("--pending-dir", type=Path, help="Pending directory")
    parser.add_argument("--db", type=Path, help="SQLite word store (default vocab.db)")
    args = parser.parse_args()

    repo = find_repo_root()
    vocab = args.vocabulary or (ielts_vocab_dir(repo) / "vocabulary.tex")
    pending = args.pending_dir or pending_dir(repo)
    database = args.db or db_path(repo)

    if not vocab.exists():
        print(f"vocabulary.tex not found: {vocab}", file=sys.stderr)
        return 1

    new_words = ingest_vocabulary(vocab.resolve(), pending.resolve(), database.resolve())
    print(
        f"Ingested {new_words} new (unreviewed) words into {vocab} "
        f"(store: {database}); pending cleared."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
