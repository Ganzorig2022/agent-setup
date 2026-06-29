---
description: Safely identify and remove unused JavaScript/TypeScript code with validation after each change.
argument-hint: "[path | scope | optional cleanup goal]"
---

# Clean Dead Code

Safely identify and remove unused JavaScript/TypeScript code with validation after each change.

This command is for cleanup only. Do not refactor behavior, rename APIs, redesign architecture, or introduce unrelated improvements.

## Scope

Target JavaScript and TypeScript projects.

Do not run tools for languages that are not present in the repository.

Do not install new dependencies unless the user explicitly approves.

## Step 1: Inspect Project Type

Before running cleanup tools, inspect the repository:

- `package.json`
- lockfile: `package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`, or `bun.lockb`
- `tsconfig.json`
- ESLint config
- test configuration
- source directories
- framework conventions

Determine:

- package manager
- available scripts
- whether TypeScript is used
- whether ESLint is configured
- whether tests exist
- whether the project has dynamic routing, file-based routing, plugins, generated files, or public package exports

## Step 2: Establish Baseline

Run the safest available validation commands before deleting anything.

Prefer existing scripts from `package.json`:

```bash
npm run lint
npm run typecheck
npm test
```

Use the package manager already used by the project.

```bash
pnpm lint
pnpm typecheck
pnpm test
```

If no scripts exist, use direct checks only when relevant:

```bash
npx tsc --noEmit
npx eslint .
```

If validation fails at baseline, stop. Report the existing failures and do not delete code.

## Step 3: Detect Unused Code

Use only tools already configured or safe built-in checks.

Preferred Detection Sources

| Source                       | What It Finds                               | Use when                                            |
| ---------------------------- | ------------------------------------------- | --------------------------------------------------- |
| EsLint with `no-unused-vars` | unused variables, functions, imports        | ESLint is already configured and includes this rule |
| TypeScript compiler          | unused locals, unused parameters if enabled | TypeScript is used                                  |
| IDE/compiler diagnostics     | obvious unused symbols                      | available from existing setup                       |
| grep/search                  | candidate unused exports/files              | no dedicated tool exists                            |

### Optional Tools

Only use these if already installed, already configured, or explicitly approved by the user:

| Tool     | What It Finds                         | Command        |
| -------- | ------------------------------------- | -------------- |
| ts-prune | potentially unused TypeScript exports | `npx ts-prune` |
| knip     | unused files, exports, dependencies   | `npx knip`     |
| depcheck | unused npm dependencies               | `npx depcheck` |

Do not add these tools to the project without approval.

## Step 4: Categorize Findings

Sort each candidate into a safety tier.

| Tier    | Examples                                                                                               | Action                                  |
| ------- | ------------------------------------------------------------------------------------------------------ | --------------------------------------- |
| SAFE    | unused local variables, unused imports, private helper functions used nowhere                          | delete one at a time                    |
| CAUTION | exported functions, React/Vue/Svelte components, hooks, route handlers, CLI commands                   | verify references manually              |
| DANGER  | config files, entry points, package exports, framework files, migrations, generated types, public APIs | do not delete without explicit approval |

## Step 5: Check Dynamic References

Before deleting CAUTION or DANGER candidates, search for indirect references:

```bash
grep -R "SymbolName" .
grep -R "file-name" .
grep -R "route-name" .
grep -R "import(" .
grep -R "require(" .
```

Also inspect:

- framework routing conventions
- package exports
- CLI bin entries
- config references
- test fixtures
- generated code references
- documentation examples
- external package/public API usage

If uncertain, skip the item.

## Step 6: Safe Deletion Loop

For each SAFE item:

1. Confirm the baseline is clean.
2. Delete exactly one logical item.
3. Run the most relevant validation command.
4. If validation fails, revert only that change.
5. If validation passes, continue to the next item.

Use the smallest safe edit.

Do not batch many deletions before validation unless the user explicitly asks for speed over safety.

## Step 7: Dependency Cleanup

Only remove dependencies when all of the following are true:

- the dependency is reported unused,
- no config or runtime string reference exists,
- no framework/plugin convention requires it,
- lockfile update is understood,
- validation passes after removal.

Use the project package manager:

```bash
npm uninstall package-name
pnpm remove package-name
bun remove package-name
```

Do not remove dependencies from package.json manually unless the package manager is unavailable.

## Step 8: Summary

Report results:

```text
Dead Code Cleanup
──────────────────────────────
Deleted:
- 3 unused imports
- 2 unused helper functions
- 1 unused file

Skipped:
- 1 exported component: possible dynamic route reference
- 1 dependency: referenced by config

Validation:
- lint: pass
- typecheck: pass
- tests: pass

Remaining risks:
- ...
──────────────────────────────
```

Rules

- Never delete code before establishing a baseline.
- Never proceed if baseline validation already fails.
- Delete one logical item at a time.
- Prefer existing project scripts over new tools.
- Do not install cleanup tools without explicit approval.
- Skip uncertain items.
- Do not refactor while cleaning.
- Do not change behavior.
- Do not remove public APIs without explicit approval.
- Do not delete generated files unless the generation process is understood.
