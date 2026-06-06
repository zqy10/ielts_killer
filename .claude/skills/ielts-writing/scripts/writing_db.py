#!/usr/bin/env python3
"""SQLite store for the IELTS writing skill (stdlib only).

The DB (`ielts-writing/writing.db`) is the authoritative store; `writing.tex` is
rendered as a readable view from it and compiled to a PDF organised by task type
(Task 1 / Task 2) then by theme.

Three tables:
  - sources : every searched/visited URL + the query that surfaced it, so future
              requests can check the local bank first instead of re-searching.
  - prompts : the question bank (de-duplicated by a hash of the prompt text).
  - essays  : generated Band 8.5+ essays + the analysis and the full sample text.

Searching/fetching prompts and sample essays is done by the agent's own WebSearch/
WebFetch tools — this module only touches the DB, renders the .tex, and downloads
Task 1 chart images (urllib). No third-party dependencies, no venv.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
import time
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------------------
# Canonical themes: key -> (中文, English). Used for grouping + subsection titles.
# ---------------------------------------------------------------------------
THEME_LABELS: dict[str, tuple[str, str]] = {
    "education": ("教育", "Education"),
    "environment": ("环境", "Environment"),
    "technology": ("科技", "Technology"),
    "health": ("健康", "Health"),
    "society": ("社会与家庭", "Society & Family"),
    "government": ("政府与公共开支", "Government & Public Spending"),
    "crime": ("犯罪与法律", "Crime & Law"),
    "work": ("工作与职业", "Work & Career"),
    "globalisation": ("全球化", "Globalisation"),
    "media": ("媒体与广告", "Media & Advertising"),
    "transport": ("交通", "Transport"),
    "tourism": ("旅游", "Tourism"),
    "culture": ("文化", "Culture"),
    "science": ("科学", "Science"),
    "urbanisation": ("城市化", "Urbanisation"),
    "other": ("其他", "Other"),
}

TASK_TYPES = ("task1", "task2")

TASK_SECTION = {
    "task1": {
        "header": r"\section{Task 1：图表作文 (Academic Writing Task 1)}",
        "markboth": r"\markboth{Task 1 图表作文}{}",
    },
    "task2": {
        "header": r"\section{Task 2：议论文 (Writing Task 2)}",
        "markboth": r"\markboth{Task 2 议论文}{}",
    },
}

BODY_START = "% >>> GENERATED BODY START — do not edit between the sentinels (writing_db.py rewrites this)"
BODY_END = "% <<< GENERATED BODY END"


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
def find_repo_root(start: Path | None = None) -> Path:
    # The skill lives at .claude/skills/ielts-writing/, whose name collides with the
    # project's ielts-writing/ dir — so require the repo root to hold BOTH the
    # ielts-writing/ workspace AND the .claude/ dir to avoid matching the skill dir.
    cur = (start or Path(__file__)).resolve()
    if cur.is_file():
        cur = cur.parent
    for parent in [cur, *cur.parents]:
        if (parent / "ielts-writing").is_dir() and (parent / ".claude").is_dir():
            return parent
    return cur.parents[3] if len(cur.parents) > 3 else cur


def ielts_writing_dir(repo_root: Path | None = None) -> Path:
    return (repo_root or find_repo_root()) / "ielts-writing"


def db_path(repo_root: Path | None = None) -> Path:
    return ielts_writing_dir(repo_root) / "writing.db"


def tex_path(repo_root: Path | None = None) -> Path:
    return ielts_writing_dir(repo_root) / "writing.tex"


def pending_dir(repo_root: Path | None = None) -> Path:
    d = ielts_writing_dir(repo_root) / "pending"
    d.mkdir(parents=True, exist_ok=True)
    return d


def images_dir(repo_root: Path | None = None) -> Path:
    d = ielts_writing_dir(repo_root) / "images"
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
            task_type  TEXT,
            theme      TEXT,
            title      TEXT,
            fetched_at INTEGER
        );
        CREATE TABLE IF NOT EXISTS prompts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            prompt_hash TEXT UNIQUE,
            task_type   TEXT NOT NULL,
            subtype     TEXT,
            theme       TEXT NOT NULL,
            prompt_text TEXT NOT NULL,
            chart_desc  TEXT,
            image_path  TEXT,
            image_url   TEXT,
            source_url  TEXT,
            added_at    INTEGER
        );
        CREATE TABLE IF NOT EXISTS essays (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            prompt_id         INTEGER NOT NULL REFERENCES prompts(id),
            sample_found      INTEGER DEFAULT 0,
            sample_source_url TEXT,
            sample_title      TEXT,
            sample_text       TEXT,
            analysis          TEXT,
            highlights        TEXT,
            essay_text        TEXT NOT NULL,
            word_count        INTEGER,
            band              TEXT DEFAULT '8.5+',
            generated_at      INTEGER
        );
        """
    )
    conn.commit()
    ensure_schema(conn)


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Add columns missing from pre-existing DBs. Idempotent."""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(essays)").fetchall()}
    if "sample_title" not in cols:
        conn.execute("ALTER TABLE essays ADD COLUMN sample_title TEXT")
        conn.commit()


def connect(database: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(database)
    init_db(conn)
    return conn


# ---------------------------------------------------------------------------
# Normalisation / dedup helpers
# ---------------------------------------------------------------------------
def _normalize_prompt(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def prompt_hash(text: str) -> str:
    return hashlib.sha1(_normalize_prompt(text).encode("utf-8")).hexdigest()


def _theme_key(theme: str) -> str:
    key = (theme or "").strip().lower()
    return key if key in THEME_LABELS else "other"


def _task_key(task_type: str) -> str:
    key = (task_type or "").strip().lower().replace(" ", "")
    if key in ("task1", "t1", "1", "academic1"):
        return "task1"
    if key in ("task2", "t2", "2"):
        return "task2"
    return key if key in TASK_TYPES else "task2"


# ---------------------------------------------------------------------------
# Mutations
# ---------------------------------------------------------------------------
def upsert_prompt(conn: sqlite3.Connection, rec: dict) -> int:
    """Insert a prompt (dedup by prompt_hash, first wins). Return its row id."""
    text = rec.get("prompt_text", "").strip()
    if not text:
        raise ValueError("prompt_text is required")
    h = prompt_hash(text)
    row = conn.execute("SELECT id FROM prompts WHERE prompt_hash = ?", (h,)).fetchone()
    if row:
        return row[0]
    cur = conn.execute(
        "INSERT INTO prompts (prompt_hash, task_type, subtype, theme, prompt_text, "
        " chart_desc, image_path, image_url, source_url, added_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            h,
            _task_key(rec.get("task_type", "")),
            rec.get("subtype", ""),
            _theme_key(rec.get("theme", "")),
            text,
            rec.get("chart_desc", ""),
            rec.get("image_path", ""),
            rec.get("image_url", ""),
            rec.get("source_url") or rec.get("sample_source_url", ""),
            int(time.time()),
        ),
    )
    conn.commit()
    return cur.lastrowid


def insert_essay(conn: sqlite3.Connection, prompt_id: int, rec: dict) -> int:
    highlights = rec.get("highlights") or []
    cur = conn.execute(
        "INSERT INTO essays (prompt_id, sample_found, sample_source_url, sample_title, "
        " sample_text, analysis, highlights, essay_text, word_count, band, generated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            prompt_id,
            1 if rec.get("sample_found") else 0,
            rec.get("sample_source_url", ""),
            rec.get("sample_title", ""),
            rec.get("sample_text", ""),
            rec.get("analysis", ""),
            json.dumps(highlights, ensure_ascii=False),
            rec.get("essay_text", ""),
            int(rec.get("word_count") or _count_words(rec.get("essay_text", ""))),
            rec.get("band", "8.5+"),
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
    task_type: str = "",
    theme: str = "",
    title: str = "",
) -> None:
    if not url:
        return
    conn.execute(
        "INSERT INTO sources (url, kind, query, task_type, theme, title, fetched_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(url) DO UPDATE SET kind=excluded.kind, query=excluded.query, "
        " task_type=excluded.task_type, theme=excluded.theme, title=excluded.title, "
        " fetched_at=excluded.fetched_at",
        (url, kind, query, task_type, theme, title, int(time.time())),
    )
    conn.commit()


def _count_words(text: str) -> int:
    return len(re.findall(r"[A-Za-z][A-Za-z'-]*", text or ""))


# ---------------------------------------------------------------------------
# Queries (used by the agent to avoid re-searching)
# ---------------------------------------------------------------------------
def find_prompts(
    conn: sqlite3.Connection, task_type: str = "", theme: str = ""
) -> list[dict]:
    where, params = [], []
    if task_type:
        where.append("task_type = ?")
        params.append(_task_key(task_type))
    if theme:
        where.append("theme = ?")
        params.append(_theme_key(theme))
    sql = "SELECT id, task_type, subtype, theme, prompt_text, source_url FROM prompts"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY id"
    keys = ("id", "task_type", "subtype", "theme", "prompt_text", "source_url")
    return [dict(zip(keys, r)) for r in conn.execute(sql, params).fetchall()]


def find_sources(
    conn: sqlite3.Connection, task_type: str = "", theme: str = "", kind: str = ""
) -> list[dict]:
    where, params = [], []
    if task_type:
        where.append("task_type = ?")
        params.append(_task_key(task_type))
    if theme:
        where.append("theme = ?")
        params.append(_theme_key(theme))
    if kind:
        where.append("kind = ?")
        params.append(kind)
    sql = "SELECT url, kind, query, task_type, theme, title FROM sources"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY fetched_at DESC"
    keys = ("url", "kind", "query", "task_type", "theme", "title")
    return [dict(zip(keys, r)) for r in conn.execute(sql, params).fetchall()]


# ---------------------------------------------------------------------------
# Image download (Task 1 charts)
# ---------------------------------------------------------------------------
_EXT_BY_CTYPE = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
}


def download_image(url: str, dest_dir: Path, slug: str = "") -> str:
    """Download a chart image to dest_dir.

    Return the path relative to the ielts-writing/ dir (i.e. how \\includegraphics
    resolves it from writing.tex), e.g. ``images/chart.png``.
    """
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; IELTS-Writing/1.0)",
            "Accept": "image/*,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()
        ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
    ext = _EXT_BY_CTYPE.get(ctype, "")
    if not ext:
        m = re.search(r"\.(jpe?g|png|gif|webp|svg)(?:\?|$)", url, re.IGNORECASE)
        ext = ("." + m.group(1).lower().replace("jpeg", "jpg")) if m else ".png"
    base = re.sub(r"[^a-z0-9]+", "-", (slug or "chart").lower()).strip("-") or "chart"
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = f"{base}{ext}"
    out = dest_dir / name
    i = 2
    while out.exists():
        name = f"{base}-{i}{ext}"
        out = dest_dir / name
        i += 1
    out.write_bytes(data)
    base_dir = ielts_writing_dir()
    try:
        return str(out.resolve().relative_to(base_dir.resolve()))
    except ValueError:
        return str(out)


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


def latex_paragraphs(text: str) -> str:
    """Escape prose, highlight [[...]] spans, and join paragraphs with \\par."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", (text or "").strip()) if p.strip()]
    escaped = [
        _apply_inline_highlights(latex_escape(re.sub(r"\s*\n\s*", " ", p)))
        for p in paras
    ]
    return "\n\n\\par\n\n".join(escaped)


