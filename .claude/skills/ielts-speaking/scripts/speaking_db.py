#!/usr/bin/env python3
"""SQLite store for the IELTS speaking skill (stdlib only).

The DB (`ielts-speaking/speaking.db`) is the authoritative store; `speaking.tex`
is rendered as a readable view from it and compiled to a PDF with three sections:
Part 1 (grouped by topic), Part 2 & 3 (grouped by cue-card topic), and the
practice log (chronological scoring records).

Four tables:
  - sources   : every searched/visited URL + the query that surfaced it, so future
                requests can check the local bank first instead of re-searching.
  - topics    : topic groups (de-duplicated by part_group + title hash).
  - questions : the question bank. `id` is the GLOBAL user-facing question number
                (Q17) — AUTOINCREMENT so numbers are never reused; de-duplicated
                by a hash of part + question text so re-ingest never mints new ids.
  - attempts  : the user's scored practice answers (transcript + FC/LR/GRA +
                overall + advice/upgrades/grammar fixes). Pronunciation is never
                stored: it cannot be judged from a transcript and renders as N/A.

Searching/fetching questions is done by the agent's own WebSearch/WebFetch tools —
this module only touches the DB and renders the .tex. No third-party dependencies.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Canonical speaking themes: key -> (中文, English). Used for subsection titles.
# ---------------------------------------------------------------------------
THEME_LABELS: dict[str, tuple[str, str]] = {
    "hometown": ("家乡", "Hometown"),
    "home": ("住所", "Home & Accommodation"),
    "work-study": ("工作与学习", "Work & Study"),
    "hobbies": ("兴趣爱好", "Hobbies & Leisure"),
    "people": ("人物与关系", "People & Relationships"),
    "daily-life": ("日常生活", "Daily Life"),
    "technology": ("科技", "Technology"),
    "travel": ("旅行与地点", "Travel & Places"),
    "food": ("饮食", "Food"),
    "media": ("媒体与娱乐", "Media & Entertainment"),
    "environment": ("环境与自然", "Environment & Nature"),
    "shopping": ("购物与消费", "Shopping & Consumption"),
    "health": ("健康", "Health"),
    "education": ("教育", "Education"),
    "culture": ("文化与节日", "Culture & Festivals"),
    "experiences": ("经历与事件", "Experiences & Events"),
    "objects": ("物品", "Objects"),
    "other": ("其他", "Other"),
}

PART_GROUPS = ("p1", "p23")

SECTION = {
    "p1": {
        "header": r"\section{Part 1：日常问答 (Speaking Part 1)}",
        "markboth": r"\markboth{Part 1 日常问答}{}",
    },
    "p23": {
        "header": r"\section{Part 2 \& 3：话题卡与深入讨论 (Speaking Part 2 \& 3)}",
        "markboth": r"\markboth{Part 2 \& 3 话题卡与深入讨论}{}",
    },
    "log": {
        "header": r"\section{练习记录 (Practice Log)}",
        "markboth": r"\markboth{练习记录}{}",
    },
}

BODY_START = "% >>> GENERATED BODY START — do not edit between the sentinels (speaking_db.py rewrites this)"
BODY_END = "% <<< GENERATED BODY END"


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
def find_repo_root(start: Path | None = None) -> Path:
    # The skill lives at .claude/skills/ielts-speaking/, whose name collides with the
    # project's ielts-speaking/ dir — so require the repo root to hold BOTH the
    # ielts-speaking/ workspace AND the .claude/ dir to avoid matching the skill dir.
    cur = (start or Path(__file__)).resolve()
    if cur.is_file():
        cur = cur.parent
    for parent in [cur, *cur.parents]:
        if (parent / "ielts-speaking").is_dir() and (parent / ".claude").is_dir():
            return parent
    return cur.parents[3] if len(cur.parents) > 3 else cur


def ielts_speaking_dir(repo_root: Path | None = None) -> Path:
    return (repo_root or find_repo_root()) / "ielts-speaking"


def db_path(repo_root: Path | None = None) -> Path:
    return ielts_speaking_dir(repo_root) / "speaking.db"


def tex_path(repo_root: Path | None = None) -> Path:
    return ielts_speaking_dir(repo_root) / "speaking.tex"


def pending_dir(repo_root: Path | None = None) -> Path:
    d = ielts_speaking_dir(repo_root) / "pending"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS sources (
            url        TEXT PRIMARY KEY,
            kind       TEXT,
            query      TEXT,
            part       TEXT,
            theme      TEXT,
            title      TEXT,
            fetched_at INTEGER
        );
        CREATE TABLE IF NOT EXISTS topics (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            topic_hash TEXT UNIQUE,
            part_group TEXT NOT NULL,
            theme      TEXT NOT NULL,
            title      TEXT NOT NULL,
            source_url TEXT,
            added_at   INTEGER
        );
        CREATE TABLE IF NOT EXISTS questions (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            question_hash TEXT UNIQUE,
            topic_id      INTEGER NOT NULL REFERENCES topics(id),
            part          TEXT NOT NULL,
            ord           INTEGER DEFAULT 0,
            question_text TEXT NOT NULL,
            cue_points    TEXT,
            model_answer  TEXT NOT NULL,
            word_count    INTEGER,
            added_at      INTEGER
        );
        CREATE TABLE IF NOT EXISTS attempts (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id   INTEGER NOT NULL REFERENCES questions(id),
            transcript    TEXT NOT NULL,
            score_fc      REAL,
            score_lr      REAL,
            score_gra     REAL,
            overall       REAL,
            advice        TEXT,
            upgrades      TEXT,
            grammar_fixes TEXT,
            attempted_at  INTEGER
        );
        """
    )
    conn.commit()


