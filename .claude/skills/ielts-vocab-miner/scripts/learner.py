#!/usr/bin/env python3
"""Persist user review feedback and generate learned-preferences for Agent/scripts."""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any

PREFERENCES_VERSION = 1


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


def reviewed_dir(repo_root: Path | None = None) -> Path:
    d = ielts_vocab_dir(repo_root) / "reviewed"
    d.mkdir(parents=True, exist_ok=True)
    return d


def classify_source_url(url: str, meta: dict | None = None) -> str:
    """Return video | article | book."""
    if meta and meta.get("source_type") in ("video", "article", "book"):
        return meta["source_type"]
    u = (url or "").lower()
    if any(x in u for x in ("youtube.com", "youtu.be", "ted.com", "nebula.tv")):
        return "video"
    if any(x in u for x in ("goodreads", ".epub", "/dp/", "books.google")):
        return "book"
    if u.startswith("local://") or not u:
        return "article"
    return "article"


def parse_vocabsource_line(line: str) -> tuple[str, str, str] | None:
    m = re.search(r"\\vocabsource", line)
    if not m:
        return None
    fields, _ = parse_braced_args(line, m.end())
    if len(fields) < 3:
        return None
    return fields[0], fields[1], fields[2]


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

def learner_dir(repo_root: Path | None = None) -> Path:
    root = repo_root or find_repo_root()
    d = root / "ielts-vocab" / "learner"
    d.mkdir(parents=True, exist_ok=True)
    return d


def preferences_path(repo_root: Path | None = None) -> Path:
    return learner_dir(repo_root) / "preferences.json"


def summary_path(repo_root: Path | None = None) -> Path:
    return learner_dir(repo_root) / "learned-preferences.md"


def default_preferences() -> dict[str, Any]:
    return {
        "version": PREFERENCES_VERSION,
        "lemma_boost": {},
        "lemma_penalty": {},
        "pos_boost": {},
        "min_length_preference": 7,
        "reject_lemmas": [],
        "prefer_phrases": True,
        "sessions": [],
    }


def load_preferences(repo_root: Path | None = None) -> dict[str, Any]:
    path = preferences_path(repo_root)
    if not path.exists():
        return default_preferences()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and data.get("version") == PREFERENCES_VERSION:
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return default_preferences()


