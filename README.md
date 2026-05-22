# RetroPRD

[![skills.sh](https://skills.sh/b/yagneshlp/retroprd)](https://skills.sh/yagneshlp/retroprd)
[![License: MIT](https://img.shields.io/badge/license-MIT-a78bfa.svg)](LICENSE)

**Retroactive PRDs for builders who started coding before they started documenting.**

You were in flow. You shipped things. Now you want structure — context files, decision logs, a change trail that future-you (or a future AI agent) can actually read.

RetroPRD is an agent skill that reads your git history, Claude Code / Codex session transcripts, and codebase, then generates retroactive PRDs, ADRs, and builder OS scaffold files — all in one pass.

```bash
npx skills add yagneshlp/retroprd
```

Works with Claude Code, Cursor, Gemini CLI, Codex CLI, and any agent that supports the skills standard.

**[retroprd.ylp.pm](https://retroprd.ylp.pm)**

---

## What it does

RetroPRD runs a structured archaeological dig on your repo and produces:

| Output | Description |
|---|---|
| **PRDs** (`.prd/NNN-*.md`) | One per feature, bug fix, or infra change — in chronological order |
| **ADRs** (`.dev/decisions.md`) | Architectural decision records with context, alternatives, and consequences |
| **Session handoff** (`.context/session.md`) | Current product state for the next agent session |
| **Backlog** (`.context/backlog.md`) | Deferred items, known bugs, and ideas surfaced during the dig |
| **AGENTS.md fill-in** | Populates TODO sections with real product context |
| **PRD index** (`.prd/README.md`) | Master changelog of everything shipped |

All PRDs carry a **reconstruction confidence marker** (High / Medium / Low) so you know what's documented vs inferred.

---

## Installation

```bash
npx skills add yagneshlp/retroprd
```

This installs the skill into your project's `.claude/skills/` (or the equivalent for your agent). Reload your agent and type `/retroprd` to activate.

### Manual install (Claude Code)

```bash
# Project-local
cp -r skills/retroprd .claude/skills/

# Or global (all projects)
cp -r skills/retroprd ~/.claude/skills/
```

---

## Usage

Once installed, trigger it in your agent:

```
/retroprd                          # Full run — git dig + PRDs + all scaffold files
/retroprd --agent codex            # Use Codex CLI transcripts instead of Claude Code
/retroprd --prds-only              # Skip scaffold files, just generate PRDs
/retroprd --scaffold-only          # Just populate AGENTS.md and context files
```

Or just describe what you want in plain language:

```
Document what I've built so far
Generate retroactive PRDs from my git history
Catch up my builder OS files
I've been building without docs — help me add structure
```

---

## How it works

RetroPRD runs five phases:

**Phase 0 — Orient:** Reads existing scaffold files (AGENTS.md, README, `.prd/`) to understand conventions before touching anything.

**Phase 1 — Archaeological dig:** Three-layer evidence gathering:
- Git log, diffs, and file evolution
- Agent session transcripts (Claude Code at `~/.claude/projects/`, Codex at `~/.codex/sessions/`, or any JSONL file via `--transcript`)
- Code reading for intent (schema, routes, entry points)

The bundled `scripts/read_transcripts.py` handles transcript extraction across agents and optionally calls the Claude API to synthesize raw transcripts into a structured product narrative.

**Phase 2 — Classify:** Groups related commits into PRD-sized units (feature, bug, infra, CR) — not one PRD per commit.

**Phase 3 — Write PRDs:** Produces dated, typed PRDs with problem/change/files sections and a confidence marker.

**Phase 4 — Populate scaffold:** Fills in `session.md`, `backlog.md`, `decisions.md`, and AGENTS.md TODO sections.

**Phase 5 — Debrief:** Summarises what was reconstructed, what confidence level, and what needs builder verification.

---

## Supported agents

| Agent | Transcript location | Notes |
|---|---|---|
| Claude Code | `~/.claude/projects/<hash>/sessions/*.jsonl` | Full support |
| Codex CLI | `~/.codex/sessions/**/*.jsonl` | Also reads `~/.codex/memories/` |
| Any agent | `--transcript /path/to/file.jsonl` | Generic parser |

See `skills/retroprd/references/agent-adapters.md` for the full adapter spec and how to add new agents.

---

## Works with builder OS

RetroPRD is designed around the [AGENTS.md builder OS convention](https://github.com/buildwithai/builder-os) — the same convention used by Codex CLI, Claude Code, and most major coding agents. If your repo already has an AGENTS.md with TODO sections, RetroPRD fills them in.

---

## Requirements

- A git repo (even a single-commit one — code reading still works)
- Python 3.8+ (for the transcript reader script)
- `ANTHROPIC_API_KEY` in env if using `--synthesize` (already set inside Claude Code)

---

## License

MIT — [Yagnesh L P](https://github.com/yagneshlp)
