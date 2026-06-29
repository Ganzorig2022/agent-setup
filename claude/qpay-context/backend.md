# QPay Backend — Standing Facts

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