def _essay_blocks(conn: sqlite3.Connection, task_type: str) -> dict[str, list[str]]:
    """Return {theme_key: [rendered latex block, ...]} for one task type."""
    rows = conn.execute(
        "SELECT p.id, p.subtype, p.theme, p.prompt_text, p.chart_desc, p.image_path, "
        "       p.source_url, e.sample_found, e.sample_source_url, e.sample_title, "
        "       e.sample_text, e.analysis, e.highlights, e.essay_text, e.word_count, e.band "
        "FROM prompts p JOIN essays e ON e.prompt_id = p.id "
        "WHERE p.task_type = ? ORDER BY p.theme, e.id",
        (task_type,),
    ).fetchall()
    by_theme: dict[str, list[str]] = {}
    task_label = "Task 1" if task_type == "task1" else "Task 2"
    for r in rows:
        (
            _pid, subtype, theme, prompt_text, chart_desc, image_path, _src,
            _sf, sample_src, sample_title, sample_text, analysis, highlights_json,
            essay_text, word_count, band,
        ) = r
        by_theme.setdefault(theme, []).append(
            _render_essay_block(
                task_label, subtype, theme, prompt_text, chart_desc, image_path,
                sample_src, sample_title, sample_text, analysis, highlights_json,
                essay_text, word_count, band,
            )
        )
    return by_theme


