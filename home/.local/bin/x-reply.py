#!/usr/bin/env python3
"""Auto-post the tech-brief's drafted X replies via the logged-in headless Chrome
(same dedicated profile as x-harvest.py). Called by tech-brief.py after the
"Reply opportunities" drafts are generated; results flow back into the brief as
a "## Replies posted" confirmation section.

Input (stdin): JSON list of targets: [{"handle", "link", "reply", "reason"}]
Output (stdout): the same list with "status" ("posted"|"skipped"|"failed") and
"detail" added per target. Exit 0 always — posting is best-effort; failures are
reported in the brief for manual follow-up, never raised into it.

Safety rails:
  - kill switch: touch ~/Desktop/tech-brief/.no-auto-reply to disable posting
  - dedupe: never replies twice to the same tweet (.cache/replied.json)
  - caps: MAX_PER_RUN replies per run, 280-char guard, total wall-clock budget
  - spacing: 60-150s jittered pause between posts (no machine-gun pattern)
  - verify: reply text is confirmed in the composer before Send is clicked, and
    the composer must clear afterwards for the post to count as confirmed

Mechanics (verified 2026-07-02, see STATE.md lessons):
  - text via eval + execCommand('insertText') — exact; CDP `fill` eats the first
    char on X's Draft.js editor, so it is NOT used for text
  - Send via real CDP `click @uid` — snapshot refs go stale within seconds on
    X's live DOM, so every click re-snapshots and acts immediately, with retries
  - loose `type` keystrokes trigger X keyboard shortcuts — never type without
    a verified-focused composer
"""
from __future__ import annotations
import datetime
import glob
import json
import os
import pathlib
import random
import re
import subprocess
import sys
import time

HOME = pathlib.Path.home()
PROFILE = HOME / ".local/share/tech-brief-chrome"
OUT_DIR = HOME / "Desktop/tech-brief"
CACHE_DIR = OUT_DIR / ".cache"
REPLIED = CACHE_DIR / "replied.json"
KILL_SWITCH = OUT_DIR / ".no-auto-reply"
LOG = HOME / "Library/Logs/tech-brief.log"

MAX_PER_RUN = 4
MAX_CHARS = 280
TOTAL_BUDGET_S = 600
OPEN_TIMEOUT = 50
CMD_TIMEOUT = 30
SPACING_RANGE_S = (60, 150)

COMPOSER = '[data-testid="tweetTextarea_0"]'


def log(msg: str) -> None:
    try:
        with open(LOG, "a") as f:
            f.write(f"{datetime.datetime.now():%F %T} x-reply: {msg}\n")
    except Exception:
        pass


def _ver(path: str) -> tuple:
    m = re.search(r"/v(\d+)\.(\d+)\.(\d+)/", path)
    return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)


def find_npx() -> str:
    cands = []
    if os.environ.get("NPX_BIN"):
        cands.append(os.environ["NPX_BIN"])
    cands += sorted(glob.glob(str(HOME / ".nvm/versions/node/*/bin/npx")), key=_ver, reverse=True)
    cands += ["/opt/homebrew/bin/npx", "/usr/local/bin/npx"]
    for c in cands:
        if c and pathlib.Path(c).exists():
            return c
    return "npx"


NPX = find_npx()


def axi(args: list[str], timeout: int = CMD_TIMEOUT) -> str:
    env = dict(os.environ)
    env["CHROME_DEVTOOLS_AXI_USER_DATA_DIR"] = str(PROFILE)
    env.pop("CHROME_DEVTOOLS_AXI_HEADED", None)
    env["PATH"] = str(pathlib.Path(NPX).parent) + os.pathsep + env.get("PATH", "")
    res = subprocess.run([NPX, "-y", "chrome-devtools-axi", *args],
                         capture_output=True, text=True, timeout=timeout, env=env)
    return (res.stdout or "") + (res.stderr or "")


def eval_js(js: str) -> str | None:
    """Run JS in the page; return the decoded string result (or None)."""
    out = axi(["eval", js])
    i = out.find("result:")
    if i < 0:
        return None
    chunk = out[i + len("result:"):].strip().split("\nhelp[")[0].strip()
    for _ in range(3):  # result may be multiply JSON-encoded
        try:
            v = json.loads(chunk)
        except Exception:
            return chunk
        if isinstance(v, str):
            chunk = v
            continue
        return json.dumps(v)
    return chunk


def composer_text() -> str | None:
    """Current composer textContent, or None if no composer on the page."""
    r = eval_js(
        "(() => { const el = document.querySelector('" + COMPOSER + "');"
        " return el ? el.textContent : '__NO_COMPOSER__'; })()")
    if r is None or r == "__NO_COMPOSER__":
        return None
    return r


def set_composer_text(text: str) -> bool:
    """Focus the reply composer, clear any stale draft, insert exact text, verify."""
    payload = json.dumps(text)
    r = eval_js(
        "(() => { const el = document.querySelector('" + COMPOSER + "');"
        " if (!el) return '__NO_COMPOSER__';"
        " el.focus(); document.execCommand('selectAll'); document.execCommand('delete');"
        " document.execCommand('insertText', false, " + payload + ");"
        " return el.textContent; })()")
    return r == text


