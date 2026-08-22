---
name: deep-research
description: Multi-source deep research over a free tool ladder (homelab SearXNG, WebSearch, WebFetch, Jina Reader, scrape.do, Chrome). Searches the web, synthesizes findings, and delivers cited reports with source attribution. Use when the user wants thorough research on any topic with evidence and citations.
origin: ECC
---

# Deep Research

> **Drift-prone skill.** Free-tier quotas, endpoint shapes, and tool names change.
> Verify a tier is actually reachable before promising coverage or quoting live
> source counts. Never claim a source was read if its fetch failed.

Produce thorough, cited research reports from multiple web sources using a
zero-to-low-cost tool ladder. No Firecrawl or Exa MCP is required.

## When to Activate

- User asks to research any topic in depth
- Competitive analysis, technology evaluation, or market sizing
- Due diligence on companies, investors, or technologies
- Any question requiring synthesis from multiple sources
- User says "research", "deep dive", "investigate", or "what's the current state of"

## Tool Ladder

Climb only as far as you must. Every tier below is free; the cost is speed,
quota, or attention. **Start at the cheapest tier that can do the job and stop
as soon as you have the content.**

| # | Tool | Handles | Budget |
|---|------|---------|--------|
| 0 | Homelab SearXNG | search, private + unmetered | unlimited (needs Tailscale) |
| 1 | `WebSearch` | search | unmetered |
| 2 | `WebFetch` | ordinary pages | unmetered |
| 3 | Jina Reader | JS-rendered / SPA pages | ~free (20 req/min keyless) |
| 4 | scrape.do | Cloudflare / WAF / bot walls | ~40 hard fetches/month |
| 5 | Chrome | anything a human browser reaches | unlimited, **main session only** |

Tiers 0–1 are search (finding URLs). Tiers 2–5 are fetch (reading them).

### Tier 0 — Homelab SearXNG (preferred search)

Private meta-search on the homelab, JSON output enabled, no quota, no third
party sees the query. Requires Tailscale up on the Mac and the box awake.

**Preflight — run once per session before relying on it:**
```bash
curl -s -m 10 -o /dev/null -w '%{http_code}' \
  "https://homelab.tailfe4036.ts.net:9443/search?q=ping&format=json"
```
`200` → use it. Anything else (`000` = Tailscale stopped or box asleep) → fall
straight to Tier 1 and say so in the Methodology section. Do not retry more
than once; do not try to start Tailscale yourself.

**Search:**
```bash
curl -s -m 20 --get \
  --data-urlencode "q=<sub-question keywords>" \
  --data-urlencode "format=json" \
  "https://homelab.tailfe4036.ts.net:9443/search" \
  | python3 -c 'import json,sys
for r in json.load(sys.stdin)["results"][:8]:
    print(r["title"]); print("  " + r["url"]); print("  " + r.get("content","")[:200] + "\n")'
```

Optional params: `&categories=news`, `&time_range=year`, `&engines=google,duckduckgo`.

Heavy use can get upstream engines to rate-limit the home IP. If results come
back empty across several queries, drop to Tier 1 rather than hammering it.

### Tier 1 — WebSearch (fallback search)

Built in, no key, no quota worth worrying about. Always available, so this is
the floor the whole skill stands on.

```
WebSearch(query: "<sub-question keywords>")
```

### Tier 2 — WebFetch (default read)

```
WebFetch(url: "<url>", prompt: "<what you need from this page>")
```

Note it answers your prompt via a small model rather than returning raw
markdown. That is usually what you want for research. When you need the actual
text — to quote precisely or to judge whether the page is worth citing — use
Tier 3 instead.

### Tier 3 — Jina Reader (JS-heavy pages)

Renders JavaScript and returns clean markdown. Use when Tier 2 comes back empty,
truncated, or is obviously an app shell.

```bash
curl -s -m 30 "https://r.jina.ai/<full-url-including-https>"
```

Keyless is ~20 req/min. Export `JINA_API_KEY` and add
`-H "Authorization: Bearer $JINA_API_KEY"` to raise it.

### Tier 4 — scrape.do (anti-bot walls)

Residential proxies + JS rendering. Reach for it only when a page is actively
blocking you (403, Cloudflare interstitial, bot challenge).

```bash
curl -s -m 45 --get \
  --data-urlencode "url=<target-url>" \
  "https://api.scrape.do/?token=$SCRAPEDO_TOKEN&render=true&super=true"
```

**Budget discipline.** Credits are not requests: plain datacenter = 1 credit,
`render=true&super=true` = 25. The free tier is 1,000 credits/month, so the
blocked-page mode is worth **~40 fetches per month**. Drop `super=true` (and
then `render=true`) whenever the page does not need them. Requires
`SCRAPEDO_TOKEN` in the environment; if it is unset, skip this tier and record
the source as a gap.

