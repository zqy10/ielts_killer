# Examples — pending JSON & rendered output

## 1. Bank JSON (Flow A, Part 2 & 3)

`ielts-speaking/pending/bank-p23-technology-2026-06-11.json`:

```json
{
  "kind": "bank",
  "part_group": "p23",
  "theme": "technology",
  "topic_title": "Describe a piece of technology you find useful",
  "source_url": "https://example.com/speaking-bank",
  "questions": [
    {
      "part": "p2",
      "question_text": "Describe a piece of technology you find useful.",
      "cue_points": [
        "What it is",
        "When you started using it",
        "How often you use it",
        "And explain why you find it useful"
      ],
      "model_answer": "The gadget I'd like to talk about is my e-reader, which has honestly been [[an absolute game-changer]] for me.\n\nI picked it up about three years ago, and these days I [[reach for it almost instinctively]] whenever I have a spare moment — on the metro, in queues, you name it. ...",
      "word_count": 252
    },
    {
      "part": "p3",
      "question_text": "Do you think people rely on technology too much?",
      "model_answer": "To a large extent, yes. There's clearly [[an over-reliance on]] smartphones in particular — most of us would feel genuinely lost without them. For instance, hardly anyone can navigate an unfamiliar city without GPS anymore, which suggests we've [[outsourced basic skills to our devices]]."
    }
  ],
  "sources": [
    {"url": "https://example.com/speaking-bank", "kind": "question_bank",
     "query": "ielts speaking part 2 technology 2026", "title": "Speaking bank"}
  ]
}
```

A Part 1 bank is the same shape with `"part_group": "p1"`, a topic name as
`topic_title` (e.g. `"Hometown"`), 4–6 question objects all `"part": "p1"`,
and no `cue_points`.

Rules: prose is plain text, paragraphs split by `\n\n`; `[[...]]` marks 2–4
high-value expressions per answer (rendered as yellow `\hi{}` highlights); never
write raw LaTeX in any field; no `[[...]]` inside `cue_points`.

## 2. Attempt JSON (Flow B)

`ielts-speaking/pending/attempt-q2-2026-06-11.json`:

```json
{
  "kind": "attempt",
  "question_id": 2,
  "transcript": "Well, er, I think people is rely on technology too much because, you know, everyone use phone all the time. They very convenient so we use them more and more.",
  "score_fc": 5.5,
  "score_lr": 5.0,
  "score_gra": 5.0,
  "overall": 5.0,
  "advice": "开头先直接表态（Yes, definitely / To a large extent）再展开理由，避免 well/er 起手。\n\n例子要具体：与其说 everyone use phone，不如举一个真实场景（导航、支付）。",
  "upgrades": [
    {"said": "very convenient", "better": "saves me an enormous amount of hassle", "note": "具体化 + 地道搭配"},
    {"said": "use phone all the time", "better": "are glued to their screens", "note": "形象的习语表达"}
  ],
  "grammar_fixes": [
    {"error": "people is rely on", "fix": "people rely on", "note": "主谓一致；rely 是实义动词，前面不加 is"},
    {"error": "everyone use phone", "fix": "everyone uses their phones", "note": "everyone 接单数动词"}
  ]
}
```

Rules: `transcript` is the user's words verbatim (no `[[...]]`, no edits);
`overall` must equal the mean of the three scores rounded to the nearest 0.5
(the ingest script recomputes and overrides it); `better` is plain text — the
renderer wraps it in `\hi{}` itself.

## 3. Rendered snippets

Question bank (Part 2 & 3 section):

```latex
\subsection{科技 Technology — Describe a piece of technology you find useful}

\begin{cuecardbox}
\noindent{\large\bfseries\textcolor{headerblue}{Q1}}\enspace{\small\bfseries\textcolor{cuecardborder}{[Part 2]}}\par\vspace{3pt}
\noindent\textbf{Describe a piece of technology you find useful.}\par\vspace{2pt}
You should say:
\begin{itemize}\setlength\itemsep{1pt}
\item What it is
...
\end{itemize}
\end{cuecardbox}
\answermeta{252}
The gadget I'd like to talk about is my e-reader, which has honestly been \hi{an absolute game-changer} for me.
...
\speakingq{2}{3}{Do you think people rely on technology too much?}
\answermeta{43}
To a large extent, yes. There's clearly \hi{an over-reliance on} smartphones ...
```

Practice log:

```latex
\begin{attemptbox}
\noindent{\large\bfseries\textcolor{headerblue}{Q2}}\enspace{\small\bfseries\textcolor{attemptborder}{[Part 3]}}\hfill{\small\textcolor{metacolor}{2026-06-11}}\par\vspace{2pt}
\noindent{\itshape Do you think people rely on technology too much?}\par\vspace{4pt}
\noindent\textbf{你的回答（转写）：}\par\vspace{2pt}
Well, er, I think people is rely on technology too much ...
\scoreline{5.5}{5.0}{5.0}{5.0}
\noindent\textbf{表达升级}\par
\begin{itemize}\setlength\itemsep{1pt}
\item “very convenient” → \hi{saves me an enormous amount of hassle} \textcolor{gray}{——具体化 + 地道搭配}
\end{itemize}
...
\end{attemptbox}
```
