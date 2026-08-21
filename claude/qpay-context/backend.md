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
2026-07-29. **It is driven by the Maintainer app, not Jenkins/Argo** (confirmed 2026-08-19 —
see "Deploying and observing" below).

Consequence when picking where a check goes: the image build is the only non-skippable gate —
a failing `RUN` step means no image and no deploy, and the pipeline runs that Dockerfile. A
`.husky/` pre-commit hook is local and bypassable (`git commit --no-verify`, or any fresh clone
before `pnpm install` fires husky's `prepare`), so moving a check out of the Dockerfile and into
a hook downgrades it from enforced to advisory. Say so explicitly rather than treating the two
as equivalent.

## Deploying and observing (sandbox; prod is the same tooling)
- **Deploy** = `sandbox-maintainer.qpay.mn/services`. Per-service row: edit icon → *Pod settings*
  → Git branches → **Refresh** (a newly pushed branch will NOT appear until you do) → select →
  Update → *Build & Deploy* → confirm. Status badge goes Building → Success; a build is ~1–3 min.
- The row's branch **persists**: anyone deploying that service later rebuilds whatever branch is
  set, so leaving a feature branch there silently hijacks the next deploy. Repoint when done.
- **A green "Success" build does NOT mean the new code is running.** The build pushes a new image,
  but the k8s Deployment still references the previously-set image, so the rolled pod comes up on
  the OLD image and the deploy silently has no effect. After every build you must update the
  Deployment's image in `sandbox-dashboard.qpay.mn` to the newly built one. Symptoms when skipped:
  maintainer shows Success and a fresh `Last deployed` time, the pod restarts with a NEW
  pod-template-hash and 0 restarts, and the app still serves the old behaviour — so pod age and
  build status both look correct and prove nothing. Verify the code, not the badge: for a
  frontend, fetch a `/_next/static/chunks/*.js` and grep for the changed logic; for a backend,
  check the boot log for a line the new build added.
- One repo can map to **several Maintainer rows** (callcenter: web / backend / embedder, each with
  its own Docker tag and `Last deployed`). "I deployed" is therefore ambiguous — check the row for
  the service you mean; deploying one leaves every other image untouched.
- Deploying a sibling branch **removes** whatever the previous branch shipped. Check what is
  currently deployed before repointing, or you will silently un-deploy tickets sitting in QA.
- **Logs/health** = `sandbox-dashboard.qpay.mn` → namespace picker (e.g. `qpay-sms`) → Pods:
  Status, Restarts, age; the pod detail page has Logs. The dashboard token expires quickly and
  only the user can re-auth.
- **Nobody on the app side has cluster access.** The user cannot run `kubectl`; a dedicated
  DevOps engineer executes every k8s command and deployment. Prefer a path through the deployed
  app's own API over anything needing `kubectl exec`/`cp` — it removes a human round-trip.
- Both are behind `sandbox-sso.qpay.mn`. Claude must never enter credentials — hand login to the
  user. UI caution: the maintainer's accessibility labels are unreliable (a **delete** button has
  been returned as "edit button") and rows reorder after an update, so map controls by position
  via `read_page` and re-read after every change.

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
- **Joi schema at route entry only** — `.required()`, `.valid()`, `.uuid()`, `.max()`; never validate in service layer. **`stripUnknown` does nothing here**: `qpay-micro-service/src/method/index.js` hardcodes `allowUnknown: true` and *discards* `joi.value`, so the handler always sees the raw body — destructure named fields, never spread `req.body` into a write. For **GET the schema validates `req.query`, never `req.params`**, which is why route-param routes pass `null` and re-validate by hand.
- **Service functions have no req/res/next** — they receive plain data and return data or throw
- **Config from `src/config/`** — never read `process.env` directly inside services or models
- **`configure()` picks the env block from `SERVER_ENV`, not `NODE_ENV`** (`qpay-micro-service/utils/configure.js`), defaulting to `development`. Blocks seen across old-core: `development | dev | sandbox | prod | prod_new`. A pod can carry `NODE_ENV=sandbox` while running `prod_new` config — `NODE_ENV` is decorative. A wrong value fails narrowly and misleadingly: most hosts fall back to in-cluster service names, so only the few with explicit public-hostname overrides (e.g. S3) break, and code gated on an exact value (`SERVER_ENV === "prod"`) silently never fires. Check the deployment manifest before trusting the env name.
- **Run `npx eslint --fix` only** — no standalone prettier, no `.prettierrc`

## Framework Error Handling (qpay-micro-service, Stack A/B)
- `errorHandler` status map: Validation/JoiValidation → 400 · Unauthorized → 401 · Forbidden → 403 · **Notfound → 422 (NOT 404)** · Unique → 409 · Custom/InternalServer/TypeError/DatabaseConnection → 500. Any *unhandled* throw → 500 `SYSTEM_BUSY`.
- So `SYSTEM_BUSY` in a response or UI toast carries zero diagnostic information — it means "go read the pod log". Never document 404 for a `NotfoundError` route in OpenAPI; it is 422.
- `BaseError(code, message)`: an Error passed as the 2nd arg becomes `errorMessage`, which is server-log only and never serialized to the client. No `{ cause }` chaining — the stack is captured at the throw site, not at the original failure.

## Postgres Grants — every new table needs one
Tables are owned by `postgres`, but services connect as a *separate* role holding explicit per-table grants, so a newly created table inherits none. First use fails `permission denied` (SQLSTATE 42501, `aclcheck_error`), surfacing to the caller as `SYSTEM_BUSY`. Grant explicitly to the app role (`database.username` in the service config). Do NOT mirror "every grantee on a peer table" — that copies *who* has access without *what*, handing write access to read-only `*_ro` roles.

## Raw SQL (Stack A/B)
`db.query(sql, replacements, options)` from `qpay-sequelize-postgres` supports named `:param` binding and returns `{select,update,create,delete,raw}()`; the 3rd arg is the session/transaction. Use it instead of string interpolation. Postgres `::CAST` syntax is safe with sequelize replacements (verified on 6.37.8). Three traps:
- Replacements are **client-side escaped substitution, not server-side bind params**, so a JSON string `"20"` bound to `:limit` renders `LIMIT '20'` and errors — `Number()` limit/offset before binding.
- A placeholder must be followed by a **non-word character**. Appending `"AND ..."` with no leading space after `:merchant_id` yields `:merchant_idAND`, which Sequelize reads as a placeholder of that name and never binds. Interpolating SQL *structure* (`${where}`, connectors, conditional clauses) is fine; interpolating a *value* is the injection.
- **Unused replacement keys are tolerated**, so one object can feed both a count query and a rows query.

## Stack C Critical Rules
- **Zod schema at route entry** — `z.object({ ... }).strict()`
- **Use `fastify-type-provider-zod`** for automatic type inference
- **`npx tsc --noEmit` must pass** before submitting
- **Run `npx eslint --fix`** after tsc passes
