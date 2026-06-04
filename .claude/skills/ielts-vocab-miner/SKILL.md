---
name: ielts-vocab-miner
description: >-
  Fetches subtitles and articles from YouTube, TED, BBC, and news sites,
  extracts Band 8.5+ difficulty English (about half IELTS-oriented advanced,
  half domain-specific advanced), outputs \vocabentry and \vocabsource with IPA.
  Supports interactive review and learned preferences. Use for IELTS vocabulary,
  Band 8.5, advanced English, C1/C2, difficult words, subtitles, TED, BBC.
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
- [ ] Step 6 (optional): Human review + update learned preferences
```

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

Candidate ranking incorporates `ielts-vocab/learner/preferences.json` when it exists (from prior reviews).

If `text` is empty or script exits non-zero, report `warnings` and suggest alternatives. Article fetch may fail on paywalls—allow one WebFetch fallback; add warning `fallback:webfetch`.

### Step 3: Curate vocabulary (dual track, Band 8.5+)

**Before curating**: if [ielts-vocab/learner/learned-preferences.md](../../ielts-vocab/learner/learned-preferences.md) exists, read and apply its keep/reject tendencies.

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

### Step 6: Interactive review (optional)

After writing `.tex` to `ielts-vocab/pending/`, user runs from repo root:

```bash
ielts-vocab/review.sh        # review 1 random pending file (default)
ielts-vocab/review.sh 3      # review 3 random pending files
```

Or directly:

```bash
.claude/skills/ielts-vocab-miner/scripts/.venv/bin/python \
  .claude/skills/ielts-vocab-miner/scripts/review_vocab.py -n 3 \
  --pending-dir ielts-vocab/pending --reviewed-dir ielts-vocab/reviewed
```

Per entry: **Enter/换行 = 保留**, **空格 = 删除**, **q = 结束本文件** (remaining entries in that file are dropped).

After all files in the session: enter **学习率 0–100** once (higher = stronger update to personal preferences).

`review.sh` also runs `merge_vocab.py` to update `ielts-vocab/vocabulary.tex` (video / article / book sections).

Outputs:

- `ielts-vocab/reviewed/<file>.tex` — kept entries only
- `ielts-vocab/vocabulary.tex` — merged master notebook
- `ielts-vocab/learner/preferences.json` — weights (gitignored)
- `ielts-vocab/learner/learned-preferences.md` — Agent-readable summary

## Examples

Full sample outputs: [examples.md](examples.md)

## Additional resources

- Band 8.5+ rubric, exclude list, IPA, learner: [reference.md](reference.md)
- Scripts: [fetch_content.py](scripts/fetch_content.py), [clean_text.py](scripts/clean_text.py), [review_vocab.py](scripts/review_vocab.py), [merge_vocab.py](scripts/merge_vocab.py), [learner.py](scripts/learner.py)
