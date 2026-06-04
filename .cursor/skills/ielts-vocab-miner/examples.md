# Example outputs

Illustrative `\vocabsource` + `\vocabentry` blocks (abbreviated). Real runs target **20–25** entries at **Band 8.5+** difficulty: roughly **half IELTS advanced (Track A)** and **half domain advanced from the source (Track B)**. Entries are **not** labeled by track in the `.tex` file.

## Interactive review (after generating `.tex` in `pending/`)

From repo root, in a terminal:

```bash
ielts-vocab/review.sh     # default: 1 random pending file
ielts-vocab/review.sh 3   # 3 random pending files
```

- **Enter / 换行** — keep entry  
- **Space** — delete entry  
- **q** — end current file (remaining entries in that file are dropped)  
- After all files: enter **learning rate 0–100** once (higher = stronger personal bias on future runs)

Moves reviewed files to `ielts-vocab/reviewed/`, merges into `vocabulary.tex`, updates `ielts-vocab/learner/preferences.json` and `learned-preferences.md`.

## YouTube / TED (video)

Mix note: ~6 Track A (e.g. `substantiate`, `colossal`, `disparity`) + ~7 Track B (e.g. `pyrrhic`, `Generalissimo`, `urbanisation`).

```latex
\vocabsource{The surprising science of happiness}{https://www.youtube.com/watch?v=example}{2011-05-10}

\vocabentry{substantiate}{v.}{/səbˈstæn.ʃi.eɪt/}{证实；使巩固}{Superficial reforms cannot substantiate long-term resilience.}{corroborate, validate}{undermine}
\vocabentry{colossal}{adj.}{/kəˈlɒs.əl/}{巨大的}{The present upsurge of the peasant movement is a colossal event.}{immense, gigantic}{negligible}
\vocabentry{impoverished}{adj.}{/ɪmˈpɒv.ər.ɪʃt/}{贫乏的}{An impoverished experiential horizon limits what we notice.}{deprived, meagre}{affluent}
\vocabentry{pyrrhic}{adj.}{/ˈpɪr.ɪk/}{得不偿失的}{However pyrrhic the Long March was, the CCP lived to fight another day.}{hollow, costly}{decisive}
```

## BBC News (article)

Mix note: ~6 Track A (e.g. `contentious`, `sanctions relief`) + ~6 Track B (e.g. `interceptor`, `unladen`, `charge d'affaires`).

```latex
\vocabsource{Climate summit opens amid mounting pressure}{https://www.bbc.com/news/example}{2026-06-04}

\vocabentry{contentious}{adj.}{/kənˈten.ʃəs/}{有争议的}{Financing remains the most contentious issue on the agenda.}{divisive, controversial}{uncontroversial}
\vocabentry{sanctions relief}{phr.}{/ˈsæŋk.ʃənz rɪˈliːf/}{解除制裁}{Negotiators had not offered Iran sanctions relief in exchange for reopening the strait.}{easing of sanctions}{-}
\vocabentry{interceptor}{n.}{/ˌɪn.təˈsep.tər/}{拦截装置}{The damage was caused by an error from a US missile interceptor.}{defence system}{-}
\vocabentry{unladen}{adj.}{/ʌnˈleɪ.dən/}{未载货的}{Centcom disabled an unladen oil tanker sailing towards Iran.}{empty, without cargo}{laden}
```

## Field notes

- Multi-word lemmas: use `phr.` or `n.` for fixed expressions.
- Proper nouns in examples are fine; avoid listing bare country names as vocabulary.
- Do not pad Track B with easy news words (`attack`, `deal`, `official`) to hit the count.
