#!/usr/bin/env python3
"""Merge reviewed .tex into the SQLite word store and regenerate vocabulary.tex.

The DB (`ielts-vocab/vocab.db`) is the authoritative, globally de-duplicated word
list; `vocabulary.tex` is rendered from it. De-dup is by lowercased word
(first occurrence wins), so the same word from different sources never repeats.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

from learner import find_repo_root, ielts_vocab_dir, reviewed_dir
from vocab_db import (
    db_path,
    import_reviewed,
    init_db,
    migrate_from_tex,
    render_vocabulary_tex,
)


def merge_vocabulary(vocabulary_path: Path, reviewed: Path, database: Path) -> None:
    conn = sqlite3.connect(database)
    try:
        init_db(conn)
        # Seed from existing tex (idempotent) so manual edits and pre-DB content
        # are absorbed, then ingest freshly reviewed files.
        migrate_from_tex(conn, vocabulary_path)
        import_reviewed(conn, reviewed)
        render_vocabulary_tex(conn, vocabulary_path)
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge reviewed tex into vocabulary.tex")
    parser.add_argument("--vocabulary", type=Path, help="Path to vocabulary.tex")
    parser.add_argument("--reviewed-dir", type=Path, help="Reviewed directory")
    parser.add_argument("--db", type=Path, help="SQLite word store (default vocab.db)")
    args = parser.parse_args()

    repo = find_repo_root()
    vocab = args.vocabulary or (ielts_vocab_dir(repo) / "vocabulary.tex")
    rev = args.reviewed_dir or reviewed_dir(repo)
    database = args.db or db_path(repo)

    if not vocab.exists():
        print(f"vocabulary.tex not found: {vocab}", file=sys.stderr)
        return 1

    merge_vocabulary(vocab.resolve(), rev.resolve(), database.resolve())
    print(f"Merged reviewed blocks into {vocab} (store: {database})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
