#!/usr/bin/env python3
"""Clean local subtitle or text files into the same JSON schema as fetch_content.py."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Import shared helpers from sibling module
from fetch_content import build_candidate_pools, srt_to_text, vtt_to_text


def read_input(path: Path) -> str:
    raw = path.read_text(encoding="utf-8", errors="replace")
    suffix = path.suffix.lower()
    if suffix == ".vtt":
        return vtt_to_text(raw)
    if suffix == ".srt":
        return srt_to_text(raw)
    return raw.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Clean local subtitles/text for IELTS vocab mining")
    parser.add_argument("--input", required=True, help="Path to .vtt, .srt, or .txt")
    parser.add_argument("--title", default="Local transcript")
    parser.add_argument("--url", default="local://file")
    parser.add_argument("--date", default="unknown")
    parser.add_argument("--out", help="Write JSON to this path (also prints to stdout)")
    args = parser.parse_args()

    path = Path(args.input)
    if not path.exists():
        print(json.dumps({"warnings": [f"file not found: {path}"]}), file=sys.stderr)
        return 1

    text = read_input(path)
    warnings: list[str] = []
    if len(text) < 50:
        warnings.append("text_very_short")

    result = {
        "title": args.title,
        "url": args.url,
        "date": args.date,
        "source_type": "local",
        "text": text,
        **build_candidate_pools(text),
        "warnings": warnings,
    }

    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(payload, encoding="utf-8")
    print(payload)
    return 0 if text else 1


if __name__ == "__main__":
    sys.exit(main())
