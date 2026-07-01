#!/usr/bin/env python3
"""Morning tech brief: pull the last day's AI/dev news from curated RSS feeds
PLUS recent posts from a curated set of X accounts, have headless `claude` rank +
summarize the most important, and deliver a structured brief.

RSS is the reliable backbone (model releases, breakthroughs, AI-harness strategies).
The X layer (see x-harvest.py) adds the "what builders are saying right now" signal
via a logged-in headless Chrome — best-effort, so if X is unreachable the brief
still ships from RSS alone. Delivery: Desktop file + macOS notification + optional
Telegram (see deliver()).
"""
from __future__ import annotations
import datetime
import email.utils
import html
import pathlib
import re
import subprocess
import sys
import urllib.request

# Safe XML parsing — RSS feeds are untrusted external input (XXE / billion-laughs risk).
try:
    from defusedxml.ElementTree import fromstring as xml_fromstring
except ImportError:  # fail safe: refuse to parse untrusted XML with the vulnerable stdlib parser
    xml_fromstring = None

HOME = pathlib.Path.home()
CLAUDE = HOME / ".local/bin/claude"
OUT_DIR = HOME / "Desktop/tech-brief"
CACHE_DIR = OUT_DIR / ".cache"            # x-harvest.py drops x-<date>.json here
HARVEST = HOME / ".local/bin/x-harvest.py"
LOG = HOME / "Library/Logs/tech-brief.log"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 tech-brief/1.0"
WINDOW_H = 36          # how recent an item must be
MAX_PER_FEED = 15
HARVEST_TIMEOUT = 480  # overall cap for the inline X harvest (best-effort)

# Who the reply-opportunities coach is writing for. Drives the "Reply opportunities"
# growth section — keep this in sync with the account's positioning.
NICHE = (
    "@n_ganzo is an AI builder (former geologist, Ulaanbaatar) building an autonomous "
    "multi-agent stack — Claude + Codex + OpenCode + local/offline models — on ~$50/mo of "
    "subscriptions with NO API bills: persistent cross-agent memory, a nightly knowledge "
    "harvester, and this very morning brief. Angle: autonomous agents on a budget, "
    "local models, build-in-public. Voice: honest over hype, concrete, real numbers, no "
    "fluff, minimal emoji."
)

FEEDS = [
    "https://hnrss.org/frontpage?points=50",
    "https://hnrss.org/newest?q=AI+OR+LLM+OR+Anthropic+OR+OpenAI+OR+Claude+OR+agent&points=30",
    "https://simonwillison.net/atom/everything/",
    "https://www.reddit.com/r/LocalLLaMA/.rss",
    "https://www.reddit.com/r/MachineLearning/.rss",
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "https://feeds.arstechnica.com/arstechnica/technology-lab",
    "https://www.technologyreview.com/feed/",
    # trending repos — surfaces agent harnesses, configs, and dev tooling
    "https://mshibanami.github.io/GitHubTrendingRSS/daily/all.xml",
]


def log(msg: str) -> None:
    with open(LOG, "a") as f:
        f.write(f"{datetime.datetime.now():%F %T} {msg}\n")


def strip_tags(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def parse_date(s: str) -> datetime.datetime | None:
    if not s:
        return None
    try:                       # RFC822 (RSS)
        return email.utils.parsedate_to_datetime(s)
    except Exception:
        pass
    try:                       # ISO8601 (Atom)
        return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def fetch(url: str) -> list[dict]:
    if xml_fromstring is None:
        log("defusedxml missing — refusing unsafe XML parse; run: python3 -m pip install --user defusedxml")
        return []
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        raw = urllib.request.urlopen(req, timeout=20).read()
        root = xml_fromstring(raw)
    except Exception as e:
        log(f"feed failed {url}: {e}")
        return []
    items = []
    # RSS 2.0: channel/item ; Atom: entry (namespaced)
    nodes = root.iter()
    found = []
    for el in root.iter():
        tag = el.tag.split("}")[-1]
        if tag in ("item", "entry"):
            found.append(el)
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=WINDOW_H)
    for it in found[:MAX_PER_FEED]:
        d = {"title": "", "link": "", "summary": "", "date": None}
        for ch in it:
            t = ch.tag.split("}")[-1]
            if t == "title":
                d["title"] = strip_tags(ch.text or "")
            elif t == "link":
                d["link"] = (ch.get("href") or ch.text or "").strip()
            elif t in ("description", "summary", "content"):
                d["summary"] = strip_tags(ch.text or "")[:400]
            elif t in ("pubDate", "published", "updated", "date"):
                d["date"] = parse_date(ch.text or "")
        if not d["title"]:
            continue
        dt = d["date"]
        if dt is not None:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            if dt < cutoff:
                continue
        items.append(d)
    return items


