---
name: ielts-vocab-miner
description: >-
  Fetches subtitles and articles from YouTube, TED, BBC, and news sites,
  extracts Band 8.5+ difficulty English (about half IELTS-oriented advanced,
  half domain-specific advanced), outputs \vocabentry and \vocabsource with IPA,
  ingests them into a de-duplicated SQLite store and renders a PDF notebook.
  Use for IELTS vocabulary, Band 8.5, advanced English, C1/C2, difficult words,
  subtitles, TED, BBC. Also expands the user's own word list
  (ielts-vocab/pending/my.md) into full entries — triggers: 整理词汇, 自选词汇,
  my.md, word list expansion.
---

# IELTS Vocab Miner

Extract **Band 8.5+** English from quality sources (YouTube/TED subtitles, BBC/news). Each batch is roughly **50% IELTS advanced** + **50% non-IELTS advanced** (no type labels in `.tex`).

## Output contract (mandatory)

Every run must produce:

1. **Source block** (before entries):

   `\vocabsource{标题}{URL}{日期}`

   Date format: `YYYY-MM-DD`, or `unknown` if unavailable.

2. **Each entry** (exactly 7 brace fields):

   `\vocabentry{单词}{词性}{音标}{中文释义}{例句}{近义词}{反义词}`

3. **IPA**: Standard IPA with Unicode characters (`ˈ`, `ˌ`, `ɪ`, `æ`, etc.). Never use ASCII approximations like `/mitigate/`.

4. **Synonyms/antonyms**: 1–3 items comma-separated; use `-` if none.

Default output path: `ielts-vocab/pending/<slug>-<date>.tex` (ask user once if they prefer another directory).

## Quick workflow

```
Task Progress:
- [ ] Step 1: Identify source (URL or local file)
- [ ] Step 2: Fetch and preprocess with scripts
- [ ] Step 3: Curate ~50% Track A + ~50% Track B (Band 8.5+)
- [ ] Step 4: Write .tex with \vocabsource + \vocabentry blocks
- [ ] Step 5: Run quality checklist
- [ ] Step 6: **You (agent) ingest** the `.tex` into the DB + regenerate vocabulary.tex — run automatically, no human gate
- [ ] Step 7: **You (agent) render** vocabulary.tex → vocabulary.pdf — run automatically, no human gate
```

> **One automatic pipeline.** Steps 1–7 run end to end with **you running the
> ingest and render yourself** — do not stop after writing the `.tex` and do not
> ask the user to run a script. After the quality checklist passes, invoke
> `ingest_vocab.py` (Step 6) then `render.sh` (Step 7). The DB
> (`ielts-vocab/vocab.db`) is authoritative; `vocabulary.tex` is its rendered view.

### Step 1: Identify source

| Type | Host/pattern | Action |
|------|--------------|--------|
| Video | `youtube.com`, `youtu.be`, `ted.com` | `fetch_content.py --url URL` (tries youtube-transcript-api, then yt-dlp VTT) |
| Article | `bbc.com`, `bbc.co.uk`, `reuters.com`, `theguardian.com`, `nytimes.com`, etc. | `fetch_content.py --url URL` (auto → article) |
| Local | `.vtt`, `.srt`, `.txt` | `clean_text.py --input PATH --title "..."` |

TED on ted.com: try `fetch_content.py` first; if it fails, ask user for the YouTube mirror URL.

### Step 2: Run scripts

From repo root (requires network for URLs):

```bash
cd .claude/skills/ielts-vocab-miner/scripts
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m spacy download en_core_web_sm   # optional; Python 3.10+ only

.venv/bin/python fetch_content.py --url "<URL>" --out /tmp/ielts_raw.json
# or local:
.venv/bin/python clean_text.py --input "<path>" --title "<title>" --out /tmp/ielts_raw.json
```

Read JSON: `title`, `url`, `date`, `text`, `source_type`, `candidates_ielts[]`, `candidates_advanced[]`, `candidates[]`, `warnings[]`.

If `text` is empty or script exits non-zero, report `warnings` and suggest alternatives. Article fetch may fail on paywalls—allow one WebFetch fallback; add warning `fallback:webfetch`.

### Step 3: Curate vocabulary (dual track, Band 8.5+)

Default **N = 20–25** entries (15–30 range; up to **40** for long texts).

| Track | Share | Pool | Focus |
|-------|-------|------|--------|
| **A — IELTS advanced** | ~50% | `candidates_ielts[]` + `text` | Band 8.5+: AWL, Task 2 chains, precise collocations |
| **B — Non-IELTS advanced** | ~50% | `candidates_advanced[]` + `text` | Domain high register: news, military, diplomacy |

**Band 8.5+ bar**: Each item should impress in writing/speaking samples—not merely “advanced enough for Band 7”. See [reference.md](reference.md).

**Exclude**: news skeleton words, pseudo-advanced (`significant`, `important`), bare nationalities, short generic lemmas.

**Chinese gloss**: Track A — exam/writing; Track B — register/meaning. No type prefixes in output.

**POS tags**: `n.`, `v.`, `adj.`, `adv.`, `phr.`, `prep.`, `conj.`

### Step 4: Assemble output

