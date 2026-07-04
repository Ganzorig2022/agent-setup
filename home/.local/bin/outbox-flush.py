#!/usr/bin/env python3
"""Outbox flusher: deliver queued Telegram messages that failed to send when
their job ran offline (rule: content is always generated; delivery keeps
retrying until the network lets it through).

Queue: ~/.outbox/tg-<epoch>-<n>.json  {"text": str, "parse_mode": "HTML"|null}
Files are flushed oldest-first and flushing STOPS at the first failure so
multi-part messages stay ordered. Sent files are deleted; files older than
14 days are dropped (logged) so the queue can't grow unbounded.

Runs via launchd com.dev.outbox-flush every 30 min + at login. Zero cost when
the queue is empty. Jobs enqueue by writing a JSON file — no shared library.
"""
import datetime
import json
import pathlib
import sys
import time
import urllib.request

HOME = pathlib.Path.home()
OUTBOX = HOME / ".outbox"
LOG = HOME / "Library/Logs/outbox-flush.log"
MAX_AGE_DAYS = 14


def log(msg: str) -> None:
    with open(LOG, "a") as f:
        f.write(f"{datetime.datetime.now():%F %T} {msg}\n")


def creds():
    env = HOME / ".hermes/.env"
    tok = chat = None
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("TELEGRAM_BOT_TOKEN="):
                tok = line.split("=", 1)[1].strip()
            elif line.startswith("TELEGRAM_CHAT_ID="):
                chat = line.split("=", 1)[1].strip()
    return tok, chat


def main() -> int:
    if not OUTBOX.exists():
        return 0
    files = sorted(OUTBOX.glob("tg-*.json"))
    if not files:
        return 0
    tok, chat = creds()
    if not (tok and chat):
        log("no telegram creds; leaving queue")
        return 0
    now = time.time()
    for f in files:
        if now - f.stat().st_mtime > MAX_AGE_DAYS * 86400:
            log(f"dropping {f.name} (older than {MAX_AGE_DAYS}d)")
            f.unlink(missing_ok=True)
            continue
        try:
            msg = json.loads(f.read_text())
            payload = {"chat_id": chat, "text": msg["text"][:4000],
                       "disable_web_page_preview": True}
            if msg.get("parse_mode"):
                payload["parse_mode"] = msg["parse_mode"]
            r = urllib.request.Request(
                f"https://api.telegram.org/bot{tok}/sendMessage",
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"})
            urllib.request.urlopen(r, timeout=15)
            f.unlink()
            log(f"flushed {f.name}")
        except Exception as e:
            log(f"flush stopped at {f.name}: {e}")
            return 0  # keep order; retry next interval
    return 0


if __name__ == "__main__":
    sys.exit(main())
