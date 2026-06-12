---
name: ielts-writing
description: >-
  Finds IELTS writing prompts (Task 1 / Task 2) online by user-specified task type
  and theme, finds Band 8.5+ sample essays, analyses them for high-value expressions
  and ideas, then writes a fresh Band 8.5+ essay. Stores prompts, sample text and
  essays in a SQLite DB (logging searched URLs to avoid re-searching), regenerates
  writing.tex and renders a PDF organised by Task 1 (by chart type) and Task 2 (by
  theme). Use for IELTS
  writing, 雅思写作, 大作文, 小作文, 范文, 议论文, 图表作文, Task 1, Task 2, Band 8.5/9 essay.
---

# IELTS Writing

Generate **Band 8.5+** IELTS essays on demand. The user names a **task type**
(Task 1 / Task 2) and a **theme** (e.g. environment, education); you find a real
prompt + a high-band sample, mine the sample for high-value language, then write
your own Band 8.5+ essay. Everything is stored in `ielts-writing/writing.db` and
rendered into `ielts-writing/writing.pdf`, grouped by **Task 1 / Task 2** — Task 1
essays are then grouped by **chart type** (line / bar / pie / table / map / process /
mixed), Task 2 essays by **theme**.

> **One prompt per request** unless the user explicitly asks for a batch. Do not
> bulk-scrape. Personal study use only.

## How this skill is wired

- The **DB (`ielts-writing/writing.db`) is authoritative**; `writing.tex` is its
  rendered view, compiled to PDF by `render.sh`.
- **Searching/fetching is done with your own `WebSearch` / `WebFetch` tools** — the
  Python scripts only touch the DB, render the `.tex`, and download chart images.
  No venv, no pip install (stdlib only; run with system `python3`).
- Every URL/query you touch is **logged in the `sources` table** so the next request
  for the same task+theme can reuse the local bank instead of re-searching (saves tokens).

## Workflow

```
Task Progress:
- [ ] Step 1: Parse request → task_type + theme (+ subtype; required for Task 1)
- [ ] Step 2: DB-first — reuse stored prompts / logged URLs before searching
- [ ] Step 3: Find a real prompt (WebSearch), log every URL touched
- [ ] Step 4: Find a Band 8.5+ sample essay; capture its full text + source URL
- [ ] Step 5 (Task 1 only): download the chart image + write a data description
- [ ] Step 6: Analyse the sample → analysis + highlights[]
- [ ] Step 7: Write a Band 8.5+ essay per reference.md
- [ ] Step 8: Write pending JSON
- [ ] Step 9: Ingest (auto) → DB + regenerate writing.tex
- [ ] Step 10: Render → writing.pdf, report what was added
```

### Step 1 — Parse the request

Map the user's words to:
- `task_type`: `task1` (academic chart/graph/map/process) or `task2` (essay).
- `theme`: one canonical key from `reference.md` (education, environment, technology,
  health, society, government, crime, work, globalisation, media, transport, tourism,
  culture, science, urbanisation, other).
- `subtype`: T1 → line/bar/pie/table/map/process/mixed (**required** — the PDF groups
  Task 1 essays by this chart type; theme is still stored but only displayed per
  prompt); T2 (optional) →
  opinion / discussion / problem-solution / advantages-disadvantages / two-part.

### Step 2 — Check the DB first (saves tokens)

```bash
PY=python3
DB=.claude/skills/ielts-writing/scripts/writing_db.py
$PY $DB find-prompts --task task2 --theme environment
$PY $DB find-sources --task task2 --theme environment
```

- If a suitable **prompt already exists**, you may reuse it (write a new essay for it
  without re-searching the prompt).
- If a `prompt_bank` URL is logged, prefer `WebFetch` on it over a fresh `WebSearch`.

### Step 3 — Find a prompt

If nothing reusable, `WebSearch` for a real exam prompt of that task+theme (e.g.
`IELTS Task 2 environment opinion essay question`). Pick **one** authentic prompt.
**Immediately log each URL you open:**

```bash
$PY $DB log-source --url "<URL>" --kind prompt_bank \
  --query "ielts task2 environment opinion" --task task2 --theme environment --title "<title>"
```

### Step 4 — Find a Band 8.5+ sample essay

