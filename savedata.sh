#!/usr/bin/env bash
# 一键存档三个数据小仓库（ielts-vocab / ielts-writing / ielts-speaking）。
# 用法: ./savedata.sh [备注]   —— 备注可选，会附在提交信息里
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
NOTE="${1:-}"
DATE="$(date +%Y-%m-%d)"
SAVED=0

for dir in ielts-vocab ielts-writing ielts-speaking; do
    repo="$ROOT/$dir"
    if [[ ! -d "$repo/.git" ]]; then
        echo "⚠️  $dir: 不是 git 仓库，跳过（先按 GIT_GUIDE.md 初始化）"
        continue
    fi
    if [[ -z "$(git -C "$repo" status --porcelain)" ]]; then
        echo "✓  $dir: 无变更"
        continue
    fi
    msg="data: $DATE"
    [[ -n "$NOTE" ]] && msg="$msg — $NOTE"
    git -C "$repo" add -A
    git -C "$repo" commit -q -m "$msg"
    echo "💾 $dir: 已存档 ($(git -C "$repo" log --oneline -1))"
    SAVED=$((SAVED + 1))
done

echo "----"
echo "完成：$SAVED 个仓库有新存档。"