def clear_composer() -> None:
    eval_js(
        "(() => { const el = document.querySelector('" + COMPOSER + "');"
        " if (el) { el.focus(); document.execCommand('selectAll'); document.execCommand('delete'); }"
        " return true; })()")


def find_reply_button_uid() -> str | None:
    """Snapshot and return the uid of the ENABLED inline Reply button.
    Must be used immediately — X's live DOM invalidates refs within seconds."""
    snap = axi(["snapshot"], timeout=45)
    for line in snap.splitlines():
        # want: uid=gNN:M_K button "Reply"   (no 'disabled', not "N Replies. Reply")
        m = re.search(r'uid=(\S+) button "Reply"\s*$', line.strip())
        if m and "disabled" not in line:
            return m.group(1)
    return None


def click_send() -> bool:
    """Snapshot->click the enabled Reply button, retrying on stale refs."""
    for attempt in range(4):
        uid = find_reply_button_uid()
        if not uid:
            time.sleep(1.5)
            continue
        out = axi(["click", f"@{uid}"])
        if "STALE_REF" in out:
            log(f"send click stale (attempt {attempt + 1}); retrying")
            continue
        return True
    return False


def verify_posted(reply: str) -> bool:
    """After Send: the inline composer clears (or collapses) on success."""
    for _ in range(6):
        time.sleep(2)
        txt = composer_text()
        if txt is None or txt.strip() == "":
            return True
        if txt.strip() == reply.strip():
            continue  # still pending
    return False


def load_replied() -> dict:
    try:
        return json.loads(REPLIED.read_text())
    except Exception:
        return {}


def save_replied(d: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    REPLIED.write_text(json.dumps(d, ensure_ascii=False, indent=1))


def post_one(target: dict) -> tuple[str, str]:
    """Post one reply. Returns (status, detail)."""
    link, reply = target["link"], target["reply"].strip()
    axi(["open", link], timeout=OPEN_TIMEOUT)
    time.sleep(3)
    if composer_text() is None:
        return "failed", "no reply composer on page (logged out? tweet gone?)"
    if not set_composer_text(reply):
        # one retry — first attempt occasionally races the editor init
        time.sleep(2)
        if not set_composer_text(reply):
            clear_composer()
            return "failed", "could not set exact reply text in composer"
    if not click_send():
        clear_composer()
        return "failed", "Reply button not found/clickable"
    if not verify_posted(reply):
        return "failed", "sent click but composer did not clear — unconfirmed, check manually"
    return "posted", ""


def main() -> int:
    dry = "--dry-run" in sys.argv
    try:
        targets = json.loads(sys.stdin.read() or "[]")
    except Exception as e:
        log(f"bad input: {e}")
        print("[]")
        return 0
    if KILL_SWITCH.exists():
        log("kill switch present; skipping all")
        for t in targets:
            t["status"], t["detail"] = "skipped", "auto-reply disabled (.no-auto-reply)"
        print(json.dumps(targets, ensure_ascii=False))
        return 0

    replied = load_replied()
    start = time.time()
    posted_this_run = 0
    for t in targets:
        link, reply = (t.get("link") or "").strip(), (t.get("reply") or "").strip()
        t["status"], t["detail"] = "skipped", ""
        if not link.startswith("https://x.com/") or "/status/" not in link:
            t["detail"] = "no valid tweet link"
            continue
        if not reply or len(reply) > MAX_CHARS:
            t["detail"] = f"reply empty or over {MAX_CHARS} chars"
            continue
        if link in replied:
            t["detail"] = f"already replied on {replied[link].get('date', '?')}"
            continue
        if posted_this_run >= MAX_PER_RUN:
            t["detail"] = f"per-run cap ({MAX_PER_RUN}) reached"
            continue
        if time.time() - start > TOTAL_BUDGET_S:
            t["detail"] = "time budget exhausted"
            continue
        if dry:
            t["status"], t["detail"] = "skipped", "dry run"
            continue
        if posted_this_run:
            pause = random.randint(*SPACING_RANGE_S)
            log(f"spacing {pause}s before next reply")
            time.sleep(pause)
        try:
            t["status"], t["detail"] = post_one(t)
        except subprocess.TimeoutExpired:
            t["status"], t["detail"] = "failed", "browser command timeout"
        except Exception as e:
            t["status"], t["detail"] = "failed", str(e)[:200]
        log(f"@{t.get('handle', '?')} -> {t['status']} {t['detail']}")
        if t["status"] == "posted":
            posted_this_run += 1
            replied[link] = {"date": datetime.date.today().isoformat(),
                             "handle": t.get("handle", ""), "reply": reply}
            save_replied(replied)

    try:
        axi(["stop"], timeout=20)
    except Exception:
        pass
    print(json.dumps(targets, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
