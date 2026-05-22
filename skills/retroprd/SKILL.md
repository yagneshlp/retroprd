---
name: retroprd
description: >
  Use this skill when the user wants to retroactively document a codebase they've already built:
  generate PRDs from git history or agent transcripts, populate builder OS scaffold files
  (AGENTS.md, session.md, backlog.md, decisions.md), or create an audit trail for an undocumented
  repo. Trigger on: "document what I built", "retroactive PRD", "retroprd", "catch up my docs",
  "write PRDs for existing features", "populate my builder OS", "I've been building without docs",
  or when a user shares an AGENTS.md with TODO sections to fill in. Also trigger when asked to read
  repo history and produce documentation artifacts, even without those exact words. Do NOT trigger
  for new feature planning, writing PRDs for things not yet built, or general code explanation.
compatibility: >
  Requires git (for history analysis) and Python 3.8+ (for the transcript reader script).
  The --synthesize flag additionally requires ANTHROPIC_API_KEY. Works in Claude Code,
  GitHub Copilot (Agent mode), and any agent that supports the Agent Skills format.
metadata:
  author: yagnesh-lp
  version: "1.1"
allowed-tools: Bash Read
---

# RetroPRD — Retroactive Documentation for Builders in Flow

You are helping a builder who started coding before they set up documentation. Your job is to
archaeology their codebase, reconstruct what was built and *why*, then produce structured PRDs
and scaffold files that make the repo legible to future agents and collaborators.

This is a two-part job: **understand** (read the history, infer intent) then **write** (produce
the docs). Never skip the understand phase. Bad archaeology produces worse documentation than none.

---

## Phase 0 — Orient before you act

Before generating anything, read these in order:

1. `AGENTS.md` — understand the builder OS conventions this repo uses
2. `README.md` — product context, tech stack, setup instructions
3. `.prd/README.md` (if it exists) — what's already been documented
4. `.context/session.md` (if it exists) — last known state
5. `.dev/README.md` or `docs/` (if it exists) — technical architecture

If these files don't exist yet, note what's missing. You'll create them as part of the output.

---

## Pre-flight — Commit checkpoint

Before writing any documentation files, run `git status --short` to check for uncommitted
changes.

**If there are uncommitted changes:**

Tell the user:
> "You have uncommitted changes in this repo. Would you like to commit them before I write
> documentation files? This gives you a clean checkpoint to revert to if anything goes wrong."

Wait for their response.
- If yes → help them stage and commit: `git add -A && git commit -m "WIP: pre-retroprd checkpoint"` (or a message they prefer), then proceed.
- If no → note it and proceed. Do not block on this.

**If the working tree is clean**, proceed to Phase 1 immediately with no mention of this check.

---

## Phase 1 — Archaeological Dig

### 1a. Git history analysis

Run these in sequence to build a complete picture of what was built:

```bash
# Timeline of all commits
git log --oneline --reverse

# All files ever touched, grouped by commit
git log --name-only --pretty=format:"COMMIT: %h | %ad | %s" --date=short --reverse

# Commits by feature area (infer from path patterns)
git log --oneline --reverse -- src/
git log --oneline --reverse -- components/ app/ pages/

# Understand what changed in major commits
git show --stat <commit-hash>

# Diff a specific commit fully
git show <commit-hash>

# See the full evolution of a critical file
git log --follow -p -- <filepath>

# Understand the branch story (if any)
git log --oneline --graph --all
```

### 1b. Agent transcript mining

Session transcripts are the gold mine of RetroPRD — they contain the builder's actual reasoning,
not just what was built. Use the bundled script to extract this signal.

**Run the transcript reader:**

```bash
# Claude Code — reads ~/.claude/projects/<project-hash>/sessions/*.jsonl
python3 scripts/read_transcripts.py --agent claude-code --project-path .

# OpenAI Codex CLI — reads ~/.codex/sessions/**/*.jsonl filtered by project
python3 scripts/read_transcripts.py --agent codex --project-path .

# Explicit transcript file (any agent, generic parser)
python3 scripts/read_transcripts.py --transcript /path/to/session.jsonl

# Call Claude API to synthesize into a structured product narrative (recommended)
python3 scripts/read_transcripts.py --agent claude-code --project-path . --synthesize
```

