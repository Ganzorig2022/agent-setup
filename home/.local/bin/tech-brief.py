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
import json
import pathlib
import re
import socket
import subprocess
import sys
import time
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
HARVEST_TIMEOUT = 700  # overall cap for the inline X harvest (best-effort; 25 accounts)

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


def wait_for_network(tries: int = 9, delay: int = 20) -> bool:
    """The 8am launchd slot can fire during a DNS blip — getaddrinfo then fails
    instantly for every feed and the run aborts (seen 2026-07-03). Block until
    name resolution works, up to tries*delay seconds."""
    for i in range(tries):
        try:
            socket.getaddrinfo("hnrss.org", 443)
            return True
        except OSError:
            if i == 0:
                log("network/DNS not ready; waiting...")
            time.sleep(delay)
    log(f"no DNS after {tries * delay}s; proceeding anyway (feeds may fail)")
    return False


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


def md_to_tg_html(md: str) -> str:
    """Convert the brief's markdown to Telegram HTML (parse_mode=HTML) so it
    renders readable in the chat: bold headers/emphasis, monospace code, clean
    separators. All conversions are line-local so chunking never splits a tag."""
    out = []
    for line in md.split("\n"):
        s = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        m = re.match(r"^(#{1,3})\s+(.*)$", s)
        if m:
            out.append(f"<b>{m.group(2).strip()}</b>")
            continue
        if s.strip() == "---":
            out.append("—————————")
            continue
        stripped = s.lstrip()
        if stripped.startswith("&gt; "):  # blockquote lines (drafted replies/captions)
            s = s[:len(s) - len(stripped)] + "<i>" + stripped[5:] + "</i>"
        s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
        s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
        out.append(s)
    return "\n".join(out)


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


def reply_opportunities(x_posts: dict) -> list[dict]:
    """Growth pass: from the harvested X posts, pick the best reply targets for
    audience growth and draft a ready-to-send reply for each in @n_ganzo's voice.
    Returns structured targets [{handle, link, reason, reply}] for the auto-poster.
    Reuses the already-harvested cache — no extra scraping."""
    xd = x_digest(x_posts)
    if not xd:
        return []
    prompt = (
        "You are a growth strategist for an AI-builder X (Twitter) account. " + NICHE + " "
        "At ~37 followers, his fastest growth path is thoughtful REPLIES to large accounts — "
        "adding a real data point, his own concrete result, or a sharp question (NEVER generic "
        "praise). From the recent posts by large AI accounts below, pick the 3-5 BEST reply "
        "targets — posts where his budget / local-model / multi-agent-memory angle genuinely "
        "adds value. These replies are POSTED AUTOMATICALLY with no human review, so only "
        "include a target if the reply is safe, on-voice, and specific; skip posts where he'd "
        "add nothing. Output ONLY a JSON array (no markdown, no code fences): each element "
        '{"handle": "@name", "link": "https://x.com/.../status/...", '
        '"reason": "<one line why this target>", "reply": "<the reply, <280 chars, his voice, '
        'specific, no hashtags>"}. Output [] if nothing is strong today.'
    )
    try:
        res = subprocess.run([str(CLAUDE), "-p", prompt], input=xd,
                             capture_output=True, text=True, timeout=300)
        out = res.stdout.strip()
        m = re.search(r"\[.*\]", out, re.S)  # tolerate stray prose/fences around the array
        targets = json.loads(m.group(0)) if m else []
        return [t for t in targets if isinstance(t, dict) and t.get("link") and t.get("reply")]
    except Exception as e:
        log(f"reply-opportunities failed: {e}")
        return []


def auto_reply(targets: list[dict]) -> list[dict]:
    """Post the drafted replies via x-reply.py (headless, logged-in profile).
    Best-effort: any failure marks targets failed so the brief reports them
    as manual drafts instead of blocking delivery."""
    if not targets:
        return targets
    poster = HOME / ".local/bin/x-reply.py"
    if not poster.exists():
        for t in targets:
            t["status"], t["detail"] = "failed", "x-reply.py missing"
        return targets
    try:
        res = subprocess.run([sys.executable, str(poster)],
                             input=json.dumps(targets, ensure_ascii=False),
                             capture_output=True, text=True, timeout=1200)
        return json.loads(res.stdout.strip() or "[]") or targets
    except Exception as e:
        log(f"auto-reply failed: {e}")
        for t in targets:
            t.setdefault("status", "failed")
            t.setdefault("detail", f"poster error: {e}")
        return targets


