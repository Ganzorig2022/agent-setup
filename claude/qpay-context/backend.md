# QPay Backend — Standing Facts

## Two Cores (Old vs New)
QPay runs two parallel codebases — always know which one you're in:
- **Old core** — legacy, cloned from **git.qpay.mn** (GitLab) to `/Users/dev/QPay`. The Stack A/B/C mix below (mostly Express/Babel + Sequelize/Mongo). Note `/Users/dev/QPay` also holds ~12 *new-core* clones, so the parent directory does not identify the core — read `git remote get-url origin`.
- **New core** — the **github.com/qpay-mn** org, cloned to `~/qpay-mn`. Predominantly **Fastify + TypeScript + Zod** services (same shape as Stack C, but Stack C's exemplar `qpay-ticket-service-v2` is old-core — the stack label does not imply the core) + shared `qpay-lib-*` packages; Gen-3 (Next/React/Zustand/Radix) web apps.
- Harvested architecture docs for both live in the **private** `knowledge-base` vault under `qpay/old-core/` and `qpay/new-core/`, queryable via the `qmd` MCP. Refresh with `qpay-gem-harvest.py`.

## CI — no `.gitlab-ci.yml`, but there IS a deploy pipeline
Old-core repos carry no `.gitlab-ci.yml` and `git.qpay.mn` runs no GitLab CI jobs — **never
propose a GitLab CI job** as the place to enforce lint, typecheck, tests, or builds. Applies to
frontends too.

That is NOT the same as "no automation". A pipeline does exist: it builds `deployment/Dockerfile`
with the classic (non-BuildKit) builder, tags `git.qpay.mn:5005/<group>/<repo>:prod_<YYYYMMDD>`,
pushes to that registry, then restarts the k8s deployment. Observed on qpay-vendor-web-v2,
2026-07-29. What *drives* it is unconfirmed — do not guess Jenkins/Argo/etc. in writing; ask.

Consequence when picking where a check goes: the image build is the only non-skippable gate —
a failing `RUN` step means no image and no deploy, and the pipeline runs that Dockerfile. A
`.husky/` pre-commit hook is local and bypassable (`git commit --no-verify`, or any fresh clone
before `pnpm install` fires husky's `prepare`), so moving a check out of the Dockerfile and into
a hook downgrades it from enforced to advisory. Say so explicitly rather than treating the two
as equivalent.

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

### Stack B — EASY_SYSTEM services (`/Users/dev/QPay/SYSTEM_EASY/`, `sms-*`)
Identify: has `mongoose` in package.json

- **Express 5** + **Babel** (not TypeScript)
- DB: **MongoDB** via `mongoose`
- Queues: **Bull** (some services)
- Validation: **Joi**
- Tests: **vitest** (present in some services)
- Lint: same as Stack A (`eslint-config-airbnb` + eslint-plugin-prettier, no standalone .prettierrc)

### Stack C — TICKET system (`/Users/dev/QPay/SYSTEM_TICKET/qpay-ticket-service-v2`, old-core remote)
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

## Vault CSI — house standard, copy don't invent
~37 old-core services ship a byte-identical `scripts/docker-entrypoint.sh` that promotes Vault CSI files to env vars: mount `/mnt/secrets`, `SECRETS_PROVIDER` defaults to `env` (non-K8s runs unaffected), fails fast if the mount is missing or empty, skips dotfiles, then `exec`s the real command. Only the final `exec` line is per-service. Cluster side (`SecretProviderClass`, ServiceAccount, Vault role/policy) is sysadmin-owned — never write it into an app repo. Rotation needs a rolling restart (Node reads `process.env` once at boot). Applies to frontends too (qpay-vendor-web-v2 uses it).

## Stack A/B Critical Rules (executors commonly get these wrong)
- **No try/catch in route handlers** — Express 5 catches async throws natively; adding try/catch is wrong
- **Use `qpay-micro-logging`, never `console.log`** — this is the internal logging package
- **Joi schema at route entry only** — `.required()`, `.valid()`, `.uuid()`, `.max()`, `stripUnknown: true`; never validate in service layer
- **Service functions have no req/res/next** — they receive plain data and return data or throw
- **Config from `src/config/`** — never read `process.env` directly inside services or models
- **`configure()` picks the env block from `SERVER_ENV`, not `NODE_ENV`** (`qpay-micro-service/utils/configure.js`), defaulting to `development`. Blocks seen across old-core: `development | dev | sandbox | prod | prod_new`. A pod can carry `NODE_ENV=sandbox` while running `prod_new` config — `NODE_ENV` is decorative. A wrong value fails narrowly and misleadingly: most hosts fall back to in-cluster service names, so only the few with explicit public-hostname overrides (e.g. S3) break, and code gated on an exact value (`SERVER_ENV === "prod"`) silently never fires. Check the deployment manifest before trusting the env name.
- **Run `npx eslint --fix` only** — no standalone prettier, no `.prettierrc`

## Stack C Critical Rules
- **Zod schema at route entry** — `z.object({ ... }).strict()`
- **Use `fastify-type-provider-zod`** for automatic type inference
- **`npx tsc --noEmit` must pass** before submitting
- **Run `npx eslint --fix`** after tsc passes
