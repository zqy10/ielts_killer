# IELTS Agent — Long-Term Vision & Engineering Guide

## The Goal

Transform the current vocab pipeline into a **closed-loop learning agent**: a
system that knows what you've learned, knows where your gaps are, decides what
to do each session based on your state, and gets smarter about you over time.

The current project does one thing well: mining vocabulary from sources. The
agent does that *plus* reviews, writing practice, cross-skill feedback, and
progress tracking — all connected, all informed by your history.

---

## What a Mature Agent Looks Like

A pipeline runs the same steps every time regardless of who you are or where
you are. An agent has three properties a pipeline doesn't:

**1. State awareness** — it knows your current situation before acting.
Before doing anything, the agent reads: how many words are due for review
today, when you last wrote an essay, which words you've struggled with, how
your vocabulary range is trending.

**2. Decision-making** — it proposes a plan based on that state, not a fixed
sequence. Some days it leads with review. Some days it mines new vocab. Some
days it makes you write. It adapts to what you actually need.

**3. Feedback loops** — every action updates state, which influences the next
action. Words you blank on in review come back sooner. Words you avoid in
writing get flagged. Sources that yielded high-quality vocab get preferred.

---

## The Learning Loop (Full Vision)

```
┌─────────────────────────────────────────────────────┐
│                    SESSION START                     │
│         Agent reads state → proposes a plan          │
└────────────────────┬────────────────────────────────┘
                     │
        ┌────────────┼─────────────┐
        ▼            ▼             ▼
   [REVIEW]      [MINE]        [WRITE]
   Due words     New source    Task 1/2
   Flashcard     LLM selects   Essay draft
   quiz          high-level    using mined
   → confidence  words →       words →
     recorded    ingested      vocab usage
                               recorded
        └────────────┼─────────────┘
                     ▼
            State updated in DB
            (review dates, usage,
             confidence scores)
                     │
                     ▼
              Next session
           agent knows more
```

---

## Engineering: The Three Layers

Building this agent is really about building three things on top of what you
already have: a richer **state layer** (extended DB), a set of **skill
modules** (what the agent can do), and an **orchestrator** (what decides what
to do and when).

---

### Layer 1 — State (Extended SQLite Schema)

Your current `vocab.db` tracks words. You need to extend it to track *your
relationship* with those words over time.

**New tables to add:**

```sql
-- Spaced repetition state for each word
CREATE TABLE reviews (
    word_id     INTEGER REFERENCES words(id),
    reviewed_at TEXT,           -- ISO date
    confidence  INTEGER,        -- 0=blank, 1=struggled, 2=got it
    interval    INTEGER DEFAULT 1,   -- days until next review
    ease        REAL    DEFAULT 2.5, -- SM-2 ease factor
    next_review TEXT            -- ISO date
);

-- Which DB words appeared in each essay
CREATE TABLE writing_vocab_usage (
    essay_id    INTEGER,        -- from writing.db
    word_id     INTEGER REFERENCES words(id),
    used        INTEGER,        -- 1 = appeared in essay
    natural     INTEGER         -- 1 = used naturally, 0 = forced/awkward
);

-- One row per study session
CREATE TABLE sessions (
    date            TEXT,
    words_reviewed  INTEGER DEFAULT 0,
    words_mined     INTEGER DEFAULT 0,
    writing_done    INTEGER DEFAULT 0,  -- 1 = yes
    notes           TEXT
);
```

This schema is all you need for the review loop, the writing feedback loop,
and progress tracking. It extends your existing DB — no new database.

**The spaced repetition algorithm (SM-2, simplified):**

When you review a word and rate your confidence:
- `0` (blank): reset interval to 1 day, lower ease factor slightly
- `1` (struggled): reset interval to 1 day, ease unchanged
- `2` (got it): `new_interval = old_interval × ease`, ease nudged up

`next_review = today + new_interval`

This means a word you know well will come back in weeks; a word you keep
blanking on returns every day. Simple, effective, proven.

---

### Layer 2 — Skills (What the Agent Can Do)

Think of skills as the agent's hands — discrete actions it can take. You
already have two skills (`ielts-vocab-miner`, `ielts-writing`). You need
three more:

**Skill: `ielts-review`**
Surfaces words due today from the DB, runs a flashcard loop (word →
you attempt → you self-rate confidence), writes results back to the
`reviews` table, updates `next_review` dates.

Implementation: a Python script `review_session.py` that queries
`WHERE next_review <= today`, presents each word, reads a confidence
rating (0/1/2), and runs the SM-2 update. The LLM's role is presenting
the word naturally and evaluating your spoken/typed answer.