### Tier 5 — Chrome (last resort, main session only)

`chrome-devtools-axi` skill or the Claude-in-Chrome MCP. Real browser, real
cookies, so paywalls and logged-in dashboards work where every tier above fails.
Unlimited but slow and interactive.

**Never used by subagents** — see the parallel section below.

## Workflow

### Step 1: Understand the Goal

Ask 1-2 quick clarifying questions:
- "What's your goal — learning, making a decision, or writing something?"
- "Any specific angle or depth you want?"

If the user says "just research it" — skip ahead with reasonable defaults.

### Step 2: Plan the Research

Break the topic into 3-5 research sub-questions. Example:
- Topic: "Impact of AI on healthcare"
  - What are the main AI applications in healthcare today?
  - What clinical outcomes have been measured?
  - What are the regulatory challenges?
  - What companies are leading this space?
  - What's the market size and growth trajectory?

### Step 3: Execute Multi-Source Search

Run the Tier 0 preflight once. Then for EACH sub-question, search with Tier 0
if it is up, otherwise Tier 1.

**Search strategy:**
- Use 2-3 different keyword variations per sub-question
- Mix general and news-focused queries (`&categories=news` on Tier 0)
- Aim for 15-30 unique sources total
- Prioritize: academic, official, reputable news > blogs > forums

### Step 4: Deep-Read Key Sources

For the most promising URLs, climb the fetch ladder — Tier 2, then 3, then 4 —
stopping at the first tier that returns usable content.

Read 3-5 key sources in full for depth. Do not rely only on search snippets.

If a source defeats Tier 4 (or Tier 4 is unavailable), **record it as a gap and
move on.** Do not block the research run on one source.

### Step 5: Synthesize and Write Report

Structure the report:

```markdown
# [Topic]: Research Report
*Generated: [date] | Sources: [N] | Confidence: [High/Medium/Low]*

## Executive Summary
[3-5 sentence overview of key findings]

## 1. [First Major Theme]
[Findings with inline citations]
- Key point ([Source Name](url))
- Supporting data ([Source Name](url))

## 2. [Second Major Theme]
...

## 3. [Third Major Theme]
...

## Key Takeaways
- [Actionable insight 1]
- [Actionable insight 2]
- [Actionable insight 3]

## Sources
1. [Title](url) — [one-line summary]
2. ...

## Gaps
- [Source or sub-question that could not be covered, and why]

## Methodology
Search tier used: [SearXNG / WebSearch]. Fetch tiers used: [list].
Searched [N] queries. Analyzed [M] sources. [K] sources unreachable.
Sub-questions investigated: [list]
```

Omit the Gaps section only when there genuinely were none.

### Step 6: Deliver

- **Short topics**: Post the full report in chat
- **Long reports**: Post the executive summary + key takeaways, save full report to a file

## Parallel Research with Subagents

For broad topics, use the Task tool to parallelize:

```
Launch 3 research agents in parallel:
1. Agent 1: Research sub-questions 1-2
2. Agent 2: Research sub-questions 3-4
3. Agent 3: Research sub-question 5 + cross-cutting themes
```

Each agent searches, reads sources, and returns findings. The main session
synthesizes into the final report.

**Subagents get tiers 0-4 only.** Chrome is a single shared browser — parallel
agents would fight over tabs, and tab-group IDs go stale between turns. An agent
that cannot reach a source through Tier 4 reports it as a gap and moves on.

After synthesis, the main session decides whether any remaining gap is worth
opening Chrome for manually. Usually it is not.

**Budget warning.** Three agents each escalating to Tier 4 can burn the entire
monthly scrape.do allowance in one run. Instruct agents explicitly: use Tier 4
at most once or twice each, only for sources central to their sub-question.

## Quality Rules

1. **Every claim needs a source.** No unsourced assertions.
2. **Cross-reference.** If only one source says it, flag it as unverified.
3. **Recency matters.** Prefer sources from the last 12 months.
4. **Acknowledge gaps.** If you couldn't find good info on a sub-question, say so.
5. **No hallucination.** If you don't know, say "insufficient data found."
6. **Separate fact from inference.** Label estimates, projections, and opinions clearly.
7. **Never claim an unread source.** If a fetch failed at every tier, it goes in
   Gaps — never in Sources.

## Privacy

Tiers 3 and 4 send the target URL to a third party (Jina, scrape.do), and Tier 4
also sends your token. Public pages only. For anything internal, authenticated,
or client-confidential use Tier 0 for search and Tier 5 for fetch — both stay
under your control.

## Examples

```
"Research the current state of nuclear fusion energy"
"Deep dive into Rust vs Go for backend services in 2026"
"Research the best strategies for bootstrapping a SaaS business"
"What's happening with the US housing market right now?"
"Investigate the competitive landscape for AI code editors"
```