The `--synthesize` flag makes a Claude API call (reads `ANTHROPIC_API_KEY` from env).
Inside Claude Code this is already set. It produces a structured product narrative that
maps directly to PRD sections. For Codex projects, also check:

```bash
cat ~/.codex/memories/memory_summary.md  # Codex distilled memory — often more useful
```

The extractor flags these high-signal categories: decisions made, problems fixed, builder
intent (direct user messages), and approaches rejected. The rejected category is especially
valuable for ADR writing — it surfaces what was tried and why it didn't work.

For other agents or format details, see `references/agent-adapters.md`.

### 1c. Code reading for intent

Read the actual code to infer intent where history is thin:

```bash
# Understand the data model
find . -name "schema*" -o -name "models*" -o -name "types*" | head -20

# Read the main entry points
cat src/index.* app/page.* main.* 2>/dev/null | head -100

# Understand the API surface
find . -name "routes*" -o -name "api*" -path "*/api/*" | head -20

# Configuration and env shape
cat .env.example .env.local.example config.* 2>/dev/null
```

### 1d. Synthesis — build your mental model

Before writing a single PRD, construct a mental model with these components:

| Dimension | What to determine |
|---|---|
| **Product stages** | What are the 3-5 distinct phases of building? (e.g., "core CRUD → auth → payments → polish") |
| **Feature inventory** | What features exist right now, even if incomplete? |
| **Technical decisions** | What architectural choices were made? What was the alternative? |
| **Bugs fixed** | What broke and what was the fix? |
| **Deferred items** | What was started but not finished? What was mentioned but not built? |
| **Current state** | What is the state of the product *right now*? |

---

## Phase 2 — Classify the work into PRD units

Each PRD should represent a coherent unit of product intent. The right granularity is roughly:
"a PM would have written a ticket for this."

**Good PRD units:**
- Adding a new feature (auth, payments, a new page, a new API endpoint)
- A significant refactor that changed the architecture
- A bug fix that was non-trivial (not one-liner typos)
- An infrastructure change (adding a new service, changing the deployment model)
- A data model change

**Do not write PRDs for:**
- Trivial copy changes
- Minor style/UI tweaks
- Single-line bug fixes
- Chores (dependency bumps, linting)

Group related commits into a single PRD. A feature spread across 4 commits is one PRD, not four.

---

## Phase 3 — Write the PRDs

Use the PRD format defined in `AGENTS.md`. If the repo uses a different format, use that.
The default format is in `references/prd-template.md`.

### Numbering strategy

Start from `001` unless `.prd/` already has files, in which case continue the sequence.

### Ordering

Write PRDs in **chronological order of when the work was done**, not by importance. This preserves
the builder's journey and makes the change log legible.

### Writing each PRD

For each PRD, the goal is to reconstruct what a thoughtful PM would have written *before* the
work was done — but informed by what actually happened.

Key craft principles:

**Problem section** — Answer: why did this need to exist? What was broken or missing before?
If you can't find explicit evidence in transcripts, infer from context. Be honest: "Inferred from
code pattern — no explicit record found."

**Change section** — Be specific about what was built. Reference file names. Describe the key
logic decisions, not just "added X feature." If there were meaningful implementation choices,
name them.

**Root cause (for bugs)** — Explain the actual failure mode, not just "fixed bug." Include why
the fix is safe and doesn't introduce regressions.

**Avoid:**
- Vague language ("improved performance", "enhanced UX")
- Padding — if the PRD is short because the change was small, that's fine
- Speculating beyond what the evidence supports without flagging it

### PRD confidence markers

Add a metadata field to indicate your confidence in the reconstruction:

```
**Reconstruction confidence:** High | Medium | Low
**Evidence sources:** git commits | code reading | transcript | inferred
```

