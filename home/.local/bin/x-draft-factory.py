#!/usr/bin/env python3
"""Nightly X draft factory.

Reads the user's knowledge vault, asks headless `claude` to draft a few build-in-public
posts in their brand voice, fills the proven artifact template with the AI-written content,
renders clean PNGs via headless Chrome, and drops a review packet on the Desktop.

Human-in-the-loop by design: this only DRAFTS. The user reviews, approves, and schedules
(via X's native scheduler). Nothing is ever posted automatically.
"""
from __future__ import annotations
import datetime
import glob
import html as html_lib
import os
import pathlib
import re
import subprocess
import sys

HOME = pathlib.Path.home()
CLAUDE = HOME / ".local/bin/claude"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
BRAND = HOME / ".claude/content/brand.md"
N_DRAFTS = 3
HANDLE = "@n_ganzo"
LOG = HOME / "Library/Logs/x-draft-factory.log"


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


# --- proven artifact template (matches the post the user already shipped) ---
TEMPLATE = """<!doctype html><html lang="en"><head><meta charset="utf-8"/>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;700;800&family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet"/>
<style>
:root{--bg:#0A0C10;--surface:#12161D;--border:#232A35;--text:#E8EEF5;--muted:#8B97A7;--accent:#2EE6A6;--accent-soft:rgba(46,230,166,0.12)}
*{margin:0;padding:0;box-sizing:border-box}html,body{background:var(--bg)}
.card{width:640px;height:800px;background:var(--bg);padding:56px 52px;display:flex;flex-direction:column;font-family:Manrope,system-ui,sans-serif;color:var(--text);-webkit-font-smoothing:antialiased;position:relative;overflow:hidden}
.card::before{content:"";position:absolute;top:-120px;left:-120px;width:280px;height:280px;background:radial-gradient(circle,var(--accent-soft),transparent 70%)}
.eyebrow{font-family:'JetBrains Mono',monospace;font-weight:500;font-size:13px;letter-spacing:.18em;text-transform:uppercase;color:var(--accent)}
h1{font-size:46px;line-height:1.05;font-weight:800;letter-spacing:-.02em;margin:18px 0 14px}
.sub{font-size:18px;line-height:1.45;color:var(--muted);max-width:90%}
.rule{width:48px;height:3px;background:var(--accent);border-radius:99px;margin:26px 0 22px}
.beats{display:flex;flex-direction:column;gap:18px;flex:1}
.beat{display:flex;gap:16px;align-items:flex-start}
.num{font-family:'JetBrains Mono',monospace;font-weight:700;font-size:15px;color:var(--accent);min-width:26px;padding-top:3px}
.beat .t{font-size:18px;font-weight:700;line-height:1.25}
.beat .d{font-size:15px;color:var(--muted);line-height:1.4;margin-top:3px}
.takeaway{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:18px 20px;margin-top:8px;font-size:16px;line-height:1.45}
.takeaway b{color:var(--accent);font-weight:700}
footer{display:flex;justify-content:space-between;align-items:center;margin-top:24px;font-family:'JetBrains Mono',monospace;font-size:12.5px;color:var(--muted)}
.mark{display:inline-flex;align-items:center;gap:8px;color:var(--text);font-weight:700}
.dot{width:11px;height:11px;border-radius:3px;background:var(--accent)}
</style></head><body><div class="card">
<div class="eyebrow">{EYEBROW}</div>
<h1>{HOOK}</h1>
<div class="sub">{SUB}</div>
<div class="rule"></div>
<div class="beats">{BEATS}
<div class="takeaway">{TAKEAWAY}</div>
</div>
<footer><span class="mark"><span class="dot"></span>{HANDLE}</span><span>built with Claude · Codex · OpenCode</span></footer>
</div></body></html>"""


def esc(s: str, allow_br: bool = False) -> str:
    s = html_lib.escape(s, quote=False)
    if allow_br:
        s = s.replace("&lt;br&gt;", "<br>")
    return s


def bold(s: str) -> str:
    s = esc(s)
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)


