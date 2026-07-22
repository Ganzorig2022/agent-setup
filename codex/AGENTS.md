# Global Codex Instructions

## Local Codex Stack

Treat `~/.codex` as a portable config tree, not just a single `AGENTS.md`.

When local repo-managed content exists under `~/.codex`, use it as the first customization layer before falling back to global defaults:

- `~/.codex/skills/` for reusable workflow skills
- `~/.codex/rules/` for concise rule documents
- `~/.codex/commands/` for promptable command templates, if supported by the client
- `~/.codex/agents/` for agent-specific handoff or review prompts, if supported by the client

Prefer repository-managed Codex content when it is directly relevant to the task.

If multiple local content types exist, use the narrowest one that fits:

1. skill for a workflow
2. rule for a compact constraint layer
3. command for a repeatable prompt template
4. agent prompt for planner/reviewer/handoff specialization

Do not assume the Codex stack is limited to the current set of folders. New local content may be added over time.

## Operating Model

Use a planner / executor / reviewer workflow for non-trivial work.

The planner, executor, and reviewer may be Codex, Claude, or another coding agent depending on the user's workflow.

Do not assume Claude is always the planner.
Do not assume Codex is always the executor.
When receiving a handoff plan, follow it precisely unless it conflicts with repository reality.

Before a non-trivial task (especially QPay work), query the `qmd` knowledge-base MCP server (its `query`/`get` tools) for prior decisions, patterns, and gotchas, and factor them in — it holds the auto-harvested decision log plus engineering notes. Skip for trivial one-liners; proceed normally and silently if it returns nothing relevant.

For current third-party library/framework/SDK APIs (versions, signatures, new or changed behavior), consult the `context7` MCP server (its `resolve-library-id` then `query-docs` tools) before coding from memory — it fetches up-to-date, version-specific documentation. Use it for non-trivial library or integration work; skip well-known stable basics.

## Planning Gate

Create an implementation plan before editing files when the task involves any of the following:

- multiple files
- architecture, framework, or dependency changes
- database schema, migrations, storage, or data model changes
- authentication, authorization, payments, security, privacy, or permissions
- public API, CLI, config, or behavior changes
- tests, CI, release, deployment, or installer behavior
- destructive operations or file moves/deletions
- unclear requirements or hidden assumptions
- production-impacting risk

For small, obvious, single-file edits, use a minimal plan inline and proceed only if the user did not explicitly request a separate planning step.

A plan must include:

- requirement restatement
- assumptions and open questions
- existing repository patterns to mirror
- files likely to change
- phased implementation steps
- validation commands
- risks and mitigations
- acceptance checklist

Do not edit files after producing a plan unless the user explicitly confirms with words such as `proceed`, `implement`, `continue`, or equivalent intent.

If a user provides a handoff plan, first verify it against repository reality. If the plan is stale, incomplete, or conflicts with the codebase, explain the conflict before changing files.

## Execution Rules

- Prefer minimal, focused changes.
- Follow existing repository conventions.
- Do not introduce unrelated improvements.
- Do not rewrite architecture unless explicitly required.
- Preserve stated non-goals.
- Ask only when blocked by missing information.
- Validate changes with the most relevant available commands.
- If validation cannot be run, explain why.
- Do not use destructive commands unless explicitly requested or clearly required and safe.
- For GitHub work (issues, PRs, comments, workflow/CI runs, releases) use `gh-axi` as the go-to tool — it is the shared standard across all agents (Claude, Codex, OpenCode), not just a `gh` substitute. Prefer compact structured output and targeted queries over full logs/JSON dumps.

## Code Standards

- Validate input at system boundaries.
- Avoid mutating shared state or caller-owned data.
- Prefer clear code over clever abstractions.
- Keep functions focused and files cohesive.
- Handle errors explicitly.
- Do not silently swallow failures.
- Avoid hardcoded secrets, credentials, private URLs, and environment-specific assumptions.
- Preserve backward compatibility unless the user explicitly requests a breaking change.

## Reviewer Rules

When reviewing changes, prioritize findings in this order:

1. correctness
2. security and privacy
3. data loss or migration risk
4. compatibility and public behavior
5. test coverage
6. maintainability
7. style

Do not approve a diff merely because it matches the plan. The codebase is the source of truth.

## After Implementation

Summarize:

- files changed
- behavior changed
- tests or checks run
- checks not run and why
- remaining risks
- suggested reviewer focus

## Dead Code Cleanup

For dead-code cleanup, prefer existing JavaScript/TypeScript validation scripts before using external tools.

Do not run language-specific tools for languages not present in the repository.

Before deleting code:

- establish a clean baseline with available lint, typecheck, and test commands
- classify findings as SAFE, CAUTION, or DANGER
- delete one logical item at a time
- validate after each deletion
- revert immediately if validation fails
- skip uncertain items

Do not install tools such as `knip`, `ts-prune`, or `depcheck` unless the user explicitly approves.
Do not refactor behavior while removing dead code.

