#!/usr/bin/env python3
"""Twice-monthly X deep-dive factory (1st + 15th).

The daily card factory covers cadence; THIS covers substance. Reads a full month
of vault material and produces one long-form, bookmark-worthy piece the way a
human writer would — in passes:

  1. TOPICS   — propose 3 candidate deep dives w/ outlines, pick the strongest
  2. WRITE    — 1,500-3,000 word long-form draft (architecture, numbers, failures)
  3. CRITIQUE — cold reviewer: "would a senior dev bookmark this?" + fix list
  4. REVISE   — apply the critique
  5. CARDS    — render 2-3 branded support images via the proven card template

HUMAN-IN-THE-LOOP BY DESIGN: deep dives carry the account's reputation and ship
~2x/month, so the packet lands in ~/Desktop/x-deepdives/<date>/ for review and
manual posting (X long post / Article composer). Nothing is auto-posted.
"""
from __future__ import annotations
import datetime
import glob
import importlib.util
import json
import os
import pathlib
import re
import subprocess
import sys
import urllib.request

HOME = pathlib.Path.home()
CLAUDE = HOME / ".local/bin/claude"
BRAND = HOME / ".claude/content/brand.md"
OUT_ROOT = HOME / "Desktop/x-deepdives"
LOG = HOME / "Library/Logs/x-deepdive.log"
HANDLE = "@n_ganzo"
LOOKBACK_DAYS = 31
CALL_TIMEOUT = 600

CONFIDENTIALITY = """=== CONFIDENTIALITY — NON-NEGOTIABLE ===
The notes may contain the author's EMPLOYER's confidential details. These must NEVER
appear (this is for PUBLIC posting): company/product/brand names, internal repo/service/
table names, API shapes, proprietary architecture, CI/build/infra specifics,
settlement/ledger/payment internals. Write ONLY about general transferable techniques
or the author's OWN personal tooling, in universal terms. When in doubt, leave it out.
=== END CONFIDENTIALITY ==="""


def log(msg: str) -> None:
    ts = datetime.datetime.now().strftime("%F %T")
    with open(LOG, "a") as f:
        f.write(f"{ts} {msg}\n")


def vault_path() -> pathlib.Path:
    env = HOME / ".hermes/.env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("OBSIDIAN_VAULT_PATH="):
                return pathlib.Path(line.split("=", 1)[1].strip())
    return HOME / "GIthub/knowledge-base"


def claude_pass(prompt: str, stdin: str) -> str:
    res = subprocess.run([str(CLAUDE), "-p", prompt], input=stdin,
                         capture_output=True, text=True, timeout=CALL_TIMEOUT)
    return res.stdout.strip()


def gather_material(vault: pathlib.Path) -> str:
    cutoff = datetime.date.today() - datetime.timedelta(days=LOOKBACK_DAYS)
    chunks = []
    for f in sorted(glob.glob(str(vault / "decisions/*.md"))):
        m = re.search(r"(\d{4}-\d{2}-\d{2})", pathlib.Path(f).stem)
        if m and datetime.date.fromisoformat(m.group(1)) >= cutoff:
            chunks.append(pathlib.Path(f).read_text(errors="ignore"))
    p = vault / "profile/creator-journey.md"
    if p.exists():
        chunks.append(p.read_text(errors="ignore"))
    return "\n\n---\n\n".join(chunks)[:180_000]


TOPICS_PROMPT = f"""You are the content strategist for {HANDLE} (AI-agent builder, build-in-public,
audience: English-speaking developers). From a MONTH of his real work notes, find the material
for ONE deep-dive worth a senior developer's bookmark — the kind of long-form piece a big
account drops twice a month. Not tips. A real system, with architecture, numbers, and failures.

{CONFIDENTIALITY}

Propose exactly 3 candidates, then pick the winner. A great candidate: a complete system or
hard-won journey visible ACROSS the month's notes (not one day's trick), with concrete
numbers/tools, where his experience is genuinely differentiated.

Output EXACTLY one JSON object, nothing else:
{{"candidates": [{{"title": "...", "angle": "<one line: why this resonates>",
"outline": ["<section>", "..."]}}, ...],
"winner": <1-based index>, "why": "<one line>"}}"""