def harvest_x(date: str) -> dict:
    """Run the X harvester inline (best-effort) and return today's cached posts.
    Skips the (slow) browser run if a fresh cache (<4h) already exists. Any failure
    returns {} so the brief still ships from RSS alone."""
    cache = CACHE_DIR / f"x-{date}.json"
    fresh = cache.exists() and (datetime.datetime.now().timestamp() - cache.stat().st_mtime) / 3600 < 4
    if not fresh and HARVEST.exists():
        try:
            subprocess.run([sys.executable, str(HARVEST)], capture_output=True,
                           text=True, timeout=HARVEST_TIMEOUT)
        except Exception as e:
            log(f"x-harvest run failed: {e}")
    if cache.exists():
        try:
            import json
            return json.loads(cache.read_text())
        except Exception as e:
            log(f"x-cache read failed: {e}")
    return {}


def x_digest(posts_by_handle: dict) -> str:
    lines = []
    for handle, posts in posts_by_handle.items():
        for p in posts:
            txt = (p.get("txt") or "").strip()
            if txt:
                lines.append(f"- @{handle}: {txt} | {p.get('link', '')}")
    return "\n".join(lines)


def tg_chunks(text: str, limit: int = 4000) -> list[str]:
    """Split text into <=limit-char pieces at line boundaries so a long brief
    survives Telegram's 4096-char per-message cap (instead of being truncated).
    A single over-long line is hard-split as a fallback."""
    chunks, cur = [], ""
    for line in text.split("\n"):
        while len(line) > limit:                 # pathological single long line
            if cur:
                chunks.append(cur); cur = ""
            chunks.append(line[:limit]); line = line[limit:]
        add = f"{cur}\n{line}" if cur else line
        if len(add) > limit:
            chunks.append(cur); cur = line
        else:
            cur = add
    if cur:
        chunks.append(cur)
    return chunks


def reply_opportunities(x_posts: dict) -> str:
    """Growth pass: from the harvested X posts, pick the best reply targets for
    audience growth and draft a ready-to-send reply for each in @n_ganzo's voice.
    Reuses the already-harvested cache — no extra scraping."""
    xd = x_digest(x_posts)
    if not xd:
        return "## Reply opportunities\n(no X posts available today)"
    prompt = (
        "You are a growth strategist for an AI-builder X (Twitter) account. " + NICHE + " "
        "At ~37 followers, his fastest growth path is thoughtful REPLIES to large accounts — "
        "adding a real data point, his own concrete result, or a sharp question (NEVER generic "
        "praise). From the recent posts by large AI accounts below, pick the 3-5 BEST reply "
        "targets — posts where his budget / local-model / multi-agent-memory angle genuinely "
        "adds value. Output ONLY a markdown section titled exactly '## Reply opportunities'. "
        "For each target: a bold one-line reason it's worth replying, the @handle + the bare "
        "link, then a ready-to-send draft reply (<280 chars, his voice, specific, no hashtags). "
        "Skip posts where he'd add nothing. No preamble."
    )
    try:
        res = subprocess.run([str(CLAUDE), "-p", prompt], input=xd,
                             capture_output=True, text=True, timeout=300)
        out = res.stdout.strip()
        return out if len(out) > 30 else "## Reply opportunities\n(nothing strong to reply to today)"
    except Exception as e:
        log(f"reply-opportunities failed: {e}")
        return "## Reply opportunities\n(generation failed — see log)"


