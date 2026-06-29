---
name: retro
description: Close the learning loop at the end of a task or session — harvest durable standing facts from the conversation and curate them into the right memory file for Claude and Codex, pruning anything stale. Use when wrapping up work, when the user says "retro", "capture learnings", "update memory/STATE", or before ending a long session. Keeps memory lean by design.
---

# Retro — Capture Standing Facts Into Memory

Memory only compounds if something writes to it. STATE.md and the Codex rules files are
read into every session but **nothing updates them automatically** — this skill is that step.
Run it to turn what was learned this session into durable, reusable facts so a future agent
doesn't re-derive them (or repeat a mistake).

## The bar — what qualifies as a standing fact

A fact earns a place in memory only if it is **durable AND reusable**:

- ✅ Stack/config truths ("X service uses Bull, not BullMQ"), tooling mechanics that surprised
  us, conventions, gotchas that will recur, locations of authoritative files.
- ❌ Session journal entries ("fixed bug in file Y today"), one-off task details, anything
  tied to a single PR/ticket, anything already stated in an existing memory file, speculation.

When unsure, leave it out. A lean memory that's all signal beats a bloated one nobody trusts.

## Memory map — route each fact to the correct file

| Fact type | Claude target | Codex target |
|-----------|---------------|--------------|
| QPay backend/frontend stack facts | `~/.claude/qpay-context/backend.md` · `frontend.md` | `~/.codex/rules/qpay/backend.md` · `frontend.md` |
| General QPay standing facts | `~/.claude/agent-memory/STATE.md` → *Verified Facts* | `~/.codex/rules/qpay/` (nearest file) |
| Claude Code tooling/config mechanics | `~/.claude/agent-memory/STATE.md` → *Lessons Learned* | — (Claude-specific, do not copy) |
| Codex tooling/config mechanics | — (Codex-specific) | `~/.codex/rules/lessons.md` |
| Cross-tool workflow / handoff rules | `~/.claude/CLAUDE.md` or STATE.md | `~/.codex/AGENTS.md` or `/Users/dev/QPay/AGENTS.md` |

Rules:
- **Respect ecosystem boundaries.** Claude-internal mechanics (subagent loading, `model:`
  frontmatter, `@import` behavior) are NOT Codex facts — never copy them across. Only
  stack facts, conventions, and cross-tool workflow rules belong in both.
- **Keep stack facts in sync.** If a QPay stack fact changes, update both the Claude
  `qpay-context/` file and the Codex `rules/qpay/` file.
- Do not invent symmetry. If a session produced no durable Codex fact, write nothing to Codex.

## Procedure

1. **Scan the session.** Identify candidate facts that meet the bar above. Prefer 0–6 high-value
   items over a long list.
2. **Dedupe against existing memory.** Read the target file(s) first. Skip anything already
   captured; if a candidate refines an existing entry, propose an edit, not a duplicate.
3. **Route** each surviving fact to its target file via the memory map.
4. **Prune.** While in each file, flag entries that are now stale, contradicted, or no longer
   reusable, and propose removing them. Memory health = adding AND removing.
5. **Propose, then write.** Show the user the exact additions/edits/removals per file and get
   approval before writing. One concise diff summary, not a wall of text.
6. **Write** the approved changes. Keep each entry to one terse line where possible.

## Guardrails

- Never let a memory file become a changelog. If *Lessons Learned* grows past ~12 entries,
  consolidate or graduate items into the more specific context files.
- Never write secrets, credentials, tokens, or PII into memory.
- If nothing this session meets the bar, say so and write nothing — that is a valid retro.