WRITE_PROMPT = f"""You are {HANDLE}'s long-form ghostwriter. Voice: clean, direct, specific,
lightly opinionated, no hype, no emoji, first person. Audience: senior developers.

{CONFIDENTIALITY}

Write the deep-dive below as an X long-form post (1,500-3,000 words). Structure:
- A first line that earns the click: concrete claim or number, no clickbait.
- Short sections with plain-text headers (ALL-CAPS line or numbered), scannable paragraphs.
- The real HOW: architecture, actual tools by name (his own stack only), real numbers,
  code/config fragments where they teach something.
- What FAILED and what he'd do differently — this is what makes it credible.
- End: one honest takeaway + a soft invitation to follow the build.

Output ONLY the piece, no commentary. Markdown is fine (the human pastes into X's composer)."""

CRITIQUE_PROMPT = """You are a cold, skeptical senior-developer reviewer. You did NOT write this.
Judge the long-form draft below: Would you bookmark it? Where does it get generic? What claim
lacks a number? What's confusing, bloated, or missing? Does anything read as confidential
employer material (name it — hard veto)? Is the opening line strong enough?

Output EXACTLY one JSON object, nothing else:
{"verdict": "<bookmark-worthy | needs-work | reject>", "fixes": ["<specific, actionable fix>", "..."],
"confidentiality_flags": ["<quote any leaking phrase>", "..."]}"""

REVISE_PROMPT = f"""You are {HANDLE}'s editor. Apply the reviewer's fixes to the draft — tighten,
add the missing specifics ONLY where the work notes support them, remove anything flagged for
confidentiality, keep the voice (clean, direct, no hype). Do not pad; cutting is fine.

{CONFIDENTIALITY}

Input contains the DRAFT, the REVIEWER FIXES, and the WORK NOTES for reference.
Output ONLY the revised piece, no commentary."""

CARDS_PROMPT = """From the final deep-dive below, spec 2-3 branded support images: one HOOK card
(the piece's core claim) and 1-2 SYSTEM cards (a key architecture/flow as numbered beats).
Output EXACTLY a JSON array, nothing else; each element:
{"eyebrow": "<short mono label>", "hook": "<headline, <=7 words>", "sub": "<one line>",
"beats": [["<title>", "<one-line detail>"], ...], "takeaway": "<payoff, ONE word in **bold**>"}
Use 3-4 beats per card. Keep every line tight enough for a 640px card."""


