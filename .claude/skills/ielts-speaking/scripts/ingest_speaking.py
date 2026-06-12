#!/usr/bin/env python3
"""Ingest pending speaking JSON into the DB and regenerate speaking.tex.

Runs with NO human gate (mirrors the other skills). Each file in
`ielts-speaking/pending/*.json` is one of two kinds (the `kind` field):

  - "bank"    : one topic + its questions with Band 8.5+ model answers
                (Flow A — 题库生成). Upserts the topic, upserts every question
                (de-duplicated globally by part + question text, so re-ingesting
                never mints new question numbers), and logs the listed sources.
  - "attempt" : one scored practice answer for an existing question number
                (Flow B — 评分). Validates the question exists, recomputes the
                overall band as the mean of FC/LR/GRA rounded to the nearest 0.5,
                and inserts the attempt row.

Files that ingest cleanly are deleted (the DB is the authoritative store);
files that fail validation are KEPT in pending/ and reported, so a bad attempt
(e.g. an unknown question number) is never silently lost.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

from speaking_db import (
    connect,
    db_path,
    find_repo_root,
    insert_attempt,
    log_source,
    pending_dir,
    render_speaking_tex,
    tex_path,
    upsert_question,
)
import speaking_db


def _ingest_bank(conn: sqlite3.Connection, rec: dict) -> list[int]:
    """Ingest one bank record. Return the question ids touched (new or existing)."""
    questions = rec.get("questions") or []
    if not questions:
        raise ValueError("bank record has no questions[]")
    for q in questions:
        if not (q.get("question_text") or "").strip():
            raise ValueError("a question is missing question_text")
        if not (q.get("model_answer") or "").strip():
            raise ValueError(f"question missing model_answer: {q.get('question_text', '')[:60]!r}")
    topic_id = speaking_db.upsert_topic(conn, rec)
    qids: list[int] = []
    for ord_, q in enumerate(questions):
        qid, _created = upsert_question(conn, topic_id, ord_, q)
        qids.append(qid)
    for s in rec.get("sources", []) or []:
        log_source(
            conn,
            url=s.get("url", ""),
            kind=s.get("kind", "search"),
            query=s.get("query", ""),
            part=s.get("part", rec.get("part_group", "")),
            theme=s.get("theme", rec.get("theme", "")),
            title=s.get("title", ""),
        )
    if rec.get("source_url"):
        log_source(
            conn,
            url=rec["source_url"],
            kind="question_bank",
            query=rec.get("theme", ""),
            part=rec.get("part_group", ""),
            theme=rec.get("theme", ""),
            title=rec.get("topic_title", ""),
        )
    return qids


def _ingest_attempt(conn: sqlite3.Connection, rec: dict) -> int:
    qid = rec.get("question_id")
    if not isinstance(qid, int):
        raise ValueError(f"question_id must be an integer, got {qid!r}")
    # SQLite does not enforce FKs by default — validate by hand so an attempt can
    # never reference a question number that was never issued.
    row = conn.execute("SELECT id FROM questions WHERE id = ?", (qid,)).fetchone()
    if not row:
        raise ValueError(f"question Q{qid} does not exist in the bank")
    if not (rec.get("transcript") or "").strip():
        raise ValueError("attempt is missing transcript")
    for k in ("score_fc", "score_lr", "score_gra"):
        v = rec.get(k)
        if not isinstance(v, (int, float)) or not (0 <= float(v) <= 9):
            raise ValueError(f"{k} must be a number in [0, 9], got {v!r}")
    insert_attempt(conn, rec)
    return qid


def ingest(pending: Path, speaking: Path, database: Path) -> tuple[int, int, list[str]]:
    """Return (banks ingested, attempts ingested, failure messages)."""
    conn = connect(database)
    ingested_files: list[Path] = []
    failures: list[str] = []
    n_banks = n_attempts = 0
    try:
        for jf in sorted(pending.glob("*.json")):
            try:
                rec = json.loads(jf.read_text(encoding="utf-8"))
                items = rec if isinstance(rec, list) else [rec]
                for item in items:
                    kind = item.get("kind", "")
                    if kind == "bank":
                        qids = _ingest_bank(conn, item)
                        n_banks += 1
                        print(f"  bank {jf.name}: questions Q{min(qids)}–Q{max(qids)}")
                    elif kind == "attempt":
                        qid = _ingest_attempt(conn, item)
                        n_attempts += 1
                        print(f"  attempt {jf.name}: scored Q{qid}")
                    else:
                        raise ValueError(f"unknown kind {kind!r} (expected 'bank' or 'attempt')")
                ingested_files.append(jf)
            except (ValueError, json.JSONDecodeError, KeyError) as e:
                failures.append(f"{jf.name}: {e}")
                print(f"  KEPT (failed): {jf.name}: {e}", file=sys.stderr)
        render_speaking_tex(conn, speaking)
    finally:
        conn.close()
    for f in ingested_files:
        f.unlink()
    return n_banks, n_attempts, failures


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ingest pending speaking JSON into the DB and regenerate speaking.tex"
    )
    parser.add_argument("--pending-dir", type=Path, default=None)
    parser.add_argument("--tex", type=Path, default=None)
    parser.add_argument("--db", type=Path, default=None)
    args = parser.parse_args()

    repo = find_repo_root()
    pending = (args.pending_dir or pending_dir(repo)).resolve()
    speaking = (args.tex or tex_path(repo)).resolve()
    database = (args.db or db_path(repo)).resolve()

    if not speaking.exists():
        print(f"speaking.tex not found: {speaking}", file=sys.stderr)
        return 1

    n_banks, n_attempts, failures = ingest(pending, speaking, database)
    print(
        f"Ingested {n_banks} bank file(s) + {n_attempts} attempt(s) into {database}; "
        f"regenerated {speaking}."
    )
    if failures:
        print(f"{len(failures)} file(s) kept in pending/ due to errors:", file=sys.stderr)
        for msg in failures:
            print(f"  - {msg}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
