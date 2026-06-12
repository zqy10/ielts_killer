#!/usr/bin/env python3
"""tex/路径解析工具：定位仓库目录、解析与格式化 \\vocabsource / \\vocabentry 块。

供生成主线（fetch → ingest → render）共享，无审核/偏好逻辑。
"""

from __future__ import annotations

import json
import re
from pathlib import Path


def find_repo_root(start: Path | None = None) -> Path:
    cur = (start or Path(__file__)).resolve()
    if cur.is_file():
        cur = cur.parent
    for parent in [cur, *cur.parents]:
        if (parent / "ielts-vocab").is_dir():
            return parent
    return cur.parents[3] if len(cur.parents) > 3 else cur


def ielts_vocab_dir(repo_root: Path | None = None) -> Path:
    root = repo_root or find_repo_root()
    return root / "ielts-vocab"


def pending_dir(repo_root: Path | None = None) -> Path:
    d = ielts_vocab_dir(repo_root) / "pending"
    d.mkdir(parents=True, exist_ok=True)
    return d


def classify_source_url(url: str, meta: dict | None = None) -> str:
    """Return video | article | book | other."""
    if meta and meta.get("source_type") in ("video", "article", "book", "other"):
        return meta["source_type"]
    u = (url or "").lower()
    if u.startswith("local://my-words"):
        return "other"
    if any(x in u for x in ("youtube.com", "youtu.be", "ted.com", "nebula.tv")):
        return "video"
    if any(x in u for x in ("goodreads", ".epub", "/dp/", "books.google")):
        return "book"
    if u.startswith("local://") or not u:
        return "article"
    return "article"


def parse_braced_args(s: str, start: int) -> tuple[list[str], int]:
    """Parse {a}{b}{c} from s starting at index of first '{'. Returns fields, index after."""
    fields: list[str] = []
    i = start
    n = len(s)
    while i < n:
        if s[i] != "{":
            break
        i += 1
        depth = 1
        buf: list[str] = []
        while i < n and depth > 0:
            ch = s[i]
            if ch == "{":
                depth += 1
                buf.append(ch)
            elif ch == "}":
                depth -= 1
                if depth > 0:
                    buf.append(ch)
            else:
                buf.append(ch)
            i += 1
        fields.append("".join(buf))
    return fields, i


def parse_vocabsource_line(line: str) -> tuple[str, str, str] | None:
    m = re.search(r"\\vocabsource", line)
    if not m:
        return None
    fields, _ = parse_braced_args(line, m.end())
    if len(fields) < 3:
        return None
    return fields[0], fields[1], fields[2]


def parse_vocabentry_line(line: str) -> dict | None:
    m = re.search(r"\\vocabentry", line)
    if not m:
        return None
    fields, _ = parse_braced_args(line, m.end())
    if len(fields) != 7:
        return None
    return {
        "word": fields[0],
        "pos": fields[1],
        "ipa": fields[2],
        "gloss_zh": fields[3],
        "example": fields[4],
        "synonyms": fields[5],
        "antonyms": fields[6],
        "raw": line.strip(),
    }


def format_vocabentry(entry: dict) -> str:
    return (
        f"\\vocabentry{{{entry['word']}}}{{{entry['pos']}}}{{{entry['ipa']}}}"
        f"{{{entry['gloss_zh']}}}{{{entry['example']}}}{{{entry['synonyms']}}}"
        f"{{{entry['antonyms']}}}"
    )


def load_sidecar_meta(tex_path: Path) -> dict | None:
    meta_path = tex_path.with_suffix(".meta.json")
    if not meta_path.exists():
        meta_path = tex_path.parent / (tex_path.stem + ".meta.json")
    if not meta_path.exists():
        return None
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def parse_source_blocks(tex_content: str) -> list[dict]:
    """Split tex into source blocks; preserves raw entry text for multi-line entries."""
    lines = tex_content.splitlines()
    blocks: list[dict] = []
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if not stripped.startswith("\\vocabsource"):
            i += 1
            continue
        source_line = stripped
        parsed = parse_vocabsource_line(stripped)
        title, url, date = parsed if parsed else ("", "", "")
        block_lines = [source_line, ""]
        entries: list[dict] = []
        i += 1
        while i < len(lines):
            s = lines[i].strip()
            if s.startswith("\\vocabsource") or s.startswith("\\section"):
                break
            if not s or s.startswith("%"):
                i += 1
                continue
            if "\\vocabentry" in lines[i]:
                single = parse_vocabentry_line(lines[i])
                if single:
                    entries.append(single)
                    block_lines.append(format_vocabentry(single))
                    i += 1
                    continue
                entry_buf = [lines[i]]
                i += 1
                while i < len(lines):
                    s = lines[i].strip()
                    if s.startswith("\\vocabentry") or s.startswith("\\vocabsource") or s.startswith(
                        "\\section"
                    ):
                        break
                    entry_buf.append(lines[i])
                    i += 1
                joined = "".join(x.strip() for x in entry_buf)
                parsed_entry = parse_vocabentry_line(joined)
                if parsed_entry:
                    entries.append(parsed_entry)
                block_lines.extend(entry_buf)
                block_lines.append("")
                continue
            block_lines.append(lines[i])
            i += 1
        blocks.append(
            {
                "source_line": source_line,
                "title": title,
                "url": url,
                "date": date,
                "entries": entries,
                "raw": "\n".join(block_lines).strip() + "\n",
            }
        )
    return blocks


def format_source_block(block: dict) -> str:
    if block.get("entries"):
        lines = [block["source_line"], ""]
        for e in block["entries"]:
            lines.append(format_vocabentry(e))
        return "\n".join(lines) + "\n"
    return block.get("raw", block.get("source_line", "")) + "\n"