def _render_prompt(task_label, subtype, theme, prompt_text) -> str:
    theme_zh, theme_en = THEME_LABELS.get(theme, THEME_LABELS["other"])
    return (
        f"\\writingprompt{{{latex_escape(task_label)}}}"
        f"{{{latex_escape(subtype or '')}}}"
        f"{{{latex_escape(f'{theme_zh} {theme_en}')}}}"
        f"{{{latex_escape(prompt_text)}}}"
    )


def _render_sample_box(sample_src, sample_title, sample_text) -> str:
    # Source shown as a title hyperlink, never a bare URL.
    src = ""
    if sample_src:
        label = latex_escape(sample_title or "查看原文")
        src = f" \\textcolor{{gray}}{{\\small (来源：\\href{{{sample_src}}}{{{label}}})}}"
    return (
        "\\begin{samplebox}\n"
        f"\\textbf{{参考范文}}{src}\\par\\vspace{{3pt}}\n"
        f"{latex_paragraphs(sample_text)}\n"
        "\\end{samplebox}"
    )


def _render_analysis_box(analysis, highlights_json) -> str | None:
    try:
        highlights = json.loads(highlights_json) if highlights_json else []
    except json.JSONDecodeError:
        highlights = []
    if not (analysis or highlights):
        return None
    block = ["\\begin{analysisbox}"]
    if analysis:
        block.append("\\textbf{亮点分析}\\par\\vspace{2pt}")
        block.append(latex_paragraphs(analysis))
    if highlights:
        block.append("\\vspace{3pt}\\textbf{高分表达}\\par")
        block.append("\\begin{itemize}\\setlength\\itemsep{1pt}")
        for h in highlights:
            expr = latex_escape(h.get("expr", ""))
            zh = latex_escape(h.get("zh", ""))
            note = latex_escape(h.get("note", ""))
            tail = f" \\textcolor{{gray}}{{——{note}}}" if note else ""
            block.append(f"\\item \\hi{{{expr}}}{(' （' + zh + '）') if zh else ''}{tail}")
        block.append("\\end{itemize}")
    block.append("\\end{analysisbox}")
    return "\n".join(block)


