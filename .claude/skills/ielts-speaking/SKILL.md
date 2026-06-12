---
name: ielts-speaking
description: >-
  IELTS speaking trainer with two flows. Flow A: user names Part 1 or Part 2&3
  (optionally a theme); finds real current IELTS speaking questions online,
  generates Band 8.5+ model answers, stores them in a SQLite question bank where
  every question gets a permanent global number (Q1, Q2, ...), and renders a PDF.
  Flow B: user picks a question by number and answers by voice (transcribed to
  text); scores the transcript against the official IELTS speaking band
  descriptors (FC/LR/GRA; pronunciation N/A) with upgrade suggestions, and logs
  the attempt into the PDF practice log. Use for IELTS speaking, 雅思口语,
  Part 1, Part 2, Part 3, 话题卡, cue card, 口语题库, 口语评分, 回答第 N 题,
  口语练习, speaking practice, band score.
---

# IELTS Speaking

Train IELTS speaking end to end: build a **question bank** of real current exam
questions with **Band 8.5+ model answers**, and **score the user's spoken answers**
(voice → transcript) against the official band descriptors. Everything is stored in
`ielts-speaking/speaking.db` and rendered into `ielts-speaking/speaking.pdf` with
three sections: **Part 1** (by topic), **Part 2 & 3** (by cue-card topic), and the
**练习记录 practice log** (chronological).

> **One topic per request** unless the user explicitly asks for a batch. Do not
> bulk-scrape. Personal study use only.

## How this skill is wired

- The **DB (`ielts-speaking/speaking.db`) is authoritative**; `speaking.tex` is its
  rendered view, compiled to PDF by `render.sh`.
- **Searching/fetching is done with your own `WebSearch` / `WebFetch` tools** — the
  Python scripts only touch the DB and render the `.tex`. No venv, no pip install
  (stdlib only; run with system `python3`).
- Every URL/query you touch is **logged in the `sources` table** so the next request
  for the same part+theme can reuse the local bank instead of re-searching.
- **Question numbers are global and permanent.** `questions.id` is AUTOINCREMENT
  (never reused) and questions are de-duplicated by a hash of part + text, so
  re-ingesting the same question never mints a new number. The PDF prints the
  number prominently (Q17) — it is how the user picks a question to practise.

## Step 0 — Branch on the request

| User says | Flow |
|---|---|
| a part (part1 / part2&3 / part2 / part3) and/or a theme — wants questions | **Flow A 题库生成** |
| "我要回答第 N 题" / "回答 Q17" / gives a question number + a spoken answer (transcript) | **Flow B 评分** |

## Flow A — Build the question bank (题库生成)

```
Task Progress:
- [ ] A1: Parse request → part_group (p1 | p23) + theme
- [ ] A2: DB-first — reuse stored topics/questions/sources before searching
- [ ] A3: WebSearch real current questions; log every URL touched
- [ ] A4: Assemble ONE topic (p1: 4–6 questions; p23: 1 cue card + 4–6 Part 3 questions)
- [ ] A5: Write a Band 8.5+ model answer for EVERY question per reference.md
- [ ] A6: Write pending bank JSON
- [ ] A7: Ingest (auto) → DB + regenerate speaking.tex
- [ ] A8: Render → speaking.pdf, report the new Q numbers
```

### A1 — Parse the request

- `part_group`: `p1` (Part 1) or `p23` (Part 2 & 3 — they always come as a set:
  one cue card + its discussion questions). "part2" or "part3" alone → `p23`.
  A bare theme with no part → ask once, or default to `p23`.
- `theme`: one canonical key from [reference.md](reference.md) (hometown, home,
  work-study, hobbies, people, daily-life, technology, travel, food, media,
  environment, shopping, health, education, culture, experiences, objects, other).

### A2 — Check the DB first (saves tokens)

```bash
PY=python3
DB=.claude/skills/ielts-speaking/scripts/speaking_db.py
$PY $DB find-topics    --part p23 --theme technology
$PY $DB find-questions --part p23 --theme technology
$PY $DB find-sources   --part p23 --theme technology
```

