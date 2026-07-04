#!/usr/bin/env python3
"""subagentStatusLine: render each row in the background-agents panel as
"<description> (<model>, <tokens> tok)".

stdin: JSON with a `tasks` array (id, description/label/name, tokenCount, ...).
stdout: one JSON line per task: {"id": ..., "content": ...}. Empty output keeps
default rendering. Model isn't in the payload, so it's read once from the
agent's transcript (first assistant record) and memoized on disk.

Debug: touch ~/.claude/hooks/.sl-debug to append raw stdin to subagent-statusline.log
"""
import json
import pathlib
import sys

HOME = pathlib.Path.home()
CACHE = HOME / ".claude/hooks/.agent-model-cache.json"
DEBUG_FLAG = HOME / ".claude/hooks/.sl-debug"
LOG = HOME / ".claude/hooks/subagent-statusline.log"


def fmt(n) -> str:
    try:
        n = int(n)
    except Exception:
        return "?"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


def model_for(agent_id: str, cache: dict):  # -> str or None (py3.9-safe)
    if agent_id in cache:
        return cache[agent_id]
    for tp in HOME.glob(f".claude/projects/*/*/subagents/agent-{agent_id}*.jsonl"):
        try:
            with open(tp) as f:
                for line in f:
                    rec = json.loads(line)
                    m = (rec.get("message") or {}).get("model")
                    if rec.get("type") == "assistant" and m:
                        import re
                        short = re.sub(r"^claude-|-\d{8}$", "", m)
                        cache[agent_id] = short
                        return short
        except Exception:
            continue
    return None  # not flushed yet; retry on next refresh


def main() -> int:
    raw = sys.stdin.read()
    if DEBUG_FLAG.exists():
        try:
            with open(LOG, "a") as f:
                f.write(raw[:2000] + "\n---\n")
        except Exception:
            pass
    try:
        payload = json.loads(raw)
    except Exception:
        return 0
    tasks = payload.get("tasks") if isinstance(payload, dict) else None
    if tasks is None:
        tasks = [payload] if isinstance(payload, dict) and payload.get("id") else []

    try:
        cache = json.loads(CACHE.read_text())
    except Exception:
        cache = {}
    dirty = False

    for t in tasks:
        if not isinstance(t, dict):
            continue
        tid = t.get("id")
        desc = t.get("description") or t.get("label") or t.get("name") or ""
        tok = t.get("tokenCount")
        if isinstance(tok, dict):
            tok = tok.get("output") or tok.get("total") or sum(
                v for v in tok.values() if isinstance(v, (int, float)))
        before = len(cache)
        model = model_for(str(t.get("agentId") or tid or ""), cache)
        dirty = dirty or len(cache) != before
        bits = [b for b in (model, f"{fmt(tok)} tok" if tok is not None else None) if b]
        if tid is None or not bits:
            continue  # keep default rendering
        print(json.dumps({"id": tid, "content": f"{desc} ({', '.join(bits)})"}))

    if dirty:
        try:
            if len(cache) > 300:
                cache = dict(list(cache.items())[-150:])
            CACHE.write_text(json.dumps(cache))
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
