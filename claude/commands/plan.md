---
description: Restate requirements, inspect repo patterns, assess risks, and create an implementation plan. Wait for explicit confirmation before editing code.
argument-hint: "[feature description | bug description | refactor request | path/to/context.md]"
---

# Plan Command

Create a clear implementation plan before writing or modifying code.

Do not edit files.
Do not run destructive commands.
Do not call subagents by default.
Do not proceed to implementation until the user explicitly confirms with words like `yes`, `proceed`, `implement`, or `continue`.

## When to Use

Use `/plan` when:

- starting a new feature
- fixing a non-trivial bug
- refactoring multiple files
- changing architecture or behavior
- requirements are unclear
- tests, migrations, scripts, or config may be affected

For tiny edits, avoid over-planning. State that the task is small and propose a minimal plan.

## Input Modes

| Input | Mode | Behavior |
|---|---|---|
| Free-form text | Request mode | Plan from the provided requirement |
| Markdown file path | Context mode | Read the file and plan from its contents |
| Empty input | Clarification mode | Ask what should be planned |

## Required Process

### 1. Restate the Request

Summarize the user's goal in concrete terms.

Include:

- desired behavior
- affected area
- explicit non-goals, if any
- assumptions

If requirements are ambiguous, list the ambiguity instead of pretending it is solved.

### 2. Inspect Existing Patterns

Before proposing implementation details, inspect relevant files in the repository.

Capture patterns for:

| Category | What to inspect |
|---|---|
| Naming | files, commands, scripts, functions, types |
| Structure | directories, modules, config layout |
| Error handling | exits, exceptions, user-facing messages |
| Logging/output | command output style and verbosity |
| Tests/validation | test framework, lint commands, check scripts |
| Install behavior | shell scripts, backup behavior, target paths |

If no similar pattern exists, say so explicitly.

Do not invent repository conventions.

### 3. Identify Files to Change

List likely file changes.

Use this format:

| File | Action | Reason |
|---|---|---|
| `path/to/file` | CREATE / UPDATE / DELETE | why this file is needed |

### 4. Create the Implementation Plan

Break the work into ordered phases.

Each phase must include:

- goal
- concrete edits
- pattern to mirror
- validation command

### 5. Assess Risk

Use this table:

| Risk | Severity | Mitigation |
|---|---|---|
| description | Low / Medium / High | mitigation |

Include risks around:

- breaking existing install behavior
- overwriting user config
- inconsistent Claude/Codex behavior
- missing validation
- unclear requirements

### 6. Define Validation

List exact commands the user or assistant should run.

Prefer repository-local commands, for example:

```bash
bash scripts/check.sh
bash scripts/install.sh --target claude --backup
ls -1 ~/.claude/commands