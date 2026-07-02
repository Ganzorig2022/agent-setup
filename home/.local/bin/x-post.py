#!/usr/bin/env python3
"""Post queued x-draft-factory posts (caption + branded PNG) at their target
windows via the logged-in headless Chrome (same profile as x-harvest/x-reply).

Queue: ~/Desktop/x-drafts/queue.json — entries written by x-draft-factory.py:
  {"id", "date", "window", "post_at" (local ISO), "caption", "png", "status", "detail"}

Run from launchd hourly; exits instantly unless an entry is due. An entry is due
when post_at <= now; if it is more than GRACE_H past its window it is marked
stale-skipped instead of posting at a weird hour.

Safety rails:
  - kill switch: touch ~/Desktop/x-drafts/.no-auto-post to disable posting
  - max 1 post per run; captions capped at 280 chars; PNG must exist
  - caption text verified in the composer before Post is clicked; the post only
    counts as confirmed when the compose dialog is gone afterwards
  - every attempt logged; failures keep the packet on the Desktop for manual use

Mechanics: same verified rules as x-reply.py (2026-07-02) — text via
execCommand('insertText') (CDP fill eats the first char), buttons via real CDP
click with snapshot-then-act-immediately + stale-ref retries.
"""
from __future__ import annotations
import datetime
import glob
import json
import os
import pathlib
import re
import subprocess
import sys
import time

HOME = pathlib.Path.home()
PROFILE = HOME / ".local/share/tech-brief-chrome"
DRAFT_DIR = HOME / "Desktop/x-drafts"
QUEUE = DRAFT_DIR / "queue.json"
KILL_SWITCH = DRAFT_DIR / ".no-auto-post"
LOG = HOME / "Library/Logs/x-draft-factory.log"

MAX_CHARS = 280
GRACE_H = 3           # post at most this late; later -> stale-skip
OPEN_TIMEOUT = 50
CMD_TIMEOUT = 30
UPLOAD_WAIT_S = 20    # X needs a moment to process the attached image

COMPOSER = '[data-testid="tweetTextarea_0"]'


def log(msg: str) -> None:
    try:
        with open(LOG, "a") as f:
            f.write(f"{datetime.datetime.now():%F %T} x-post: {msg}\n")
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
    out = axi(["eval", js])
    i = out.find("result:")
    if i < 0:
        return None
    chunk = out[i + len("result:"):].strip().split("\nhelp[")[0].strip()
    for _ in range(3):
        try:
            v = json.loads(chunk)
        except Exception:
            return chunk
        if isinstance(v, str):
            chunk = v
            continue
        return json.dumps(v)
    return chunk


def set_composer_text(text: str) -> bool:
    payload = json.dumps(text)
    r = eval_js(
        "(() => { const el = document.querySelector('" + COMPOSER + "');"
        " if (!el) return '__NO_COMPOSER__';"
        " el.focus(); document.execCommand('selectAll'); document.execCommand('delete');"
        " document.execCommand('insertText', false, " + payload + ");"
        " return el.textContent; })()")
    return r == text


def snapshot_uid(pattern: str, forbid: str = "disabled") -> str | None:
    """Snapshot and return the uid of the first line matching `pattern` regex.
    Use the uid IMMEDIATELY — X's live DOM invalidates refs within seconds."""
    snap = axi(["snapshot"], timeout=45)
    for line in snap.splitlines():
        if forbid and forbid in line:
            continue
        m = re.search(pattern, line.strip())
        if m:
            u = re.search(r"uid=(\S+)", line)
            if u:
                return u.group(1)
    return None


def click_when_found(pattern: str, label: str, attempts: int = 4) -> bool:
    for i in range(attempts):
        uid = snapshot_uid(pattern)
        if not uid:
            time.sleep(2)
            continue
        out = axi(["click", f"@{uid}"])
        if "STALE_REF" in out:
            log(f"{label}: stale ref (attempt {i + 1}); retrying")
            continue
        return True
    return False