- If a suitable topic already exists, tell the user its Q numbers instead of
  re-fetching (they may just want to practise it — that's Flow B).
- If a `question_bank` URL is logged, prefer `WebFetch` on it over a fresh search.

### A3 — Find real questions

`WebSearch` for **current/recent real exam questions** (e.g. `IELTS speaking
part 2 technology cue card 2026`, `雅思口语 当季题库 part1`). Prefer recent
question-bank sites. Pick **one** authentic topic. **Immediately log each URL:**

```bash
$PY $DB log-source --url "<URL>" --kind question_bank \
  --query "ielts speaking part 2 technology 2026" --part p23 --theme technology --title "<title>"
```

### A4 — Assemble one topic

- **p1**: one topic (e.g. "Hometown") with its typical **4–6 questions**.
- **p23**: exactly **one Part 2 cue card** — headline ("Describe a ...") plus its
  **4 bullet points** (`cue_points`) — followed by **4–6 related Part 3 questions**.
  The cue card must be the first item in `questions[]`.

Use the questions as found (light cleanup OK); do not invent fake "exam questions".

### A5 — Write Band 8.5+ model answers

Per [reference.md](reference.md) style guide:

- **Part 1**: 2–4 sentences, natural spoken register, direct answer + detail.
- **Part 2**: a ~2-minute monologue, **220–280 words**, covering all 4 cue points
  in order, with a hook and a reflective close. Paragraphs separated by blank lines.
- **Part 3**: 4–6 sentences — stance → reason → concrete example (→ optional concession).

**Inline highlights — mandatory.** Wrap **2–4 high-value expressions per answer**
with `[[double brackets]]`; the renderer converts them to `\hi{...}` (yellow
highlight). Never write `\hi{}` or any LaTeX in prose fields. No `[[...]]` in
`cue_points` (exam text, not learning targets).

### A6 — Write the pending bank JSON

One file `ielts-speaking/pending/bank-<part_group>-<theme>-<YYYY-MM-DD>.json`:

```json
{
  "kind": "bank",
  "part_group": "p23",
  "theme": "technology",
  "topic_title": "Describe a piece of technology you find useful",
  "source_url": "https://...",
  "questions": [
    {
      "part": "p2",
      "question_text": "Describe a piece of technology you find useful.",
      "cue_points": ["What it is", "When you started using it", "How you use it", "And explain why you find it useful"],
      "model_answer": "The gadget I'd like to talk about ... [[an absolute game-changer]] ...",
      "word_count": 252
    },
    {"part": "p3", "question_text": "Do you think people rely on technology too much?",
     "model_answer": "To a large extent, yes. ... [[an over-reliance on]] ..."}
  ],
  "sources": [
    {"url": "https://...", "kind": "question_bank", "query": "ielts speaking part 2 technology 2026", "title": "..."}
  ]
}
```

For `p1` banks: 4–6 question objects, all `"part": "p1"`, no `cue_points`;
`topic_title` is the topic name (e.g. "Hometown").

### A7 + A8 — Ingest and render (automatic, no gate)

```bash
python3 .claude/skills/ielts-speaking/scripts/ingest_speaking.py
.claude/skills/ielts-speaking/scripts/render.sh --no-open
```

Ingest prints the Q-number range it assigned (e.g. `questions Q17–Q23`). Report to
the user: the topic added, **the new Q numbers** (so they can pick one to practise),
and that `speaking.pdf` is updated.

## Flow B — Score a practice answer (评分)

```
Task Progress:
- [ ] B1: Get the question number + the user's transcript
- [ ] B2: get-question --id N (never invent a question)
- [ ] B3: Score FC / LR / GRA per reference.md band anchors; Pron = N/A
- [ ] B4: Build upgrades + grammar fixes + advice
- [ ] B5: Write pending attempt JSON
- [ ] B6: Ingest (auto) → DB + regenerate speaking.tex
- [ ] B7: Render → speaking.pdf; report scores + advice in chat too
```

### B1 + B2 — Fetch the question

The user picks by global number ("我要回答第 23 题"). Their spoken answer arrives
as transcribed text.

```bash
$PY $DB get-question --id 23 --json
```

If not found: say so plainly, suggest `find-questions` or Flow A. **Never invent
question text.** If the user gave a number but no answer yet, show the question
(and cue points for Part 2) and wait for their answer.

### B3 — Score the transcript

Score **three** criteria against the Band 6/7/8/9 anchors in
[reference.md](reference.md), each to the nearest 0.5:

- **FC** Fluency & Coherence — fillers (er/um), self-correction, repetition,
  connective range, topic development, answer length for the part.
- **LR** Lexical Resource — range, precision, collocation, idiomaticity, paraphrase.
- **GRA** Grammatical Range & Accuracy — structure variety, error density.

**Pronunciation = N/A** (cannot be judged from a transcript — say this to the user).
**Overall = mean of the three, rounded to the nearest 0.5** (halves up). The ingest
script recomputes this; your number must match.

### B4 — Improvement advice

- `upgrades[]`: `{said, better, note}` — 2–5 expressions the user actually said →
  a Band 8 alternative (plain text; the renderer highlights `better` automatically).
- `grammar_fixes[]`: `{error, fix, note}` — actual errors quoted from the transcript.
- `advice`: 2–4 short paragraphs on structure/content (中文 OK), blank-line separated.

### B5 — Write the pending attempt JSON

One file `ielts-speaking/pending/attempt-q<N>-<YYYY-MM-DD>.json`:

```json
{
  "kind": "attempt",
  "question_id": 23,
  "transcript": "Well, I think people use technology too much because ...",
  "score_fc": 6.5, "score_lr": 6.0, "score_gra": 6.5, "overall": 6.5,
  "advice": "开头先直接表态再展开...\n\n例子要更具体...",
  "upgrades": [{"said": "very convenient", "better": "saves me an enormous amount of hassle", "note": "具体化 + 地道搭配"}],
  "grammar_fixes": [{"error": "people is rely on", "fix": "people rely on", "note": "主谓一致"}]
}
```

The transcript is stored verbatim (it is the user's own words — no `[[...]]`
markers, no edits beyond removing transcription artefacts the user didn't say).

### B6 + B7 — Ingest, render, report

```bash
python3 .claude/skills/ielts-speaking/scripts/ingest_speaking.py
.claude/skills/ielts-speaking/scripts/render.sh --no-open
```

A failed attempt file (e.g. unknown question number) is **kept in pending/** and
reported — fix it or delete it, don't ignore it. Then give the user the full
scorecard **in chat** (FC/LR/GRA, Pron N/A, overall, upgrades, fixes, advice) and
note that the 练习记录 section of `speaking.pdf` is updated.

## Additional resources

- Band anchors (FC/LR/GRA, Band 6–9), answer style guide, theme list: [reference.md](reference.md)
- Sample bank + attempt JSON and rendered snippets: [examples.md](examples.md)
- Scripts: [speaking_db.py](scripts/speaking_db.py), [ingest_speaking.py](scripts/ingest_speaking.py)
