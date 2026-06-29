---
name: handoff-impl
description: Produce a structured implementation brief for any external agent (Codex, ChatGPT, Kimi, GLM, etc). Run when a plan is approved and ready to hand off to an implementer. Detects the current project stack from package.json and emits a self-contained brief with stack context, files to touch, constraints, and acceptance criteria.
argument-hint: "Brief description of the task being handed off"
---

# Implementation Handoff

Produce a structured implementation brief an external agent can execute without needing session history. Save to a path from `mktemp -t impl-brief-XXXXXX.md` and print the path.

## Step 1: Detect the Stack

Read `package.json` in the current working directory. Check `dependencies` and `devDependencies`.

**Backend:**
- Has `qpay-sequelize-postgres` → Stack A: Express 5 / Babel / PostgreSQL / Joi / Bull 4.x / qpay-micro-logging / no standalone .prettierrc / `npx eslint --fix`
- Has `mongoose` → Stack B: Express 5 / Babel / MongoDB / Joi / Bull 4.x / same lint rules
- Has `fastify` → Stack C: Fastify 5 / TypeScript / Zod / BullMQ / `npx tsc --noEmit` + `npx eslint --fix`
- None → generic Node.js; note package manager from lockfile

**Frontend:**
- Has `@radix-ui/react-*` or `next` ≥ 15 → Gen 3: Next.js 16+ / React 19 / Tailwind v4/ Zod v4/ Radix UI / TanStack Query v5 / `eslint.config.mjs` / `npx eslint --fix` only
- Has `antd` ≥ 5 + `redux` → Gen 1.5: Next.js 12 / React 18 / AntD 5 / TanStack Query v5 / `prettier --write` then `eslint --fix`
- Has `antd` ≤ 4 + `redux` → Gen 1: Next.js 12 / React 17 / AntD 4 / SWR / `prettier --write` then `eslint --fix`
- Has `tailwindcss` + `zustand` (no Radix) → Gen 2: Next.js 13-14 / Tailwind / Zustand / `prettier --write` then `eslint --fix`

## Step 2: Summarize the Approved Plan

From the current session, extract in ≤ 5 bullets:
- What is being built or changed
- Why (requirement or bug)
- Explicit non-goals / out of scope

If a plan file path was saved earlier in this session, reference it by path — do not re-paste its contents.

## Step 3: List Files to Touch

For each file the implementer should modify or create:
- Full relative path from repo root
- What kind of change: add / modify / create
- One-line reason

Only list files that actually need touching.

## Step 4: Write the Brief

Output exactly this structure:

```
# Implementation Brief: <task name>

## Repo
<absolute path to the repo, e.g. /Users/dev/QPay/qpay-invoice-service>

## Stack
<language · framework · DB · validation · queue · test runner if any>
<lint command to run before submitting>

## Task
<2–3 sentences: what to implement and why>

## Out of scope
<explicit non-goals>

## Files to touch
| File | Change | Notes |
|------|--------|-------|
| src/... | add / modify / create | reason |

## Constraints
<stack-specific rules that apply — pulled from detected stack above>
Examples for Stack A:
- Use qpay-micro-logging, never console.log
- No try/catch in route handlers — Express 5 catches async throws natively
- Validate all inputs with Joi at the route entry (not in the service)
- Config values from src/config/ — never process.env directly in services
- Run npx eslint --fix only; no standalone prettier

## Acceptance criteria
- [ ] <observable outcome 1>
- [ ] <observable outcome 2>
- [ ] Lint passes: <lint command>
- [ ] Manual test: <curl or UI action that proves it works>
- [ ] No existing routes or behavior broken

## Reference
<path to plan file, or "plan was in session — no file">
```

Save the file and print: `Brief saved to: <path>`
