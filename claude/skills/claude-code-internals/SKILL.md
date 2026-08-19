---
name: claude-code-internals
description: Claude Code configuration and runtime mechanics — how custom subagents load CLAUDE.md and @imports, agent `model:` frontmatter, settings.json hook commands and their output channels, headless `claude -p` permission-mode behaviour, and the SubagentStop payload. Use when editing hooks, settings.json, agent frontmatter, or debugging why a hook/agent/headless run behaves unexpectedly.
---

# Claude Code Internals

Mechanics that surprised us in practice. Each was paid for once; do not re-derive.

## Subagents and memory

- Custom subagents load ~/.claude/CLAUDE.md and its `@imports` (the built-in Explore/Plan agents skip it). Share content into all agents via a file `@import`'d from CLAUDE.md, not per-agent copies — e.g. the deduped Prompt Defense baseline now lives once at ~/.claude/prompt-defense.md.
- STATE.md is a static `@import`, NOT Claude Code's subagent persistent-memory feature (that needs `memory: user|project|local` frontmatter and lives at ~/.claude/agent-memory/<agent>/MEMORY.md). Nothing auto-writes STATE.md — capture learnings with `/retro`.

## Agent frontmatter

- Agent `model:` frontmatter IS honored: `sonnet|opus|haiku|fable|inherit|<full-id>` (defaults to `inherit`).

## Hooks and settings.json

- settings.json hook commands run via shell — write `$HOME/...`, never a hardcoded home path. Hardcoded /Users/dev silently disabled ALL hooks on the Fedora box (no error; hooks just never fire). Hooks load at session start — path fixes need a new session.
- Hook mechanics: output channels — top-level `systemMessage` = user-facing non-blocking; `hookSpecificOutput.additionalContext` = injected for Claude's next request; `decision:"block"`+`reason` (or exit 2) = blocks & feeds Claude. Stop fires every turn-end (no true session-end event) — throttle via marker file; `stop_hook_active` guards recursion. PostToolUse can match a specific tool name (`ExitPlanMode` = fires on plan approval — the "plan is done" interception point); hooks CANNOT add choices to the native plan-approval menu.

## Headless runs

- Headless `claude -p` (and `--agent`) inherits `permissions.defaultMode` — with global "plan", agents write findings to a plan FILE and stdout gets only a handoff line (looks like the agent found nothing). ALWAYS pass `--permission-mode default` in automation; also retry transient "API Error: ConnectionRefused" outputs in long sequential runs.

## SubagentStop

- SubagentStop payload: use `agent_transcript_path` (`transcript_path` = the MAIN session — docs are wrong); the hook can fire before the agent transcript flushes (poll ~3s). `subagentStatusLine` stdin = `{tasks:[{id=agentId, description, tokenCount(live), status}]}` per refresh, output `{"id","content"}` JSON lines; model NOT in payload — read it from the agent transcript.
