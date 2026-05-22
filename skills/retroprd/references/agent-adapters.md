# Agent Adapter Reference

RetroPRD supports multiple coding agents through an adapter system. Each adapter defines
how to locate transcripts for a specific agent and how to parse their format.

This file documents the adapter protocol and the known agents, so you can:
1. Know what to expect from each agent's history
2. Add support for new agents as they emerge
3. Understand gaps or format differences when transcripts don't parse cleanly

---

## Adapter protocol

Each adapter in `scripts/read_transcripts.py` has these fields:

| Field | Type | Description |
|---|---|---|
| `label` | str | Human-readable agent name |
| `history_root` | callable → Path | Returns the root directory for session storage |
| `locate` | str | How sessions are organized (`hash`, `date-tree`, `explicit`) |
| `format` | str | Parser key (`jsonl-cc`, `jsonl-codex`, `jsonl-generic`) |
| `session_glob` | str | Glob pattern relative to history_root to find sessions |
| `fallback_glob` | str or None | Alternative glob if primary fails |

To add a new agent, add an entry to `AGENT_ADAPTERS` and implement a parser function if
the format differs from existing ones. Then register the parser in `PARSERS`.

---

## Supported agents

### Claude Code (`--agent claude-code`)

**Vendor:** Anthropic
**Storage:** `~/.claude/projects/<encoded-project-path>/sessions/<uuid>.jsonl`
**Path encoding:** Absolute project path with `/` replaced by `-`, prefixed with `-`
  - Example: `/Users/yagnesh/myapp` → `-Users-yagnesh-myapp`
**Format:** JSONL, one JSON object per line
**Message shape:**
```json
{
  "role": "user" | "assistant",
  "content": "string" | [{"type": "text", "text": "..."}, {"type": "tool_use", ...}],
  "uuid": "...",
  "parentUuid": "...",
  "timestamp": "ISO8601"
}
```
**Tool calls:** Embedded as content blocks with `type: "tool_use"` and `type: "tool_result"`
**Session cleanup:** Old sessions are auto-deleted after some time. Archive with:
```bash
cp -r ~/.claude/projects/ ~/claude-history-backup/
```
**Finding sessions manually:**
```bash
# List all projects
ls ~/.claude/projects/

# List sessions for a project (sort by recency)
ls -lt ~/.claude/projects/-Users-you-myproject/sessions/ | head -10

# Read a session
cat ~/.claude/projects/-Users-you-myproject/sessions/<uuid>.jsonl | python3 -m json.tool | head -100
```

---

### OpenAI Codex CLI (`--agent codex`)

**Vendor:** OpenAI
**Storage:** `~/.codex/sessions/YYYY/MM/DD/rollout-<timestamp>-<uuid>.jsonl`
**Path encoding:** Date-tree — NOT scoped by project path. Sessions must be filtered
  by checking if the project path appears in the session content.
**Format:** JSONL
**Message shape:** Similar to Claude Code but with variations:
```json
{"role": "user", "content": "...", "timestamp": "..."}
{"role": "assistant", "content": [...], "timestamp": "..."}
```
**Memory system:** Codex writes consolidated memory to `~/.codex/memories/memory_summary.md`
  and `~/.codex/memories/MEMORY.md`. These are often more useful than raw transcripts for
  RetroPRD because they represent Codex's own distilled understanding of the project.
  **Always check these files first for Codex projects:**
```bash
cat ~/.codex/memories/memory_summary.md
cat ~/.codex/memories/MEMORY.md
```
**Tool calls:** Embedded as tool use blocks, similar to Claude Code
**Session management:** `codex --resume` / `codex -r` for interactive session picker

---

### Gemini CLI / Google Agents (coming soon)

**Vendor:** Google
**Status:** Not yet documented publicly at the level needed for a reliable adapter
**Known:** Google's Gemini CLI stores session data locally, likely in `~/.gemini/` or
  `~/.config/gemini/`, but the exact format is not confirmed in public docs as of May 2026.
**Fallback:** Use `--transcript /path/to/session.jsonl` with `--agent generic` and the
  generic parser will do best-effort extraction.

---

### Cursor / GitHub Copilot Chat

**Note:** These are IDE-embedded agents rather than CLI agents. Their conversation history
  is generally not stored in accessible JSONL files — it lives in the IDE's internal state.
**Workaround:** Export conversation transcripts manually from the IDE if the feature exists,
  then use `--transcript /path/to/export.json --agent generic`.

---

### Custom / Unknown agents (`--agent generic`)

Use this for any agent whose format isn't explicitly supported. The generic parser does
best-effort extraction by looking for common field names: `role`, `content`, `text`,
`message`, `speaker`, `body`.

If you regularly use an agent not listed here, add an adapter. The protocol is small:
1. Define the adapter dict entry in `AGENT_ADAPTERS`
2. Write a `find_<agent>_sessions(project_path)` function
3. Write a `parse_<agent>_jsonl(path)` function
4. Register in `PARSERS`

---

## AGENTS.md compatibility

Codex CLI also uses `AGENTS.md` files for persistent context — the same convention as
this builder OS. This means Codex projects may already have an `AGENTS.md` in the repo
root or in `~/.codex/AGENTS.md`. RetroPRD should read these as additional context sources
during Phase 0. The format is compatible since both Anthropic and OpenAI converged on the
same spec.

---

## Format comparison table

| Agent | Storage root | Scoped by project? | Format | Memory distillation? |
|---|---|---|---|---|
| Claude Code | `~/.claude/projects/` | Yes (path hash) | JSONL | No |
| Codex CLI | `~/.codex/sessions/` | No (date-tree) | JSONL | Yes (`memory_summary.md`) |
| Gemini CLI | `~/.gemini/` (unconfirmed) | Unknown | Unknown | Unknown |
| Cursor | IDE internal | N/A | Not accessible | No |

---

## Handling missing or corrupted sessions

Claude Code has a known issue where `sessions-index.json` can become corrupted, causing
sessions to disappear from the picker even though the JSONL files still exist. If sessions
are missing from `--resume` but you know they should be there:

```bash
# Check if the JSONL files actually exist
find ~/.claude -name "*.jsonl" -path "*/sessions/*" | wc -l

# Read the index file directly
cat ~/.claude/projects/<project-hash>/sessions-index.json | python3 -m json.tool
```

Codex auto-deletes old sessions. If important sessions are missing, they may be gone.
The memory files (`memory_summary.md`) are more durable and should be checked first.
