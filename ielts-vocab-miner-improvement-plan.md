# IELTS Vocab Miner — Conversation Summary & Improvement Plan

## What We Covered

We reviewed how the `ielts-vocab-miner` skill works end to end, diagnosed its
performance bottlenecks, and evaluated whether the pipeline architecture is the
right fit for the goal of selecting high-level English words and expressions.

---

## How Word Selection Currently Works

1. **Fetch** — `fetch_content.py` extracts article body (via trafilatura) or
   subtitle text (via youtube-transcript-api → yt-dlp fallback), producing a
   plain-English `text` field.
2. **Score candidates** — spaCy (`en_core_web_sm`) tokenises the text, applies
   exclusion lists, and scores each lemma under two heuristics:
   - `_score_ielts`: frequency × AWL membership → `candidates_ielts[]` (top 40)
   - `_score_advanced`: length/rarity-weighted → `candidates_advanced[]` (top 40)
3. **LLM curation** — Claude picks ~20–25 entries from those pools, targeting
   ~50% Track A (IELTS AWL / Task 2 collocations) + ~50% Track B (domain
   high-register), enforcing the Band 8.5+ bar and the shared exclude list.
4. **Write `.tex`** → **ingest into SQLite DB** → **render PDF**.

---

## Weaknesses Identified

| Issue | Detail |
|-------|--------|
| Thin scoring signal | Candidates ranked by frequency × AWL/rarity — a word appearing 5× scores higher than a precise rare collocation used once |
| Phrases are second-class | Multi-word expressions are not systematically extracted; they depend on the LLM noticing them during curation |
| No known-word filter | De-duplication only prevents repeated DB entries, not words the user already knows well |
| Rigid 50/50 split | Balance is source-agnostic; a diplomatic news article may naturally yield 80% Track B |

---

## Performance Bottlenecks (Worst → Best)

| Step | Typical cost | Cause |
|------|-------------|-------|
| **LaTeX render** | 60–120 s | Full `vocabulary.tex` compiled every run; grows with DB |
| **spaCy NLP** | 15–30 s | Cold model load (`en_core_web_sm`) + full-text pipeline each run |
| **yt-dlp metadata prefetch** | 10–60 s | Separate subprocess call just for title/date, before transcript fetch |
| **LLM curation passes** | 30–60 s | Multiple round-trips if quality checklist triggers corrections |

---

## Improvement Plan

### 1. Skip auto-render (highest ROI, easiest)

**Problem**: PDF compiled after every run even when you don't need it.

**Fix**: Edit `SKILL.md` Step 7 — change the default from "render automatically"
to "skip unless user explicitly asks for a PDF". One line change, permanent fix.

> Don't rely on saying "do not render" each session — the skill's instructions
> override conversational hints unless the SKILL.md itself is changed.

---

### 2. Replace spaCy candidate scoring with LLM-direct selection

**Problem**: The scoring heuristic (frequency × AWL weight) is a weak proxy for
what you actually want. It misses collocations and over-weights repeated common words.

**Fix**: After fetching and cleaning text, pass it directly to the LLM with a
tight prompt — no intermediate candidate pool. The LLM natively understands
register, collocation, and Band 8.5+ nuance better than any frequency scorer.

**Requirements for the prompt**:
- Require every selected word/phrase to be quoted verbatim from the source text
  (prevents hallucination)
- Explicitly request multi-word expressions, not just single lemmas
- Keep the dual-track framing (IELTS AWL vs. domain high-register) as a prompt
  instruction, not a script constraint

**Keep**: `fetch_content.py` and `clean_text.py` for subtitle parsing and article
extraction — that part is genuinely useful. Drop only the candidate scoring step.

---

### 3. Remove the yt-dlp metadata prefetch for videos

**Problem**: `_video_metadata()` spawns a full yt-dlp subprocess just to get
title/date/URL before the transcript is even attempted. That's one slow network
round-trip wasted on metadata.

**Fix**: Patch `fetch_video()` to skip `_video_metadata()` on first attempt —
use the original URL as a placeholder and attempt the transcript API immediately.
Fall back to yt-dlp only if the transcript API fails, and collect metadata then.

---

### 4. Use agent WebFetch for articles (skip the Python subprocess)

**Problem**: For articles, the pipeline spawns a bash process → Python → trafilatura,
adding subprocess overhead.

**Fix**: For article URLs (BBC, Guardian, Reuters, etc.), have Claude call
`mcp__workspace__web_fetch` directly instead of running the script. Faster,
no venv required. Keep the Python script path as fallback for edge cases.

> Note: This only applies to articles. YouTube transcript fetching still requires
> the Python scripts (no agent-tool equivalent for `youtube-transcript-api`).

---

### 5. Explicit collocation extraction pass (quality improvement)

**Problem**: High-value multi-word expressions (`sanctions relief`, `pyrrhic victory`,
`charge d'affaires`) are structurally missing from candidate generation.

**Fix**: Add a dedicated collocation pass in the LLM prompt — explicitly ask for
verb+noun and adjective+noun pairs at C1/C2 level, not just single-word lemmas.
This is a prompt engineering change, not a script change.

---

## Priority Order

1. **Skip auto-render** — edit SKILL.md, 5 minutes, biggest time saving
2. **LLM-direct selection** — rewire the skill prompt, removes spaCy bottleneck and improves quality simultaneously
3. **Collocation extraction** — prompt addition, no code change
4. **yt-dlp metadata prefetch fix** — small script patch, moderate gain
5. **Agent WebFetch for articles** — skill logic change, moderate gain