def connect(database: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(database)
    init_db(conn)
    return conn


# ---------------------------------------------------------------------------
# Normalisation / dedup helpers
# ---------------------------------------------------------------------------
def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def topic_hash(part_group: str, title: str) -> str:
    return hashlib.sha1(f"{part_group}|{_normalize(title)}".encode("utf-8")).hexdigest()


def question_hash(part: str, question_text: str) -> str:
    return hashlib.sha1(f"{part}|{_normalize(question_text)}".encode("utf-8")).hexdigest()


def _theme_key(theme: str) -> str:
    key = (theme or "").strip().lower()
    return key if key in THEME_LABELS else "other"


def _part_group_key(value: str) -> str:
    key = re.sub(r"[\s&-]+", "", (value or "").strip().lower())
    if key in ("p1", "part1", "1", "one"):
        return "p1"
    if key in ("p23", "part23", "p2", "p3", "part2", "part3", "2", "3", "23",
               "part2and3", "p2andp3", "part2part3"):
        return "p23"
    return key if key in PART_GROUPS else "p23"


def _part_key(value: str) -> str:
    key = re.sub(r"[\s&-]+", "", (value or "").strip().lower())
    if key in ("p1", "part1", "1"):
        return "p1"
    if key in ("p2", "part2", "2"):
        return "p2"
    if key in ("p3", "part3", "3"):
        return "p3"
    return "p1"


PART_DISPLAY = {"p1": "1", "p2": "2", "p3": "3"}


def round_half(value: float) -> float:
    """Round to the nearest 0.5, halves up (6.25 -> 6.5)."""
    return int(value * 2 + 0.5) / 2


# ---------------------------------------------------------------------------
# Mutations
# ---------------------------------------------------------------------------
def upsert_topic(conn: sqlite3.Connection, rec: dict) -> int:
    """Insert a topic (dedup by part_group+title hash, first wins). Return its id."""
    title = (rec.get("topic_title") or rec.get("title") or "").strip()
    if not title:
        raise ValueError("topic_title is required")
    pg = _part_group_key(rec.get("part_group", ""))
    h = topic_hash(pg, title)
    row = conn.execute("SELECT id FROM topics WHERE topic_hash = ?", (h,)).fetchone()
    if row:
        return row[0]
    cur = conn.execute(
        "INSERT INTO topics (topic_hash, part_group, theme, title, source_url, added_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (h, pg, _theme_key(rec.get("theme", "")), title,
         rec.get("source_url", ""), int(time.time())),
    )
    conn.commit()
    return cur.lastrowid


