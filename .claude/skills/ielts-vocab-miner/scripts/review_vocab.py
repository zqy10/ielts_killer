#!/usr/bin/env python3
"""Review workflow: annotate unreviewed words in the DB and learn preferences.

Operates on the SQLite word store (not on .tex files). Pulls all unreviewed words
(reviewed=0), lets the user keep/reject each one, then applies the result:
  - kept words   → marked reviewed=1
  - rejected words → deleted from the DB
Preferences are updated and vocabulary.tex is regenerated. Left-arrow steps back
to the previous word to fix a mis-label; `q` stops early (undecided words stay
unreviewed for next time).
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import termios
import tty
from pathlib import Path

from learner import find_repo_root, ielts_vocab_dir, preferences_path, summary_path, update_preferences
from vocab_db import (
    db_path,
    delete_words,
    fetch_unreviewed,
    init_db,
    mark_reviewed,
    render_vocabulary_tex,
)

RECOMMENDED_LR = 65


def read_key() -> str:
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch in ("\n", "\r"):
            return "enter"
        if ch == " ":
            return "space"
        if ch.lower() == "q":
            return "q"
        if ch == "\x03":
            raise KeyboardInterrupt
        if ch == "\x1b":  # escape sequence (arrow keys send ESC [ <X>)
            seq = sys.stdin.read(2)
            if seq == "[D":
                return "left"
            if seq == "[C":
                return "right"
            return "other"
        return "other"
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def truncate(s: str, max_len: int = 72) -> str:
    s = (s or "").replace("\n", " ")
    if len(s) <= max_len:
        return s
    return s[: max_len - 3] + "..."


def display_entry(idx: int, total: int, entry: dict, pending_action: str | None) -> None:
    print()
    print("=" * 72)
    src = truncate(entry.get("source_title", ""), 50)
    print(f"词条 [{idx + 1}/{total}]  来源: {src}")
    print(f"{entry['word']}  ({entry['pos']})  {entry['ipa']}")
    print(f"释义: {entry['gloss_zh']}")
    print(f"例句: {truncate(entry['example'])}")
    print(f"近义: {entry['synonyms']}  |  反义: {entry['antonyms']}")
    if pending_action:
        label = "保留" if pending_action == "keep" else "删除"
        print(f"(上次标注: {label} —— 重新选择以覆盖)")
    print("-" * 72)
    print("Enter=保留   空格=删除   ←=回到上一个   q=结束(其余留待下次)")


def prompt_learning_rate() -> int:
    print()
    print("学习率 0-100:决定本次保留/删除对今后选词偏好的影响强度。")
    print("  越大 → 越快固化偏好(更倾向你这次的取舍);越小 → 影响越轻、便于试探。")
    print(f"  建议:{RECOMMENDED_LR}(直接回车采用建议值)。")
    while True:
        raw = input(f"学习率 [{RECOMMENDED_LR}]: ").strip()
        if not raw:
            return RECOMMENDED_LR
        try:
            val = int(raw)
            if 0 <= val <= 100:
                return val
        except ValueError:
            pass
        print("请输入 0 到 100 之间的整数。")


def review_loop(words: list[dict]) -> dict[str, str]:
    """Interactive keep/reject with back-step. Returns {word_lower: keep|reject}."""
    total = len(words)
    actions: dict[str, str] = {}
    i = 0
    while i < total:
        entry = words[i]
        wl = entry["word_lower"]
        display_entry(i, total, entry, actions.get(wl))
        while True:
            key = read_key()
            if key == "enter":
                actions[wl] = "keep"
                print("-> 保留")
                i += 1
                break
            if key == "space":
                actions[wl] = "reject"
                print("-> 删除")
                i += 1
                break
            if key == "left":
                if i > 0:
                    i -= 1
                    print("-> 回到上一个")
                else:
                    print("(已是第一个,无法回退)")
                    continue
                break
            if key == "q":
                print("-> 结束本次审核(未标注的词保持未审核)")
                return actions
            print("(请按 Enter 保留、空格删除、← 回退、或 q 结束)")
    return actions


def main() -> int:
    parser = argparse.ArgumentParser(description="Review unreviewed words in the DB")
    parser.add_argument("--vocabulary", type=Path, help="Path to vocabulary.tex")
    parser.add_argument("--db", type=Path, help="SQLite word store (default vocab.db)")
    parser.add_argument(
        "--learning-rate",
        type=int,
        default=None,
        help="Non-interactive: keep all unreviewed words, apply this learning rate",
    )
    args = parser.parse_args()

    repo = find_repo_root()
    vocab = args.vocabulary or (ielts_vocab_dir(repo) / "vocabulary.tex")
    database = args.db or db_path(repo)

    if not vocab.exists():
        print(f"vocabulary.tex not found: {vocab}", file=sys.stderr)
        return 1

    interactive = args.learning_rate is None
    if interactive and not sys.stdin.isatty():
        print("需要交互终端。请在终端运行 ./review.sh,或使用 --learning-rate。", file=sys.stderr)
        return 1

    conn = sqlite3.connect(database)
    try:
        init_db(conn)
        words = fetch_unreviewed(conn)
        if not words:
            print("没有未审核的词。先运行 ./ingest.sh 入库。")
            return 0

        by_lower = {w["word_lower"]: w for w in words}
        print(f"本次待审核 {len(words)} 个未审核词。")

        if interactive:
            actions = review_loop(words)
        else:
            actions = {w["word_lower"]: "keep" for w in words}

        kept_lowers = [wl for wl, a in actions.items() if a == "keep"]
        rejected_lowers = [wl for wl, a in actions.items() if a == "reject"]

        kept_entries = [by_lower[wl] for wl in kept_lowers]
        rejected_entries = [by_lower[wl] for wl in rejected_lowers]

        print(
            f"\n会话合计: 保留 {len(kept_lowers)} 条, 删除 {len(rejected_lowers)} 条, "
            f"未标注 {len(words) - len(actions)} 条"
        )

        if not kept_lowers and not rejected_lowers:
            print("无任何标注,未改动数据库。")
            return 0

        lr = prompt_learning_rate() if interactive else (args.learning_rate or 0)

        mark_reviewed(conn, kept_lowers)
        delete_words(conn, rejected_lowers)
        render_vocabulary_tex(conn, vocab)
    finally:
        conn.close()

    update_preferences(
        kept_entries,
        rejected_entries,
        lr,
        source_file="(db review)",
        repo_root=repo,
    )

    print(f"\n已更新 vocabulary.tex(已删除被拒词、保留词标记为已审核)")
    print(f"已更新: {preferences_path(repo)}")
    print(f"已更新: {summary_path(repo)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