def build_html(d: dict) -> str:
    beats_html = ""
    for i, (t, det) in enumerate(d["beats"], 1):
        beats_html += (
            f'\n<div class="beat"><div class="num">{i:02d}</div><div>'
            f'<div class="t">{esc(t)}</div><div class="d">{esc(det)}</div></div></div>'
        )
    return (
        TEMPLATE
        .replace("{EYEBROW}", esc(d["eyebrow"]))
        .replace("{HOOK}", esc(d["hook"], allow_br=True))
        .replace("{SUB}", esc(d["sub"]))
        .replace("{BEATS}", beats_html)
        .replace("{TAKEAWAY}", bold(d["takeaway"]))
        .replace("{HANDLE}", HANDLE)
    )


def gather_material(vault: pathlib.Path) -> str:
    # SAFETY: only read the daily decision log + the creator profile. Deliberately
    # EXCLUDE deep-internal notes (systems/, models/, qpay/, internal/) — those hold
    # employer architecture that must never reach a public-facing draft. The decision
    # log can still contain work specifics, so the prompt enforces a hard confidentiality
    # guardrail on top, and the human reviews every draft before posting.
    chunks = []
    for f in sorted(glob.glob(str(vault / "decisions/*.md")))[-3:]:
        chunks.append(pathlib.Path(f).read_text(errors="ignore"))
    p = vault / "profile/creator-journey.md"
    if p.exists():
        chunks.append(p.read_text(errors="ignore"))
    return "\n\n---\n\n".join(chunks)[:120_000]


PROMPT = f"""You are the content strategist for {HANDLE}, a software engineer building in
public on X about AI agents, dev tooling, and productivity. Audience: English-speaking
developers (mostly US). Brand voice: clean, direct, specific, lightly opinionated, NO hype,
no emoji. Show the HOW, name real tools, give one concrete number when possible.

=== CONFIDENTIALITY — NON-NEGOTIABLE ===
The work notes below may contain the user's EMPLOYER's confidential details. These must NEVER
appear in a draft (drafts are for PUBLIC posting):
- company / product / brand names, or internal repo names
- internal database schema, table/column names, service names, API shapes
- proprietary architecture, business logic, CI/build/infra specifics, settlement/ledger/payment internals
Write ONLY about GENERAL, transferable techniques OR the user's OWN general/personal tooling
(e.g. his AI-agent memory setup, local-model workflow, generic Docker/CI lessons stated in
universal terms). If an item cannot be shared without revealing employer specifics, SKIP it
entirely — produce fewer drafts rather than leak. Generalize: "a service" not the real name,
"a build" not the internal pipeline. When in doubt, leave it out.
=== END CONFIDENTIALITY ===

From the raw work notes below, write {N_DRAFTS} DISTINCT post drafts for tomorrow. Pick the
most genuinely interesting, differentiated angles — real specifics from the notes, not generic
tips. Each draft pairs a caption with a branded one-pager image in a fixed "numbered build-log"
format, so give exactly these fields.

Output EXACTLY this delimited format, nothing else (no markdown, no commentary):

@@@DRAFT@@@
WINDOW: <one of: 9am ET | 12pm ET | 6pm ET>
CAPTION:
<2-5 short lines, <=270 chars total, build-in-public voice, last line a soft lead-in to the image>
EYEBROW: <short mono label, e.g. BUILD LOG / HOW I DID IT / LESSON>
HOOK: <headline, <=7 words, you may use one <br> to balance two lines>
SUB: <one clarifying line>
BEAT: <title> :: <one-line detail>
BEAT: <title> :: <one-line detail>
BEAT: <title> :: <one-line detail>
TAKEAWAY: <payoff line; wrap ONE key word in **double asterisks**>
@@@END@@@

Use 3 or 4 BEAT lines per draft. Keep every line tight enough to fit a card.
"""


