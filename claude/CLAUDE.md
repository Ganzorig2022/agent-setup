# Global Claude Code Instructions

@~/.claude/agent-memory/STATE.md
@~/.claude/prompt-defense.md

## Environment
- Projects: QPay — old-core `/Users/dev/QPay` (Express 5 + Babel JS microservices) · new-core `~/qpay-mn` (Fastify + TypeScript) · Next.js/React frontends (Gen 1–3)
- Package managers: npm (backends) · frontends vary by generation — check the lockfile (see qpay-context/frontend.md)
- Models: main sessions use the selected/default model · custom subagents use their agent-frontmatter model (opus for architect/planner/bug-hunter, sonnet for reviewers, haiku for lightweight roles) · agents without a model inherit the main session

## Agent Triggers
Self-invoked checklist — not automatic. When a trigger below matches, I should spawn the listed agent without waiting to be asked. This is a standing instruction I follow, not a harness guarantee; if a trigger is skipped, say so rather than implying review happened.

| Trigger | Agent |
|---------|-------|
| Complex feature / refactor / migration / architecture | `planner` or `architect` |
| Code written or modified — ONE reviewer by file type | `.tsx/.jsx` → `react-reviewer` · `.ts/.js` (non-React) → `typescript-reviewer` · `.dart` → `flutter-reviewer` · other / mixed / cross-cutting → `code-reviewer` |
| Migration / schema change / raw SQL / **Sequelize** models, transactions, indexes | `database-reviewer` (Postgres/Sequelize only) |
| Money touched — balances, wallet debit/credit, pricing or tariff arithmetic, invoice/settlement amounts, charge/refund, money-moving queue jobs | `payments-reviewer` |
| Queue change — new/modified Bull or BullMQ producer, processor, or completed/failed handler | `payments-reviewer` if it moves money, else `silent-failure-hunter` |
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

Reviewer stacking: file-type reviewers (`code-reviewer`/`typescript-reviewer`/`react-reviewer`/`flutter-reviewer`) never stack with each other — pick exactly one per change. Specialists (`security-reviewer`, `database-reviewer`, `payments-reviewer`, `silent-failure-hunter`) DO stack on top when their trigger matches. On a money path, `payments-reviewer` is not optional — no other agent covers currency, rounding, or charge-once semantics.

## Agents vs Skills
Same domain, different mechanism — don't run both for one job. Need isolation, independence, or parallelism → agent. Need a checklist/procedure inline → skill.

| Domain | Default | The other one |
|--------|---------|---------------|
| Code review | one file-type reviewer agent (cold, post-change — route per trigger table) | `/code-review`, `/simplify`, `/review` skill (inline, your context) |
| Security | `security-reviewer` agent (cold review of a change/diff) | `/security-review` (quick inline pass on pending diff) · `/security-bounty-hunter` (exploit hunt across EXISTING code, not a diff) |
| TDD | `/tdd` skill (drive red-green-refactor inline) | `tdd-guide` agent (delegated enforcement) |
| Dead code | `/refactor-clean` skill (inline, validate each step) | `refactor-cleaner` agent (batch analysis + removal) |
| Planning | `planner` agent (delegated, returns plan) | `/plan` skill (plan inline in this thread) |
| Verification | `goal-verifier` agent (independent grader — preferred for /loop) | `/verify` skill (inline behavior check) |

## Operating Model
- Planner → executor → reviewer for non-trivial work
- Do not implement when user asks only for a plan
- Do not run destructive commands
- Never `git stash` — not as a side step, not with a dev server attached (it re-links `node_modules` and crashes the watcher; a stash inside a compound command has silently removed live work mid-review). To compare against HEAD, `git show HEAD:path` into the scratchpad. Same for reinstalling deps under a running watcher
- Prefer minimal, reversible changes
- For one-off or infrequent operational work, start with the simplest direct end-to-end path. Add wrappers, control planes, policy layers, custom verifiers, or automation only after a concrete blocker or repeated need justifies them
- Preserve project conventions unless asked to change them
- Do not review code without inspecting the actual diff
- Research local patterns + official docs before inventing; reuse over rebuild for auth, payments, uploads, webhooks, integrations
- Before a non-trivial task (esp. QPay work), proactively query the `qmd` knowledge base (`mcp__qmd__query`) for prior decisions, patterns, and gotchas, and factor them in — it holds the auto-harvested decision log + engineering notes. Skip for trivial one-liners; don't announce when it returns nothing relevant.
- For current third-party library/framework/SDK APIs (versions, signatures, new or changed features), consult **Context7** (`resolve-library-id` → `query-docs`) before coding from memory — it pulls up-to-date, version-specific docs. Use for non-trivial library/integration work; skip well-known stable basics. Codex has the same MCP server wired in `~/.codex/config.toml`.

## Coding Rules
House preferences only — general engineering practice is assumed, not restated.
- Files: 200–400 lines typical, 800 hard max; organize by feature/domain

## Testing
- Minimum 80% coverage · unit + integration + E2E (critical flows only)

## Skills
Invoke with `/skill-name` or they auto-trigger when task matches:

| Skill | When |
|-------|------|
| `/debug` | Something broken in a qpay-* service |
| `/debug-bull` | Bull queue not processing, stalled, or failing jobs |
| `/new-route` | Adding a new API endpoint to a backend service |
| `payment-service-patterns` | Writing (not reviewing) money code — wallet, settlement, ledger, callbacks. Reviewing is `payments-reviewer`'s job |
| `/sql-query-optimization` | Slow query, N+1, missing index |

## Commits
`<type>: <description>` — feat / fix / refactor / docs / test / chore / perf / ci