def save_preferences(prefs: dict[str, Any], repo_root: Path | None = None) -> Path:
    path = preferences_path(repo_root)
    path.write_text(json.dumps(prefs, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _lemma_key(word: str) -> str:
    return word.split()[0].lower().strip()


def _pos_key(pos: str) -> str:
    m = {"n.": "NOUN", "v.": "VERB", "adj.": "ADJ", "adv.": "ADV", "phr.": "PHR"}
    return m.get(pos.strip().lower(), pos.upper())


def update_preferences(
    kept: list[dict],
    rejected: list[dict],
    learning_rate: int,
    source_file: str = "",
    repo_root: Path | None = None,
) -> dict[str, Any]:
    lr = max(0, min(100, int(learning_rate)))
    alpha = lr / 100.0
    prefs = load_preferences(repo_root)

    for entry in kept:
        lemma = _lemma_key(entry.get("word", ""))
        if not lemma:
            continue
        old = float(prefs["lemma_boost"].get(lemma, 0.0))
        prefs["lemma_boost"][lemma] = round(min(1.0, old * (1 - alpha) + 1.0 * alpha), 3)

    for entry in rejected:
        lemma = _lemma_key(entry.get("word", ""))
        if not lemma:
            continue
        old = float(prefs["lemma_penalty"].get(lemma, 0.0))
        new_pen = min(1.0, old * (1 - alpha) + 1.0 * alpha)
        prefs["lemma_penalty"][lemma] = round(new_pen, 3)
        if new_pen > 0.5:
            rejects = set(prefs.get("reject_lemmas") or [])
            rejects.add(lemma)
            prefs["reject_lemmas"] = sorted(rejects)

    if kept and alpha > 0:
        lengths = [len(_lemma_key(e.get("word", ""))) for e in kept]
        avg_len = sum(lengths) / len(lengths)
        old_min = float(prefs.get("min_length_preference", 7))
        prefs["min_length_preference"] = round(old_min * (1 - alpha) + avg_len * alpha)

        pos_counts: dict[str, int] = {}
        for e in kept:
            pk = _pos_key(e.get("pos", ""))
            pos_counts[pk] = pos_counts.get(pk, 0) + 1
        total = sum(pos_counts.values()) or 1
        for pk, cnt in pos_counts.items():
            old_p = float(prefs["pos_boost"].get(pk, 0.0))
            signal = cnt / total
            prefs["pos_boost"][pk] = round(min(1.0, old_p * (1 - alpha) + signal * alpha), 3)

        prefs["prefer_phrases"] = any(" " in e.get("word", "") for e in kept) or prefs.get(
            "prefer_phrases", True
        )

    prefs["sessions"] = (prefs.get("sessions") or [])[-19:]
    prefs["sessions"].append(
        {
            "file": source_file,
            "kept": len(kept),
            "rejected": len(rejected),
            "learning_rate": lr,
            "date": date.today().isoformat(),
        }
    )

    save_preferences(prefs, repo_root)
    write_summary(prefs, repo_root)
    return prefs


def write_summary(prefs: dict[str, Any], repo_root: Path | None = None) -> Path:
    boost = prefs.get("lemma_boost") or {}
    penalty = prefs.get("lemma_penalty") or {}
    top_keep = sorted(boost.items(), key=lambda x: -x[1])[:15]
    top_reject = sorted(penalty.items(), key=lambda x: -x[1])[:15]
    reject_list = prefs.get("reject_lemmas") or []
    pos_boost = prefs.get("pos_boost") or {}
    min_len = prefs.get("min_length_preference", 7)
    sessions = (prefs.get("sessions") or [])[-3:]

    lines = [
        "# Learned preferences (auto-generated)",
        "",
        "Agent: read this file before curating vocabulary when it exists.",
        "",
        f"- Preferred minimum lemma length (soft): **{min_len}**",
        f"- Prefer phrases: **{prefs.get('prefer_phrases', True)}**",
        "",
        "## Tend to keep",
    ]
    if top_keep:
        for lemma, w in top_keep:
            lines.append(f"- `{lemma}` (boost {w})")
    else:
        lines.append("- (none yet)")

    lines.extend(["", "## Tend to reject"])
    if top_reject:
        for lemma, w in top_reject:
            lines.append(f"- `{lemma}` (penalty {w})")
    else:
        lines.append("- (none yet)")

    if reject_list:
        lines.extend(["", "## Hard reject list"])
        lines.append(", ".join(f"`{x}`" for x in reject_list[:30]))

    if pos_boost:
        lines.extend(["", "## POS preference"])
        for pk, w in sorted(pos_boost.items(), key=lambda x: -x[1]):
            lines.append(f"- {pk}: {w}")

    lines.extend(["", "## Recent review sessions"])
    for s in sessions:
        lines.append(
            f"- {s.get('date')}: kept {s.get('kept')}, rejected {s.get('rejected')}, "
            f"lr={s.get('learning_rate')} — `{s.get('file', '')}`"
        )

    path = summary_path(repo_root)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def load_learner_weights(repo_root: Path | None = None) -> dict[str, Any]:
    """Weights for fetch_content scoring."""
    prefs = load_preferences(repo_root)
    return {
        "lemma_boost": prefs.get("lemma_boost") or {},
        "lemma_penalty": prefs.get("lemma_penalty") or {},
        "reject_lemmas": set(prefs.get("reject_lemmas") or []),
        "min_length_preference": int(prefs.get("min_length_preference", 7)),
        "pos_boost": prefs.get("pos_boost") or {},
    }


def apply_learner_score_adjustment(score: float, lemma: str, pos: str, weights: dict[str, Any]) -> float:
    if lemma in weights.get("reject_lemmas", set()):
        return -10.0
    score += float(weights.get("lemma_boost", {}).get(lemma, 0)) * 2.0
    score -= float(weights.get("lemma_penalty", {}).get(lemma, 0)) * 3.0
    min_len = int(weights.get("min_length_preference", 7))
    if len(lemma) < min_len:
        score -= 1.0
    pos_map = {"NOUN": "NOUN", "VERB": "VERB", "ADJ": "ADJ", "ADV": "ADV", "UNK": "UNK"}
    pk = pos if pos in pos_map else pos
    score += float(weights.get("pos_boost", {}).get(pk, 0)) * 0.5
    return score


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


def parse_tex_file(path: Path) -> tuple[str | None, list[dict]]:
    text = path.read_text(encoding="utf-8")
    source_line: str | None = None
    entries: list[dict] = []
    for line in text.splitlines():
        if line.strip().startswith("\\vocabsource"):
            source_line = line.strip()
        elif "\\vocabentry" in line:
            entry = parse_vocabentry_line(line)
            if entry:
                entries.append(entry)
    return source_line, entries


def format_vocabentry(entry: dict) -> str:
    return (
        f"\\vocabentry{{{entry['word']}}}{{{entry['pos']}}}{{{entry['ipa']}}}"
        f"{{{entry['gloss_zh']}}}{{{entry['example']}}}{{{entry['synonyms']}}}"
        f"{{{entry['antonyms']}}}"
    )


def write_reviewed_tex(
    source_line: str | None,
    kept: list[dict],
    out_path: Path,
) -> None:
    lines: list[str] = []
    if source_line:
        lines.append(source_line)
        lines.append("")
    for e in kept:
        lines.append(format_vocabentry(e))
    lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")
