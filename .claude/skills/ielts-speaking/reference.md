# IELTS Speaking — scoring anchors & style reference

## 1. Part definitions

| Part | Format | Expected answer |
|---|---|---|
| **Part 1** | 熟悉话题的日常问答（家乡、工作、爱好…），每话题 4–6 问 | 每问 2–4 句：直接回答 + 一个细节/理由 |
| **Part 2** | 话题卡（cue card）：1 分钟准备 + 2 分钟独白，卡上 4 个提示点 | ~2 分钟独白（约 220–280 词），按顺序覆盖 4 个提示点 |
| **Part 3** | 基于 Part 2 话题的抽象讨论 | 每问 4–6 句：表态 → 理由 → 具体例子 →（可选让步） |

Part 2 与 Part 3 在考试中绑定出现，本技能按 `p23` 整组收录；但**每个问题有独立的
全局编号**，用户可单独练任何一问。

## 2. Scoring anchors (FC / LR / GRA)

Paraphrased from the official public band descriptors. Score each criterion to the
nearest 0.5 by matching the closest anchor. **Pronunciation is always N/A** — a text
transcript carries no pronunciation information; tell the user so. **Overall = mean
of the three criteria, rounded to the nearest 0.5 (halves up)** — e.g. (6.5+6.0+6.5)/3
= 6.33 → 6.5.

### Fluency & Coherence (流利与连贯)

| Band | Anchor |
|---|---|
| 6 | Willing to speak at length but loses coherence at times; noticeable repetition, self-correction and hesitation; a limited, sometimes mechanical range of connectives (and, but, because, you know). |
| 7 | Speaks at length without noticeable effort; some hesitation, repetition or self-correction remains; uses a range of connectives and discourse markers with some flexibility. |
| 8 | Develops topics coherently and appropriately; hesitates only to search for content, not language; wide range of discourse markers used naturally. |
| 9 | Fully coherent, appropriately extended topic development; any hesitation is content-related and rare. |

**Transcript caveats**: speech rate is invisible — judge hesitation from fillers
(er, um, you know, like 滥用), restarts, self-corrections and repeated words.
Judge length against the part's expectation (a 1-sentence Part 3 answer caps FC
around 5 regardless of quality).

### Lexical Resource (词汇资源)

| Band | Anchor |
|---|---|
| 6 | Vocabulary wide enough to discuss topics at length; meaning clear despite inappropriacies; paraphrases with mixed success; few idiomatic expressions. |
| 7 | Vocabulary used flexibly; some less-common and idiomatic items with occasional inappropriate choices; effective paraphrase; some awareness of style and collocation. |
| 8 | Wide range used readily and flexibly; skilful use of less-common and idiomatic items, occasional slips only; paraphrases effectively as required. |
| 9 | Full flexibility and precision; sustained, accurate use of idiomatic language in all contexts. |

### Grammatical Range & Accuracy (语法广度与准确性)

| Band | Anchor |
|---|---|
| 6 | Mix of simple and complex forms, but complex structures contain frequent errors; errors rarely block meaning. |
| 7 | A range of complex structures used with some flexibility; frequently error-free sentences, though some errors persist. |
| 8 | Wide range of structures used flexibly; the **majority** of sentences are error-free; only occasional, non-systematic slips. |
| 9 | Full range, consistently accurate apart from native-like "slips". |

## 3. Model answer style guide (Band 8.5+)

口语不是写作 —— 参考答案必须是**自然口语语域**：

- 缩写正常用（I'd, it's, there's）；允许口语化引导（Well, honestly, to be fair）但
  不能滥用填充词。
- 习语和高分搭配自然嵌入，不堆砌；**每个答案用 `[[...]]` 标 2–4 个高价值表达**
  （渲染为黄底高亮）。
- 不要议论文腔（Furthermore / In conclusion 之类书面连接词换成 on top of that /
  so all in all）。

**Part 1**（2–4 句）：直接回答 → 一个具体细节、理由或小例子。不绕弯。

**Part 2**（220–280 词独白）：开头一句点题（hook）→ 按卡片顺序覆盖 4 个提示点，
段落间空行 → 结尾一句回扣感受/意义。讲一个**具体的**故事/对象，细节带数字、
地点、时间更可信。

**Part 3**（4–6 句）：直接表态 → 理由 → 具体例子（真实世界、可感知）→ 可选一句
让步（That said, ...）。观点要有内容，不要两边各打五十大板。

## 4. Canonical themes

Key（存库用）→ 中文 / English（渲染用）。Must stay in sync with `THEME_LABELS`
in [scripts/speaking_db.py](scripts/speaking_db.py); unknown keys fall back to `other`.

| key | 中文 | English |
|---|---|---|
| hometown | 家乡 | Hometown |
| home | 住所 | Home & Accommodation |
| work-study | 工作与学习 | Work & Study |
| hobbies | 兴趣爱好 | Hobbies & Leisure |
| people | 人物与关系 | People & Relationships |
| daily-life | 日常生活 | Daily Life |
| technology | 科技 | Technology |
| travel | 旅行与地点 | Travel & Places |
| food | 饮食 | Food |
| media | 媒体与娱乐 | Media & Entertainment |
| environment | 环境与自然 | Environment & Nature |
| shopping | 购物与消费 | Shopping & Consumption |
| health | 健康 | Health |
| education | 教育 | Education |
| culture | 文化与节日 | Culture & Festivals |
| experiences | 经历与事件 | Experiences & Events |
| objects | 物品 | Objects |
| other | 其他 | Other |

Part 2 话题卡四大类（人物/地点/物品/事件经历）分别映射到 people / travel /
objects / experiences；更具体的主题（科技、健康…）优先用具体 key。

## 5. Compliance

- 每次请求只收录**一个话题**，除非用户明确要批量。
- 不批量爬站；访问过的 URL 一律 `log-source` 记录（含失败的搜索）。
- 仅个人学习用途；题目保留来源 URL。
