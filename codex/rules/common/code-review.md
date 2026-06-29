# Code Review Standards

## When to Review

Use code review after meaningful code changes, especially when changes involve:
production code, business logic, API behavior, authentication or authorization, user input, database queries, file uploads/downloads, payments, webhooks, external API calls, dependency changes, architecture or module boundaries, cross-file refactors, AI-generated implementation work.

Review is usually unnecessary for: typo-only, comments-only, formatting-only, trivial one-line local changes with no meaningful risk.

Before commits or merges, review the actual diff. Do not claim CI, tests, lint, typecheck, or build passed unless actually verified.

## Pre-Review Requirements

- inspect `git status` and staged/unstaged diffs
- resolve obvious merge conflicts
- run relevant tests/checks or explain why not
- ensure unrelated changes are not mixed into the diff

## Review Checklist

- [ ] Code is readable and well-named
- [ ] Functions are focused and understandable; files remain cohesive
- [ ] Control flow avoids unnecessary deep nesting
- [ ] Errors are handled explicitly; boundary input is validated
- [ ] No hardcoded secrets, credentials, tokens, or private keys
- [ ] No debug `console.log` or temporary instrumentation in production paths
- [ ] Tests exist or are updated for meaningful behavior changes
- [ ] Existing behavior is preserved unless intentionally changed
- [ ] Project conventions are followed; no unrelated rewrites or speculative abstractions

## Agent Usage

| Agent                  | Use For                                                   |
| ---------------------- | --------------------------------------------------------- |
| `code-reviewer`        | Quality, correctness, regressions, tests, maintainability |
| `security-reviewer`    | Auth, secrets, injection, SSRF, unsafe crypto             |
| `build-error-resolver` | Build, typecheck, bundler, CI failures                    |
| `refactor-cleaner`     | Behavior-preserving cleanup                               |
| `tdd-guide`            | Test-first for new or changed behavior                    |
| `doc-updater`          | Docs after behavior, API, config changes                  |

## Security Review Triggers → use `security-reviewer`

auth, authz, user input, API endpoints, DB queries, file system ops, uploads/downloads, external API calls, external URLs/SSRF, crypto, session/JWT/cookie, payments, webhooks, secrets/sensitive data, dependency updates.

Security findings must be evidence-based. Do not inflate severity without a concrete exploit path.

## Review Severity

| Level    | Meaning                                                                        | Action                       |
| -------- | ------------------------------------------------------------------------------ | ---------------------------- |
| CRITICAL | Confirmed vuln, data loss, auth bypass, RCE, payment corruption                | BLOCK: must fix before merge |
| HIGH     | Likely bug, serious regression risk, missing auth/validation in sensitive path | SHOULD FIX before merge      |
| MEDIUM   | Maintainability, test coverage, edge-case robustness                           | Consider fixing              |
| LOW      | Minor style, naming, cleanup                                                   | Optional                     |
| INFO     | Observation                                                                    | No action                    |

For each finding: file + line, concrete problem, failure mode, recommendation, confidence.
For HIGH/CRITICAL: exact trigger path, impact, why existing guards are insufficient.

## Common Issues to Catch

### Security

hardcoded creds, SQL/NoSQL injection, shell command injection, XSS via unsafe HTML, path traversal, missing auth/authz checks, unverified webhooks, insecure CORS+credentials, sensitive data in logs, unsafe external URL fetches, weak password hashing or crypto misuse

### Correctness

broken edge cases, incorrect null/undefined handling, race conditions, missing idempotency for retries/webhooks, incorrect error handling, behavior changes not reflected in tests, API contract regressions, state mutation where immutable update required

### Code Quality

large or unfocused functions, large or incohesive files, deep nesting that obscures logic, duplicated logic likely to drift, speculative abstractions, unclear names, dead code, commented-out code, temporary debug statements

### Performance

N+1 queries on unbounded datasets, missing pagination or limits, unbounded memory growth, blocking synchronous I/O in async/server paths, repeated expensive computation without caching, excessive client bundle growth

Performance findings should explain why the cost matters in this specific code path.

## Approval

- **APPROVE**: no confirmed CRITICAL or HIGH
- **WARNING**: HIGH exists, no CRITICAL — merge only if risk explicitly accepted
- **BLOCK**: any confirmed CRITICAL
