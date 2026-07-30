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

## Runtime mechanics
- `codex exec --sandbox workspace-write -C <repo> "<brief>"` is the headless delegation
  entrypoint (`--full-auto` is deprecated). When the caller reviews the result, the brief
  must say "do not commit" — leave changes uncommitted.
- `config.toml` `notify` accepts a SINGLE program — to add behavior, wrap it
  (`~/.codex/hooks/notify-wrapper.py` forwards to the original notifier first, then acts).
  Subagent threads write their own rollouts under `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl`
  (never pruned) with `turn_context.model` and `token_count` events — parsed into the
  per-subagent usage log at `~/.codex/log/subagent-usage.log`. That log records **cumulative
  telemetry snapshots**, not one line per run (durations bogus, e.g. `371m` on a short run):
  count cross-check only, never a 1:1 join.
- `session_meta.payload.source.subagent` is a **tagged union**, not a flat record:
  `thread_spawn.agent_role` (custom agents) vs `other: "guardian"` (the built-in auto-review
  gate). Parsing only the first arm silently drops guardian. Guardian emits per-turn records —
  dedupe by `session_id`, not record (8 rollouts → 6 sessions; naive counting gave 199).
  `parent_thread_id` gives parent correlation.
