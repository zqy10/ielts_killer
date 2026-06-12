# IELTS Killer

一套基于 Claude Code 技能的雅思学习系统，三个技能各自维护一本可打印的 LaTeX 笔记（PDF）：

| 技能 | 功能 | 产出 |
|------|------|------|
| `ielts-vocab-miner` | 从 YouTube/TED/BBC/新闻提炼 **Band 8.5+** 词汇，入库去重 | `ielts-vocab/vocabulary.pdf` 生词本 |
| `ielts-writing` | 按题型/主题找真题与范文，分析并写 Band 8.5+ 作文 | `ielts-writing/writing.pdf` 写作笔记 |
| `ielts-speaking` | 抓取口语真题生成范答题库（全局编号），并对你的语音作答评分 | `ielts-speaking/speaking.pdf` 口语题库+练习记录 |

代码（`.claude/skills/`）与数据（三个 `ielts-*/` 目录，各自是独立 git 小仓库）完全分离，
开发与日常使用互不干扰 —— 详见 [GIT_GUIDE.md](GIT_GUIDE.md)。

## 快速开始

1. 下载 skill：直接在 Claude Code 对话框输入：

> 去 https://github.com/zqy10/ielts_killer/tree/claude/dev 下载技能

2. 使用（对话框直接说人话即可）：

> 用 ielts-vocab-miner 处理这个视频 https://www.youtube.com/watch?v=...
> 找一道环境主题的 Task 2 写作题
> 给我一个科技主题的 Part 2&3 口语题库
> 我要回答第 23 题（语音作答后自动评分入册）

技能会自动完成抓取、提炼、入库、渲染，最后告诉你新增了什么、PDF 在哪。

## 整理自选词汇（my.md）

平时把生词随手记到 `ielts-vocab/pending/my.md`（每行一个单词），然后在对话框输入：

> 整理词汇

Claude 会把这些单词扩展成完整词条（词性 / IPA / 中文 / 例句 / 近反义词，例句尽量贴合雅思写作场景），
入库后渲染进 PDF 的「**其他来源 (Other Sources)**」章节，并在征得你同意后清空 `my.md`。
若 `my.md` 为空则提示没有词汇可拓展；已收录过的词会自动跳过并在汇报中列出。

## 手动运行词汇管线（慢速开始）

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
.claude/skills/ielts-vocab-miner/scripts/render.sh    # 编译并自动打开；加 --no-open 只编译
```

写作 / 口语技能无需 venv（纯 stdlib，系统 `python3` 直接跑），渲染脚本同样在各自技能的
`scripts/render.sh`。

## 数据来源唯一性

每个技能的 SQLite 数据库是**权威数据源**（`vocab.db` 按小写单词全局去重；`writing.db`
按题目哈希去重；`speaking.db` 的题目有永久全局编号）。`*.tex` 是从数据库**重新生成**的视图，
再由 `render.sh` 编译成 PDF。不要手改 `.tex` 当真相 —— 改了也会在下次 ingest 时被库覆盖。

## 目录速查

| 路径 | 用途 |
|------|------|
| `.claude/skills/<skill>/` | 技能定义 + 脚本（含 `scripts/render.sh` 编译脚本）—— 代码，主仓库管理 |
| `ielts-vocab/` `ielts-writing/` `ielts-speaking/` | 数据工作区（db / tex / pdf / pending）—— 各自独立 git 小仓库 |
| `ielts-*/pending/` | 等待入库的临时文件（ingest 后清空）；`my.md` 例外，是用户自选词汇清单 |
| `ielts-*/.build/` | LaTeX 编译缓存（gitignored） |
| `documents/` | 前期思考文档，仅本地保存（gitignored） |
| `GIT_GUIDE.md` | 三线开发 + 双层仓库的完整 git 工作流说明 |
| `savedata.sh` | 一键提交三个数据小仓库的存档脚本 |
