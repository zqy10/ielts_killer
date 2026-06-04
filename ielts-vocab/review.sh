#!/usr/bin/env bash
# 用法: ./review.sh [N]   从 pending/ 随机审查 N 个 tex，默认 N=1
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$ROOT/.." && pwd)"
PY="$REPO/.cursor/skills/ielts-vocab-miner/scripts/.venv/bin/python"
SCRIPTS="$REPO/.cursor/skills/ielts-vocab-miner/scripts"

if [[ ! -x "$PY" ]]; then
  echo "未找到 Python venv。请先运行:" >&2
  echo "  cd $SCRIPTS && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
  exit 1
fi

N="${1:-1}"
"$PY" "$SCRIPTS/review_vocab.py" -n "$N" \
  --pending-dir "$ROOT/pending" \
  --reviewed-dir "$ROOT/reviewed"
"$PY" "$SCRIPTS/merge_vocab.py" \
  --reviewed-dir "$ROOT/reviewed" \
  --vocabulary "$ROOT/vocabulary.tex"
echo "完成。已更新 vocabulary.tex"