This is honest and helps the builder know where to verify.

---

## Phase 4 — Populate the scaffold files

After writing PRDs, populate the builder OS files. These are critical for future agent continuity.

### `.prd/README.md`

Create or update this as the master index. Format:

```markdown
# PRD Index

## Shipped

| # | Title | Type | Date | Status |
|---|---|---|---|---|
| PRD-001 | ... | feature | YYYY-MM-DD | Shipped |

## In Progress

## Roadmap / Backlog
```

### `.context/session.md`

Capture current state as of the retroprd run:

```markdown
# Session Handoff — [DATE]

## What was done this session
RetroPRD run: generated N PRDs covering [date range] of work.

## Current product state
[Describe the product as it stands right now]

## Open / unfinished
[List incomplete features, known issues, things mentioned but not built]

## Suggested next priorities
[Based on what you read, what should the builder tackle next?]
```

### `.context/backlog.md`

Populate from your archaeological dig. Every deferred item, mentioned-but-not-built feature, and
known bug goes here:

```markdown
# Backlog

| ID | Item | Type | Priority | Notes |
|---|---|---|---|---|
| B-001 | ... | bug/feature/improvement | P1/P2/P3 | ... |
```

### `.dev/decisions.md`

This is the ADR (Architectural Decision Record) log. Each entry:

```markdown
## ADR-NNN: [Title]

**Date:** [approximate, from git]
**Status:** Decided

**Context:** What situation forced this decision?
**Decision:** What was chosen?
**Alternatives considered:** What else could have been done?
**Consequences:** What does this enable or constrain going forward?
```

Write one ADR per meaningful architectural choice. Aim for 5-15. If you can't find evidence
for the reasoning, write what you can and flag it: "(reasoning inferred — verify with builder)"

### `.context/team.md` (if solo builder)

```markdown
# Team

**Builder:** [name if available]
**Working style:** Solo / async
**Conventions:** [anything specific to how this person builds]
```

### `AGENTS.md` — fill in the TODOs

The AGENTS.md file often has TODO sections. Fill them in:

