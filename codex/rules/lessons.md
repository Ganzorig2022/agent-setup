# Codex — Standing Lessons

Curated, durable facts only — the Codex analog to Claude's `~/.claude/agent-memory/STATE.md`
*Lessons Learned*. Not a session journal. Keep lean. QPay stack facts live in `rules/qpay/`;
general rules in `rules/common/`; this file is for cross-cutting tooling/workflow lessons.

## Memory & config topology
- Codex runtime/agent state is in sqlite (`~/.codex/{memories,goals,state}_*.sqlite`); curated
  human-readable standing facts live in `~/.codex/rules/` (`qpay/` stack facts, `common/` general
  rules, this file). Hand-edit the markdown; leave the sqlite stores to the runtime.

## Cross-tool source-of-truth
- Reviewer agents are mirrored across tools: `~/.codex/agents/*.toml` are ports of
  `~/.claude/agents/*.md`. The Claude `.md` is the source of truth — when a reviewer prompt
  changes, edit the Claude `.md` first, then sync the `.toml` body (keep its
  `## Codex Compatibility` footer last). See QPay/AGENTS.md "Review layer".
- `/Users/dev/QPay/AGENT_GUIDE.md` is the QPay workspace handoff authority for planner →
  implementer → reviewer flows.
