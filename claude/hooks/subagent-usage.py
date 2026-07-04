#!/usr/bin/env python3
"""SubagentStop hook: print each finished subagent's model, token usage, tool
calls, and duration into the session as a systemMessage (user-visible only).

stdin: hook JSON with transcript_path pointing at the SUBAGENT's own transcript
(<proj>/<session-id>/subagents/agent-<id>.jsonl, .meta.json sibling has the
description). Fail-safe: any error exits 0 with no output — never blocks.
"""
import datetime
import json
import pathlib
import re
import sys
import time


def fmt(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


def main() -> int:
    payload = json.load(sys.stdin)
    # agent_transcript_path = the SUBAGENT's transcript. (transcript_path is the
    # MAIN session's — using it reports the whole session, verified 2026-07-04.)
    tp = pathlib.Path(payload.get("agent_transcript_path", ""))
    if not tp.exists():
        # fallback: locate by agent_id under the session's subagents dir
        aid = payload.get("agent_id", "")
        hits = list(pathlib.Path.home().glob(
            f".claude/projects/*/*/subagents/agent-{aid}*.jsonl")) if aid else []
        if not hits:
            return 0
        tp = hits[0]

    label = payload.get("agent_type", "agent")
    meta = tp.with_suffix("").with_suffix(".meta.json") if tp.suffix == ".jsonl" else None
    meta = tp.parent / (tp.stem + ".meta.json")
    if meta.exists():
        try:
            d = json.loads(meta.read_text()).get("description")
            if d:
                label = f"{payload.get('agent_type', 'agent')}: {d}"
        except Exception:
            pass

    # The hook can fire before the transcript's assistant records are flushed —
    # poll briefly until usage data appears (verified race 2026-07-04).
    models, ts = set(), []
    out = cc = cr = tools = 0
    for attempt in range(15):
        models, ts = set(), []
        out = cc = cr = tools = 0
        for line in tp.read_text().splitlines():
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if rec.get("timestamp"):
                ts.append(rec["timestamp"])
            msg = rec.get("message") or {}
            if rec.get("type") != "assistant":
                continue
            if msg.get("model"):
                models.add(msg["model"])
            u = msg.get("usage") or {}
            out += u.get("output_tokens", 0)
            cc += u.get("cache_creation_input_tokens", 0)
            cr += u.get("cache_read_input_tokens", 0)
            tools += sum(1 for b in (msg.get("content") or [])
                         if isinstance(b, dict) and b.get("type") == "tool_use")
        if models:
            break
        time.sleep(0.2)

    # claude-haiku-4-5-20251001 -> haiku-4-5; claude-fable-5 -> fable-5
    short = [re.sub(r"^claude-|-\d{8}$", "", m) for m in sorted(models)] or ["?"]
    dur = ""
    if len(ts) >= 2:
        try:
            t0 = datetime.datetime.fromisoformat(ts[0].replace("Z", "+00:00"))
            t1 = datetime.datetime.fromisoformat(ts[-1].replace("Z", "+00:00"))
            s = int((t1 - t0).total_seconds())
            dur = f" · {s // 60}m{s % 60:02d}s"
        except Exception:
            pass

    line = (f"◇ {label} — {'+'.join(short)} · out {fmt(out)} · "
            f"cache r/w {fmt(cr)}/{fmt(cc)} · {tools} tools{dur}")
    try:  # debug/audit trail; also proves firing without watching the UI
        with open(pathlib.Path.home() / ".claude/hooks/subagent-usage.log", "a") as f:
            f.write(f"{datetime.datetime.now():%F %T} {line}\n")
    except Exception:
        pass
    print(json.dumps({"systemMessage": line}))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