def upsert_question(conn: sqlite3.Connection, topic_id: int, ord_: int, rec: dict) -> tuple[int, bool]:
    """Insert a question (dedup by part+text hash, first wins).

    Return (question id, created) — the id is the global user-facing number.
    """
    text = (rec.get("question_text") or "").strip()
    if not text:
        raise ValueError("question_text is required")
    part = _part_key(rec.get("part", ""))
    h = question_hash(part, text)
    row = conn.execute("SELECT id FROM questions WHERE question_hash = ?", (h,)).fetchone()
    if row:
        return row[0], False
    cue_points = rec.get("cue_points") or []
    cur = conn.execute(
        "INSERT INTO questions (question_hash, topic_id, part, ord, question_text, "
        " cue_points, model_answer, word_count, added_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            h, topic_id, part, ord_, text,
            json.dumps(cue_points, ensure_ascii=False) if cue_points else "",
            rec.get("model_answer", ""),
            int(rec.get("word_count") or _count_words(rec.get("model_answer", ""))),
            int(time.time()),
        ),
    )
    conn.commit()
    return cur.lastrowid, True


def insert_attempt(conn: sqlite3.Connection, rec: dict) -> int:
    """Insert a scored attempt. The question must already exist (validated by caller)."""
    qid = int(rec["question_id"])
    scores = [float(rec.get(k)) for k in ("score_fc", "score_lr", "score_gra")]
    overall = round_half(sum(scores) / len(scores))
    cur = conn.execute(
        "INSERT INTO attempts (question_id, transcript, score_fc, score_lr, score_gra, "
        " overall, advice, upgrades, grammar_fixes, attempted_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            qid,
            rec.get("transcript", ""),
            scores[0], scores[1], scores[2], overall,
            rec.get("advice", ""),
            json.dumps(rec.get("upgrades") or [], ensure_ascii=False),
            json.dumps(rec.get("grammar_fixes") or [], ensure_ascii=False),
            int(time.time()),
        ),
    )
    conn.commit()
    return cur.lastrowid


def log_source(
    conn: sqlite3.Connection,
    url: str,
    kind: str = "search",
    query: str = "",
    part: str = "",
    theme: str = "",
    title: str = "",
) -> None:
    if not url:
        return
    conn.execute(
        "INSERT INTO sources (url, kind, query, part, theme, title, fetched_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(url) DO UPDATE SET kind=excluded.kind, query=excluded.query, "
        " part=excluded.part, theme=excluded.theme, title=excluded.title, "
        " fetched_at=excluded.fetched_at",
        (url, kind, query, _part_group_key(part) if part else "", theme, title,
         int(time.time())),
    )
    conn.commit()


def _count_words(text: str) -> int:
    return len(re.findall(r"[A-Za-z][A-Za-z'-]*", text or ""))


# ---------------------------------------------------------------------------
# Queries (used by the agent to avoid re-searching / to fetch a question to score)
# ---------------------------------------------------------------------------
def find_topics(conn: sqlite3.Connection, part: str = "", theme: str = "") -> list[dict]:
    where, params = [], []
    if part:
        where.append("t.part_group = ?")
        params.append(_part_group_key(part))
    if theme:
        where.append("t.theme = ?")
        params.append(_theme_key(theme))
    sql = (
        "SELECT t.id, t.part_group, t.theme, t.title, COUNT(q.id) "
        "FROM topics t LEFT JOIN questions q ON q.topic_id = t.id"
    )
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " GROUP BY t.id ORDER BY t.id"
    keys = ("id", "part_group", "theme", "title", "question_count")
    return [dict(zip(keys, r)) for r in conn.execute(sql, params).fetchall()]