def load_factory():
    """Reuse the proven card template + renderer from x-draft-factory.py."""
    spec = importlib.util.spec_from_file_location(
        "xdf", str(HOME / ".local/bin/x-draft-factory.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def parse_json(text: str, fallback):
    m = re.search(r"\[.*\]|\{.*\}", text, re.S)
    try:
        return json.loads(m.group(0)) if m else fallback
    except Exception:
        return fallback


def notify(date: str, title: str, verdict: str, out: pathlib.Path) -> None:
    # title is model-generated (untrusted) — never interpolate it into AppleScript
    # source; pass it out-of-band via the process environment instead.
    try:
        subprocess.run(["osascript", "-e",
                        'display notification (system attribute "DD_TITLE") '
                        'with title (system attribute "DD_HEADING")'],
                       env={**os.environ, "DD_TITLE": title[:120],
                            "DD_HEADING": f"Deep-dive packet {date}"},
                       capture_output=True, timeout=10)
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
        msg = (f"📝 Deep-dive draft ready — “{title}”\n"
               f"Reviewer verdict: {verdict}\n"
               f"Review & post manually: {out}/article.md")
        try:
            data = json.dumps({"chat_id": chat, "text": msg}).encode()
            r = urllib.request.Request(f"https://api.telegram.org/bot{tok}/sendMessage",
                                       data=data, headers={"Content-Type": "application/json"})
            urllib.request.urlopen(r, timeout=15)
        except Exception as e:
            log(f"telegram notify failed: {e}")


def main() -> int:
    date = datetime.date.today().isoformat()
    out = OUT_ROOT / date
    log(f"=== run {date} ===")

    # Throttle: one packet per half-month; RunAtLoad catch-up must not re-draft.
    force = "--force" in sys.argv
    recent = sorted(OUT_ROOT.glob("*/article.md"))
    if not force and recent:
        newest = datetime.date.fromisoformat(recent[-1].parent.name)
        if (datetime.date.today() - newest).days < 10:
            log(f"last packet {newest} is <10 days old; skipping (use --force)")
            return 0

    vault = vault_path()
    material = gather_material(vault)
    if len(material) < 2000:
        log("not enough vault material for a deep dive; abort")
        return 0
    brand = BRAND.read_text() if BRAND.exists() else ""

    log("pass 1/5: topics")
    topics = parse_json(claude_pass(TOPICS_PROMPT, material), {})
    cands = topics.get("candidates") or []
    win = topics.get("winner")
    if not cands or not isinstance(win, int) or not (1 <= win <= len(cands)):
        log(f"no usable topic ({str(topics)[:200]}); abort")
        return 1
    chosen = cands[win - 1]
    log(f"topic: {chosen.get('title')!r} ({topics.get('why', '')})")

    log("pass 2/5: write")
    task = (f"CHOSEN DEEP DIVE:\nTitle: {chosen.get('title')}\nAngle: {chosen.get('angle')}\n"
            f"Outline: {json.dumps(chosen.get('outline', []))}\n\nBRAND SPEC:\n{brand}\n\n"
            f"WORK NOTES (the only source of facts):\n{material}")
    draft = claude_pass(WRITE_PROMPT, task)
    if len(draft) < 2000:
        log(f"draft too short ({len(draft)} chars); abort")
        return 1

    log("pass 3/5: critique")
    critique = parse_json(claude_pass(CRITIQUE_PROMPT, draft), {})
    verdict = critique.get("verdict", "needs-work")
    fixes = critique.get("fixes", [])
    flags = critique.get("confidentiality_flags", [])
    log(f"critique: {verdict}, {len(fixes)} fixes, {len(flags)} confidentiality flags")

    log("pass 4/5: revise")
    final = draft
    if fixes or flags:
        rev_in = (f"DRAFT:\n{draft}\n\nREVIEWER FIXES:\n{json.dumps(fixes, indent=1)}\n"
                  f"CONFIDENTIALITY FLAGS (must all be removed):\n{json.dumps(flags, indent=1)}\n\n"
                  f"WORK NOTES:\n{material[:80_000]}")
        revised = claude_pass(REVISE_PROMPT, rev_in)
        if len(revised) > 1500:
            final = revised

    log("pass 5/5: cards")
    out.mkdir(parents=True, exist_ok=True)
    xdf = load_factory()
    cards = parse_json(claude_pass(CARDS_PROMPT, final), [])
    card_lines = []
    for i, c in enumerate(cards[:3], 1):
        try:
            d = {"eyebrow": c.get("eyebrow", "DEEP DIVE"), "hook": c.get("hook", ""),
                 "sub": c.get("sub", ""), "takeaway": c.get("takeaway", ""),
                 "beats": [tuple(b) for b in c.get("beats", []) if len(b) == 2]}
            if not d["hook"] or not d["beats"]:
                continue
            html_path, png_path = out / f"card{i}.html", out / f"card{i}.png"
            html_path.write_text(xdf.build_html(d))
            ok = xdf.render_png(html_path, png_path)
            card_lines.append(f"- `card{i}.png`" + ("" if ok else " ⚠️ render failed"))
        except Exception as e:
            log(f"card {i} failed: {e}")

    title = chosen.get("title", "Deep dive")
    (out / "article.md").write_text(
        f"# {title}\n\n_Deep-dive packet {date} — reviewer verdict: **{verdict}**. "
        "REVIEW BEFORE POSTING (X long post / Article composer). Nothing was auto-posted._\n\n"
        + (f"_Attach:_\n" + "\n".join(card_lines) + "\n\n" if card_lines else "")
        + "---\n\n" + final + "\n")
    (out / "critique.md").write_text(
        f"# Cold review — {date}\n\nVerdict: {verdict}\n\nFixes applied:\n"
        + "\n".join(f"- {f}" for f in fixes) + "\n\nConfidentiality flags:\n"
        + ("\n".join(f"- {f}" for f in flags) or "- none") + "\n")
    log(f"packet -> {out} ({len(final)} chars, {len(card_lines)} cards)")
    notify(date, title, verdict, out)
    print(f"deep-dive packet -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
