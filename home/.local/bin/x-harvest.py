#!/usr/bin/env python3
"""Harvest recent posts from a curated set of X (Twitter) accounts via a
logged-in, headless Chrome driven by chrome-devtools-axi, and cache them as JSON
for the morning tech-brief to fold in.

No API tokens. Uses a DEDICATED persistent Chrome profile (separate from your
normal browser) that you log into X once:

    x-harvest.py --login      # opens a visible window; sign into X, then close it

After that, the headless 8am run reuses the saved session until X expires it.

Design: best-effort. Every failure mode (X logout, captcha, UI change, timeout)
degrades to an empty/partial cache and is logged — it NEVER raises into the brief.
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
PROFILE = HOME / ".local/share/tech-brief-chrome"   # dedicated X-only Chrome profile
OUT_DIR = HOME / "Desktop/tech-brief"
CACHE_DIR = OUT_DIR / ".cache"
LOG = HOME / "Library/Logs/tech-brief.log"

WINDOW_H = 36            # only keep posts this recent (matches the brief's window)
MAX_PER_ACCOUNT = 4     # cap posts per account so the digest stays scannable
OPEN_TIMEOUT = 50       # per-page load budget (s)
EVAL_TIMEOUT = 30       # per-scrape budget (s)
TOTAL_BUDGET_S = 420    # overall wall-clock cap; bail out gracefully past this

# Curated from @n_ganzo's followings — high-signal AI/dev: model releases, agent
# harnesses, configs/tooling. Edit this list freely; one handle per line.
HANDLES = [
    "testingcatalog",   # AI news: agents, model releases, tools, leaks
    "kimmonismus",      # daily AI news / releases
    "aiedge_",          # breaking AI news + practical guides
    "claudeai",         # Anthropic / Claude releases
    "ClaudeDevs",       # Claude developer + agent updates
    "cursor_ai",        # coding-agent updates
    "Codex_Changelog",  # OpenAI Codex CLI changelog (harness/config)
    "Teknium",          # agent harnesses, open models (Nous/Hermes)
    "NousResearch",     # open-source AI / models
    "aiDotEngineer",    # AI engineering / agent builders
    "dr_cintas",        # practical AI + cybersecurity
    "DanWahlin",        # agentic AI @ Microsoft/GitHub
    "exolabs",          # local / on-device frontier AI
    "pdev110",          # Ollama (local models)
    "davidcrawshaw",    # dev tooling / AI infra
]

# Scrape the visible tweets on a profile page. Runs in the page; returns an array
# of {when, link, txt}. No shell escaping needed — passed as a single argv.
SCRAPE_JS = r"""(() => {
  const arts = [...document.querySelectorAll('article[data-testid="tweet"]')].slice(0, 12);
  const out = [];
  for (const a of arts) {
    const txt = (a.querySelector('div[data-testid="tweetText"]')?.textContent || '')
      .replace(/\s+/g, ' ').trim();
    const timeEl = a.querySelector('a[href*="/status/"] time');
    if (!txt || !timeEl) continue;
    const href = timeEl.closest('a').getAttribute('href') || '';
    out.push({ when: timeEl.getAttribute('datetime') || '', link: 'https://x.com' + href, txt: txt.slice(0, 280) });
  }
  return out;
})()"""


def log(msg: str) -> None:
    try:
        with open(LOG, "a") as f:
            f.write(f"{datetime.datetime.now():%F %T} {msg}\n")
    except Exception:
        pass


def _ver(path: str) -> tuple:
    m = re.search(r"/v(\d+)\.(\d+)\.(\d+)/", path)
    return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)


def find_npx() -> str:
    """Resolve npx robustly so the cron survives Node upgrades (nvm paths move).
    Order: explicit override -> newest nvm version -> Homebrew -> PATH."""
    cands = []
    if os.environ.get("NPX_BIN"):
        cands.append(os.environ["NPX_BIN"])
    cands += sorted(glob.glob(str(HOME / ".nvm/versions/node/*/bin/npx")), key=_ver, reverse=True)
    cands += ["/opt/homebrew/bin/npx", "/usr/local/bin/npx"]
    for c in cands:
        if c and pathlib.Path(c).exists():
            return c
    return "npx"  # last resort: hope it's on PATH


NPX = find_npx()


def axi(args: list[str], timeout: int, headed: bool = False) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["CHROME_DEVTOOLS_AXI_USER_DATA_DIR"] = str(PROFILE)
    if headed:
        env["CHROME_DEVTOOLS_AXI_HEADED"] = "1"
    else:
        env.pop("CHROME_DEVTOOLS_AXI_HEADED", None)
    env["PATH"] = str(pathlib.Path(NPX).parent) + os.pathsep + env.get("PATH", "")
    return subprocess.run([NPX, "-y", "chrome-devtools-axi", *args],
                          capture_output=True, text=True, timeout=timeout, env=env)


def parse_eval(stdout: str):
    """chrome-devtools-axi prints `result: <json>` (sometimes the value is itself a
    JSON-encoded string). Extract and decode, tolerating both encodings."""
    i = stdout.find("result:")
    if i < 0:
        return None
    chunk = stdout[i + len("result:"):]
    j = chunk.find("\nhelp[")
    if j >= 0:
        chunk = chunk[:j]
    chunk = chunk.strip()
    for _ in range(2):  # may be double-encoded
        try:
            v = json.loads(chunk)
        except Exception:
            return None
        if isinstance(v, str):
            chunk = v
            continue
        return v
    return None


def parse_when(s: str):
    if not s:
        return None
    try:
        return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def login() -> int:
    PROFILE.mkdir(parents=True, exist_ok=True)
    print("Opening a visible Chrome window. Log into X, then close the window.")
    try:
        axi(["open", "https://x.com/login"], 60, headed=True)
    except Exception as e:
        print(f"login launch failed: {e}")
        return 1
    print("When you're done, the saved session will be reused by the 8am run.")
    return 0


def harvest() -> dict:
    start = time.time()
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=WINDOW_H)
    results: dict[str, list] = {}
    for h in HANDLES:
        if time.time() - start > TOTAL_BUDGET_S:
            log("x-harvest: total budget exceeded; stopping early")
            break
        posts = []
        try:
            axi(["open", f"https://x.com/{h}"], OPEN_TIMEOUT)
            time.sleep(1.5)  # let lazy-loaded tweets render
            res = axi(["eval", SCRAPE_JS], EVAL_TIMEOUT)
            posts = parse_eval(res.stdout) or []
        except subprocess.TimeoutExpired:
            log(f"x-harvest @{h}: timeout")
        except Exception as e:
            log(f"x-harvest @{h}: {e}")
        keep, seen = [], set()
        for p in posts:
            txt = (p.get("txt") or "").strip()
            if not txt or txt in seen:
                continue
            dt = parse_when(p.get("when"))
            if dt is not None and dt < cutoff:
                continue
            seen.add(txt)
            keep.append({"when": p.get("when", ""), "link": p.get("link", ""), "txt": txt})
            if len(keep) >= MAX_PER_ACCOUNT:
                break
        results[h] = keep
        log(f"x {len(keep):2d}  @{h}")
    try:
        axi(["stop"], 20)
    except Exception:
        pass
    return results


def main() -> int:
    if "--login" in sys.argv:
        return login()
    date = datetime.date.today().isoformat()
    results = harvest()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache = CACHE_DIR / f"x-{date}.json"
    cache.write_text(json.dumps(results, ensure_ascii=False))
    total = sum(len(v) for v in results.values())
    log(f"x-harvest done: {total} posts / {len(results)} accounts -> {cache}")
    if results and total == 0:
        # Every account empty usually means the X session expired (headless gets the
        # logged-out wall). Flag it so the brief's "From X" section can be restored.
        log("x-harvest WARNING: 0 posts everywhere — session may be logged out; "
            "re-run: x-harvest.py --login")
    print(f"x-harvest -> {cache} ({total} posts)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
