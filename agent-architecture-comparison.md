# Agent Architecture Comparison

## First, a Correction on Structure 3

You said Hermes is "like the first structure." It's actually closer to the
opposite. The word "skill" appears in both, but they mean different things:

- **Structure 1 skill**: a markdown prompt file that tells Claude how to behave
- **Hermes skill**: a Python function/module that the Hermes runtime executes

Structure 1 is LLM-native — prompts drive everything. Structure 3 is
framework-native — code drives everything, the LLM is just a configured
backend. The real spectrum is:

```
Structure 1          Structure 3          Structure 2
(LLM-native)    ←   (Framework-native)  →  (Code-native)
Prompts drive       Framework drives        Your code drives
everything          everything              everything
LLM is the app      LLM is a plugin         LLM is a tool call
```

---

## Structure 1 — Claude Skills (What You Have Now)

### How It Works

You open Claude.ai (Cowork). Claude reads the `SKILL.md` file, follows its
instructions, calls bash scripts when needed, and writes outputs. Claude is
both the interface and the orchestrator. You interact in natural language.

```
You (chat) → Claude reads SKILL.md → Claude calls scripts → Claude writes .tex
```

The "agent" is a reinforced Claude — Claude with extra instructions and tools.
There is no standalone process. If you close the app, nothing runs.

### Engineering

- Skills are markdown files (`SKILL.md`) — no code required to write a skill
- Scripts (`fetch_content.py`, `ingest_vocab.py`) are called by Claude via bash
- State lives in SQLite (`vocab.db`) — this part is solid
- Orchestration is implicit: Claude decides the order of steps based on the skill prompt

### Pros

- **Already works today** — no new setup, no API account, uses your Pro subscription
- **Natural language interface** — you talk to it like a person
- **Fast to iterate** — changing behavior means editing a markdown file, not code
- **No terminal required** — accessible to anyone
- **Zero API costs** — covered by Pro plan

### Cons

- **Claude-locked** — you cannot swap models; DeepSeek, GPT-4, etc. are not options
- **Not portable** — can't run on a schedule, can't run headlessly, can't run on a server
- **Unpredictable orchestration** — Claude decides what to do; it can misinterpret
  instructions, skip steps, or behave differently across sessions
- **No true autonomy** — requires you to open the app and start a conversation
- **Dependent on Anthropic's platform** — if the app changes or your account has issues,
  everything breaks

### Verdict for IELTS

Good for where you are now. Bad long-term. The moment you want scheduled reviews,
autonomous daily sessions, or model flexibility, this structure hits a wall.

---

## Structure 2 — Python CLI with API

### How It Works

A Python application lives on your machine. You run it from the terminal. When it
needs LLM intelligence, it makes an API call to whatever model you've configured,
gets a response, and continues. No app open. No conversation. Just a process.

```
You (terminal) → Python app reads DB state → decides action → calls LLM API
               → executes scripts → writes to DB → reports result
```

The LLM is a tool the app calls — not the app itself.

### Engineering

The app has three layers:

**1. CLI layer** — entry point, parses commands

```python
# ielts.py
import argparse
from session import run_session
from review import run_review
from miner import run_miner

parser = argparse.ArgumentParser()
subparsers = parser.add_subparsers(dest="command")
subparsers.add_parser("study")      # full session
subparsers.add_parser("review")     # flashcards only
subparsers.add_parser("mine")       # vocab mining only
subparsers.add_parser("stats")      # progress report
args = parser.parse_args()
```

**2. LLM layer** — one abstraction function, swappable backend

```python
# llm.py
from openai import OpenAI  # works for DeepSeek, Claude-compat, GPT-4

client = OpenAI(
    api_key=os.environ["LLM_API_KEY"],
    base_url=os.environ["LLM_BASE_URL"]  # e.g. https://api.deepseek.com
)

def ask_llm(prompt: str) -> str:
    response = client.chat.completions.create(
        model=os.environ["LLM_MODEL"],
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content
```

Swap model by changing two environment variables. No code changes.

**3. State layer** — reads/writes SQLite, SM-2 logic, session tracking

```python
# state.py
def get_due_reviews(db) -> list:
    return db.execute(
        "SELECT * FROM reviews WHERE next_review <= date('now')"
    ).fetchall()

def update_review(db, word_id, confidence):
    # SM-2 algorithm: update interval and ease factor
    ...
```

### Pros

- **Full control** — deterministic orchestration; the app does exactly what you coded
- **Model-agnostic** — change `LLM_BASE_URL` and `LLM_MODEL` in `.env` to switch models
- **Portable** — runs anywhere Python runs: your laptop, a server, a Raspberry Pi
- **Schedulable** — add a cron job: `0 8 * * * python /path/to/ielts.py review`
- **No UI dependency** — works headlessly, scriptable, composable with other tools
- **Cheap** — API costs for personal use are $2–5/month

