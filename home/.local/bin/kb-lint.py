#!/usr/bin/env python3
"""Weekly knowledge-base lint: audits agent memory for rot so stale facts get
caught by a scheduled job instead of a failing script.

Two layers:
  MECHANICAL (pure python, deterministic)
    - referenced paths in STATE.md / CLAUDE.md that no longer exist
    - qpay-context <-> Codex rules drift (STATE.md says byte-identical is the contract)
    - "verified YYYY-MM" style claims older than STALE_DAYS
  SEMANTIC (one headless `claude -p` call over the always-loaded memory set)
    - facts that contradict each other (cites both)
    - facts likely stale (world moved, versions bumped, sessions expire)
    - entries that are session-journal noise rather than standing facts

READ-ONLY BY DESIGN: reports only; fixing is a human / `/retro` decision.
Report -> ~/kb-lint/<date>.md (+ macOS notification + optional Telegram).
Throttle: skips if the last report is <5 days old (RunAtLoad catch-up safe).
"""
from __future__ import annotations
import datetime
import glob as globmod
import json
import os
import pathlib
import re
import subprocess
import sys
import urllib.request

HOME = pathlib.Path.home()
CLAUDE = HOME / ".local/bin/claude"
OUT_DIR = HOME / "kb-lint"          # NOT ~/Desktop — TCC blocks launchd there (see x-deepdive, 2026-07-02)
LOG = HOME / "Library/Logs/kb-lint.log"
STALE_DAYS = 45
CALL_TIMEOUT = 600

# The always-loaded memory set — what every session (and subagent) reads.
MEMORY_FILES = [
    HOME / ".claude/agent-memory/STATE.md",
    HOME / ".claude/CLAUDE.md",
    HOME / ".claude/qpay-context/backend.md",
    HOME / ".claude/qpay-context/frontend.md",
    HOME / ".claude/qpay-context/design.md",
]
# Byte-identical mirror contract (Claude file is source of truth).
DRIFT_PAIRS = [
    (HOME / ".claude/qpay-context/backend.md", HOME / ".codex/rules/qpay/backend.md"),
    (HOME / ".claude/qpay-context/frontend.md", HOME / ".codex/rules/qpay/frontend.md"),
]

PROMPT = """You are a knowledge-base linter. Below are the memory/context files that load
into EVERY agent session for this user, plus mechanical findings already computed.

Report ONLY genuine problems, grouped exactly like this:

## Contradictions
Facts that cannot both be true. Quote both lines (with file names). If none: "none found".

## Likely stale
Facts that were probably true when written but plausibly aren't now: expired sessions,
"verified <date>" claims, version numbers, tool behaviors that change over time, counts
that drift. For each: the line, why it's suspect, and how to re-verify in one step.
Do NOT flag stable facts (paths, conventions, architecture decisions) just for being old.

## Journal noise
Entries that are one-off session details rather than durable reusable facts (the files'
own stated bar). Quote them. If none: "none found".

Be conservative: a short list of real issues beats a long list of maybes. No preamble,
no advice sections, nothing outside the three headings."""


def log(msg: str) -> None:
    with open(LOG, "a") as f:
        f.write(f"{datetime.datetime.now():%F %T} {msg}\n")


# ---------- mechanical checks ----------

PATH_RE = re.compile(r"(?:/Users/dev|~)/[A-Za-z0-9._/\-]+")


def check_paths() -> list[str]:
    """Paths referenced in memory files that don't exist on disk anymore."""
    missing = []
    seen = set()
    for f in MEMORY_FILES:
        if not f.exists():
            missing.append(f"- memory file itself is MISSING: `{f}`")
            continue
        for m in PATH_RE.findall(f.read_text()):
            p = m.rstrip(".,;:)`'\"")
            if p in seen:
                continue
            seen.add(p)
            expanded = os.path.expanduser(p)
            hits = globmod.glob(expanded) if "*" in expanded else (
                [expanded] if os.path.lexists(expanded) else [])
            if not hits:
                missing.append(f"- `{p}` (referenced in {f.name}) does not exist")
    return missing


def check_drift() -> list[str]:
    out = []
    for src, mirror in DRIFT_PAIRS:
        if not mirror.exists():
            out.append(f"- mirror MISSING: `{mirror}` (source: {src.name})")
        elif src.exists() and src.read_bytes() != mirror.read_bytes():
            out.append(f"- DRIFT: `{src}` != `{mirror}` — re-cp the Claude file over the Codex copy")
    return out


