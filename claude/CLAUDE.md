# Global Claude Code Instructions

@~/.claude/agent-memory/STATE.md
@~/.claude/prompt-defense.md

## Environment
- Projects: `/Users/dev/QPay` — Node.js/TypeScript microservices + Next.js/React frontends
- Package managers: npm (backend services), pnpm or yarn (frontend — check project)
- Models: fable (main) · haiku (default for subagents via `CLAUDE_CODE_SUBAGENT_MODEL`) · per-agent overrides in agent frontmatter (opus for architect/planner/bug-hunter, sonnet for reviewers)

## Agent Triggers
Self-invoked checklist — not automatic. When a trigger below matches, I should spawn the listed agent without waiting to be asked. This is a standing instruction I follow, not a harness guarantee; if a trigger is skipped, say so rather than implying review happened.

| Trigger | Agent |
|---------|-------|
| Complex feature / refactor / migration / architecture | `planner` or `architect` |
| Code written or modified | `code-reviewer` |
| Dart/Flutter code written or modified | `flutter-reviewer` |
| Migration / schema change / raw SQL / Sequelize models, transactions, indexes | `database-reviewer` |
| Error handling touched — catch blocks, fallbacks, retries, webhook acks | `silent-failure-hunter` |
| Something is slow — endpoint latency, N+1, bundle size, memory growth | `performance-optimizer` |
| Bug sweep of an existing/inherited area (NOT a diff) / pre-refactor audit | `bug-hunter` (via `/hunt-bugs`) |
| Task or loop iteration complete — did we achieve the goal? | `goal-verifier` |
| Auth / secrets / payments / user input / uploads / webhooks | `security-reviewer` |
| Build / typecheck / bundler / CI fails | `build-error-resolver` |
| New feature or bug to fix | `tdd-guide` |
| Dead code / cleanup / simplification | `refactor-cleaner` |
| Docs need updating | `doc-updater` |

Run independent agents in parallel — never sequential when tasks don't depend on each other.

## Agents vs Skills
Same domain, different mechanism — don't run both for one job:
- **Agent** = delegated worker in its own context window; returns only a summary. Use for independent/cold review or grading, heavy fan-out exploration, parallel work, or keeping large output out of the main thread.
- **Skill** = procedure/knowledge injected into the *current* context; you stay in control and keep full context. Use for a guided workflow or project-specific procedure applied to work you're actively doing in this thread.

Rule of thumb: need isolation, independence, or parallelism → agent. Need a checklist/procedure inline → skill.

| Domain | Default | The other one |
|--------|---------|---------------|
| Code review | `code-reviewer` / `react-reviewer` / `typescript-reviewer` agent (cold, post-change) | `/code-review`, `/simplify`, `/review` skill (inline, your context) |
| Security | `security-reviewer` agent (review) | `/security-bounty-hunter` (exploit hunting), `/security-review` (inline diff) |
| TDD | `/tdd` skill (drive red-green-refactor inline) | `tdd-guide` agent (delegated enforcement) |
| Dead code | `/refactor-clean` skill (inline, validate each step) | `refactor-cleaner` agent (batch analysis + removal) |
| Planning | `planner` agent (delegated, returns plan) | `/plan` skill (plan inline in this thread) |
| Verification | `goal-verifier` agent (independent grader — preferred for /loop) | `/verify` skill (inline behavior check) |

## Operating Model
- Planner → executor → reviewer for non-trivial work
- Do not implement when user asks only for a plan
- Do not run destructive commands
- Prefer minimal, reversible changes
- Preserve project conventions unless asked to change them
- Do not review code without inspecting the actual diff
- Research local patterns + official docs before inventing; reuse over rebuild for auth, payments, uploads, webhooks, integrations
- Before a non-trivial task (esp. QPay work), proactively query the `qmd` knowledge base (`mcp__qmd__query`) for prior decisions, patterns, and gotchas, and factor them in — it holds the auto-harvested decision log + engineering notes. Skip for trivial one-liners; don't announce when it returns nothing relevant.

## Coding Rules
- Prefer immutable updates; never mutate function inputs, shared state, or caller-owned data
- Local mutation is fine when confined to a function and not leaking side effects
- KISS: simplest solution that works; clarity over cleverness
- DRY: extract repeated logic; no copy-paste drift; abstract when repetition is real, not speculative
- YAGNI: no features or abstractions before they're needed
- Files: 200–400 lines typical, 800 hard max; organize by feature/domain
- Names: `camelCase` vars/functions · `PascalCase` types/components · `UPPER_SNAKE_CASE` constants · `is/has/should/can` booleans
- Errors: handle explicitly; never swallow silently; user-friendly in UI, diagnostic context on server
- Validate only at system boundaries (user input, external APIs); trust internal code
- No hardcoded secrets, tokens, credentials, or environment-specific values — ever
- No `console.log` debug statements in production paths
- No speculative abstractions, broad rewrites, or unrelated cleanup

## Testing
- Minimum 80% coverage · unit + integration + E2E (critical flows only)
- Arrange-Act-Assert structure · descriptive test names that explain behavior

## Skills
Invoke with `/skill-name` or they auto-trigger when task matches:

| Skill | When |
|-------|------|
| `/debug` | Something broken in a qpay-* service |
| `/debug-bull` | Bull queue not processing, stalled, or failing jobs |
| `/new-route` | Adding a new API endpoint to a backend service |
| `/sql-query-optimization` | Slow query, N+1, missing index |

## Commits
`<type>: <description>` — feat / fix / refactor / docs / test / chore / perf / ci
