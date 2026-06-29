# Development Workflow

Use for non-trivial features, refactors, migrations, architecture changes, security-sensitive work, unfamiliar codebases.
Skip for typo fixes, formatting-only changes, obvious one-file fixes.

## Core Workflow

1. Research and reuse when needed
2. Plan before implementation
3. Prefer TDD for testable behavior
4. Review after meaningful code changes
5. Run validation checks
6. Summarize clearly
7. Commit only when explicitly asked

## Research Priority

1. **Local repo first** — search existing patterns, similar modules, tests, routes, components, utilities. Prefer local consistency over external examples.
2. **Primary docs** — official/vendor docs for API behavior, version-specific details, supported patterns. Prefer primary sources over blog posts.
3. **Package registries** — check npm/PyPI/crates.io before writing reusable infrastructure. Prefer established libraries for generic/security-sensitive problems. Avoid deps for trivial utilities.
4. **Code search** — use only when examples/patterns would meaningfully reduce risk. Do not copy without license review.
5. **Web research** — last resort when above sources are insufficient.

Research mandatory for: unfamiliar APIs, new dependencies, security-sensitive behavior, architecture decisions, external integrations, unclear requirements.
Research optional for: small local fixes, simple refactors, project-specific glue code, obvious changes using existing patterns.

## Plan First

Use the `planner` agent or `/plan` for: complex features, architecture changes, cross-file refactors, migrations, security-sensitive changes, unfamiliar codebases, handoffs to another agent/session.

A useful plan includes: requirements, assumptions, non-goals, affected files/modules, files to inspect first, likely files to modify, implementation phases, dependencies, risks and mitigations, validation commands, testing strategy, handoff prompt when relevant.

Planning should be proportional. Do not create heavyweight PRDs for simple fixes.

## TDD

Use `tdd-guide` agent for: new business logic, bugs with reproducible failures, validation rules, API behavior changes, refactoring behavior that must be preserved.

Loop: RED (failing test) → GREEN (minimal implementation) → IMPROVE (refactor) → VERIFY (run checks).

Skip TDD for: exploring unknown codebase, mechanical docs work, tiny config changes, test setup that doesn't exist and adding it would be larger than the change.

## Implementation Discipline

- Make minimal, focused changes
- Follow existing project conventions
- Preserve stated non-goals; avoid unrelated cleanup
- Avoid broad rewrites unless explicitly justified
- Keep changes reversible
- If plan conflicts with repo reality, update the plan

## Security Review → use `security-reviewer`

Trigger on: auth, authz, user input, API endpoints, DB queries, file uploads/downloads, payments, webhooks, external URLs, secrets, sensitive data, dependency updates.
Findings must be evidence-based and include concrete impact.

## Code Review → use `code-reviewer`

After meaningful code changes. Focus: correctness, regressions, security risks, missing tests, maintainability, unnecessary complexity, convention violations.

Address CRITICAL/HIGH before merge. MEDIUM when practical. LOW only when clear value.

## Validation Before Done

Run the most relevant available checks. Prefer existing package scripts and the project's package manager. Report what ran and what didn't. Never claim a check passed unless actually run.

Relevant checks: tests, typecheck, lint, build, dependency audit for security-sensitive work. E2E tests only for critical browser journeys or when explicitly requested.

## Documentation → use `doc-updater`

When changes affect: README, API behavior, CLI behavior, configuration, environment variables, migration steps, examples, changelog.
Skip for invisible internal changes unless docs would prevent future mistakes.

## Done Criteria

- Requested scope satisfied; unrelated changes avoided
- Meaningful edge cases handled
- Relevant validation run or limitations stated
- Review findings addressed based on severity
- Final summary: changed files, validation results, remaining risks