def check_dated_claims() -> list[str]:
    """'verified 2026-06' style stamps older than STALE_DAYS need re-verification."""
    out = []
    today = datetime.date.today()
    for f in MEMORY_FILES:
        if not f.exists():
            continue
        for line in f.read_text().splitlines():
            for m in re.finditer(r"(?:verified|as of|since)\s+(20\d\d)-(\d\d)", line, re.I):
                y, mo = int(m.group(1)), int(m.group(2))
                age = (today - datetime.date(y, mo, 1)).days
                if age > STALE_DAYS:
                    out.append(f"- {f.name}: dated claim ({m.group(0)}, ~{age}d old): "
                               f"“{line.strip()[:120]}”")
    return out


# ---------- semantic pass ----------

def semantic_pass(mech_report: str) -> str:
    material = mech_report + "\n\n"
    for f in MEMORY_FILES:
        if f.exists():
            material += f"\n===== FILE: {f} =====\n{f.read_text()}\n"
    try:
        res = subprocess.run([str(CLAUDE), "-p", PROMPT], input=material,
                             capture_output=True, text=True, timeout=CALL_TIMEOUT)
        if res.returncode != 0:
            log(f"claude pass failed rc={res.returncode}: {res.stderr[:200]}")
            return "_semantic pass failed — see log_"
        return res.stdout.strip()
    except Exception as e:
        log(f"claude pass error: {e}")
        return f"_semantic pass error: {e}_"


# ---------- delivery (tech-brief conventions) ----------

def deliver(date: str, report: str) -> pathlib.Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    note = OUT_DIR / f"{date}.md"
    note.write_text(report)
    try:
        subprocess.run(["osascript", "-e",
                        f'display notification "KB lint report ready" '
                        f'with title "KB Lint {date}"'], capture_output=True, timeout=10)
    except Exception:
        pass
    env = HOME / ".hermes/.env"
    tok = chat = None
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("TELEGRAM_BOT_TOKEN="):
                tok = line.split("=", 1)[1].strip()
            elif line.startswith("TELEGRAM_CHAT_ID="):
                chat = line.split("=", 1)[1].strip()
    if tok and chat:
        text = f"🧹 KB Lint — {date}\n\n{report}"
        try:
            for i in range(0, min(len(text), 12000), 4000):
                payload = {"chat_id": chat, "text": text[i:i + 4000],
                           "disable_web_page_preview": True}
                r = urllib.request.Request(
                    f"https://api.telegram.org/bot{tok}/sendMessage",
                    data=json.dumps(payload).encode(),
                    headers={"Content-Type": "application/json"})
                urllib.request.urlopen(r, timeout=15)
            log("sent to Telegram")
        except Exception as e:
            log(f"telegram failed: {e}")
    return note


def main() -> int:
    date = datetime.date.today().isoformat()
    log(f"=== run {date} ===")

    # Throttle: weekly job + RunAtLoad catch-up must not re-lint every login.
    if "--force" not in sys.argv:
        prior = sorted(OUT_DIR.glob("*.md"))
        if prior:
            newest = datetime.date.fromisoformat(prior[-1].stem)
            if (datetime.date.today() - newest).days < 5:
                log(f"last report {newest} is <5 days old; skipping (use --force)")
                return 0

    sections = []
    paths = check_paths()
    drift = check_drift()
    dated = check_dated_claims()
    sections.append("## Mechanical checks\n")
    sections.append("### Dead path references\n" + ("\n".join(paths) or "- none") + "\n")
    sections.append("### Claude↔Codex mirror drift\n" + ("\n".join(drift) or "- none (byte-identical)") + "\n")
    sections.append(f"### Dated claims older than {STALE_DAYS}d\n" + ("\n".join(dated) or "- none") + "\n")
    mech = "\n".join(sections)
    log(f"mechanical: {len(paths)} dead paths, {len(drift)} drift, {len(dated)} dated")

    if "--no-llm" in sys.argv:
        semantic = "_skipped (--no-llm)_"
    else:
        log("semantic pass...")
        semantic = semantic_pass(mech)

    report = (f"# KB Lint — {date}\n\n_Read-only audit of always-loaded agent memory. "
              f"Fix via `/retro` or direct edit; nothing was changed automatically._\n\n"
              f"{mech}\n## Semantic pass\n\n{semantic}\n")
    note = deliver(date, report)
    log(f"delivered -> {note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
