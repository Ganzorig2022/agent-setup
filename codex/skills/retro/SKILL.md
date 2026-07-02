---
name: retro
description: Close the learning loop at the end of a Codex task or session — harvest durable standing facts from the conversation and curate them into the right memory file, pruning anything stale. Use when wrapping up work, when the user says "retro", "capture learnings", or before ending a long session. Keeps memory lean by design.
---

# Retro — Capture Standing Facts Into Memory (Codex edition)

Memory only compounds if something writes to it. The rules files are read into every
session but **nothing updates them automatically** — this skill is that step. Run it to
turn what was learned this session into durable, reusable facts so a future agent doesn't
re-derive them (or repeat a mistake).

Note: the nightly `daily-decisions` harvester already journals Codex sessions into the
knowledge vault (qmd-searchable). This skill is NOT that journal — it curates the small,
always-loaded standing-facts files.

## The bar — what qualifies as a standing fact

A fact earns a place in memory only if it is **durable AND reusable**:

- ✅ Stack/config truths ("X service uses Bull, not BullMQ"), tooling mechanics that
  surprised us, conventions, gotchas that will recur, locations of authoritative files.
- ❌ Session journal entries ("fixed bug in file Y today"), one-off task details, anything
  tied to a single PR/ticket, anything already stated in an existing memory file, speculation.

When unsure, leave it out. A lean memory that's all signal beats a bloated one nobody trusts.

## Memory map — route each fact to the correct file

| Fact type | Target |
|-----------|--------|
| Codex tooling/config mechanics | `~/.codex/rules/lessons.md` |
| QPay backend/frontend stack facts | EDIT `~/.claude/qpay-context/backend.md` / `frontend.md`, then `cp` to `~/.codex/rules/qpay/` (the Codex copies are byte-identical mirrors — never edit them directly) |
| Cross-tool workflow / handoff rules | `/Users/dev/QPay/AGENTS.md` or `~/.codex/AGENTS.md` |
| Claude-internal mechanics | — none. Do NOT write Claude's files (`~/.claude/agent-memory/STATE.md` is curated from Claude's own `/retro`) |

Rules:
- **Respect ecosystem boundaries.** Codex-internal mechanics (config.toml, sandbox modes,
  .toml agents) are NOT Claude facts. Only stack facts, conventions, and cross-tool
  workflow rules belong in shared files.
- **Keep the qpay mirrors byte-identical.** Always edit the Claude-side source and copy;
  `diff ~/.claude/qpay-context/backend.md ~/.codex/rules/qpay/backend.md` must stay empty.
- Do not invent symmetry. If a session produced no durable fact, write nothing.

## Procedure

1. **Scan the session.** Identify candidate facts that meet the bar above. Prefer 0–6
   high-value items over a long list.
2. **Dedupe against existing memory.** Read the target file(s) first. Skip anything already
   captured; if a candidate refines an existing entry, propose an edit, not a duplicate.
3. **Route** each surviving fact via the memory map.
4. **Prune.** While in each file, flag entries that are now stale, contradicted, or no
   longer reusable, and propose removing them. Memory health = adding AND removing.
5. **Propose, then write.** Show the user the exact additions/edits/removals per file and
   get approval before writing. One concise diff summary, not a wall of text.
6. **Write** the approved changes. Keep each entry to one terse line where possible.

## Guardrails

- Never let a memory file become a changelog. If `lessons.md` grows past ~12 entries,
  consolidate or graduate items into more specific rules files.
- Never write secrets, credentials, tokens, or PII into memory.
- If nothing this session meets the bar, say so and write nothing — that is a valid retro.
