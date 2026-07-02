# Codex — Standing Lessons

Curated, durable facts only — the Codex analog to Claude's `~/.claude/agent-memory/STATE.md`
*Lessons Learned*. Not a session journal. Keep lean. QPay stack facts live in `rules/qpay/`;
general rules in `rules/common/`; this file is for cross-cutting tooling/workflow lessons.

## Memory & config topology
- Codex runtime/agent state is in sqlite (`~/.codex/{memories,goals,state}_*.sqlite`); curated
  human-readable standing facts live in `~/.codex/rules/` (`qpay/` stack facts, `common/` general
  rules, this file). Hand-edit the markdown; leave the sqlite stores to the runtime.

## Cross-tool source-of-truth
- Agent `.toml`s are mirrored across tools: `~/.codex/agents/*.toml` are regenerated wholesale
  from `~/.claude/agents/*.md` (Claude `.md` = source of truth) — do not hand-edit a ported
  `.toml`; edits are overwritten on resync (agent-setup/scripts/resync-codex-agents.py).
  Likewise `rules/qpay/*.md` are byte-identical mirrors of `~/.claude/qpay-context/` — edit the
  Claude side, then copy. See QPay/AGENTS.md "Review layer".
- `/Users/dev/QPay/AGENT_GUIDE.md` is the QPay workspace handoff authority for planner →
  implementer → reviewer flows.