- **Project context** — 3-5 sentence description of what the product is, who it's for, what problem it solves
- **Three build phases** — label the phases you identified in your dig
- **Stage / Tech / PM / Current focus** — fill in the suggested context elements
- **Key learnings** — populate with the gotchas from your dig (bugs fixed, patterns that broke, approaches that didn't work)
- **Folder map** — update with any folders that exist but weren't in the original map
- **Active backlog** — link to `.context/backlog.md` and list top 3 items

---

## Phase 5 — Deliver and debrief

After writing all files, give the builder a summary:

### Output summary format

```
## RetroPRD Complete

**Coverage:** [date range covered]
**PRDs generated:** N ([list titles briefly])
**Files created/updated:** [list]

**Confidence summary:**
- High confidence: [N PRDs] — strong commit + transcript evidence
- Medium confidence: [N PRDs] — good code evidence, some inference
- Low confidence: [N PRDs] — mostly inferred, builder should verify

**Things I couldn't reconstruct:** [honest list of gaps]

**Suggested builder actions:**
1. Review low-confidence PRDs and correct anything that's wrong
2. Check the backlog — did I miss anything?
3. Verify the ADRs — do the decisions I recorded match your memory?
4. [Any specific follow-up items]
```

### Git hygiene reminder

After the summary, always run these two checks:

```bash
git log -1 --format="Last commit: %ar (%h)"
git status --short
```

Then remind the user to commit and push if either condition is true:
- the last commit was more than 24 hours ago, **or**
- there are uncommitted files right now (including the docs just written)

Deliver the reminder like this:
> "Your last commit was [X] ago. Run `git add -A && git commit -m 'docs: retroprd run [DATE]'`
> followed by `git push` to back up your work and the new documentation."

If neither condition is true (last commit was recent AND working tree is clean after this run),
skip the reminder.

---

## Handling common situations

### "I don't have a git repo / it's all in one commit"

Fall back to code archaeology only. Read the actual files, infer the feature set from routes,
components, and data model. Be upfront that confidence will be lower. Still produce the PRDs
— imperfect documentation is better than none.

### "I have Claude Code transcripts"

This is the jackpot. Read them carefully — they contain the builder's actual thinking. Use
transcript evidence to write PRDs with much higher fidelity. Quote the builder's own words
where helpful.

### "I only want PRDs, not the scaffold files"

Respect this. Do Phase 1-3 and skip Phase 4. Offer to do the scaffold files afterward.

### "The repo already has some PRDs"

Read existing PRDs first. Don't duplicate. Fill the gaps. Update `.prd/README.md` to include both
old and new.

### "This is a big repo with hundreds of commits"

Bucket commits into feature areas first. Write PRDs by area, not by commit. For a very large
repo, offer to do one area at a time and get the builder's sign-off before proceeding.

### "I want to catch up my AGENTS.md specifically"

Go straight to Phase 4, focusing on AGENTS.md. Still do a quick Phase 1 so you have the context
to fill it in accurately.

---

## Quality bar

A good retroPRD run produces documentation that:

1. **A new engineer could read and understand** what the product is and how it got here
2. **A future AI agent could read** and pick up the work without asking basic questions
3. **The builder recognizes** as an accurate account of what they built and why
4. **Identifies gaps** the builder might not have noticed (deferred items, undocumented decisions)

If you're producing PRDs that are vague, padded, or speculative beyond what the evidence supports,
stop and re-read the git history more carefully.

---

## Gotchas

- **Script path is relative to the skill root, not the user's project.** When invoking
  `read_transcripts.py` from the user's project directory, pass the full path to the script:
  `python3 ~/.claude/skills/retroprd/scripts/read_transcripts.py --agent claude-code --project-path .`
  Inside Claude Code, use the skill-relative path shown in this file — the harness resolves it.

- **Claude Code transcript directories use `-` as path separator, not `/`.** The folder for
  `/Users/you/myapp` is `~/.claude/projects/-Users-you-myapp/`. The script handles this
  automatically — do not manually construct the hash path.

- **Codex transcripts are NOT project-scoped** — they use date-tree storage
  (`~/.codex/sessions/YYYY/MM/DD/`). The script filters by matching file path references inside
  sessions. Always pass `--project-path` when using `--agent codex` or results will be noisy.

- **Merge commits inflate the commit count without adding product signal.** Use
  `git log --no-merges --oneline --reverse` as the base command for Phase 1a. Only dive into
  merge commits if they contain a squashed feature that isn't visible elsewhere.

- **Read `.prd/` BEFORE generating any PRDs.** Run `ls .prd/*.md 2>/dev/null` first. If PRDs
  already exist, read every one of them to avoid duplication and continue the correct numbering
  sequence. Writing PRD-001 when PRD-003 already exists breaks the index.

- **`--synthesize` is almost always worth using** when transcripts exist. Inside Claude Code the
  `ANTHROPIC_API_KEY` is already set in the environment. The structured narrative it returns maps
  directly to PRD sections and dramatically reduces inference work — the extra API call pays for
  itself in output quality.

- **Single-commit or no-git repos still yield useful output.** Fall back to code archaeology
  (Phase 1c) and be explicit about lower confidence. Never skip output because evidence is thin —
  imperfect documentation is better than none.

---

## Reference files

- `references/prd-template.md` — Default PRD format with all required sections and anti-patterns
- `references/adr-examples.md` — Good ADR examples to calibrate writing depth and reasoning
- `references/agent-adapters.md` — Storage locations, JSONL formats, and extensibility spec for
  all supported coding agents (Claude Code, Codex CLI, and how to add new ones)
- `scripts/read_transcripts.py` — Transcript reader script; runs standalone or via `--synthesize`
  to call Claude API for structured synthesis

Read prd-template and adr-examples when calibrating output quality.
Read agent-adapters when the agent isn't Claude Code or when transcripts fail to parse.
