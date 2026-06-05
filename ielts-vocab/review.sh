#!/usr/bin/env bash
# 用法: ./review.sh   审核词库中所有「未审核」的词(保留/删除 + 偏好学习)
# 保留→标记已审核;删除→从词库移除;结束后重新生成 vocabulary.tex。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$ROOT/.." && pwd)"
PY="$REPO/.claude/skills/ielts-vocab-miner/scripts/.venv/bin/python"
SCRIPTS="$REPO/.claude/skills/ielts-vocab-miner/scripts"

if [[ ! -x "$PY" ]]; then
  echo "未找到 Python venv。请先运行:" >&2
  echo "  cd $SCRIPTS && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
  exit 1
fi

"$PY" "$SCRIPTS/review_vocab.py" \
  --vocabulary "$ROOT/vocabulary.tex"
