#!/usr/bin/env python3
"""
RetroPRD — Agent Transcript Reader
===================================
Reads coding agent session transcripts (Claude Code, Codex, or generic JSONL)
from their local storage locations and outputs the full conversation for PRD
generation — no filtering, no truncation, no pre-categorization.

Usage:
    python read_transcripts.py --agent claude-code --project-path /path/to/repo
    python read_transcripts.py --agent codex --project-path /path/to/repo
    python read_transcripts.py --transcript /path/to/session.jsonl
    python read_transcripts.py --agent claude-code --project-path . --json

Outputs:
    - Human-readable conversation dump (default)
    - Full JSON for downstream use (--json flag)
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path


# ─── Agent adapter registry ────────────────────────────────────────────────────

AGENT_ADAPTERS = {
    "claude-code": {
        "label": "Claude Code",
        "history_root": lambda: Path.home() / ".claude" / "projects",
        "locate": "encoded-path",
        "format": "jsonl-cc",
    },
    "codex": {
        "label": "OpenAI Codex CLI",
        "history_root": lambda: Path.home() / ".codex" / "sessions",
        "locate": "date-tree",
        "format": "jsonl-codex",
    },
    "generic": {
        "label": "Generic JSONL",
        "history_root": None,
        "locate": "explicit",
        "format": "jsonl-generic",
    },
}


# ─── Session locators ──────────────────────────────────────────────────────────

def find_claude_code_sessions(project_path: Path) -> list[Path]:
    history_root = Path.home() / ".claude" / "projects"
    if not history_root.exists():
        print(f"[warn] Claude Code history directory not found: {history_root}", file=sys.stderr)
        return []

    abs_path = str(project_path.resolve())
    encoded = abs_path.replace("/", "-").replace("\\", "-")
    project_dir = history_root / encoded

    sessions = []
    sessions_dir = project_dir / "sessions"
    if sessions_dir.exists():
        sessions = sorted(sessions_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
    elif project_dir.exists():
        sessions = sorted(project_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)

    if not sessions:
        candidates = list(history_root.iterdir())
        partial = [c for c in candidates if encoded[-20:] in c.name or c.name[-20:] in encoded]
        if partial:
            print(f"[info] Exact match not found. Nearest candidates:", file=sys.stderr)
            for c in partial[:5]:
                print(f"       {c}", file=sys.stderr)

    return sessions


def find_codex_sessions(project_path: Path) -> list[Path]:
    history_root = Path.home() / ".codex" / "sessions"
    if not history_root.exists():
        print(f"[warn] Codex history directory not found: {history_root}", file=sys.stderr)
        return []

    all_sessions = sorted(history_root.rglob("*.jsonl"), key=lambda p: p.stat().st_mtime)
    project_str = str(project_path.resolve())

    relevant = []
    for sf in all_sessions:
        try:
            first_lines = sf.read_text(errors="ignore")[:2000]
            if project_str in first_lines or project_path.name in first_lines:
                relevant.append(sf)
        except Exception:
            pass

    if not relevant:
        print(f"[info] No Codex sessions referencing {project_path.name}. Returning last 20.", file=sys.stderr)
        return all_sessions[-20:]

    return relevant


# ─── Content cleaning ──────────────────────────────────────────────────────────

_IDE_TAG_RE = re.compile(r"<ide_[^>]+>.*?</ide_[^>]+>\s*", re.DOTALL)
_SYSTEM_TAG_RE = re.compile(
    r"<[a-z_-]+-(?:reminder|hook|context)[^>]*>.*?</[a-z_-]+-(?:reminder|hook|context)[^>]*>\s*",
    re.DOTALL
)

def _clean_user_text(text: str) -> str:
    """Strip harness-injected IDE/system tags — not builder content."""
    text = _IDE_TAG_RE.sub("", text)
    text = _SYSTEM_TAG_RE.sub("", text)
    return text.strip()


# ─── JSONL parsers ─────────────────────────────────────────────────────────────

def parse_claude_code_jsonl(path: Path) -> list[dict]:
    """
    Parse a Claude Code JSONL session file.

    Output per message:
      role        — "user" or "assistant"
      text        — full text content, cleaned of harness tags
      tools       — list of tool calls made (assistant only):
                    {name, input} — full input, no truncation
      timestamp   — ISO string from the session file
      session_id  — stem of the source file
    """
    messages = []
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    msg = entry.get("message") if isinstance(entry.get("message"), dict) else entry
                    role = msg.get("role")
                    if role not in ("user", "assistant"):
                        continue

                    content = msg.get("content", "")
                    text_parts = []
                    tools = []

                    if isinstance(content, list):
                        for block in content:
                            if not isinstance(block, dict):
                                continue
                            btype = block.get("type")
                            if btype == "text":
                                text_parts.append(block.get("text", ""))
                            elif btype == "tool_use":
                                tools.append({
                                    "name": block.get("name", "unknown"),
                                    "input": block.get("input", {}),
                                })
                            # tool_result blocks are harness responses (file contents,
                            # bash output) — not builder intent, skip them
                        text = "\n".join(text_parts)
                    else:
                        text = str(content)

                    if role == "user":
                        text = _clean_user_text(text)

                    # Skip entries that are empty after cleaning
                    if not text and not tools:
                        continue

                    messages.append({
                        "role": role,
                        "text": text.strip(),
                        "tools": tools,
                        "timestamp": entry.get("timestamp", ""),
                        "session_id": path.stem,
                    })

                except json.JSONDecodeError:
                    continue
    except Exception as e:
        print(f"[warn] Could not read {path}: {e}", file=sys.stderr)

    return messages


def parse_codex_jsonl(path: Path) -> list[dict]:
    messages = []
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    role = entry.get("role") or entry.get("type")
                    content = (
                        entry.get("content")
                        or entry.get("text")
                        or entry.get("message", {}).get("content", "")
                    )
                    if isinstance(content, list):
                        content = " ".join(
                            b.get("text", "") for b in content
                            if isinstance(b, dict) and b.get("type") == "text"
                        )
                    if role and content:
                        messages.append({
                            "role": role,
                            "text": str(content).strip(),
                            "tools": [],
                            "timestamp": entry.get("timestamp") or entry.get("created_at", ""),
                            "session_id": path.stem,
                        })
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        print(f"[warn] Could not read {path}: {e}", file=sys.stderr)

    return messages


def parse_generic_jsonl(path: Path) -> list[dict]:
    messages = []
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    role = (entry.get("role") or entry.get("speaker")
                            or entry.get("type") or "unknown")
                    content = (entry.get("content") or entry.get("text")
                               or entry.get("message") or entry.get("body") or "")
                    if isinstance(content, dict):
                        content = json.dumps(content)
                    if content:
                        messages.append({
                            "role": str(role),
                            "text": str(content).strip(),
                            "tools": [],
                            "timestamp": "",
                            "session_id": path.stem,
                        })
                except (json.JSONDecodeError, TypeError):
                    continue
    except Exception as e:
        print(f"[warn] Could not read {path}: {e}", file=sys.stderr)

    return messages


PARSERS = {
    "jsonl-cc": parse_claude_code_jsonl,
    "jsonl-codex": parse_codex_jsonl,
    "jsonl-generic": parse_generic_jsonl,
}


# ─── Session grouping ──────────────────────────────────────────────────────────

def group_by_session(messages: list[dict]) -> list[dict]:
    """Group messages into sessions, preserving order."""
    sessions: dict[str, dict] = {}
    for msg in messages:
        sid = msg["session_id"]
        if sid not in sessions:
            sessions[sid] = {
                "session_id": sid,
                "started": msg.get("timestamp", ""),
                "messages": [],
            }
        sessions[sid]["messages"].append({
            "role": msg["role"],
            "text": msg["text"],
            "tools": msg.get("tools", []),
            "timestamp": msg.get("timestamp", ""),
        })

    result = list(sessions.values())
    # Sort sessions by their first timestamp
    result.sort(key=lambda s: s["started"])
    return result


# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="RetroPRD Transcript Reader")
    parser.add_argument("--agent", choices=list(AGENT_ADAPTERS.keys()),
                        default="claude-code", help="Which coding agent to read history from")
    parser.add_argument("--project-path", type=Path, default=Path("."),
                        help="Path to the project repo (used to locate sessions)")
    parser.add_argument("--transcript", type=Path,
                        help="Explicit path to a single JSONL transcript file")
    parser.add_argument("--json", action="store_true",
                        help="Output full session data as JSON")
    parser.add_argument("--max-sessions", type=int, default=50,
                        help="Maximum number of session files to read (default: 50)")
    args = parser.parse_args()

    # ── Locate session files ──
    if args.transcript:
        session_files = [args.transcript]
        fmt = "jsonl-generic"
    elif args.agent == "claude-code":
        session_files = find_claude_code_sessions(args.project_path)
        fmt = "jsonl-cc"
    elif args.agent == "codex":
        session_files = find_codex_sessions(args.project_path)
        fmt = "jsonl-codex"
    else:
        session_files = []
        fmt = "jsonl-generic"

    if not session_files:
        print("[error] No session files found. Check --project-path or use --transcript.")
        sys.exit(1)

    session_files = session_files[-args.max_sessions:]
    print(f"[info] Reading {len(session_files)} session file(s) "
          f"(agent: {AGENT_ADAPTERS[args.agent]['label']})", file=sys.stderr)

    # ── Parse ──
    parse_fn = PARSERS.get(fmt, parse_generic_jsonl)
    all_messages = []
    for sf in session_files:
        msgs = parse_fn(sf)
        all_messages.extend(msgs)
        print(f"       {sf.name}: {len(msgs)} messages", file=sys.stderr)

    print(f"[info] Total messages: {len(all_messages)}", file=sys.stderr)

    sessions = group_by_session(all_messages)

    # ── JSON output ──
    if args.json:
        output = {
            "project": str(args.project_path.resolve()),
            "agent": args.agent,
            "total_sessions": len(sessions),
            "total_messages": len(all_messages),
            "sessions": sessions,
        }
        print(json.dumps(output, indent=2))
        return

    # ── Human-readable output ──
    print(f"\n=== RetroPRD Transcript Dump ===")
    print(f"Project : {args.project_path.resolve()}")
    print(f"Sessions: {len(sessions)}  |  Messages: {len(all_messages)}\n")

    for session in sessions:
        print(f"{'─'*70}")
        print(f"SESSION {session['session_id'][:8]}  started: {session['started'][:19]}")
        print()
        for msg in session["messages"]:
            role_label = "USER     " if msg["role"] == "user" else "ASSISTANT"
            if msg["text"]:
                print(f"[{role_label}] {msg['text']}")
            for tool in msg.get("tools", []):
                tool_name = tool.get("name", "?")
                tool_input = tool.get("input", {})
                # Highlight the most useful fields per tool type
                if tool_name == "Write":
                    print(f"  → Write {tool_input.get('file_path', '')}")
                elif tool_name in ("Edit", "MultiEdit"):
                    print(f"  → Edit  {tool_input.get('file_path', '')}")
                elif tool_name == "Bash":
                    print(f"  → Bash  {str(tool_input.get('command', ''))[:120]}")
                elif tool_name == "Read":
                    print(f"  → Read  {tool_input.get('file_path', '')}")
                else:
                    print(f"  → {tool_name} {json.dumps(tool_input)[:120]}")
            print()

    print(f"{'─'*70}")


if __name__ == "__main__":
    main()