def find_questions(
    conn: sqlite3.Connection, part: str = "", theme: str = "", topic_id: int | None = None
) -> list[dict]:
    where, params = [], []
    if part:
        where.append("t.part_group = ?")
        params.append(_part_group_key(part))
    if theme:
        where.append("t.theme = ?")
        params.append(_theme_key(theme))
    if topic_id is not None:
        where.append("q.topic_id = ?")
        params.append(topic_id)
    sql = (
        "SELECT q.id, q.part, t.theme, t.title, q.question_text "
        "FROM questions q JOIN topics t ON t.id = q.topic_id"
    )
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY q.id"
    keys = ("id", "part", "theme", "topic_title", "question_text")
    return [dict(zip(keys, r)) for r in conn.execute(sql, params).fetchall()]


def get_question(conn: sqlite3.Connection, qid: int) -> dict | None:
    row = conn.execute(
        "SELECT q.id, q.part, q.topic_id, t.part_group, t.theme, t.title, "
        "       q.question_text, q.cue_points, q.model_answer, q.word_count "
        "FROM questions q JOIN topics t ON t.id = q.topic_id WHERE q.id = ?",
        (qid,),
    ).fetchone()
    if not row:
        return None
    keys = ("id", "part", "topic_id", "part_group", "theme", "topic_title",
            "question_text", "cue_points", "model_answer", "word_count")
    rec = dict(zip(keys, row))
    try:
        rec["cue_points"] = json.loads(rec["cue_points"]) if rec["cue_points"] else []
    except json.JSONDecodeError:
        rec["cue_points"] = []
    rec["attempts_count"] = conn.execute(
        "SELECT COUNT(*) FROM attempts WHERE question_id = ?", (qid,)
    ).fetchone()[0]
    return rec


def find_sources(
    conn: sqlite3.Connection, part: str = "", theme: str = "", kind: str = ""
) -> list[dict]:
    where, params = [], []
    if part:
        where.append("part = ?")
        params.append(_part_group_key(part))
    if theme:
        where.append("theme = ?")
        params.append(theme)
    if kind:
        where.append("kind = ?")
        params.append(kind)
    sql = "SELECT url, kind, query, part, theme, title FROM sources"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY fetched_at DESC"
    keys = ("url", "kind", "query", "part", "theme", "title")
    return [dict(zip(keys, r)) for r in conn.execute(sql, params).fetchall()]


# ---------------------------------------------------------------------------
# LaTeX rendering
# ---------------------------------------------------------------------------
_LATEX_SPECIAL = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def latex_escape(text: str) -> str:
    out = []
    for ch in text or "":
        out.append(_LATEX_SPECIAL.get(ch, ch))
    return "".join(out)


def _apply_inline_highlights(escaped: str) -> str:
    """Convert [[good expression]] markers (left intact by latex_escape, since [ ] are
    not LaTeX specials) into \\hi{...} so the phrase is highlighted in the prose."""
    return re.sub(r"\[\[(.+?)\]\]", r"\\hi{\1}", escaped)


def latex_paragraphs(text: str, highlights: bool = True) -> str:
    """Escape prose and join paragraphs with \\par.

    `highlights=True` additionally converts [[...]] spans to \\hi{...} — used for
    model answers only. User transcripts must pass highlights=False (arbitrary
    speech, [[...]] has no meaning there).
    """
    paras = [p.strip() for p in re.split(r"\n\s*\n", (text or "").strip()) if p.strip()]
    escaped = [latex_escape(re.sub(r"\s*\n\s*", " ", p)) for p in paras]
    if highlights:
        escaped = [_apply_inline_highlights(p) for p in escaped]
    return "\n\n\\par\n\n".join(escaped)


def _fmt_score(value) -> str:
    return f"{float(value):.1f}" if value is not None else "—"


