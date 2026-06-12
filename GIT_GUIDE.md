# Git 开发指南（IELTS Killer）

本项目采用 **双层仓库** 结构：代码与数据完全隔离，互不干扰。
本文档说明日常如何高效使用与开发。

## 一、整体结构

```
ielts_killer/                  ← 主仓库：只管「代码」，三线分支开发
├── .claude/skills/…           ← 三个技能的定义、脚本（含 render.sh）
├── README.md  GIT_GUIDE.md    ← 文档
├── savedata.sh                ← 一键存档数据仓库
├── .gitignore                 ← 忽略下面所有数据/本地文件
│
├── ielts-vocab/      ← 独立小仓库（自己的 .git），单线，永不分支
├── ielts-writing/    ← 同上
├── ielts-speaking/   ← 同上
└── documents/        ← 前期思考文档，不进任何 git
```

**为什么这样设计**：db 是二进制权威数据，进了分支就会产生无法 diff 的合并冲突；
而数据本来就只会向前累积、不需要分支。把数据挪进各自的嵌套小仓库后——

- 在**任何**代码分支上使用**任何**功能（挖词/写作/口语），主仓库完全无感知；
- 切分支时 git 不会碰数据目录 → **三个 PDF 永远留在原地随时可看**；
- db 仍有完整 git 历史，可回滚、可备份。

## 二、日常使用（学习）

在哪个分支上都行，直接对 Claude 说人话用功能。用完之后存档一次：

```bash
./savedata.sh                # 三个数据仓库各自提交（无变更的自动跳过）
./savedata.sh "挖了一期TED"   # 可附备注
```

就这一条命令，数据安全落袋。

## 三、功能开发（三线并行）

主仓库主干是 **`claude/dev`**，三条功能线已建好：
`feat/vocab`、`feat/writing`、`feat/speaking`。

```bash
# 1. 切到要开发的线（VSCode 左下角点分支名也行）
git switch feat/vocab

# 2. 改代码（.claude/skills/ 下），随做随提交
git add -A && git commit -m "feat: vocab xxx"

# 3. 开发完成，合回主干
git switch claude/dev
git merge feat/vocab            # 图上会看到这条线汇入主干

# 4.（可选）下一轮开发前，把功能分支推进到主干最新点
git switch feat/vocab && git merge claude/dev
```

三条线都合并后，VSCode Source Control 的 Graph 就是你想要的
「一点分三线、三线汇一点」。

**冲突怎么办**：代码全是文本（.py/.md/.sh），冲突时 git 会在文件里标出
`<<<<<<<`/`>>>>>>>`，手工保留想要的部分再 `git add` + `git commit` 即可。
只要各条线尽量只改自己技能目录下的文件，冲突会很少
（公共文件如 `README.md`、根 `.gitignore` 是主要冲突点，改前先合一次主干）。

## 四、ignore 清单说明（谁被忽略、为什么）

### 主仓库 `.gitignore`

| 条目 | 原因 |
|------|------|
| `.DS_Store` | macOS 系统垃圾 |
| `CLAUDE.md` | 沿用项目原有约定：本地 Claude 指令不入库 |
| `.claude/settings.local.json` | Claude Code 本地个人配置 |
| `.claude/worktrees/` | Claude Code 临时工作树 |
| `ielts-vocab/` `ielts-writing/` `ielts-speaking/` | 数据工作区，由各自的嵌套小仓库管理（见下） |
| `documents/` | 你的前期思考文档，只在本地保存，不进 git |

### 三个数据仓库各自的 `.gitignore`

| 条目 | 原因 |
|------|------|
| `*.pdf` | 编译产物，随时可由 render.sh 从 db 重新生成；不追踪它，切主仓库分支/重渲染都不产生 git 噪音 |
| `.build/` | LaTeX 编译缓存 |
| `pending/*` | 等待 ingest 的临时文件，入库后即删 |
| `!pending/.gitkeep` | 保住空目录 |
| `!pending/my.md`（仅 vocab） | **例外**：你的手记单词表是用户数据，要受版本保护 |
| `.DS_Store` | 同上 |

**被追踪的数据**（即每次 `./savedata.sh` 存档的内容）：
`vocab.db` / `writing.db` / `speaking.db`（权威数据）、三个 `.tex`（含手工维护的
preamble）、`ielts-writing/images/`（Task 1 图表，PDF 引用它们）、`my.md`。

## 五、FAQ

**Q: 为什么三个 PDF 一直都能看到？**
PDF 不被任何仓库追踪，git 切分支不会动它们；每次渲染就地更新，三本笔记始终在
`ielts-*/` 目录里。

**Q: 在 feat/vocab 分支上用了写作功能，会乱吗？**
不会。写作数据写进 `ielts-writing/`（独立小仓库），主仓库根本看不见。
下次 `./savedata.sh` 正常存档即可。

**Q: db 误操作了怎么回滚？**
进对应目录用普通 git 操作，例如：
```bash
cd ielts-writing
git log --oneline          # 找到想回到的存档
git checkout <hash> -- writing.db   # 只恢复 db
```
然后重跑对应技能的 render.sh 重新生成 tex/PDF。

**Q: 怎么推送备份？**
- 代码：`git push origin claude/dev`（功能分支同理）。注意远端 claude/dev
  历史中仍保留旧的 db/pdf（未重写历史），从本次重构起不再上传新数据。
- 数据：默认只在本地。想云备份时给数据仓库建私有远端：
  ```bash
  cd ielts-vocab
  gh repo create ielts-vocab-data --private --source=. --push
  ```
  （三个数据目录同理；也可以靠 Time Machine/iCloud 兜底。）

**Q: VSCode 里怎么看三条线？**
Source Control 侧栏 → Graph 面板（或装 Git Graph 插件）。在 feat/* 分支各有提交后，
就能看到从 `claude/dev` 分出的三条线；merge 后汇合。注意 VSCode 打开仓库根时
显示的是**主仓库**的图；要看数据仓库的历史，在对应目录里 `git log` 或单独打开该目录。

**Q: 新电脑怎么恢复环境？**
clone 主仓库 → 三个数据目录是空的（被 ignore）→ 从备份恢复数据仓库（或重新
`git clone` 各数据远端到对应目录名）→ 跑三个 render.sh 重新生成 PDF。