**Skill: `ielts-writing` (extend existing)**
Already exists but needs one addition: after generating an essay, scan
it against the vocab DB and record which DB words appear. Write those
matches to `writing_vocab_usage`. This closes the loop between mining
and writing.

Implementation: after essay generation, run a simple string-match
(or spaCy lemma-match) between essay text and all words in `vocab.db`,
write results to `writing_vocab_usage`.

**Skill: `ielts-session` (new — the orchestrator)**
This is the most important new skill. It runs at the start of every
session, reads your state, and proposes a plan. It answers: what should
you do today?

```python
# Pseudocode for the orchestrator's decision logic
due_reviews = count(reviews WHERE next_review <= today)
days_since_writing = days_since(last session WHERE writing_done = 1)
total_words = count(words)
weak_words = count(reviews WHERE confidence = 0 AND reviewed_at > 7_days_ago)

if due_reviews > 20:
    suggest("review first — {due_reviews} words overdue")
elif days_since_writing > 3:
    suggest("you haven't written in {days_since_writing} days — time for an essay")
elif weak_words > 5:
    suggest("you have {weak_words} persistently weak words — focused drill?")
else:
    suggest("mine new vocab — you're on track")
```

The orchestrator doesn't make decisions for you, it makes *informed
suggestions* based on your actual state.

---

### Layer 3 — Orchestrator (How It All Connects)

The orchestrator is `ielts-session`. Here's what a full session flow looks
like at the code level:

```
User: "Ready to study"

ielts-session:
  1. read_state()          → {due: 23, last_write: 4 days ago, weak: 3}
  2. propose_plan()        → "23 reviews due, then mine + write?"
  3. user confirms

  4. call ielts-review     → runs 23 flashcards, writes confidence to DB
  5. call ielts-vocab-miner → mines new source, ingests words
  6. call ielts-writing    → generates Task 2, user writes, feedback given
  7. record writing_vocab_usage → which mined words appeared in essay?
  8. update sessions table → session complete

  9. report_summary()      → "Reviewed 23, mined 18 new, wrote 1 essay.
                              You struggled with: exacerbate, inimical.
                              You used 6 mined words naturally in your essay."
```

Everything feeds back into state. The next session starts smarter.

---

## How to Build It (Phased Plan)

Don't try to build everything at once. Each phase is independently useful.

### Phase 1 — Add the review loop (highest value, 1–2 days)
1. Add `reviews` and `sessions` tables to `vocab.db`
2. Write `review_session.py` with SM-2 logic
3. Write `SKILL.md` for `ielts-review`
4. Test: run a review session, verify DB updates correctly

**Result**: you can now do spaced repetition on your existing 340 words.
This alone turns the project from a notebook into a learning tool.

### Phase 2 — Writing feedback loop (1 day)
1. After each essay in `ielts-writing`, run vocab match against `vocab.db`
2. Write matches to `writing_vocab_usage`
3. Surface unused words as "practice targets" in the post-essay report

**Result**: every writing session tells you which mined words you're
actually using and which you're avoiding.

### Phase 3 — Session orchestrator (1–2 days)
1. Write `session_state.py` — queries all tables, returns a state summary
2. Write `SKILL.md` for `ielts-session`
3. Wire it to call the other skills in sequence based on state

**Result**: you have a full agent. One command starts a session and the
agent decides what you need.

### Phase 4 — LLM-direct mining (improves quality + speed)
1. Rewrite the curation step in `ielts-vocab-miner` to skip spaCy scoring
2. Pass cleaned text directly to the LLM with a collocation-aware prompt
3. Keep fetch scripts for text extraction

**Result**: better word/phrase selection, faster runs, fewer missed collocations.

---

## Key Insight for Agent Engineering

The hardest part of building an agent is not the LLM — it's the **state**.
Most "agent" projects fail because they have no persistent state between
sessions, so every conversation starts from zero.

Your project already has the right instinct: SQLite as the authoritative
store, not the conversation history. That's the correct foundation. The
rest is extending that store to capture *your relationship with the material*,
not just the material itself.

Once state is rich enough, the orchestrator writes itself — it's just a
function that reads state and maps it to actions. The LLM handles the
nuanced parts (evaluating your answer quality, generating natural flashcard
prompts, giving writing feedback). The code handles the mechanical parts
(SM-2 math, DB writes, due-date queries).

**State + Skills + Orchestrator = Agent.**