def attachment_present() -> bool:
    r = eval_js(
        "(() => !!document.querySelector('[data-testid=\"attachments\"] img,"
        " [aria-label=\"Media\"] img'))()")
    return r == "true"


def dialog_open() -> bool:
    r = eval_js("(() => location.pathname.includes('/compose/') || "
                "!!document.querySelector('[role=\"dialog\"] [data-testid=\"tweetTextarea_0\"]'))()")
    return r == "true"


def post_one(entry: dict) -> tuple[str, str]:
    caption, png = entry["caption"].strip(), pathlib.Path(entry["png"])
    if not png.exists():
        return "failed", f"image missing: {png}"
    axi(["open", "https://x.com/compose/post"], timeout=OPEN_TIMEOUT)
    time.sleep(3)
    if not set_composer_text(caption):
        time.sleep(2)
        if not set_composer_text(caption):
            return "failed", "could not set exact caption in composer"
    # attach the card image via the file input (real CDP upload)
    for i in range(4):
        uid = snapshot_uid(r'button "Choose Files"', forbid="")
        if not uid:
            time.sleep(2)
            continue
        out = axi(["upload", f"@{uid}", str(png)], timeout=60)
        if "STALE_REF" in out:
            log(f"upload: stale ref (attempt {i + 1}); retrying")
            continue
        break
    else:
        return "failed", "file input not found for image upload"
    deadline = time.time() + UPLOAD_WAIT_S
    while time.time() < deadline and not attachment_present():
        time.sleep(2)
    if not attachment_present():
        return "failed", "image did not attach (upload rejected or timed out)"
    # send: the dialog's Post button enables once caption+media are in
    if not click_when_found(r'button "Post"\s*$', "post button"):
        return "failed", "Post button not found/clickable"
    for _ in range(8):
        time.sleep(2)
        if not dialog_open():
            return "posted", ""
    return "failed", "clicked Post but composer did not close — unconfirmed, check manually"


def main() -> int:
    dry = "--dry-run" in sys.argv
    if not QUEUE.exists():
        return 0
    try:
        queue = json.loads(QUEUE.read_text())
    except Exception as e:
        log(f"queue unreadable: {e}")
        return 0
    if KILL_SWITCH.exists():
        return 0  # silently inert — drafts stay manual

    now = datetime.datetime.now().astimezone()
    changed = False
    for entry in queue:
        if entry.get("status") != "pending":
            continue
        try:
            due = datetime.datetime.fromisoformat(entry["post_at"])
        except Exception:
            entry["status"], entry["detail"] = "failed", "bad post_at"
            changed = True
            continue
        if now < due:
            continue
        if (now - due).total_seconds() > GRACE_H * 3600:
            entry["status"], entry["detail"] = "skipped", f"missed window by >{GRACE_H}h"
            changed = True
            log(f"{entry['id']}: {entry['detail']}")
            continue
        if len(entry.get("caption", "")) > MAX_CHARS:
            entry["status"], entry["detail"] = "skipped", f"caption over {MAX_CHARS} chars"
            changed = True
            continue
        if dry:
            log(f"{entry['id']}: due (dry run, not posting)")
            continue
        log(f"{entry['id']}: posting ({entry['window']})")
        try:
            entry["status"], entry["detail"] = post_one(entry)
        except subprocess.TimeoutExpired:
            entry["status"], entry["detail"] = "failed", "browser command timeout"
        except Exception as e:
            entry["status"], entry["detail"] = "failed", str(e)[:200]
        entry["posted_at"] = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
        changed = True
        log(f"{entry['id']}: {entry['status']} {entry['detail']}")
        try:
            axi(["stop"], timeout=20)
        except Exception:
            pass
        break  # max one post per run

    if changed:
        QUEUE.write_text(json.dumps(queue, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