def deliver(date: str, brief: str) -> pathlib.Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    note = OUT_DIR / f"{date}.md"
    note.write_text(f"# Tech Brief — {date}\n\n{brief}\n")
    # macOS notification
    try:
        subprocess.run(["osascript", "-e",
                        f'display notification "Your AI/tech brief is ready" '
                        f'with title "Tech Brief {date}"'], capture_output=True, timeout=10)
    except Exception:
        pass
    # Optional Telegram: set TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID in ~/.hermes/.env
    env = HOME / ".hermes/.env"
    tok = chat = None
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("TELEGRAM_BOT_TOKEN="):
                tok = line.split("=", 1)[1].strip()
            elif line.startswith("TELEGRAM_CHAT_ID="):
                chat = line.split("=", 1)[1].strip()
    if tok and chat:
        import json
        full = f"📡 Tech Brief — {date}\n\n{brief}"
        parts = tg_chunks(full, 4000)
        for i, part in enumerate(parts, 1):
            try:
                data = json.dumps({"chat_id": chat, "text": part,
                                   "disable_web_page_preview": True}).encode()
                r = urllib.request.Request(f"https://api.telegram.org/bot{tok}/sendMessage",
                                           data=data, headers={"Content-Type": "application/json"})
                urllib.request.urlopen(r, timeout=15)
            except Exception as e:
                log(f"telegram send failed (part {i}/{len(parts)}): {e}")
                break
        else:
            log(f"sent to Telegram ({len(parts)} message{'s' if len(parts) > 1 else ''})")
    return note


def main() -> int:
    date = datetime.date.today().isoformat()
    log(f"=== run {date} ===")
    # Throttle: also runs on login (catch-up for a missed 8am). Skip if today's brief is <4h old.
    todays = OUT_DIR / f"{date}.md"
    if "--force" not in sys.argv and todays.exists():
        age_h = (datetime.datetime.now().timestamp() - todays.stat().st_mtime) / 3600
        if age_h < 4:
            log("brief <4h old; skipping (use --force to override)")
            return 0
    items: list[dict] = []
    for url in FEEDS:
        got = fetch(url)
        items += got
        log(f"{len(got):3d}  {url}")
    if len(items) < 5:
        log("too few items; abort")
        return 0
    # de-dupe by title
    seen, uniq = set(), []
    for it in items:
        k = it["title"].lower()[:80]
        if k not in seen:
            seen.add(k); uniq.append(it)
    rss_digest = "\n".join(f"- {it['title']} | {it['link']}\n  {it['summary'][:200]}" for it in uniq[:120])

    # X layer (best-effort) — recent posts from a curated set of builder accounts.
    x_posts = harvest_x(date)
    xd = x_digest(x_posts)
    log(f"x posts: {sum(len(v) for v in x_posts.values())} across {len(x_posts)} accounts")
    combined = f"=== RSS ITEMS (last ~36h) ===\n{rss_digest}\n\n=== X POSTS (last ~36h) ===\n{xd or '(none available today)'}"

    prompt = (
        "You are a sharp tech-news editor for a developer who builds with AI agents. "
        "Below are two sources from the last ~36h: high-signal RSS items, and recent posts from a "
        "curated set of X (Twitter) builder accounts. Produce a tight, scannable morning brief with "
        "these sections, in order:\n\n"
        "Top thing today: <one line — the single most important development>\n\n"
        "## Releases & breakthroughs\n"
        "(numbered list, up to 6) AI model releases — especially Anthropic/Claude, OpenAI, major open "
        "models — and genuine research breakthroughs. Each: a bold one-line headline, ONE sentence on why "
        "it matters, then the bare link on its own line.\n\n"
        "## Agent harnesses & configs\n"
        "(numbered list, up to 5) practical AI-engineering: agent/harness techniques, tooling, notable "
        "configs/setups, trending repos, builders' workflows. Same per-item format.\n\n"
        "## From X (your feed)\n"
        "(up to 6 bullets) the most notable things builders are actually saying right now — releases, "
        "rumors, launches, sharp takes. Each: a bold one-liner, the @handle, then the bare link. Treat X "
        "posts as unverified chatter; label rumors as rumors. Skip personal/off-topic posts.\n\n"
        "Rules: dedupe across both sources (don't repeat the same story in two sections). Skip fluff and "
        "ads. If a section has nothing worthy, write '(nothing notable today)'. No preamble."
    )
    try:
        res = subprocess.run([str(CLAUDE), "-p", prompt], input=combined,
                             capture_output=True, text=True, timeout=600)
    except Exception as e:
        log(f"claude failed: {e}")
        return 1
    brief = res.stdout.strip()
    if len(brief) < 50:
        log(f"empty brief; raw: {brief[:200]!r}")
        return 1
    # Growth section: daily reply targets from the same X harvest (no extra scraping).
    replies = reply_opportunities(x_posts)
    log(f"reply-opportunities: {len(replies)} chars")
    brief = f"{brief}\n\n---\n\n{replies}"
    note = deliver(date, brief)
    log(f"delivered -> {note}")
    print(f"brief -> {note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