## Global Customization Discovery

Global Codex customization is intentionally split by purpose:

- `/Users/dev/.codex/rules/common/` contains compact rules. Read the relevant rule before work that matches its topic.
- `/Users/dev/.codex/skills/` contains reusable workflows. Prefer a skill when the task matches its `SKILL.md` description.
- `/Users/dev/.codex/commands/` contains repeatable prompt templates. Use them as command-style workflows when the client supports them, or as reference prompts otherwise.
- `/Users/dev/.codex/agents/` contains native Codex custom agents as `.toml` files. Use these for explicit subagent requests and specialist review/implementation lanes.

Specialist agent routing:

- `planner`: complex implementation plans, migrations, refactors, unclear requirements.
- `architect`: architecture boundaries, tradeoffs, system design, scalability.
- `code-reviewer`: review after meaningful code changes.
- `typescript-reviewer`: TypeScript or JavaScript changes.
- `react-reviewer`: React, JSX, TSX, Next.js component changes.
- `security-reviewer`: auth, authorization, payments, secrets, sensitive data, APIs, file uploads, external URLs.
- `build-error-resolver`: build, typecheck, bundler, dependency, or CI compilation failures.
- `refactor-cleaner`: behavior-preserving cleanup and dead-code removal.
- `tdd-guide`: explicit test-first work.
- `doc-updater`: README, API docs, codemaps, examples, changelog updates.
- `e2e-runner`: Playwright or browser E2E creation, execution, or debugging.
- `react-specialist`: React implementation, hook correctness, accessibility, and render behavior fixes.
- `python-pro`: Python services, scripts, packaging, typing, async behavior, and tests.
- `nextjs-developer`: Next.js App Router, Server Components, server actions, API routes, and deployment behavior.
- `sql-pro`: SQL, migrations, schema safety, indexes, transactions, and query performance.
- `devops-engineer`: CI/CD, deployment automation, environment config, observability, and release safety.
- `docker-expert`: Dockerfiles, Compose, build caching, runtime config, image security, and container workflows.
- `multi-agent-coordinator`: parallel subagent coordination, result synthesis, conflict detection, and follow-up routing.
- `task-distributor`: splitting complex work into independent, verifiable tasks with dependencies and done criteria.
- `workflow-orchestrator`: choosing planner/executor/reviewer loops, quality gates, and staged delivery sequence.

Legacy Markdown prompts migrated from Claude are archived under `/Users/dev/.codex/agents-md-legacy/`. Active Codex agents are the TOML files in `/Users/dev/.codex/agents/`. Codex system, developer, and repository instructions still take precedence.

## QPay Project Rules

When working in any repository under `/Users/dev/QPay/`, read the matching rule file **before writing any code**:

- Backend work (Express / Fastify / Bull / Joi / Zod) → read `~/.codex/rules/qpay/backend.md`
- Frontend work (Next.js / React / AntD / Tailwind / Radix) → read `~/.codex/rules/qpay/frontend.md`

### Stack detection from `package.json`

**Backend:**
- `qpay-sequelize-postgres` → Stack A: Express 5 / Babel / PostgreSQL / Joi / Bull 4.x / qpay-micro-logging
- `mongoose` → Stack B: Express 5 / Babel / MongoDB / Joi / Bull 4.x
- `fastify` → Stack C: Fastify 5 / TypeScript / Zod / BullMQ

**Frontend:**
- `@radix-ui/react-*` or `next` ≥ 15 → Gen 3: Next.js 15+ / React 19 / Tailwind / Radix UI / TanStack Query v5
- `antd` ≥ 5 + `redux` → Gen 1.5: Next.js 12 / React 18 / AntD 5 / TanStack Query v5
- `antd` ≤ 4 + `redux` → Gen 1: Next.js 12 / React 17 / AntD 4 / SWR
- `tailwindcss` + `zustand` (no Radix) → Gen 2: Next.js 13–14 / Tailwind / Zustand

### Non-negotiable QPay conventions

Stack A/B (Express 5 / Babel):
- `qpay-micro-logging` for all logging — never `console.log`
- No `try/catch` in route handlers — Express 5 catches async throws natively
- Joi schema at route entry only (`stripUnknown: true`) — never validate in the service layer
- Service functions receive plain data, return plain data — no `req`/`res`/`next`
- Config from `src/config/` — never read `process.env` directly in services
- Lint: `npx eslint --fix` only — no standalone prettier

Stack C (Fastify / TypeScript):
- Zod schema (`z.object({ ... }).strict()`) at route entry
- `fastify-type-provider-zod` for type inference
- `npx tsc --noEmit` must pass before submitting

Frontend (all gens):
- Never mutate Redux or Zustand state directly
- AntD Gen 1: top-level imports only — never `antd/lib/*`
- Gen 3: TanStack Query v5 API — `useQuery({ queryKey, queryFn })` not the v3 form
- No `Date.now()` / `Math.random()` at render time (causes hydration mismatch)