def _strip_markers(text: str) -> str:
    return re.sub(r"\[\[(.+?)\]\]", r"\1", text or "")


def _render_answer(model_answer: str, word_count) -> str:
    wc = str(int(word_count)) if word_count else ""
    return f"\\answermeta{{{wc}}}\n{latex_paragraphs(model_answer)}"


def _render_p1_topic(theme: str, title: str, questions: list[tuple]) -> str:
    theme_zh, theme_en = THEME_LABELS.get(theme, THEME_LABELS["other"])
    lines = [f"\\subsection{{{latex_escape(theme_zh)} {latex_escape(theme_en)} — {latex_escape(title)}}}", ""]
    for qid, part, q_text, _cues, answer, wc in questions:
        lines.append(f"\\speakingq{{{qid}}}{{{PART_DISPLAY.get(part, '1')}}}{{{latex_escape(q_text)}}}")
        lines.append(_render_answer(answer, wc))
        lines.append("")
    lines.append("\\vspace{10pt}\\hrule height 0.2pt\\vspace{10pt}")
    return "\n".join(lines)


def _render_cue_card(qid: int, q_text: str, cues_json: str) -> str:
    try:
        cues = json.loads(cues_json) if cues_json else []
    except json.JSONDecodeError:
        cues = []
    lines = [
        "\\begin{cuecardbox}",
        f"\\noindent{{\\large\\bfseries\\textcolor{{headerblue}}{{Q{qid}}}}}"
        "\\enspace{\\small\\bfseries\\textcolor{cuecardborder}{[Part 2]}}\\par\\vspace{3pt}",
        f"\\noindent\\textbf{{{latex_escape(q_text)}}}\\par\\vspace{{2pt}}",
    ]
    if cues:
        lines.append("You should say:")
        lines.append("\\begin{itemize}\\setlength\\itemsep{1pt}")
        for c in cues:
            lines.append(f"\\item {latex_escape(c)}")
        lines.append("\\end{itemize}")
    lines.append("\\end{cuecardbox}")
    return "\n".join(lines)


def _render_p23_topic(theme: str, title: str, questions: list[tuple]) -> str:
    theme_zh, theme_en = THEME_LABELS.get(theme, THEME_LABELS["other"])
    lines = [f"\\subsection{{{latex_escape(theme_zh)} {latex_escape(theme_en)} — {latex_escape(title)}}}", ""]
    for qid, part, q_text, cues_json, answer, wc in questions:
        if part == "p2":
            lines.append(_render_cue_card(qid, q_text, cues_json))
        else:
            lines.append(f"\\speakingq{{{qid}}}{{{PART_DISPLAY.get(part, '3')}}}{{{latex_escape(q_text)}}}")
        lines.append(_render_answer(answer, wc))
        lines.append("")
    lines.append("\\vspace{10pt}\\hrule height 0.2pt\\vspace{10pt}")
    return "\n".join(lines)


def _topics_with_questions(conn: sqlite3.Connection, part_group: str) -> list[tuple]:
    """[(theme, title, [(qid, part, text, cue_points, model_answer, word_count), ...])]"""
    topics = conn.execute(
        "SELECT id, theme, title FROM topics WHERE part_group = ? ORDER BY id",
        (part_group,),
    ).fetchall()
    out = []
    for tid, theme, title in topics:
        # Cue card (p2) first, then by global number — stable even when later
        # ingests append questions to an existing topic with overlapping `ord`s.
        qs = conn.execute(
            "SELECT id, part, question_text, cue_points, model_answer, word_count "
            "FROM questions WHERE topic_id = ? ORDER BY (part != 'p2'), id",
            (tid,),
        ).fetchall()
        if qs:
            out.append((theme, title, qs))
    return out