def parse_drafts(text: str) -> list[dict]:
    drafts = []
    blocks = re.findall(r"@@@DRAFT@@@(.*?)@@@END@@@", text, re.S)
    for b in blocks:
        d = {"window": "9am ET", "caption": "", "eyebrow": "BUILD LOG",
             "hook": "", "sub": "", "beats": [], "takeaway": ""}
        # caption spans multiple lines until the next FIELD: marker
        cap = re.search(r"CAPTION:\s*(.*?)\n(?:EYEBROW|WINDOW|HOOK):", b, re.S)
        if cap:
            d["caption"] = cap.group(1).strip()
        for line in b.splitlines():
            line = line.strip()
            if line.startswith("WINDOW:"):
                d["window"] = line[7:].strip() or d["window"]
            elif line.startswith("EYEBROW:"):
                d["eyebrow"] = line[8:].strip() or d["eyebrow"]
            elif line.startswith("HOOK:"):
                d["hook"] = line[5:].strip()
            elif line.startswith("SUB:"):
                d["sub"] = line[4:].strip()
            elif line.startswith("BEAT:"):
                body = line[5:].strip()
                if "::" in body:
                    t, det = body.split("::", 1)
                    d["beats"].append((t.strip(), det.strip()))
            elif line.startswith("TAKEAWAY:"):
                d["takeaway"] = line[9:].strip()
        if d["hook"] and d["beats"]:
            drafts.append(d)
    return drafts


def render_png(html_path: pathlib.Path, png_path: pathlib.Path) -> bool:
    try:
        subprocess.run(
            [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
             "--force-device-scale-factor=2", "--window-size=640,800",
             "--default-background-color=0A0C10FF", "--virtual-time-budget=3000",
             f"--screenshot={png_path}", f"file://{html_path}"],
            capture_output=True, timeout=90,
        )
        return png_path.exists()
    except Exception as e:
        log(f"render failed: {e}")
        return False


def main() -> int:
    vault = vault_path()
    date = datetime.date.today().isoformat()
    out = HOME / "Desktop/x-drafts" / date
    out.mkdir(parents=True, exist_ok=True)
    log(f"=== run {date} · vault={vault} ===")

    # Throttle: also runs on login (catch-up). Skip if today's packet is <6h old.
    force = "--force" in sys.argv
    packet = out / "drafts.md"
    if not force and packet.exists():
        age_h = (datetime.datetime.now().timestamp() - packet.stat().st_mtime) / 3600
        if age_h < 6:
            log("drafts <6h old; skipping (use --force to override)")
            return 0

    material = gather_material(vault)
    if len(material) < 200:
        log("not enough vault material; abort")
        return 0

    brand = BRAND.read_text() if BRAND.exists() else ""
    stdin = f"BRAND SPEC (voice reference):\n{brand}\n\nWORK NOTES:\n{material}"
    try:
        res = subprocess.run([str(CLAUDE), "-p", PROMPT], input=stdin,
                             capture_output=True, text=True, timeout=600)
    except Exception as e:
        log(f"claude failed: {e}")
        return 1
    drafts = parse_drafts(res.stdout)
    log(f"parsed {len(drafts)} drafts")
    if not drafts:
        log(f"no drafts parsed; raw head: {res.stdout[:400]!r}")
        return 1

    review = [f"# X drafts — {date}\n",
              "_Auto-drafted while you slept. Review, tweak, then schedule the good ones "
              "via X's native scheduler (calendar icon in the composer). Nothing was posted._\n"]
    for i, d in enumerate(drafts, 1):
        html_path = out / f"draft{i}.html"
        png_path = out / f"draft{i}.png"
        html_path.write_text(build_html(d))
        ok = render_png(html_path, png_path)
        review += [
            f"\n## Draft {i} — suggested window: {d['window']}\n",
            "**Caption** (copy-paste):\n```\n" + d["caption"] + "\n```",
            f"**Image:** `{png_path.name}`" + ("" if ok else "  ⚠️ render failed"),
            "\n---",
        ]
    (out / "drafts.md").write_text("\n".join(review))
    log(f"wrote {len(drafts)} drafts to {out}")
    print(f"{len(drafts)} drafts -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
