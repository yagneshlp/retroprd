#!/usr/bin/env python3
"""
RetroPRD — Agent Transcript Reader
===================================
Reads coding agent session transcripts (Claude Code, Codex, or generic JSONL)
from their local storage locations, extracts meaningful signal, and optionally
calls the Claude API to produce a structured synthesis for PRD generation.

Usage:
    python read_transcripts.py --agent claude-code --project-path /path/to/repo
    python read_transcripts.py --agent codex --project-path /path/to/repo
    python read_transcripts.py --transcript /path/to/session.jsonl
    python read_transcripts.py --agent claude-code --project-path . --synthesize

Outputs:
    - Raw extraction to stdout (default)
    - Structured synthesis via Claude API (--synthesize flag)
    - JSON format for downstream use (--json flag)
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# ─── Agent adapter registry ────────────────────────────────────────────────────
# Each adapter defines how to locate and parse transcripts for a specific agent.
# To add a new agent, implement the adapter protocol below and register it here.
# See references/agent-adapters.md for the full adapter spec.

AGENT_ADAPTERS = {
    "claude-code": {
        "label": "Claude Code",
        "history_root": lambda: Path.home() / ".claude" / "projects",
        "locate": "hash",           # project path → sha256 hash → directory
        "format": "jsonl-cc",       # Claude Code JSONL format
        "session_glob": "sessions/*.jsonl",
        "fallback_glob": "*.jsonl", # older Claude Code versions
    },
    "codex": {
        "label": "OpenAI Codex CLI",
        "history_root": lambda: Path.home() / ".codex" / "sessions",
        "locate": "date-tree",      # sessions/YYYY/MM/DD/rollout-*.jsonl
        "format": "jsonl-codex",
        "session_glob": "**/*.jsonl",
        "fallback_glob": None,
    },
    "generic": {
        "label": "Generic JSONL",
        "history_root": None,
        "locate": "explicit",       # requires --transcript flag
        "format": "jsonl-generic",
        "session_glob": "*.jsonl",
        "fallback_glob": None,
    },
}


# ─── Project path → transcript directory ───────────────────────────────────────

def encode_project_path_claude(project_path: Path) -> str:
    """Claude Code encodes the project path as a URL-like string with - separators."""
    # ~/.claude/projects/-Users-you-myproject/
    abs_path = str(project_path.resolve())
    return abs_path.replace("/", "-").replace("\\", "-")


def find_claude_code_sessions(project_path: Path) -> list[Path]:
    """Locate Claude Code session files for a given project path."""
    history_root = Path.home() / ".claude" / "projects"
    if not history_root.exists():
        print(f"[warn] Claude Code history directory not found: {history_root}", file=sys.stderr)
        return []

    encoded = encode_project_path_claude(project_path)
    project_dir = history_root / encoded

    sessions = []
    # Try new path (sessions/ subdirectory)
    sessions_dir = project_dir / "sessions"
    if sessions_dir.exists():
        sessions = sorted(sessions_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
    # Fallback: old path (files directly in project dir)
    elif project_dir.exists():
        sessions = sorted(project_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)

    if not sessions:
        # Fuzzy match: user might have renamed or moved the project
        candidates = list(history_root.iterdir())
        partial = [c for c in candidates if encoded[-20:] in c.name or c.name[-20:] in encoded]
        if partial:
            print(f"[info] Exact match not found. Nearest candidates:", file=sys.stderr)
            for c in partial[:5]:
                print(f"       {c}", file=sys.stderr)

    return sessions


def find_codex_sessions(project_path: Path) -> list[Path]:
    """Locate Codex CLI session files. Codex uses a date-tree structure."""
    history_root = Path.home() / ".codex" / "sessions"
    if not history_root.exists():
        print(f"[warn] Codex history directory not found: {history_root}", file=sys.stderr)
        return []

    # Codex doesn't scope by project path — filter by cwd in session content instead
    all_sessions = sorted(history_root.rglob("*.jsonl"), key=lambda p: p.stat().st_mtime)
    project_str = str(project_path.resolve())

    relevant = []
    for session_file in all_sessions:
        # Quick scan: check if this project path appears in the session
        try:
            first_lines = session_file.read_text(errors="ignore")[:2000]
            if project_str in first_lines or project_path.name in first_lines:
                relevant.append(session_file)
        except Exception:
            pass

    if not relevant:
        print(f"[info] No Codex sessions found referencing {project_path.name}. "
              f"Returning all recent sessions instead.", file=sys.stderr)
        return all_sessions[-20:]  # last 20 sessions as fallback

    return relevant


# ─── JSONL parsers per format ──────────────────────────────────────────────────

def parse_claude_code_jsonl(path: Path) -> list[dict]:
    """Parse Claude Code JSONL session file into a list of message dicts."""
    messages = []
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    # Claude Code format: {"role": ..., "content": ..., "uuid": ..., "parentUuid": ...}
                    role = entry.get("role")
                    content = entry.get("content", "")

                    # Content can be a string or a list of blocks
                    if isinstance(content, list):
                        text_parts = []
                        for block in content:
                            if isinstance(block, dict):
                                if block.get("type") == "text":
                                    text_parts.append(block.get("text", ""))
                                elif block.get("type") == "tool_use":
                                    tool_name = block.get("name", "unknown_tool")
                                    tool_input = json.dumps(block.get("input", {}))[:200]
                                    text_parts.append(f"[tool: {tool_name}] {tool_input}")
                                elif block.get("type") == "tool_result":
                                    result_content = block.get("content", "")
                                    if isinstance(result_content, list):
                                        result_content = " ".join(
                                            b.get("text", "") for b in result_content
                                            if isinstance(b, dict)
                                        )
                                    text_parts.append(f"[tool_result] {str(result_content)[:300]}")
                        content = "\n".join(text_parts)

                    if role and content:
                        messages.append({
                            "role": role,
                            "content": str(content).strip(),
                            "uuid": entry.get("uuid"),
                            "timestamp": entry.get("timestamp"),
                            "session_id": path.stem,
                        })
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        print(f"[warn] Could not read {path}: {e}", file=sys.stderr)

    return messages


def parse_codex_jsonl(path: Path) -> list[dict]:
    """Parse Codex CLI JSONL session file."""
    messages = []
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    # Codex format varies; try common shapes
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
                            "content": str(content).strip(),
                            "timestamp": entry.get("timestamp") or entry.get("created_at"),
                            "session_id": path.stem,
                        })
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        print(f"[warn] Could not read {path}: {e}", file=sys.stderr)

    return messages


def parse_generic_jsonl(path: Path) -> list[dict]:
    """Best-effort parser for unknown JSONL formats."""
    messages = []
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    # Try to extract role + content from any reasonable field
                    role = (entry.get("role") or entry.get("speaker")
                            or entry.get("type") or "unknown")
                    content = (entry.get("content") or entry.get("text")
                               or entry.get("message") or entry.get("body") or "")
                    if isinstance(content, dict):
                        content = json.dumps(content)
                    if content:
                        messages.append({
                            "role": str(role),
                            "content": str(content).strip()[:1000],
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


# ─── Signal extraction ─────────────────────────────────────────────────────────

def extract_signal(messages: list[dict]) -> dict:
    """
    Extract the signal most useful for PRD generation from raw messages.
    Returns a structured dict with key categories of information.
    """
    signal = {
        "decisions": [],        # explicit choices made ("I decided to...", "let's use...")
        "problems_fixed": [],   # bugs or issues that came up and were resolved
        "features_built": [],   # things that were created
        "rejected": [],         # approaches that were tried and abandoned
        "user_intent": [],      # the builder's own words about what they wanted
        "tool_actions": [],     # significant file writes, bash commands
        "raw_sample": [],       # first N user messages for context
    }

    decision_keywords = ["decided", "going with", "let's use", "i'll use", "chosen", "picked",
                         "instead of", "rather than", "switched to", "moved to", "chose"]
    problem_keywords = ["bug", "broken", "error", "issue", "fix", "doesn't work", "failing",
                        "wrong", "incorrect", "crash", "exception", "undefined", "null"]
    rejected_keywords = ["doesn't work", "failed", "reverted", "abandoned", "too complex",
                         "won't work", "tried but", "gave up", "scratch that", "never mind"]

    user_messages = [m for m in messages if m["role"] in ("user", "human")]
    assistant_messages = [m for m in messages if m["role"] in ("assistant", "model", "ai")]

    signal["raw_sample"] = [m["content"][:400] for m in user_messages[:5]]

    for msg in user_messages:
        content_lower = msg["content"].lower()
        if any(kw in content_lower for kw in decision_keywords):
            signal["decisions"].append(msg["content"][:500])
        if any(kw in content_lower for kw in problem_keywords):
            signal["problems_fixed"].append(msg["content"][:500])
        if any(kw in content_lower for kw in rejected_keywords):
            signal["rejected"].append(msg["content"][:500])
        # User intent: short imperative messages are usually feature requests
        words = msg["content"].split()
        if 5 < len(words) < 50:
            signal["user_intent"].append(msg["content"][:300])

    for msg in messages:
        if "[tool:" in msg["content"] and "write" in msg["content"].lower():
            signal["tool_actions"].append(msg["content"][:300])
        if "created" in msg["content"].lower() or "added" in msg["content"].lower():
            signal["features_built"].append(msg["content"][:400])

    # Deduplicate and cap lists
    for key in signal:
        if isinstance(signal[key], list):
            seen = set()
            deduped = []
            for item in signal[key]:
                if item not in seen:
                    seen.add(item)
                    deduped.append(item)
            signal[key] = deduped[:15]  # cap at 15 per category

    return signal


# ─── Claude API synthesis ──────────────────────────────────────────────────────

def synthesize_with_claude(signal: dict, project_path: Path) -> str:
    """
    Call Claude API to turn raw transcript signal into a structured
    product narrative suitable for PRD generation.
    
    Requires the ANTHROPIC_API_KEY environment variable.
    """
    try:
        import urllib.request
    except ImportError:
        return "[error] urllib not available — cannot call Claude API"

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return ("[error] ANTHROPIC_API_KEY not set. Export it or pass --no-synthesize "
                "to get raw extraction only.")

    prompt = f"""You are analyzing coding agent session transcripts for a product called "{project_path.name}".
