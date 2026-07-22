---
name: verification-loop
description: Run an evidence-based independent verification loop after implementing or refactoring code, before a PR or push, or when the user asks to verify, review, double-check, or make a change ready. Separate implementation, read-only review, fixing, and re-verification across Claude, Codex, or fresh agents; report READY only when required checks pass and confirmed findings are resolved.
---

# Verification Loop

Treat verification as a gate, not a self-review checklist.

## Rules

- Do not let the implementer certify its own work. Use the other provider when practical; otherwise use a fresh read-only reviewer agent with no implementation context beyond the request, diff, and relevant repository files.
- Keep the reviewer read-only. Send confirmed findings to an executor/fixer rather than asking the reviewer to edit.
- Prefer repository-native commands and instructions. Do not assume a language, package manager, coverage target, or test command.
- Do not install tools, mutate external systems, push, create a PR, or use destructive Git commands unless already authorized.
- Never hide skipped, unavailable, flaky, or failing checks. An unverified required check prevents `READY`.
- Re-run checks after every fix. Evidence from the pre-fix tree is stale.
- Return ambiguous product or architecture decisions to the user; do not silently auto-fix them.

## 1. Freeze the verification target

Read applicable `AGENTS.md`, `CLAUDE.md`, repository documentation, and CI configuration. Record:

- requested behavior and acceptance criteria;
- current branch and base branch or comparison point;
- `git status --short`;
- changed files and the complete relevant diff, including staged, unstaged, and relevant untracked content;
- pre-existing user changes that must be preserved.

Do not use `HEAD~1` as a universal comparison. Select the merge base or explicit task baseline that represents the actual change.

If the working tree changes during review, invalidate the review and take a new snapshot.

## 2. Discover and run deterministic checks

Derive commands from existing repository sources in this order:

1. explicit user or repository instructions;
2. CI workflows and project scripts;
3. build/package configuration;
4. established language conventions only when the repository provides no command.

Run the smallest relevant checks first, then the broader required suite. Consider, as applicable:

- formatting or generated-file checks;
- lint and static analysis;
- type checking;
- focused tests for changed behavior;
- full tests required by the project;
- build or packaging checks;
- existing security or secret-scanning commands.

Capture the exact command, exit status, and concise result. Treat command output truncation as presentation only: preserve the exit status and enough diagnostics to explain failures.

## 3. Obtain an independent review

Give the reviewer only:

- the original request and acceptance criteria;
- the verification baseline and actual diff;
- relevant surrounding code and repository instructions;
- deterministic check results.

Ask it to inspect correctness first, then security/privacy, data-loss risk, compatibility, test coverage, maintainability, and style. Require every actionable finding to contain:

- severity;
- file and tight line reference;
- concrete impact or failure mode;
- supporting evidence or reproduction reasoning;
- a narrowly scoped remediation.

Reject vague preferences and findings unrelated to the change. Absence of findings is valid only after the reviewer inspected the actual diff and surrounding code.

### Cross-provider handoff

Prefer Claude reviewing Codex work or Codex reviewing Claude work when both are available. If one cannot invoke the other directly, emit a compact `REVIEW HANDOFF` containing the fields above for the user to paste into the other tool. Do not label the change `READY` until the returned review is incorporated. If the user explicitly accepts same-agent verification, disclose the reduced independence in the final report.

## 4. Triage before fixing

Classify each finding:

- `CONFIRMED`: supported and within scope; send to the fixer.
- `DECISION`: requires user/product/architecture judgment; pause that item for the user.
- `DISMISSED`: unsupported, duplicate, pre-existing, or out of scope; record the reason.

The coordinator owns classification. Do not forward raw reviewer output blindly.

## 5. Fix with a separate execution pass

Give the fixer only confirmed findings, applicable constraints, and relevant files. Require minimal changes and preservation of unrelated user work. Do not introduce opportunistic refactors.

After fixes:

1. inspect the new diff;
2. run focused regression checks for each finding;
3. rerun every required deterministic check affected by the change;
4. ask a fresh read-only reviewer to verify the fixes and inspect the new delta.

Repeat only while making evidence-backed progress. Stop and report a blocker instead of looping indefinitely.

## 6. Decide readiness

Report `READY` only when:

- all acceptance criteria are evidenced;
- all required available checks pass on the final tree;
- no confirmed finding remains;
- no unresolved decision can change correctness;
- the final diff has received independent review;
- limitations and unrun checks are explicitly recorded.

Otherwise report `NOT READY` or `BLOCKED`.

Use this compact format:

```text
VERIFICATION REPORT
Outcome: READY | NOT READY | BLOCKED
Scope: <baseline and final changed files>

Checks:
- PASS | FAIL | NOT RUN — <exact command> — <evidence/reason>

Independent review:
- Reviewer: <Claude | Codex | fresh read-only agent | same agent by user exception>
- Confirmed: <count>
- Decisions: <count>
- Dismissed: <count with reasons available>

Fixes and re-verification:
- <finding → change → regression evidence>

Residual risks:
- <risk or none>
```

Evidence, not agent confidence, determines the outcome.
