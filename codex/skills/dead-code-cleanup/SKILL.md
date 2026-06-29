---
name: dead-code-cleanup
description: Safely identify and remove unused JavaScript or TypeScript code with baseline validation and one logical deletion at a time.
origin: agent-stack
---

# Dead Code Cleanup

Use this skill for cleanup only.

Do not use it to refactor behavior, rename public APIs, redesign architecture, or introduce unrelated improvements.

## Scope

- target JavaScript and TypeScript projects
- prefer existing project tooling
- do not install new cleanup tools unless the user explicitly approves

## Workflow

### 1. Inspect The Project

Check:

- `package.json`
- lockfile
- `tsconfig.json`, if present
- ESLint config, if present
- test configuration
- source directories and framework conventions

Determine:

- package manager
- whether TypeScript is used
- available validation scripts
- whether the project has dynamic routing, public exports, plugins, or generated files

### 2. Establish A Baseline

Run the safest existing validation commands before deleting anything.

Prefer project scripts such as:

- `pnpm lint`
- `pnpm typecheck`
- `pnpm test`

If the baseline already fails, stop and report that state before deleting code.

### 3. Find Candidates

Preferred sources:

- existing ESLint unused-code rules
- TypeScript compiler diagnostics
- project-local search for unused exports or files

Use tools like `knip`, `ts-prune`, or `depcheck` only if they are already installed, already configured, or explicitly approved.

### 4. Classify Risk

- `SAFE`: unused locals, imports, or private helpers with no references
- `CAUTION`: exports, hooks, components, route handlers, CLI commands
- `DANGER`: config files, entry points, framework files, generated artifacts, public APIs

Skip uncertain items.

### 5. Delete Safely

For each `SAFE` item:

1. confirm the baseline is still clean
2. delete one logical item
3. run the most relevant validation
4. revert that deletion immediately if validation fails

Do not batch many deletions unless the user explicitly prefers speed over safety.

### 6. Dependency Removal

Only remove a dependency when:

- it is confirmed unused
- no config or runtime string reference exists
- framework conventions do not require it
- validation passes after removal

Use the project package manager rather than manual `package.json` edits when possible.

## Rules

- never delete before a clean baseline is established
- never assume exported code is unused
- do not remove public APIs without explicit approval
- do not delete generated files unless the generation path is understood
- do not change behavior while cleaning