```latex
\vocabsource{Climate summit opens in Geneva}{https://www.bbc.com/news/...}{2026-06-04}

\vocabentry{mitigate}{v.}{/ˈmɪt.ɪ.ɡeɪt/}{减轻；缓和}{Leaders pledged to mitigate the worst effects of warming.}{alleviate, reduce}{aggravate}
```

Escape LaTeX special chars if needed: `\`, `{`, `}`, `#`, `$`, `%`, `&`, `_`, `^`, `~`.

### Step 5: Quality checklist

- [ ] `\vocabsource` once before all `\vocabentry` lines
- [ ] Each `\vocabentry` has exactly 7 fields
- [ ] IPA uses Unicode stress marks (`ˈ` / `ˌ`)
- [ ] Example sentences from source text
- [ ] ~50% Track A / ~50% Track B (no labels)
- [ ] Band 8.5+: no cluster of easy news or pseudo-advanced words
- [ ] 15–30 entries unless user asked otherwise

### Step 6: Ingest into the DB (you run this automatically)

**This is part of the mining run, not a separate task.** As soon as the `.tex`
is written to `ielts-vocab/pending/` and the quality checklist passes, run the
ingest yourself — no confirmation needed, no asking the user to run a script:

```bash
.claude/skills/ielts-vocab-miner/scripts/.venv/bin/python \
  .claude/skills/ielts-vocab-miner/scripts/ingest_vocab.py \
  --pending-dir ielts-vocab/pending --vocabulary ielts-vocab/vocabulary.tex
```

(Ingest has no standalone wrapper script — call `ingest_vocab.py` directly here
as part of the run so it stays self-contained.)

This merges every pending block into `ielts-vocab/vocab.db` (de-duplicated by
lowercased word), regenerates `vocabulary.tex` (video / article / book sections),
then **deletes the pending source files** (the DB is authoritative).

### Step 7: Render PDF (you run this automatically)

**This is part of the mining run.** Immediately after ingest succeeds, render
the PDF — no confirmation needed, no asking the user to run a script:

```bash
ielts-vocab/render.sh --no-open
```

`render.sh` auto-detects the available engine (tectonic preferred, xelatex
fallback) and writes `ielts-vocab/vocabulary.pdf`. The `--no-open` flag skips
the auto-launch so the agent run stays non-interactive; the PDF path is reported
to the user in the final summary.

Then report to the user: how many new words were ingested and where the PDF is.

Outputs:

- `ielts-vocab/vocab.db` — authoritative word store (updated in place)
- `ielts-vocab/vocabulary.tex` — regenerated master notebook
- `ielts-vocab/vocabulary.pdf` — compiled PDF

## Flow: 整理词汇 (expand my.md)

Triggered when the user says **“整理词汇”** (or asks to expand `my.md` / 自选词汇).
This flow does **not** fetch any URL — the user keeps a bare word list at
`ielts-vocab/pending/my.md` (one word per line) and you expand it into full
entries under a dedicated **其他来源 (Other Sources)** section.

1. **Read `ielts-vocab/pending/my.md`.** Strip blank lines and in-file
   duplicates. If the file is missing or has no words, tell the user
   **“没有词汇可拓展”** and stop.
2. **Check the DB first.** Query `ielts-vocab/vocab.db` for words already in the
   store (de-dup key is lowercased word), e.g.:

   ```bash
   sqlite3 ielts-vocab/vocab.db \
     "SELECT word_lower FROM words WHERE word_lower IN ('word1','word2',...)"
   ```

   Skip those words (first occurrence wins) and list them in the final report.
3. **Write the entries yourself.** For each new word produce a full 7-field
   `\vocabentry` (same contract as above; IPA in Unicode). **Example sentences
   should read like IELTS Writing Task 2 prose** — argumentative, academic
   register (education, environment, technology, society…). If a word genuinely
   doesn't fit that register (e.g. `venous`, `distension`), write a natural
   example instead.
4. **Write the pending tex** to `ielts-vocab/pending/my-words-<YYYY-MM-DD>.tex`:

   ```latex
   \vocabsource{自选词汇 <YYYY-MM-DD>}{local://my-words/<YYYY-MM-DD>}{<YYYY-MM-DD>}
   ```

   The `local://my-words` URL prefix routes the block into the 其他来源 section;
   the dated URL keeps each 整理 run as its own dated block in the PDF.
5. **Ingest + render** — run Step 6 and Step 7 exactly as in the mining flow
   (`ingest_vocab.py` then `render.sh --no-open`). Ingest only deletes
   `*.tex`/`*.meta.json`, so `my.md` is untouched.
6. **Report, then ask before clearing.** Report how many words were added, which
   were skipped as already stored, and the PDF path. Then **ask the user for
   permission to clear `my.md`** — this is the only human gate in this flow. On
   approval, truncate the file to empty (keep the file itself); otherwise leave
   it as is.

## Examples

Full sample outputs: [examples.md](examples.md)

## Additional resources

- Band 8.5+ rubric, exclude list, IPA: [reference.md](reference.md)
- Scripts: [fetch_content.py](scripts/fetch_content.py), [clean_text.py](scripts/clean_text.py), [ingest_vocab.py](scripts/ingest_vocab.py), [vocab_db.py](scripts/vocab_db.py), [texlib.py](scripts/texlib.py)
