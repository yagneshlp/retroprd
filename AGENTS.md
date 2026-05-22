# AGENTS.md — RetroPRD Repo

This is the builder OS file for the retroprd skill repo itself.

---

## Project context

RetroPRD is an agent skill that generates retroactive PRDs and documentation for builders
who started coding before they started documenting. It reads git history, agent session
transcripts (Claude Code, Codex CLI), and code, then produces structured PRDs, ADRs, and
builder OS scaffold files.

- **Stage:** v1.1 — shipped
- **Tech:** Python (transcript reader), Markdown (skill), MIT license
- **Author:** Yagnesh L P
- **Current focus:** Community feedback, additional agent adapter support

---

## Folder map

| Folder / File | What it is |
|---|---|
| `skills/retroprd/SKILL.md` | The skill itself — agent instructions |
| `skills/retroprd/references/` | Reference docs loaded on demand by the skill |
| `skills/retroprd/scripts/read_transcripts.py` | Transcript reader — supports Claude Code, Codex, generic JSONL |
| `README.md` | Public-facing docs + install instructions |
| `package.json` | npm metadata for `npx skills add` compatibility |

---

## Key conventions

- The skill lives at `skills/retroprd/` — this is the canonical path `npx skills add` reads from
- All reference files are loaded on demand, not bundled into SKILL.md
- The transcript reader is standalone Python — no npm dependencies
- PRD confidence markers (High / Medium / Low) are mandatory on all generated PRDs

---

## Contributing

To add a new agent adapter:
1. Add an entry to `AGENT_ADAPTERS` in `scripts/read_transcripts.py`
2. Write a `find_<agent>_sessions()` function
3. Write a `parse_<agent>_jsonl()` function
4. Register in `PARSERS`
5. Document in `references/agent-adapters.md`

---

## Working conventions

PRDs are not required for this repo given its nature — it's a skill, not a product codebase.
Update the README and SKILL.md when behaviour changes. Bump the version in package.json on
any meaningful change to the skill instructions.

**Commit hygiene (enforced by the skill):** Before writing any documentation files the skill
checks for uncommitted changes and asks the user to commit first if any exist. At the end of
every run the skill checks when the repo was last committed and always reminds the user to
`git commit` and `git push` if the last commit was more than 24 hours ago or if new files
from the run are still uncommitted.
