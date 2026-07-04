#!/usr/bin/env python3
"""Codex notify wrapper: forward the notification to the original computer-use
client unchanged, then log per-subagent usage (model + tokens + duration) for
any subagent rollouts updated since the last run.

Mirrors Claude's SubagentStop hook (~/.claude/hooks/subagent-usage.py); log
format matches so both feed one mental model:
  ◇ <nickname> (<role>) — <model> · out X · in c/u Y/Z · reasoning R · NmNNs

Wiring (config.toml): notify = ["python3", "/Users/dev/.codex/hooks/notify-wrapper.py"]
Codex appends the notification JSON as the final argv. Fail-safe: forwarding
runs first and errors here never propagate (exit 0 always).
"""
import datetime
import json
import pathlib
import subprocess
import sys

HOME = pathlib.Path.home()
CLIENT = (HOME / ".codex/computer-use/Codex Computer Use.app/Contents/SharedSupport"
          "/SkyComputerUseClient.app/Contents/MacOS/SkyComputerUseClient")
CLIENT_ARG = "turn-ended"
SESSIONS = HOME / ".codex/sessions"
LOG = HOME / ".codex/log/subagent-usage.log"
STATE = HOME / ".codex/log/.subagent-usage-state.json"
LOOKBACK_DAYS = 2


def fmt(n) -> str:
    n = int(n or 0)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


def forward(payload: str) -> None:
    if CLIENT.exists():
        try:
            subprocess.run([str(CLIENT), CLIENT_ARG, payload], timeout=20,
                           capture_output=True)
        except Exception:
            pass


def summarize(rollout: pathlib.Path):
    """Return (key, line, total_tokens) for a subagent rollout, or None."""
    meta = model = None
    tok = {}
    first_ts = last_ts = None
    try:
        with open(rollout) as f:
            for raw in f:
                try:
                    rec = json.loads(raw)
                except Exception:
                    continue
                ts = rec.get("timestamp")
                if ts:
                    first_ts = first_ts or ts
                    last_ts = ts
                p = rec.get("payload") or {}
                if rec.get("type") == "session_meta":
                    if p.get("thread_source") != "subagent":
                        return None  # main-session rollout — not ours
                    meta = p
                elif rec.get("type") == "turn_context" and p.get("model"):
                    model = p["model"]
                elif rec.get("type") == "event_msg" and p.get("type") == "token_count":
                    tok = (p.get("info") or {}).get("total_token_usage") or tok
    except Exception:
        return None
    if not meta:
        return None
    nick = meta.get("agent_nickname") or "subagent"
    spawn = ((meta.get("source") or {}).get("subagent") or {}).get("thread_spawn") or {}
    role = spawn.get("agent_role") or ""
    dur = ""
    try:
        t0 = datetime.datetime.fromisoformat(first_ts.replace("Z", "+00:00"))
        t1 = datetime.datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
        s = int((t1 - t0).total_seconds())
        dur = f" · {s // 60}m{s % 60:02d}s"
    except Exception:
        pass
    total = int(tok.get("total_tokens") or 0)
    line = (f"◇ {nick}{f' ({role})' if role and role != nick else ''} — "
            f"{model or '?'} · out {fmt(tok.get('output_tokens'))} · "
            f"in c/u {fmt(tok.get('cached_input_tokens'))}/"
            f"{fmt(int(tok.get('input_tokens') or 0) - int(tok.get('cached_input_tokens') or 0))} · "
            f"reasoning {fmt(tok.get('reasoning_output_tokens'))}{dur}")
    return meta.get("id") or rollout.stem, line, total


def log_subagents() -> None:
    try:
        state = json.loads(STATE.read_text())
    except Exception:
        state = {}
    cutoff = datetime.date.today() - datetime.timedelta(days=LOOKBACK_DAYS)
    lines = []
    for day in range(LOOKBACK_DAYS + 1):
        d = cutoff + datetime.timedelta(days=day)
        for rollout in sorted(SESSIONS.glob(f"{d:%Y/%m/%d}/rollout-*.jsonl")):
            res = summarize(rollout)
            if not res:
                continue
            key, line, total = res
            if state.get(key) == total:
                continue  # already logged at this token count
            state[key] = total
            lines.append(f"{datetime.datetime.now():%F %T} {line}")
    if lines:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG, "a") as f:
            f.write("\n".join(lines) + "\n")
        if len(state) > 500:
            state = dict(list(state.items())[-250:])
        STATE.write_text(json.dumps(state))


if __name__ == "__main__":
    payload = sys.argv[1] if len(sys.argv) > 1 else "{}"
    forward(payload)
    try:
        log_subagents()
    except Exception:
        pass
    sys.exit(0)
