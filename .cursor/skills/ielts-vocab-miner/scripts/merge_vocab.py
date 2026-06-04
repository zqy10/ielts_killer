#!/usr/bin/env python3
"""Merge reviewed .tex source blocks into vocabulary.tex by source category."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from learner import (
    classify_source_url,
    find_repo_root,
    format_source_block,
    ielts_vocab_dir,
    load_sidecar_meta,
    parse_source_blocks,
    reviewed_dir,
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
}

PLACEHOLDER_MARKERS = ("暂无内容", r"\begin{verbatim}")


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


def blocks_from_section_content(content: str) -> list[dict]:
    if section_is_placeholder(content):
        return []
    return parse_source_blocks(content)


def block_key_set(blocks: list[dict]) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for b in blocks:
        url = b.get("url", "")
        for e in b.get("entries", []):
            keys.add((e.get("word", "").lower(), url))
        if not b.get("entries") and url:
            keys.add(("__source__", url))
    return keys


def merge_blocks(existing: list[dict], incoming: list[dict]) -> list[dict]:
    merged = list(existing)
    seen_urls = {b.get("url", "") for b in existing if b.get("url")}
    seen_keys = block_key_set(existing)

    for block in incoming:
        url = block.get("url", "")
        if url and url in seen_urls:
            new_entries = []
            for e in block.get("entries", []):
                k = (e.get("word", "").lower(), url)
                if k not in seen_keys:
                    new_entries.append(e)
                    seen_keys.add(k)
            if new_entries:
                for i, b in enumerate(merged):
                    if b.get("url") == url:
                        merged[i] = {
                            **b,
                            "entries": b.get("entries", []) + new_entries,
                        }
                        break
            continue
        if url:
            seen_urls.add(url)
        for e in block.get("entries", []):
            seen_keys.add((e.get("word", "").lower(), url))
        merged.append(block)
    return merged


def render_section(category: str, blocks: list[dict]) -> str:
    lines = [SECTION_DEFS[category]["header"], SECTION_DEFS[category]["markboth"], ""]
    for block in blocks:
        lines.append(format_source_block(block).rstrip())
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def collect_reviewed_blocks(reviewed: Path) -> dict[str, list[dict]]:
    by_cat: dict[str, list[dict]] = {"video": [], "article": [], "book": []}
    for tex_path in sorted(reviewed.glob("*.tex")):
        content = tex_path.read_text(encoding="utf-8")
        meta = load_sidecar_meta(tex_path)
        for block in parse_source_blocks(content):
            cat = classify_source_url(block.get("url", ""), meta)
            by_cat[cat].append(block)
    return by_cat


def merge_vocabulary(vocabulary_path: Path, reviewed: Path) -> None:
    text = vocabulary_path.read_text(encoding="utf-8")
    prefix, sections, suffix = split_vocabulary_tex(text)
    incoming = collect_reviewed_blocks(reviewed)

    out_sections: dict[str, str] = {}
    for cat in ("video", "article", "book"):
        existing_blocks = blocks_from_section_content(sections.get(cat, ""))
        merged = merge_blocks(existing_blocks, incoming.get(cat, []))
        out_sections[cat] = render_section(cat, merged)

    body = "\n\n".join(out_sections[cat] for cat in ("video", "article", "book"))
    if suffix and not suffix.startswith("\n"):
        suffix = "\n" + suffix
    vocabulary_path.write_text(prefix + body + suffix, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge reviewed tex into vocabulary.tex")
    parser.add_argument("--vocabulary", type=Path, help="Path to vocabulary.tex")
    parser.add_argument("--reviewed-dir", type=Path, help="Reviewed directory")
    args = parser.parse_args()

    repo = find_repo_root()
    vocab = args.vocabulary or (ielts_vocab_dir(repo) / "vocabulary.tex")
    rev = args.reviewed_dir or reviewed_dir(repo)

    if not vocab.exists():
        print(f"vocabulary.tex not found: {vocab}", file=sys.stderr)
        return 1

    merge_vocabulary(vocab.resolve(), rev.resolve())
    print(f"Merged reviewed blocks into {vocab}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