def _render_generated(band, word_count, essay_text) -> str:
    return (
        f"\\essaymeta{{{latex_escape(band or '8.5+')}}}{{{int(word_count or 0)}}}\n\n"
        f"{latex_paragraphs(essay_text)}"
    )


def _render_essay_block(
    task_label, subtype, theme, prompt_text, chart_desc, image_path,
    sample_src, sample_title, sample_text, analysis, highlights_json,
    essay_text, word_count, band,
) -> str:
    lines: list[str] = [_render_prompt(task_label, subtype, theme, prompt_text)]
    if image_path:
        lines.append(
            "\\begin{center}\\includegraphics[width=0.9\\linewidth,"
            f"keepaspectratio]{{{image_path}}}\\end{{center}}"
        )
    if chart_desc:
        lines.append(
            f"\\noindent\\textbf{{图表数据：}}{latex_escape(chart_desc)}\\par\\vspace{{4pt}}"
        )
    analysis_box = _render_analysis_box(analysis, highlights_json)
    generated = _render_generated(band, word_count, essay_text)
    # Order: 参考范文 → 亮点分析 → 生成范文. With no sample, the generated essay takes
    # the sample's place (shown first), with 亮点分析 kept after it.
    ordered: list[str | None] = (
        [_render_sample_box(sample_src, sample_title, sample_text), analysis_box, generated]
        if sample_text
        else [generated, analysis_box]
    )
    lines.extend(b for b in ordered if b)
    lines.append("\\vspace{10pt}\\hrule height 0.2pt\\vspace{10pt}")
    return "\n\n".join(lines)


