#!/usr/bin/env bash
# 编译 writing.tex → writing.pdf
# 用法: ielts-writing/render.sh [--no-open]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
TEX="$ROOT/writing.tex"
OUT="$ROOT/writing.pdf"
BUILD="$ROOT/.build"
AUTO_OPEN=true

for arg in "$@"; do
  [[ "$arg" == "--no-open" ]] && AUTO_OPEN=false
done

# ---- engine detection ----
if command -v tectonic &>/dev/null; then
    ENGINE=tectonic
elif command -v xelatex &>/dev/null; then
    ENGINE=xelatex
else
    cat >&2 <<'EOF'
未找到 LaTeX 编译器。请安装其中之一：

  轻量级（推荐，自动下载宏包）:
    brew install tectonic

  完整 TeX 发行版:
    brew install --cask mactex         # ~4 GB，开箱即用
    brew install --cask basictex       # ~100 MB，需手动 tlmgr 补包

安装后重新运行 ielts-writing/render.sh
EOF
    exit 1
fi

mkdir -p "$BUILD"
echo "引擎: $ENGINE"
echo "编译: $TEX → $OUT"

if [[ "$ENGINE" == "tectonic" ]]; then
    # 让 fontspec 能找到 macOS 系统字体（Times New Roman 等）
    export OSFONTDIR="/Library/Fonts:/System/Library/Fonts:$HOME/Library/Fonts"
    # 首次运行会自动下载缺失的 CTAN 宏包（FandolSong 等）
    tectonic --outdir "$BUILD" "$TEX"
else
    # xelatex 需运行两次以正确生成目录和超链接
    xelatex -interaction=nonstopmode -output-directory="$BUILD" "$TEX" > "$BUILD/xelatex.log" 2>&1 || true
    xelatex -interaction=nonstopmode -output-directory="$BUILD" "$TEX" > "$BUILD/xelatex.log" 2>&1 \
        || { echo "编译出错，日志: $BUILD/xelatex.log" >&2; exit 1; }
fi

cp "$BUILD/writing.pdf" "$OUT"
echo "PDF 已生成: $OUT"

if $AUTO_OPEN && [[ "$OSTYPE" == "darwin"* ]]; then
    open "$OUT"
fi