def _render_bank_section(conn: sqlite3.Connection, part_group: str) -> str:
    out = [SECTION[part_group]["header"], SECTION[part_group]["markboth"], ""]
    topics = _topics_with_questions(conn, part_group)
    if not topics:
        out.append("\\textit{暂无内容}")
        return "\n".join(out).rstrip() + "\n"
    render = _render_p1_topic if part_group == "p1" else _render_p23_topic
    for theme, title, qs in topics:
        out.append(render(theme, title, qs))
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def _render_json_list(items_json: str) -> list[dict]:
    try:
        items = json.loads(items_json) if items_json else []
    except json.JSONDecodeError:
        items = []
    return items if isinstance(items, list) else []


def _render_attempt_block(row: tuple) -> str:
    (qid, part, q_text, transcript, fc, lr, gra, overall,
     advice, upgrades_json, fixes_json, attempted_at) = row
    date = datetime.fromtimestamp(attempted_at).strftime("%Y-%m-%d") if attempted_at else ""
    lines = [
        "\\begin{attemptbox}",
        f"\\noindent{{\\large\\bfseries\\textcolor{{headerblue}}{{Q{qid}}}}}"
        f"\\enspace{{\\small\\bfseries\\textcolor{{attemptborder}}{{[Part {PART_DISPLAY.get(part, '?')}]}}}}"
        f"\\hfill{{\\small\\textcolor{{metacolor}}{{{date}}}}}\\par\\vspace{{2pt}}",
        f"\\noindent{{\\itshape {latex_escape(_strip_markers(q_text))}}}\\par\\vspace{{4pt}}",
        "\\noindent\\textbf{你的回答（转写）：}\\par\\vspace{2pt}",
        latex_paragraphs(transcript, highlights=False),
        f"\\scoreline{{{_fmt_score(fc)}}}{{{_fmt_score(lr)}}}{{{_fmt_score(gra)}}}{{{_fmt_score(overall)}}}",
    ]
    upgrades = _render_json_list(upgrades_json)
    if upgrades:
        lines.append("\\noindent\\textbf{表达升级}\\par")
        lines.append("\\begin{itemize}\\setlength\\itemsep{1pt}")
        for u in upgrades:
            said = latex_escape(u.get("said", ""))
            better = latex_escape(_strip_markers(u.get("better", "")))
            note = latex_escape(u.get("note", ""))
            tail = f" \\textcolor{{gray}}{{——{note}}}" if note else ""
            lines.append(f"\\item “{said}” → \\hi{{{better}}}{tail}")
        lines.append("\\end{itemize}")
    fixes = _render_json_list(fixes_json)
    if fixes:
        lines.append("\\noindent\\textbf{语法修正}\\par")
        lines.append("\\begin{itemize}\\setlength\\itemsep{1pt}")
        for f in fixes:
            err = latex_escape(f.get("error", ""))
            fix = latex_escape(f.get("fix", ""))
            note = latex_escape(f.get("note", ""))
            tail = f" \\textcolor{{gray}}{{——{note}}}" if note else ""
            lines.append(f"\\item \\textcolor{{fixcolor}}{{{err}}} → \\textbf{{{fix}}}{tail}")
        lines.append("\\end{itemize}")
    if advice:
        lines.append("\\noindent\\textbf{改进建议}\\par\\vspace{2pt}")
        lines.append(latex_paragraphs(advice, highlights=False))
    lines.append("\\end{attemptbox}")
    return "\n".join(lines)


