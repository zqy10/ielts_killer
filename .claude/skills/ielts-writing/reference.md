# IELTS Writing reference (Band 8.5+)

## Band 8.5+ checklist (the four criteria)

**Task Response / Task Achievement**
- Fully address every part of the prompt; a clear, sustained position (Task 2) or a
  clear **overview** of main trends/features (Task 1).
- Develop ideas with specific, relevant support — no padding, no off-topic content.
- Task 1: report and compare **key** data; quote selected figures, don't list everything.

**Coherence & Cohesion**
- Logical paragraphing: one central idea per body paragraph.
- Cohesion feels natural, not mechanical (avoid a wall of "Firstly/Secondly/Moreover").
- Skilful referencing and substitution (this trend, the former, doing so).

**Lexical Resource**
- Precise, less-common collocations used naturally; topic-specific vocabulary.
- Paraphrase the prompt accurately; avoid repeating its exact wording.
- Errors rare and non-impeding.

**Grammatical Range & Accuracy**
- Wide range of structures: conditionals, relative clauses, cleft sentences, controlled
  passives, nominalisation.
- Majority of sentences error-free; punctuation accurate.

## Word counts
- **Task 1 ≥ 150 words** (aim ~170–190). **Task 2 ≥ 250 words** (aim ~270–290).
- Never under the minimum (penalised). Don't pad far beyond — quality over length.

## Structure templates

### Task 1 (Academic) — 4 paragraphs
1. **Introduction** — paraphrase what the visual shows (what / where / when / units).
2. **Overview** — 2–3 most striking features/trends (no specific data here). *This drives
   the band — never omit it.*
3. **Body 1** — detail + compare the first group of data with selected figures.
4. **Body 2** — the remaining data / contrasts.
- Map/process variants: describe changes over time / sequential stages with the passive.

### Task 2 — 4 paragraphs
1. **Introduction** — paraphrase the topic + a clear thesis/position answering the exact
   question type.
2. **Body 1** — first main idea: claim → explanation → example.
3. **Body 2** — second main idea (or the other side, then your stance).
4. **Conclusion** — restate the position; summarise; no new ideas.

**Question types** → make the structure fit the type:
`opinion` (agree/disagree) · `discussion` (discuss both views + your opinion) ·
`problem-solution` (causes/problems + solutions) · `advantages-disadvantages` ·
`two-part` (direct-question; answer each part).

## Canonical themes (keys → labels)

`education` 教育 · `environment` 环境 · `technology` 科技 · `health` 健康 ·
`society` 社会与家庭 · `government` 政府与公共开支 · `crime` 犯罪与法律 ·
`work` 工作与职业 · `globalisation` 全球化 · `media` 媒体与广告 ·
`transport` 交通 · `tourism` 旅游 · `culture` 文化 · `science` 科学 ·
`urbanisation` 城市化 · `other` 其他.

Use the **key** in the pending JSON `theme` field. Unknown themes fall back to `other`.
Keep this list in sync with `THEME_LABELS` in `scripts/writing_db.py`.

## Task 1 chart types (keys → labels)

`line` 折线图 · `bar` 柱状图 · `pie` 饼图 · `table` 表格 · `map` 地图 ·
`process` 流程图 · `mixed` 组合图表 · `other` 其他.

The PDF groups **Task 2 by theme** but **Task 1 by chart type** (the `subtype` field),
so `subtype` is required for Task 1. Unknown subtypes fall back to `other`. Keep this
list in sync with `CHART_LABELS` in `scripts/writing_db.py`.

## High-value language to look for in samples
- Cohesion beyond basics: *that said, by the same token, in much the same way, this is
  largely because, a case in point.*
- Hedging/stance: *it is arguably the case that, there is a compelling argument that.*
- Trend verbs (Task 1): *surged, plateaued, dipped, levelled off, climbed steadily.*
- Nominalisation: *the implementation of, a marked reduction in, growing reliance on.*

## Compliance
Personal study only. **One prompt per request** unless a batch is explicitly requested.
Do not bulk-scrape question banks. Sample essays are stored and shown in full at the
user's request — keep the source URL with each so attribution is preserved.
