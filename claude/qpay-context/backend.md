# QPay Backend — Standing Facts

## Two Cores (Old vs New)
QPay runs two parallel codebases — always know which one you're in:
- **Old core** — legacy, cloned from **git.qpay.mn** (GitLab) to `/Users/dev/QPay`. The Stack A/B/C mix below (mostly Express/Babel + Sequelize/Mongo).
- **New core** — the **github.com/qpay-mn** org, cloned to `~/qpay-mn`. Predominantly **Fastify + TypeScript + Zod** (Stack C) services + shared `qpay-lib-*` packages; Gen-3 (Next/React/Zustand/Radix) web apps.
- Harvested architecture docs for both live in the **private** `knowledge-base` vault under `qpay/old-core/` and `qpay/new-core/`, queryable via the `qmd` MCP. Refresh with `qpay-gem-harvest.py`.

## Three Backend Stacks

### Stack A — Classic QPay (most qpay-* services)
Identify: has `qpay-sequelize-postgres` in package.json

- **Express 5** + **Babel** (not TypeScript)
- DB: **PostgreSQL** via `qpay-sequelize-postgres` (internal Sequelize wrapper)
- Queues: **Bull** (`src/queues/`)
- Validation: **Joi**
- Logging: `qpay-micro-logging` (internal) — never `console.log`
- Bootstrap: `qpay-micro-service` (internal) wraps Express lifecycle
- Lint: `eslint-config-airbnb` + `eslint-plugin-prettier` — NO standalone `.prettierrc`; run `npx eslint --fix` only

### Stack B — EASY_SYSTEM services
Identify: has `mongoose` in package.json

- **Express 5** + **Babel** (not TypeScript)
- DB: **MongoDB** via `mongoose`
- Queues: **Bull** (some services)
- Validation: **Joi**
- Tests: **vitest** (present in some services)
- Lint: same as Stack A (`eslint-config-airbnb` + eslint-plugin-prettier, no standalone .prettierrc)

### Stack C — TICKET_SYSTEM (qpay-ticket-service-v2)
Identify: has `fastify` in package.json

- **Fastify 5** + **TypeScript** (not Babel — uses tsc)
- Queues: **BullMQ** (not Bull)
- Validation: **Zod** (not Joi)
- Tests: **vitest**
- No internal QPay wrappers — standard npm packages only

## Source Layout (Stack A & B)
```
src/
  apis/        # route handlers (grouped by domain)
  config/      # env-based config
  constants/   # shared enums and literals
  core/        # app bootstrap / DI wiring
  middlewares/ # Express middleware
  models/      # Sequelize (A) or Mongoose (B) model definitions
  queues/      # Bull job producers/consumers (separate files per queue)
  services/    # business logic
  utils/       # pure helpers
```

## Shared Conventions (all stacks)
- CommonJS for Babel stacks; ESM/CJS per tsconfig for TypeScript stacks
- Async route handlers must be wrapped in error-catching middleware
- Environment values in `src/config/` — never access `process.env` directly in services
- No hardcoded secrets — always via environment config

## Stack A/B Critical Rules (executors commonly get these wrong)
- **No try/catch in route handlers** — Express 5 catches async throws natively; adding try/catch is wrong
- **Use `qpay-micro-logging`, never `console.log`** — this is the internal logging package
- **Joi schema at route entry only** — `.required()`, `.valid()`, `.uuid()`, `.max()`, `stripUnknown: true`; never validate in service layer
- **Service functions have no req/res/next** — they receive plain data and return data or throw
- **Config from `src/config/`** — never read `process.env` directly inside services or models
- **Run `npx eslint --fix` only** — no standalone prettier, no `.prettierrc`

## Stack C Critical Rules
- **Zod schema at route entry** — `z.object({ ... }).strict()`
- **Use `fastify-type-provider-zod`** for automatic type inference
- **`npx tsc --noEmit` must pass** before submitting
- **Run `npx eslint --fix`** after tsc passes