`WebSearch` / `WebFetch` a model answer for that prompt (prefer Band 9 / examiner
samples). Capture its **full text** (`sample_text`) and `sample_source_url`. Log the URL
(`--kind sample_essay`). If no credible high-band sample exists, set `sample_found:false`
and skip the sample box — still write your own essay.

### Step 5 — Task 1: chart image + data

For Task 1, download the chart image and write a textual data description:

```bash
$PY $DB fetch-image --url "<image URL>" --slug "task1-environment-2026-06" 
# prints e.g.  images/task1-environment-2026-06.png  → put it in image_path
```

Put the returned path in `image_path`, the original URL in `image_url`, and a concise
`chart_desc` (key figures/trends) so the essay can be checked against the data.

### Step 6 — Analyse the sample

Extract what makes it Band 8.5+: precise collocations, cohesion devices, paragraph logic,
position handling. Produce:
- `analysis`: short notes (paragraphs separated by blank lines).
- `highlights[]`: `{expr, zh, note}` — the reusable expressions worth learning.

### Step 7 — Write the essay

Write an original Band 8.5+ essay following `reference.md` (T1 ≥150 words, T2 ≥250 words;
4-paragraph structure; lexical range; cohesion; fully addressed task). Keep it your own
prose, not a paraphrase of the sample. Count words for `word_count`.

**Inline highlights — mandatory.** Wrap 5–8 high-value expressions with `[[double brackets]]`
in **both** `essay_text` and `sample_text`. The renderer converts `[[...]]` → `\hi{...}`
(yellow highlight + bold) automatically at ingest time. Use this to mark the same kind of
expressions listed in `highlights[]` — collocations, trend phrases, cohesion devices —
so they stand out on the printed page.

```
# ✓ correct — use [[ ]] markers in prose fields
"essay_text": "The data [[underwent a striking reversal]]: ..."
"sample_text": "...home to [[the overwhelming majority]] (81%)..."

# ✗ wrong — never write \hi{} or any LaTeX directly in prose fields
"essay_text": "The data \\hi{underwent a striking reversal}: ..."
```

### Step 8 — Write the pending JSON

Write one file `ielts-writing/pending/<task>-<theme>-<YYYY-MM-DD>.json`. Schema:

```json
{
  "task_type": "task2",
  "subtype": "opinion",
  "theme": "environment",
  "prompt_text": "Some people believe ... To what extent do you agree or disagree?",
  "chart_desc": "",
  "image_path": "",
  "image_url": "",
  "sample_found": true,
  "sample_source_url": "https://...",
  "sample_text": "Full sample [[with key phrases]] marked ...",
  "analysis": "Why this is Band 9 ...",
  "highlights": [
    {"expr": "mitigate the adverse effects of", "zh": "减轻……的不利影响", "note": "替代 reduce bad effects"}
  ],
  "essay_text": "Para 1 [[with key phrases]] marked ...\n\nPara 2 ...\n\nPara 3 ...\n\nPara 4 ...",
  "word_count": 268,
  "band": "8.5+",
  "sources": [
    {"url": "https://...", "kind": "prompt_bank", "query": "ielts task2 environment opinion", "title": "..."}
  ]
}
```

Prose fields are plain text; paragraphs are separated by a blank line (`\n\n`). LaTeX
escaping happens at render time — do **not** pre-escape. Use `[[...]]` for inline
highlights (see Step 7); never write `\hi{}` or any LaTeX directly in prose fields.

### Step 9 — Ingest (automatic, no gate)

```bash
python3 .claude/skills/ielts-writing/scripts/ingest_writing.py
```

Upserts the prompt (de-duplicated by prompt text), inserts the essay, logs the listed
sources, regenerates `writing.tex`, and deletes the ingested pending file.

### Step 10 — Render the PDF

```bash
.claude/skills/ielts-writing/scripts/render.sh            # compile + open
.claude/skills/ielts-writing/scripts/render.sh --no-open  # compile only
```

Then tell the user: the prompt/theme added, target band, word count, and that
`writing.pdf` is updated (Task 1 / Task 2 → theme).

## Additional resources

- Band 8.5+ rubric, structure templates, theme list, compliance: [reference.md](reference.md)
- Sample pending JSON + rendered snippet: [examples.md](examples.md)
- Scripts: [writing_db.py](scripts/writing_db.py), [ingest_writing.py](scripts/ingest_writing.py)
