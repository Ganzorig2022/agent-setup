#!/usr/bin/env python3
"""Harvest today's AI session text from Claude Code, Codex, and OpenCode.

Prints labelled, length-capped plain text to stdout — raw material for the
daily-decisions summarizer. Selection is by file mtime (last ~26h), which is
robust across the three tools' differing on-disk formats.
"""
from __future__ import annotations
import glob
import json
import sys
import time
from pathlib import Path

HOME = Path.home()
SINCE = time.time() - 48 * 3600     # last 48h — safety net for missed/late runs
CAP_TOTAL = 200_000                 # max chars fed downstream (~50k tokens)
CAP_PER_MSG = 1500                  # truncate any single message

_buf: list[str] = []
_total = 0


def emit(s: str) -> None:
    global _total
    if _total >= CAP_TOTAL or not s:
        return
    s = s[: CAP_TOTAL - _total]
    _buf.append(s)
    _total += len(s)


def recent(pattern: str) -> list[Path]:
    out = []
    for p in glob.glob(pattern, recursive=True):
        fp = Path(p)
        try:
            if fp.is_file() and fp.stat().st_mtime >= SINCE:
                out.append(fp)
        except OSError:
            pass
    return sorted(out, key=lambda f: f.stat().st_mtime)


def messages(obj) -> list[tuple[str, str]]:
    """Pull (role, text) pairs from a parsed message-ish JSON object."""
    if not isinstance(obj, dict):
        return []
    msg = obj.get("message") if isinstance(obj.get("message"), dict) else obj
    role = msg.get("role") or obj.get("role") or obj.get("type", "")
    out: list[tuple[str, str]] = []
    content = msg.get("content")
    if isinstance(content, str):
        out.append((role, content))
    elif isinstance(content, list):
        for b in content:
            if isinstance(b, dict) and b.get("type") == "text" and b.get("text"):
                out.append((role, b["text"]))
    parts = msg.get("parts")              # OpenCode shape
    if isinstance(parts, list):
        for b in parts:
            if isinstance(b, dict) and b.get("type") == "text" and b.get("text"):
                out.append((role, b["text"]))
    return out


def add_line(role: str, text: str, fallback: str = "msg") -> None:
    text = (text or "").strip()
    if text:
        emit(f"[{role or fallback}] {text[:CAP_PER_MSG]}\n")


# --- Claude Code: ~/.claude/projects/**/*.jsonl ---
emit("\n===== CLAUDE CODE =====\n")
for f in recent(str(HOME / ".claude/projects/**/*.jsonl")):
    for line in f.open(errors="ignore"):
        try:
            o = json.loads(line)
        except Exception:
            continue
        for role, t in messages(o):
            if role in ("user", "assistant"):
                add_line(role, t)

# --- Codex: ~/.codex/sessions/**/*.jsonl + history.jsonl ---
emit("\n===== CODEX =====\n")
codex_files = recent(str(HOME / ".codex/sessions/**/*.jsonl"))
hist = HOME / ".codex/history.jsonl"
try:
    if hist.is_file() and hist.stat().st_mtime >= SINCE:
        codex_files.append(hist)
except OSError:
    pass
for f in codex_files:
    for line in f.open(errors="ignore"):
        try:
            o = json.loads(line)
        except Exception:
            continue
        got = messages(o)
        if got:
            for role, t in got:
                add_line(role, t, "codex")
        else:
            t = o.get("text") or o.get("command") or ""
            if isinstance(t, str):
                add_line("codex", t)

# --- OpenCode: ~/.local/share/opencode/storage/message/**/*.json ---
emit("\n===== OPENCODE =====\n")
for f in recent(str(HOME / ".local/share/opencode/storage/message/**/*.json")):
    try:
        o = json.loads(f.read_text(errors="ignore"))
    except Exception:
        continue
    for role, t in messages(o):
        add_line(role, t)

sys.stdout.write("".join(_buf))