def _render_task_section(conn: sqlite3.Connection, task_type: str) -> str:
    by_theme = _essay_blocks(conn, task_type)
    out = [TASK_SECTION[task_type]["header"], TASK_SECTION[task_type]["markboth"], ""]
    if not by_theme:
        out.append("\\textit{暂无内容}")
        return "\n".join(out).rstrip() + "\n"
    for theme in sorted(by_theme, key=lambda t: list(THEME_LABELS).index(t) if t in THEME_LABELS else 999):
        theme_zh, theme_en = THEME_LABELS.get(theme, THEME_LABELS["other"])
        out.append(f"\\subsection{{{theme_zh} ({theme_en})}}")
        out.append("")
        for block in by_theme[theme]:
            out.append(block)
            out.append("")
    return "\n".join(out).rstrip() + "\n"


def render_writing_tex(conn: sqlite3.Connection, vocabulary_path: Path) -> None:
    text = vocabulary_path.read_text(encoding="utf-8")
    if BODY_START not in text or BODY_END not in text:
        raise ValueError(
            f"{vocabulary_path}: missing body sentinels "
            f"({BODY_START!r} / {BODY_END!r})"
        )
    prefix = text.split(BODY_START)[0]
    suffix = text.split(BODY_END, 1)[1]
    body = "\n\n".join(_render_task_section(conn, t) for t in TASK_TYPES)
    new_text = f"{prefix}{BODY_START}\n\n{body}\n{BODY_END}{suffix}"
    vocabulary_path.write_text(new_text, encoding="utf-8")


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
    parser = argparse.ArgumentParser(description="IELTS writing DB / renderer")
    parser.add_argument("--db", type=Path, help="SQLite DB (default writing.db)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="Create the DB and tables")

    p_fp = sub.add_parser("find-prompts", help="List stored prompts")
    p_fp.add_argument("--task", default="")
    p_fp.add_argument("--theme", default="")
    p_fp.add_argument("--json", action="store_true")

    p_fs = sub.add_parser("find-sources", help="List logged search/visit URLs")
    p_fs.add_argument("--task", default="")
    p_fs.add_argument("--theme", default="")
    p_fs.add_argument("--kind", default="")
    p_fs.add_argument("--json", action="store_true")

    p_ls = sub.add_parser("log-source", help="Record a searched/visited URL")
    p_ls.add_argument("--url", required=True)
    p_ls.add_argument("--kind", default="search")
    p_ls.add_argument("--query", default="")
    p_ls.add_argument("--task", default="")
    p_ls.add_argument("--theme", default="")
    p_ls.add_argument("--title", default="")

    p_fi = sub.add_parser("fetch-image", help="Download a Task 1 chart image")
    p_fi.add_argument("--url", required=True)
    p_fi.add_argument("--out-dir", type=Path, default=None)
    p_fi.add_argument("--slug", default="")

    p_rn = sub.add_parser("render", help="Regenerate writing.tex from the DB")
    p_rn.add_argument("--tex", type=Path, default=None)

    args = parser.parse_args()
    repo = find_repo_root()
    database = args.db or db_path(repo)

    if args.cmd == "init":
        conn = connect(database)
        conn.close()
        print(f"Initialised {database}")
        return 0

    if args.cmd == "fetch-image":
        out_dir = args.out_dir or images_dir(repo)
        rel = download_image(args.url, out_dir, args.slug)
        print(rel)
        return 0

    conn = connect(database)
    try:
        if args.cmd == "find-prompts":
            _print_rows(find_prompts(conn, args.task, args.theme), args.json)
        elif args.cmd == "find-sources":
            _print_rows(find_sources(conn, args.task, args.theme, args.kind), args.json)
        elif args.cmd == "log-source":
            log_source(conn, args.url, args.kind, args.query, args.task, args.theme, args.title)
            print(f"Logged {args.url}")
        elif args.cmd == "render":
            tex = args.tex or tex_path(repo)
            render_writing_tex(conn, tex.resolve())
            print(f"Regenerated {tex}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
