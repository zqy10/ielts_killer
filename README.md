<div align="center">

# 🎯 IELTS Killer

**一套基于 [Claude Code](https://claude.com/claude-code) 技能的雅思（IELTS）学习系统**

抓取真实语料 → 提炼 Band 8.5+ 内容 → 入库去重 → 自动渲染可打印的 LaTeX 笔记（PDF）

<!-- badges -->
![Claude Code](https://img.shields.io/badge/Claude%20Code-skills-7C3AED?logo=anthropic&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.x-3776AB?logo=python&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-authoritative%20store-003B57?logo=sqlite&logoColor=white)
![XeLaTeX](https://img.shields.io/badge/LaTeX-XeLaTeX%20%2F%20Tectonic-008080?logo=latex&logoColor=white)
![Use](https://img.shields.io/badge/use-personal%20study%20only-lightgrey)

</div>

---

## 目录

- [项目简介](#项目简介)
- [功能特性](#功能特性)
- [架构概览](#架构概览)
- [快速开始](#快速开始)
- [详细用法](#详细用法)
  - [词汇：ielts-vocab-miner](#词汇ielts-vocab-miner)
  - [写作：ielts-writing](#写作ielts-writing)
  - [口语：ielts-speaking](#口语ielts-speaking)
  - [整理自选词汇（my.md）](#整理自选词汇mymd)
- [手动运行词汇管线](#手动运行词汇管线进阶)
- [数据唯一性](#数据唯一性)
- [目录结构](#目录结构)
- [环境准备](#环境准备)
- [合规与许可](#合规与许可)

## 项目简介

IELTS Killer 把三个 Claude Code 技能打包成一个雅思备考工作台。你在对话框用人话提需求，
技能会自动完成「抓取语料 → 提炼高分内容 → 入库去重 → 渲染 PDF」的全流程，最后告诉你新增了
什么、PDF 在哪里。每个技能各自维护一本可打印的 LaTeX 笔记。

## 功能特性

| 技能 | 功能 | 产出 |
|------|------|------|
| **`ielts-vocab-miner`** | 从 YouTube / TED / BBC / 新闻提炼 **Band 8.5+** 词汇，入库去重 | `ielts-vocab/vocabulary.pdf` 生词本 |
| **`ielts-writing`** | 按题型 / 主题找真题与范文，分析并写 Band 8.5+ 作文 | `ielts-writing/writing.pdf` 写作笔记 |
| **`ielts-speaking`** | 抓取口语真题生成范答题库（全局编号），并对你的语音作答评分 | `ielts-speaking/speaking.pdf` 口语题库 + 练习记录 |

- 🤖 **全自动管线** —— 抓取、提炼、入库、渲染一气呵成，无需人工中间步骤
- 🗃 **SQLite 为权威数据源** —— 全局去重，`*.tex` / PDF 都是从库重新生成的视图
- 🧮 **口语全局编号** —— 每道题有永久题号（Q1、Q2…），可「我要回答第 23 题」语音作答并自动评分
- 🖨 **可打印 PDF** —— XeLaTeX / Tectonic 排版，中英混排
- 🔀 **代码与数据分离** —— 互不干扰的双层 git 仓库（详见 [GIT_GUIDE.md](GIT_GUIDE.md)）

## 架构概览

代码（`.claude/skills/`）与数据（三个 `ielts-*/` 目录，**各自是独立的 git 小仓库**）完全分离，
开发与日常使用互不干扰。

```
ielts_killer/                  ← 主仓库（只跟踪代码 / 文档）
├── .claude/skills/            ← 三个技能定义 + 脚本
│   ├── ielts-vocab-miner/
│   ├── ielts-writing/
│   └── ielts-speaking/
├── ielts-vocab/      ┐
├── ielts-writing/    ├─ 数据工作区，主仓库 gitignore，各自独立 git 仓库
└── ielts-speaking/   ┘   （db = 权威源 → 生成 tex → 渲染 pdf）
```

> 完整的 git 工作流（双层仓库、三线开发、一键存档）见 **[GIT_GUIDE.md](GIT_GUIDE.md)**。

## 快速开始

> **前置要求**：[Claude Code](https://claude.com/claude-code)、Python 3.x、LaTeX 引擎（Tectonic 或 MacTeX，见[环境准备](#环境准备)）。

**1. 下载技能** —— 在 Claude Code 对话框输入：

> 去 https://github.com/zqy10/ielts_killer/tree/claude/dev 下载技能

**2. 使用** —— 对话框直接说人话即可：

```text
用 ielts-vocab-miner 处理这个视频 https://www.youtube.com/watch?v=...
找一道环境主题的 Task 2 写作题
给我一个科技主题的 Part 2&3 口语题库
我要回答第 23 题          # 语音作答后自动评分入册
```

技能会自动完成抓取、提炼、入库、渲染，最后汇报新增内容与 PDF 路径。

## 详细用法

### 词汇：ielts-vocab-miner

提供一个 URL（YouTube / TED / BBC / 新闻）或本地字幕文本，技能提炼约一半 IELTS 取向高级词、
一半领域高级词，生成带 IPA / 中文 / 例句 / 近反义词的词条，按小写单词**全局去重**入库，
渲染进 `ielts-vocab/vocabulary.pdf`。

### 写作：ielts-writing

指定**题型**（Task 1 / Task 2）和**主题**，技能联网找真题与 Band 8.5+ 范文，分析其高分语言，
再写一篇全新的 Band 8.5+ 作文。范文原文与来源 URL 一并存库，按 Task 1（按图表类型）/ Task 2
（按主题）组织进 `writing.pdf`。每次默认一题。

### 口语：ielts-speaking

- **题库生成**：指定 Part 1 或 Part 2&3（可带主题），技能找真题、写范答、入库，**每题获得永久全局题号**。
- **评分**：「我要回答第 23 题」→ 语音作答（harness 转写）→ 按官方评分标准对 FC / LR / GRA 打分
  （发音 N/A），给出升级建议、语法纠正与练习记录，写进 `speaking.pdf` 的练习记录章节。

### 整理自选词汇（my.md）

平时把生词随手记到 `ielts-vocab/pending/my.md`（每行一个单词），然后在对话框输入：

> 整理词汇

Claude 会把这些单词扩展成完整词条（词性 / IPA / 中文 / 例句 / 近反义词，例句尽量贴合雅思写作场景），
入库后渲染进 PDF 的「**其他来源 (Other Sources)**」章节，并在征得你同意后清空 `my.md`。
若 `my.md` 为空则提示没有词汇可拓展；已收录过的词会自动跳过并在汇报中列出。

## 手动运行词汇管线（进阶）

通常不需要手动操作 —— 技能会自己跑完整条管线。需要手动调试时（先完成[环境准备](#环境准备)），
所有命令从仓库根目录运行：

```bash
PY=.claude/skills/ielts-vocab-miner/scripts/.venv/bin/python

# 1) 抓取并预处理：URL（YouTube/TED/BBC/新闻）
$PY .claude/skills/ielts-vocab-miner/scripts/fetch_content.py \
    --url "<URL>" --out /tmp/ielts_raw.json
#    或本地字幕/文本（.vtt/.srt/.txt）
$PY .claude/skills/ielts-vocab-miner/scripts/clean_text.py \
    --input "<路径>" --title "<标题>" --out /tmp/ielts_raw.json

# 2) 由 Claude 依据 fetch 结果，把词条写成 ielts-vocab/pending/<slug>-<日期>.tex
#    （1 个 \vocabsource + 若干 7 字段 \vocabentry）

# 3) 入库（合并去重 + 重生成 vocabulary.tex + 清空 pending），再渲染 PDF
$PY .claude/skills/ielts-vocab-miner/scripts/ingest_vocab.py \
    --pending-dir ielts-vocab/pending --vocabulary ielts-vocab/vocabulary.tex
.claude/skills/ielts-vocab-miner/scripts/render.sh    # 编译并自动打开；加 --no-open 只编译
```

写作 / 口语技能**无需 venv**（纯 stdlib，系统 `python3` 直接跑），渲染脚本同样在各自技能的
`scripts/render.sh`。

## 数据唯一性

每个技能的 SQLite 数据库是**权威数据源**：

| 数据库 | 去重方式 |
|--------|----------|
| `vocab.db` | 按小写单词全局去重 |
| `writing.db` | 按题目哈希去重 |
| `speaking.db` | 题目有永久全局编号（再次入库不会重新编号） |

`*.tex` 是从数据库**重新生成**的视图，再由 `render.sh` 编译成 PDF。
⚠️ 不要手改 `.tex` 当真相 —— 改了也会在下次 ingest 时被库覆盖。

## 目录结构

| 路径 | 用途 |
|------|------|
| `.claude/skills/<skill>/` | 技能定义 + 脚本（含 `scripts/render.sh` 编译脚本）—— 代码，主仓库管理 |
| `ielts-vocab/` `ielts-writing/` `ielts-speaking/` | 数据工作区（db / tex / pdf / pending）—— 各自独立 git 小仓库 |
| `ielts-*/pending/` | 等待入库的临时文件（ingest 后清空）；`my.md` 例外，是用户自选词汇清单 |
| `ielts-*/.build/` | LaTeX 编译缓存（gitignored） |
| `documents/` | 前期思考文档，仅本地保存（gitignored） |
| `GIT_GUIDE.md` | 三线开发 + 双层仓库的完整 git 工作流说明 |
| `savedata.sh` | 一键提交三个数据小仓库的存档脚本 |

## 环境准备

**LaTeX 引擎**（首次使用前安装其一）：

```bash
brew install tectonic          # 推荐：轻量，自动下载所需宏包
# 或
brew install --cask mactex     # 完整发行版（约 4 GB）
```

**词汇技能的 Python 虚拟环境**（一次性）：

```bash
cd .claude/skills/ielts-vocab-miner/scripts
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

> `render.sh` 会自动检测可用引擎（优先 `tectonic`，备用 `xelatex`）。写作 / 口语技能纯 stdlib，无需 venv。

## 合规与许可

仅供**个人学习使用**。每次请求只处理一个 URL（除非显式要求批量）；不做大规模抓取，也不转载完整字幕 / 原文。

---

<div align="center">
Made with ❤️ &nbsp;·&nbsp; powered by <a href="https://claude.com/claude-code">Claude Code</a>
</div>