### Cons

- **Requires API account** — Anthropic API or DeepSeek API, separate from Pro plan
- **Terminal only** — no natural language interface; you run commands, not conversations
- **You write everything** — orchestration, SM-2 math, DB schema, CLI commands, all from scratch
- **More upfront work** — probably 1–2 weeks to build a solid v1
- **Prompt maintenance** — as you switch models, prompts may need tuning

### Verdict for IELTS

The right long-term structure for this project. Your domain needs (SM-2, LaTeX,
IELTS-specific criteria, custom DB) fit naturally into code. You own everything.

---

## Structure 3 — Hermes (Framework-Native)

### How It Works

You deploy Hermes on your machine (clone repo, configure `.env` with your API key).
Hermes runs as a persistent process. You write skills as Python modules following
Hermes conventions. The Hermes runtime handles orchestration, memory, scheduling,
and the LLM backend. After each task, the Curator system extracts reusable patterns
and builds new skills automatically.

```
You (message/command) → Hermes runtime → selects skill → executes Python module
                     → calls LLM API → updates three-layer memory → Curator learns
```

### Engineering

A Hermes skill is a Python module with a standard interface:

```python
# skills/ielts_review.py
from hermes.skill import Skill, SkillContext

class IELTSReview(Skill):
    name = "ielts_review"
    description = "Run spaced repetition flashcards for due IELTS vocabulary"

    def run(self, ctx: SkillContext) -> str:
        due_words = ctx.memory.query("due_reviews_today")
        for word in due_words:
            response = ctx.llm.ask(f"Quiz the user on: {word}")
            confidence = ctx.input(response)
            ctx.memory.update(word, confidence=confidence)
        return f"Reviewed {len(due_words)} words"
```

Hermes handles: routing your request to the right skill, calling the LLM,
persisting memory across sessions, and the Curator creating new skills from patterns
it observes. You focus on domain logic; the framework handles the rest.

### Pros

- **Pre-built runtime** — scheduling, memory, LLM routing, messaging integrations
  all come out of the box
- **Self-improving** — the Curator system generates new skills from experience;
  the agent gets better over time without you writing new code
- **Model-agnostic** — configure any OpenAI-compatible API in `.env`
- **Persistent three-layer memory** — working memory, episodic memory, skill memory;
  no need to design your own state system
- **Always-on** — Hermes runs as a server; it can initiate sessions, not just respond
- **Active ecosystem** — 110k stars, active development, community skills to borrow from

### Cons

- **Framework opinions** — Hermes has a specific way of doing things; if your needs
  don't fit that shape, you fight the framework
- **Your specific needs need custom skills anyway** — SM-2 math, LaTeX generation,
  IELTS vocabulary criteria don't exist in Hermes' 118 bundled skills; you're writing
  custom code either way
- **Another dependency** — Hermes itself can break, update, or change its API; you're
  now maintaining your code AND tracking Hermes releases
- **Steeper learning curve** — you learn Hermes conventions on top of learning agent
  engineering
- **Still needs API** — same cost as Structure 2
- **Overkill for personal use** — Hermes is designed for multi-skill, always-on,
  multi-user agents; a personal IELTS study tool uses maybe 5% of its capabilities

### Verdict for IELTS

Hermes is genuinely impressive and the self-improving Curator is exactly the right
idea for a learning agent. But it's the right idea packaged for a more complex use
case than yours. The overhead of learning and maintaining Hermes is probably not
worth it when Structure 2 gives you the same architecture with less friction.

---

## Side-by-Side Summary

| | Structure 1 (Claude Skills) | Structure 2 (Python CLI) | Structure 3 (Hermes) |
|---|---|---|---|
| **Runs standalone** | No | Yes | Yes |
| **Model-agnostic** | No | Yes | Yes |
| **Schedulable** | No | Yes | Yes |
| **Persistent memory** | DB only | DB (you build) | Built-in (3-layer) |
| **Self-improving** | No | No | Yes (Curator) |
| **Engineering effort** | Low | Medium | Medium-High |
| **Control** | Low | High | Medium |
| **API required** | No (Pro) | Yes | Yes |
| **Learning curve** | None | Python/CLI | Python + Hermes |
| **Right for IELTS** | Now | Long-term | Overkill |

---

## Recommended Path

Start with Structure 2. Build the Python CLI with the DB extensions and SM-2
review loop described in `ielts-agent-vision.md`. It gives you full control,
model flexibility, and schedulable autonomous sessions — everything you actually
need. If the project eventually grows beyond personal use (multi-user, always-on,
autonomous skill generation), migrate the skills to Hermes at that point.

Structure 1 is not a dead end — it's where you are now and it works. Keep using
it while you build Structure 2. They share the same SQLite DB, so the transition
is gradual, not a rewrite.