Your job is to produce a structured product narrative that a PM could use to write retroactive PRDs.

Here is the extracted signal from the session transcripts:

DECISIONS MADE:
{json.dumps(signal['decisions'], indent=2)}

PROBLEMS FIXED:
{json.dumps(signal['problems_fixed'], indent=2)}

FEATURES BUILT (from agent messages):
{json.dumps(signal['features_built'][:10], indent=2)}

APPROACHES REJECTED:
{json.dumps(signal['rejected'], indent=2)}

BUILDER'S OWN WORDS (direct user messages):
{json.dumps(signal['user_intent'][:10], indent=2)}

Produce a structured output with these sections:
1. PRODUCT SUMMARY (2-3 sentences: what was built, who for, what problem it solves)
2. BUILD PHASES (3-5 phases inferred from the progression of work)
3. FEATURE INVENTORY (bullet list of discrete features that exist)
4. KEY DECISIONS (the architectural/product choices made, with inferred reasoning)
5. BUGS FIXED (what broke and how it was fixed)
6. DEFERRED ITEMS (things mentioned but not completed, or left as TODOs)
7. CONFIDENCE NOTES (where evidence is strong vs inferred)

Be specific. Name files, patterns, and technologies where you have evidence.
Flag inferences explicitly with "(inferred)".
Do not pad with generic language. If you don't have evidence for something, say so."""

    payload = json.dumps({
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 2000,
        "messages": [{"role": "user", "content": prompt}]
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
            return data["content"][0]["text"]
    except Exception as e:
        return f"[error] Claude API call failed: {e}"


# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="RetroPRD Transcript Reader")
    parser.add_argument("--agent", choices=list(AGENT_ADAPTERS.keys()),
                        default="claude-code", help="Which coding agent to read history from")
    parser.add_argument("--project-path", type=Path, default=Path("."),
                        help="Path to the project repo (used to locate sessions)")
    parser.add_argument("--transcript", type=Path,
                        help="Explicit path to a single JSONL transcript file")
    parser.add_argument("--synthesize", action="store_true",
                        help="Call Claude API to synthesize transcripts into a product narrative")
    parser.add_argument("--json", action="store_true",
                        help="Output raw signal as JSON instead of human-readable text")
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

    # ── Parse sessions ──
    parse_fn = PARSERS.get(fmt, parse_generic_jsonl)
    all_messages = []
    for sf in session_files:
        msgs = parse_fn(sf)
        all_messages.extend(msgs)
        print(f"       {sf.name}: {len(msgs)} messages", file=sys.stderr)

    print(f"[info] Total messages extracted: {len(all_messages)}", file=sys.stderr)

    # ── Extract signal ──
    signal = extract_signal(all_messages)

    if args.json:
        print(json.dumps(signal, indent=2))
        return

    # ── Human-readable output ──
    if not args.synthesize:
        print("\n=== RetroPRD Transcript Extraction ===\n")
        print(f"Project: {args.project_path.resolve()}")
        print(f"Sessions read: {len(session_files)}")
        print(f"Messages extracted: {len(all_messages)}\n")

        sections = [
            ("Builder's intent (direct messages)", "user_intent"),
            ("Decisions made", "decisions"),
            ("Problems fixed", "problems_fixed"),
            ("Features built", "features_built"),
            ("Approaches rejected", "rejected"),
        ]
        for label, key in sections:
            items = signal[key]
            if items:
                print(f"── {label} ({len(items)} items) ──")
                for item in items[:8]:
                    print(f"  • {item[:200]}")
                print()
        return

    # ── Claude API synthesis ──
    print("\n=== RetroPRD Claude Synthesis ===\n", file=sys.stderr)
    result = synthesize_with_claude(signal, args.project_path)
    print(result)


if __name__ == "__main__":
    main()