def render_replies(targets: list[dict]) -> str:
    """Confirmation section for the brief: what was auto-replied, what needs a hand."""
    if not targets:
        return "## Replies posted\n(nothing strong to reply to today)"
    lines = ["## Replies posted"]
    for i, t in enumerate(targets, 1):
        h, link = t.get("handle", "?"), t.get("link", "")
        reply, reason = t.get("reply", ""), t.get("reason", "")
        status, detail = t.get("status", "failed"), t.get("detail", "")
        if status == "posted":
            head = f"{i}. ✅ Replied to {h} — {reason}"
        elif status == "skipped":
            head = f"{i}. ⏭️ Skipped {h} ({detail})"
        else:
            head = f"{i}. ⚠️ FAILED {h} ({detail}) — post manually:"
        lines += [head, f"   {link}", f"   > {reply}"]
    return "\n".join(lines)


def render_growth() -> str:
    """One-line follower trend from x-harvest's daily snapshot (growth.json) —
    the scoreboard for the wait-until-EOY audience-building phase."""
    gfile = CACHE_DIR / "growth.json"
    try:
        hist = json.loads(gfile.read_text()) if gfile.exists() else []
    except Exception:
        return ""
    if not hist:
        return ""
    cur = hist[-1]
    n = cur.get("followers")
    if n is None:
        return ""

    def at_least_days_ago(days: int):
        target = datetime.date.today() - datetime.timedelta(days=days)
        older = [e for e in hist if e.get("date", "9999") <= target.isoformat()
                 and e.get("followers") is not None]
        return older[-1]["followers"] if older else None

    parts = [f"📈 {n} followers"]
    for label, days in (("7d", 7), ("30d", 30)):
        base = at_least_days_ago(days)
        if base is not None:
            parts.append(f"{n - base:+d} {label}")
    return " · ".join(parts)


def render_published() -> str:
    """Confirmation of x-draft-factory auto-posts (see x-post.py) from the last 24h,
    so the morning brief shows what went out overnight at the ET windows."""
    qfile = HOME / "Desktop/x-drafts/queue.json"
    try:
        queue = json.loads(qfile.read_text()) if qfile.exists() else []
    except Exception:
        return ""
    cutoff = datetime.datetime.now().astimezone() - datetime.timedelta(hours=24)
    lines = []
    for e in queue:
        stamp = e.get("posted_at") or e.get("post_at") or ""
        try:
            when = datetime.datetime.fromisoformat(stamp)
        except Exception:
            continue
        if when < cutoff or e.get("status") == "pending":
            continue
        first = (e.get("caption") or "").split("\n")[0][:80]
        if e.get("status") == "posted":
            lines.append(f"- ✅ Posted ({e.get('window', '?')}): “{first}…” — {e.get('png', '')}")
        else:
            lines.append(f"- ⚠️ {e.get('status', '?').upper()} ({e.get('detail', '')}): “{first}…” "
                         f"— still in ~/Desktop/x-drafts/{e.get('date', '')}/ for manual posting")
    pending = [e for e in queue if e.get("status") == "pending"]
    for e in pending[-2:]:
        first = (e.get("caption") or "").split("\n")[0][:80]
        lines.append(f"- ⏳ Queued for {e.get('post_at', '?')}: “{first}…”")
    if not lines:
        return ""
    return "## Posts published (auto)\n" + "\n".join(lines)


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
        full = f"<b>📡 Tech Brief — {date}</b>\n\n{md_to_tg_html(brief)}"
        parts = tg_chunks(full, 4000)

        def tg_send(text: str, mode: str | None) -> bool:
            payload = {"chat_id": chat, "text": text, "disable_web_page_preview": True}
            if mode:
                payload["parse_mode"] = mode
            data = json.dumps(payload).encode()
            r = urllib.request.Request(f"https://api.telegram.org/bot{tok}/sendMessage",
                                       data=data, headers={"Content-Type": "application/json"})
            urllib.request.urlopen(r, timeout=15)
            return True

        for i, part in enumerate(parts, 1):
            try:
                tg_send(part, "HTML")
            except Exception as e:
                log(f"telegram HTML send failed (part {i}/{len(parts)}): {e}; retrying plain")
                try:
                    tg_send(re.sub(r"</?(b|i|code|pre)>", "", part), None)
                except Exception as e2:
                    log(f"telegram plain send failed (part {i}/{len(parts)}): {e2}")
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
    wait_for_network()
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
    # Growth section: draft reply targets from the same X harvest, auto-post them,
    # and fold the confirmations into the brief. Kill switch: touch .no-auto-reply.
    targets = reply_opportunities(x_posts)
    log(f"reply-opportunities: {len(targets)} targets")
    targets = auto_reply(targets)
    posted = sum(1 for t in targets if t.get("status") == "posted")
    log(f"auto-reply: {posted}/{len(targets)} posted")
    brief = f"{brief}\n\n---\n\n{render_replies(targets)}"
    published = render_published()
    if published:
        brief = f"{brief}\n\n{published}"
    growth = render_growth()
    if growth:
        brief = f"{growth}\n\n{brief}"
    note = deliver(date, brief)
    log(f"delivered -> {note}")
    print(f"brief -> {note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
