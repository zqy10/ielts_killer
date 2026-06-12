# IELTS Vocab Notebook

从优质英文素材（YouTube/TED 字幕、BBC/新闻文章）里提炼 **Band 8.5+** 的高分词汇，
入库去重后渲染成一本可打印的 LaTeX 生词本（`vocabulary.pdf`）。

## 快速开始

1. 下载skill

直接在对话框输入：

>去 https://github.com/zqy10/ielts_killer/tree/claude/dev 下载技能


2. 使用

让 Claude Code 跑 `ielts-vocab-miner` 技能，给它一个链接即可，在对话框输入：

> 用 ielts-vocab-miner 处理这个视频 https://www.youtube.com/watch?v=...

技能会自动完成抓取、提炼、入库、渲染，最后告诉你新增了多少词、PDF 在哪。

## 整理自选词汇（my.md）

平时把生词随手记到 `ielts-vocab/pending/my.md`（每行一个单词），然后在对话框输入：

> 整理词汇

Claude 会把这些单词扩展成完整词条（词性 / IPA / 中文 / 例句 / 近反义词，例句尽量贴合雅思写作场景），
入库后渲染进 PDF 的「**其他来源 (Other Sources)**」章节，并在征得你同意后清空 `my.md`。
若 `my.md` 为空则提示没有词汇可拓展；已收录过的词会自动跳过并在汇报中列出。

## 慢速开始

需要先做一次性环境准备（见文末）。所有命令都从仓库根目录运行。

```bash
PY=.claude/skills/ielts-vocab-miner/scripts/.venv/bin/python

# 1) 抓取并预处理：URL（YouTube/TED/BBC/新闻）
$PY .claude/skills/ielts-vocab-miner/scripts/fetch_content.py \
    --url "<URL>" --out /tmp/ielts_raw.json
#    或本地字幕/文本（.vtt/.srt/.txt）
$PY .claude/skills/ielts-vocab-miner/scripts/clean_text.py \
    --input "<路径>" --title "<标题>" --out /tmp/ielts_raw.json

# 2) 把提炼好的词条写成 ielts-vocab/pending/<slug>-<日期>.tex
#    （由 Claude 依据 fetch 结果撰写：1 个 \vocabsource + 若干 7 字段 \vocabentry）

# 3) 入库（合并去重 + 重生成 vocabulary.tex + 清空 pending），再渲染 PDF
$PY .claude/skills/ielts-vocab-miner/scripts/ingest_vocab.py \
    --pending-dir ielts-vocab/pending --vocabulary ielts-vocab/vocabulary.tex
ielts-vocab/render.sh            # 编译并自动打开；加 --no-open 只编译
```

## 数据来源唯一性

`vocab.db`（SQLite）是**权威词库**，按小写单词全局去重（同一个词只收一次）。
`vocabulary.tex` 是从数据库**重新生成**的视图，按来源类别（视频 / 文章 / 书籍 / 其他）分组，
再由 `render.sh` 编译成 PDF。不要手改 `vocabulary.tex` 当真相 —— 改了也会在下次 ingest 时被库覆盖。

## 目录速查

| 路径 | 用途 |
|------|------|
| `pending/` | Claude 生成、等待入库的 `.tex`（ingest 后自动清空）；`my.md` 为用户自选词汇清单（不会被 ingest 删除） |
| `vocab.db` | SQLite 权威词库（去重存储；`vocabulary.tex` 由它生成） |
| `vocabulary.tex` | 生成的主笔记（编译为 PDF） |
| `vocabulary.pdf` | 编译产物 |
| `render.sh` | 编译脚本（`--no-open` 只编译不打开） |
| `examples/` | 样例输入/输出 |
| `.build/` | LaTeX 编译缓存（gitignored） |

