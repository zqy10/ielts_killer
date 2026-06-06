# IELTS Vocab Miner — Reference

## Recommended sources

| Source | URL pattern | Notes |
|--------|-------------|-------|
| YouTube (education) | `youtube.com/watch?v=...` | Uses `youtube-transcript-api` when yt-dlp subs need a PO token |
| TED | `ted.com/talks/...` or YouTube mirror | YouTube often more reliable for subtitles |
| BBC News | `bbc.com/news/...` | Formal register, good for Writing Task 2 |
| BBC Learning English | `bbc.co.uk/learningenglish/...` | Graded but still useful collocations |
| Reuters / Guardian | `reuters.com`, `theguardian.com` | News lexis, current affairs |


## Directory layout (`ielts-vocab/`)

| Path | Purpose |
|------|---------|
| `pending/` | Agent output `.tex` awaiting ingest (cleared by `ingest_vocab.py`) |
| `vocab.db` | SQLite word store (authoritative, de-duplicated) |
| `vocabulary.tex` | Master notebook (video / article / book sections), generated from the DB |
| `vocabulary.pdf` | Compiled PDF (output of `render.sh`) |

Optional sidecar `pending/foo.meta.json` with `"source_type": "book"` helps `ingest_vocab.py` classify sources.

## Compliance

- Personal study only; respect site Terms of Service.
- Do not bulk-scrape or republish full transcripts/articles.
- One URL per request unless the user explicitly asks for a batch.

## Dual-track curation (50% / 50%, no labels in output)

Each run targets **15–30** entries (up to **40** for long texts): about **half Track A** and **half Track B**. Do not tag entries in `.tex`; balance is enforced at curation time.

### Track A — IELTS advanced (~50%)

Band **8.5+** lexical resource (not Band 7–8 “safe” lists):

| Criterion | Look for |
|-----------|----------|
| Sophisticated control | Natural collocations, not AWL stacking |
| Less common lexis | AWL, abstract nouns, argument verbs that distinguish level in one use |
| Collocation | `mitigate effects`, `contentious issue`, `sanctions relief` |
| Task 2 | `ramification`, `disparity`, `precedent`, `substantiate` |
| Precision | Verbs/adjectives that narrow meaning vs. generic good/bad |

Prefer `candidates_ielts[]` from JSON; supplement from full `text` for phrases.

**Band 8.5+ reject “pseudo-advanced”**: `significant`, `important`, `missile`, `drone`, `airport`, `ceasefire` unless part of a high-value phrase.

### Track B — Non-IELTS advanced (~50%)

High-register words **from the source domain**, not required on IELTS word lists:

| Domain | Examples |
|--------|----------|
| News / geopolitics | `escalation`, `retaliation`, `blockade`, `summon` |
| Military / tech | `interceptor`, `mariner`, `unladen` |
| Narrative / evaluation | `pyrrhic`, `calculated`, `unmistakable`, `shaky` |

Prefer `candidates_advanced[]`; allow fixed phrases (`charge d'affaires`, `Strait of Hormuz` as `phr.`).

**Track B excludes**: ultra-rare words, transcription errors, opaque abbreviations (unless explained in source, e.g. IRGC).

### Shared exclude list (raise difficulty)

Do **not** select unless part of a strong collocation:

- News skeleton: `attack`, `strike`, `kill`, `injure`, `official`, `country`, `deal`, `leader`, `person`, `time`, `news`, `report`, `claim`, `deny`, `target`, `fire`, `launch`
- Low-value modifiers: `national`, `foreign`, `early`, `later`, `regional`, `military` (alone), `iranian`, `indian`, `communist`
- Short generic lemmas: length &lt; 6 and not AWL and not a phrase
- Pseudo-advanced (Band 8.5+): `significant`, `important`, `various`, `different`, `develop`, `increase`

**Skip**: fillers, auto-sub errors, bare country names.

## Academic Word List (AWL) — sample lemmas

Use as tie-breaker when choosing among candidates: `analysis`, `approach`, `area`, `assessment`, `assume`, `authority`, `available`, `benefit`, `concept`, `consistent`, `constitutional`, `context`, `contract`, `create`, `data`, `definition`, `derived`, `distribution`, `economic`, `environment`, `established`, `estimate`, `evidence`, `export`, `factors`, `financial`, `formula`, `function`, `identified`, `income`, `indicate`, `individual`, `interpretation`, `involved`, `issues`, `labour`, `legal`, `legislation`, `major`, `method`, `occur`, `percent`, `period`, `policy`, `principle`, `procedure`, `process`, `required`, `research`, `response`, `role`, `section`, `sector`, `significant`, `similar`, `source`, `specific`, `structure`, `theory`, `variables`.

Full list: Coxhead AWL (570 word families). Prefer **phrases** from your source over bare AWL items already mastered.

## IPA Unicode (required)

| Symbol | Meaning | Example |
|--------|---------|---------|
| `ˈ` | Primary stress | `ˈæk.ju.ri.ət` |
| `ˌ` | Secondary stress | `ˌɪn.təˈpreɪ.ʃən` |
| `ː` | Long vowel | `miːt` |
| `ɪ` `iː` | short / long i | `ˈmɪt.ɪ.ɡeɪt` |
| `æ` `ɑː` | trap / palm | `ˈæk.ju.ri.ət` |
| `ʃ` `tʃ` `dʒ` | sh, ch, j | `ˈpreʃ.ə` |

Wrap syllables in slashes: `/ˈmɪt.ɪ.ɡeɪt/`. Verify against [Cambridge Dictionary](https://dictionary.cambridge.org/) when unsure.

## LaTeX macro stubs

Add to your preamble or notes template:

```latex
\newcommand{\vocabsource}[3]{%
  \par\noindent\textbf{Source:} #1\par
  \noindent\texttt{#2}\par
  \noindent\textit{#3}\par\medskip
}

\newcommand{\vocabentry}[7]{%
  \par\noindent\textbf{#1} \textit{#2} #3\par
  \noindent#4\par
  \noindent\textit{#5}\par
  \noindent Syn: #6 \quad Ant: #7\par\smallskip
}
```

Customize styling as needed; the skill outputs the macro **calls**, not the definitions.

## JSON schema (`fetch_content.py` / `clean_text.py`)

```json
{
  "title": "string",
  "url": "string",
  "date": "YYYY-MM-DD | unknown",
  "source_type": "video | article | local",
  "text": "plain text body",
  "candidates_ielts": [
    {"lemma": "mitigate", "pos": "VERB", "count": 2, "score": 4.5, "sample": "..."}
  ],
  "candidates_advanced": [
    {"lemma": "interceptor", "pos": "NOUN", "count": 1, "score": 3.5, "sample": "..."}
  ],
  "candidates": [
    {"lemma": "mitigate", "pos": "VERB", "count": 2, "score": 4.5, "sample": "..."}
  ],
  "warnings": ["string"]
}
```

- `candidates_ielts`: AWL-weighted pool for Track A (top 40).
- `candidates_advanced`: domain/rarity-weighted pool for Track B (top 40).
- `candidates`: merged de-duplicated list (backward compatible).