def _render_log_section(conn: sqlite3.Connection) -> str:
    out = [SECTION["log"]["header"], SECTION["log"]["markboth"], ""]
    rows = conn.execute(
        "SELECT q.id, q.part, q.question_text, a.transcript, a.score_fc, a.score_lr, "
        "       a.score_gra, a.overall, a.advice, a.upgrades, a.grammar_fixes, a.attempted_at "
        "FROM attempts a JOIN questions q ON q.id = a.question_id "
        "ORDER BY a.attempted_at, a.id",
    ).fetchall()
    if not rows:
        out.append("\\textit{暂无内容}")
        return "\n".join(out).rstrip() + "\n"
    for row in rows:
        out.append(_render_attempt_block(row))
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def render_speaking_tex(conn: sqlite3.Connection, speaking_path: Path) -> None:
    text = speaking_path.read_text(encoding="utf-8")
    if BODY_START not in text or BODY_END not in text:
        raise ValueError(
            f"{speaking_path}: missing body sentinels ({BODY_START!r} / {BODY_END!r})"
        )
    prefix = text.split(BODY_START)[0]
    suffix = text.split(BODY_END, 1)[1]
    body = "\n\n".join(
        [_render_bank_section(conn, "p1"), _render_bank_section(conn, "p23"),
         _render_log_section(conn)]
    )
    new_text = f"{prefix}{BODY_START}\n\n{body}\n{BODY_END}{suffix}"
    speaking_path.write_text(new_text, encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _print_rows(rows: list[dict], as_json: bool) -> None:
    if as_json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    if not rows:
        print("(none)")
        return
    for r in rows:
        print(json.dumps(r, ensure_ascii=False))


def main() -> int:
    parser = argparse.ArgumentParser(description="IELTS speaking DB / renderer")
    parser.add_argument("--db", type=Path, help="SQLite DB (default speaking.db)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="Create the DB and tables")

    p_ft = sub.add_parser("find-topics", help="List stored topics")
    p_ft.add_argument("--part", default="")
    p_ft.add_argument("--theme", default="")
    p_ft.add_argument("--json", action="store_true")

    p_fq = sub.add_parser("find-questions", help="List stored questions")
    p_fq.add_argument("--part", default="")
    p_fq.add_argument("--theme", default="")
    p_fq.add_argument("--topic", type=int, default=None)
    p_fq.add_argument("--json", action="store_true")

    p_gq = sub.add_parser("get-question", help="Fetch one question by global number")
    p_gq.add_argument("--id", type=int, required=True)
    p_gq.add_argument("--json", action="store_true")

    p_fs = sub.add_parser("find-sources", help="List logged search/visit URLs")
    p_fs.add_argument("--part", default="")
    p_fs.add_argument("--theme", default="")
    p_fs.add_argument("--kind", default="")
    p_fs.add_argument("--json", action="store_true")

    p_ls = sub.add_parser("log-source", help="Record a searched/visited URL")
    p_ls.add_argument("--url", required=True)
    p_ls.add_argument("--kind", default="search")
    p_ls.add_argument("--query", default="")
    p_ls.add_argument("--part", default="")
    p_ls.add_argument("--theme", default="")
    p_ls.add_argument("--title", default="")

    p_rn = sub.add_parser("render", help="Regenerate speaking.tex from the DB")
    p_rn.add_argument("--tex", type=Path, default=None)

    args = parser.parse_args()
    repo = find_repo_root()
    database = args.db or db_path(repo)

    if args.cmd == "init":
        conn = connect(database)
        conn.close()
        print(f"Initialised {database}")
        return 0

    conn = connect(database)
    try:
        if args.cmd == "find-topics":
            _print_rows(find_topics(conn, args.part, args.theme), args.json)
        elif args.cmd == "find-questions":
            _print_rows(find_questions(conn, args.part, args.theme, args.topic), args.json)
        elif args.cmd == "get-question":
            rec = get_question(conn, args.id)
            if rec is None:
                print(f"Question Q{args.id} not found", file=sys.stderr)
                return 1
            _print_rows([rec], args.json)
        elif args.cmd == "find-sources":
            _print_rows(find_sources(conn, args.part, args.theme, args.kind), args.json)
        elif args.cmd == "log-source":
            log_source(conn, args.url, args.kind, args.query, args.part, args.theme, args.title)
            print(f"Logged {args.url}")
        elif args.cmd == "render":
            tex = args.tex or tex_path(repo)
            render_speaking_tex(conn, tex.resolve())
            print(f"Regenerated {tex}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
