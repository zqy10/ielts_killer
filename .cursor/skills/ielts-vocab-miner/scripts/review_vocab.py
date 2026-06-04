#!/usr/bin/env python3
"""Interactive review of pending .tex files; updates learner preferences."""

from __future__ import annotations

import argparse
import random
import sys
import termios
import tty
from pathlib import Path

from learner import (
    find_repo_root,
    parse_tex_file,
    pending_dir,
    preferences_path,
    reviewed_dir,
    summary_path,
    update_preferences,
    write_reviewed_tex,
)


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
        return "other"
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def truncate(s: str, max_len: int = 72) -> str:
    s = s.replace("\n", " ")
    if len(s) <= max_len:
        return s
    return s[: max_len - 3] + "..."


def display_entry(file_name: str, global_idx: int, file_idx: int, file_total: int, entry: dict) -> None:
    print()
    print("=" * 72)
    print(f"文件: {file_name}  |  词条 [{file_idx + 1}/{file_total}]  (#{global_idx})")
    print(f"{entry['word']}  ({entry['pos']})  {entry['ipa']}")
    print(f"释义: {entry['gloss_zh']}")
    print(f"例句: {truncate(entry['example'])}")
    print(f"近义: {entry['synonyms']}  |  反义: {entry['antonyms']}")
    print("-" * 72)
    print("Enter/换行 = 保留    空格 = 删除    q = 结束本文件")


def prompt_learning_rate() -> int:
    while True:
        raw = input("\n学习率 0-100: ").strip()
        try:
            val = int(raw)
            if 0 <= val <= 100:
                return val
        except ValueError:
            pass
        print("请输入 0 到 100 之间的整数。")


def review_file(
    tex_path: Path,
    interactive: bool,
) -> tuple[list[dict], list[dict], str | None]:
    source_line, entries = parse_tex_file(tex_path)
    if not entries:
        return [], [], source_line

    kept: list[dict] = []
    rejected: list[dict] = []
    stopped = False

    for i, entry in enumerate(entries):
        if stopped:
            rejected.append(entry)
            continue
        if interactive:
            display_entry(tex_path.name, i + 1, i, len(entries), entry)
            while True:
                key = read_key()
                if key == "enter":
                    kept.append(entry)
                    print("-> 保留")
                    break
                if key == "space":
                    rejected.append(entry)
                    print("-> 删除")
                    break
                if key == "q":
                    rejected.append(entry)
                    stopped = True
                    print("-> 结束本文件（后续词条视为删除）")
                    break
                print("(请按 Enter 保留、空格删除、或 q 结束本文件)")
        else:
            kept.append(entry)

    return kept, rejected, source_line


def pick_pending_files(pending: Path, n: int, all_files: bool) -> list[Path]:
    files = sorted(pending.glob("*.tex"))
    if not files:
        return []
    if all_files:
        return files
    n = min(n, len(files))
    return random.sample(files, n)


def main() -> int:
    parser = argparse.ArgumentParser(description="Review pending vocab .tex files")
    parser.add_argument("tex_file", nargs="?", help="Optional single .tex path")
    parser.add_argument("-n", type=int, default=1, help="Randomly pick N files from pending/ (default 1)")
    parser.add_argument("--all", action="store_true", help="Review all pending files")
    parser.add_argument("--pending-dir", type=Path, help="Pending directory")
    parser.add_argument("--reviewed-dir", type=Path, help="Reviewed directory")
    parser.add_argument(
        "--learning-rate",
        type=int,
        default=None,
        help="Non-interactive: keep all entries, apply this learning rate",
    )
    args = parser.parse_args()

    repo = find_repo_root()
    pending = args.pending_dir or pending_dir(repo)
    reviewed = args.reviewed_dir or reviewed_dir(repo)

    if args.tex_file:
        paths = [Path(args.tex_file).resolve()]
        if not paths[0].exists():
            print(f"File not found: {paths[0]}", file=sys.stderr)
            return 1
    else:
        paths = pick_pending_files(pending, args.n, args.all)
        if not paths:
            print(f"pending/ 中没有待审查的 .tex 文件: {pending}", file=sys.stderr)
            return 1

    interactive = args.learning_rate is None
    if interactive and not sys.stdin.isatty():
        print("需要交互终端。请在终端运行 ./review.sh，或使用 --learning-rate。", file=sys.stderr)
        return 1

    all_kept: list[dict] = []
    all_rejected: list[dict] = []
    reviewed_names: list[str] = []

    print(f"本次审查 {len(paths)} 个文件（来自 {pending}）")

    for tex_path in paths:
        print(f"\n>>> 开始: {tex_path.name}")
        kept, rejected, source_line = review_file(tex_path, interactive=interactive)
        if not source_line and not kept:
            print(f"跳过空文件: {tex_path.name}")
            continue

        out_path = reviewed / tex_path.name
        write_reviewed_tex(source_line, kept, out_path)

        if tex_path.parent.resolve() == pending.resolve() and tex_path.exists():
            tex_path.unlink()

        all_kept.extend(kept)
        all_rejected.extend(rejected)
        reviewed_names.append(tex_path.name)
        print(f"已保存: {out_path}（保留 {len(kept)} / 删除 {len(all_rejected)}）")

    print(f"\n会话合计: 保留 {len(all_kept)} 条, 删除 {len(all_rejected)} 条")

    if interactive:
        lr = prompt_learning_rate()
    else:
        lr = args.learning_rate or 0

    update_preferences(
        all_kept,
        all_rejected,
        lr,
        source_file=", ".join(reviewed_names),
        repo_root=repo,
    )

    print(f"\n已更新: {preferences_path(repo)}")
    print(f"已更新: {summary_path(repo)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
