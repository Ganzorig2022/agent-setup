# Claude to Codex Customization Migration

Date: 2026-06-19 21:42:53

Backup created at:

`/Users/dev/.codex/backups/codex-customization-before-claude-migration-20260619214147`

## Migrated

- Standalone agents from `/Users/dev/.claude/agents/` to `/Users/dev/.codex/agents/`.
- Command templates from `/Users/dev/.claude/commands/` to `/Users/dev/.codex/commands/`.
- Common rules from `/Users/dev/.claude/rules/common/` to `/Users/dev/.codex/rules/common/`.
- Missing skills from `/Users/dev/.claude/skills/` to `/Users/dev/.codex/skills/`:
  - `agent-architecture-audit`
  - `autonomous-loops`
  - `continuous-agent-loop`
  - `parallel-execution-optimizer`
  - `payment-service-patterns`

## Intentionally Skipped

Claude runtime state was not copied: caches, sessions, projects, file history, backups, security state, tasks, downloads, settings, and logs.

Existing Codex skills were not overwritten. Claude-origin files may still include historical references to Claude-specific tooling where the content is explicitly about Claude workflows.

## Codex Compatibility Notes

- `/Users/dev/.codex/AGENTS.md` now documents how future Codex sessions should discover rules, skills, commands, and agents.
- Copied agent files were converted from Claude-style Markdown prompts into native Codex `.toml` custom agents.
- Legacy Markdown prompts were moved to `/Users/dev/.codex/agents-md-legacy/`.
- Light compatibility edits were made to common rule docs and the `plan` command template.

## Native Codex Agent Conversion

Converted on 2026-06-19:

- 11 migrated Claude agents converted to `/Users/dev/.codex/agents/*.toml`.
- 9 additional Codex agents added:
  - `react-specialist`
  - `python-pro`
  - `nextjs-developer`
  - `sql-pro`
  - `devops-engineer`
  - `docker-expert`
  - `multi-agent-coordinator`
  - `task-distributor`
  - `workflow-orchestrator`
- Global `[agents]` settings were added to `/Users/dev/.codex/config.toml` with `max_threads = 8`, `max_depth = 1`, and `job_max_runtime_seconds = 1800`.
