---
name: debug
description: Systematic debugging for QPay backend services (Express/Babel/Sequelize/Bull). Use when something is broken, throwing errors, or behaving unexpectedly in a qpay-* service. Covers API errors, service crashes, DB issues, and queue failures.
---

# Debug — QPay Backend

## Step 1: Reproduce First

Never guess. Reproduce the failure before touching any code.

- Identify the exact request/input that triggers it
- Note the environment: dev / staging / production
- Check if it's consistent or intermittent

## Step 2: Read the Error

```bash
# Sentry — check src/instrument.js is loaded; errors flow there automatically
# Local logs — qpay-micro-logging writes structured JSON
# Check the actual error object: message, stack, code, statusCode
```

Read the full stack trace top to bottom. The first frame that is *your code* (not node_modules) is where to start.

## Step 3: Trace the Request Path

Follow the path: route handler → middleware → service → model → DB.

```
src/apis/<domain>/        # route handler — check req validation here
src/middlewares/          # auth, error handling — check order
src/services/             # business logic — most bugs live here
src/models/               # Sequelize model — check associations, hooks
```

- Check what Joi schema is applied at the route entry
- Check if async errors are caught (Express 5 catches async throws natively)
- Check if the service is returning or throwing the right shape

## Step 4: Check Config and Environment

```bash
# Values come from src/config/ — never process.env directly
# Check the right config key is being read
# Check for undefined/null config values causing downstream failures
```

## Step 5: Isolate

Narrow the broken scope:

1. Is it the route (bad request parsing)?
2. Is it the service (bad logic)?
3. Is it the DB (bad query, missing record, constraint violation)?
4. Is it an external call (timeout, bad response shape)?

Add a temporary log at each layer boundary using `qpay-micro-logging` — never `console.log`.

## Step 6: Check Recent Changes

```bash
git log --oneline -10          # what changed recently
git diff HEAD~1                # what exactly changed
```

Most bugs were introduced by the last change. Check it first.

## Step 7: Fix → Verify → Clean Up

- Fix the narrowest possible change
- Reproduce the original failure path and confirm it no longer triggers
- Remove any temporary logging added during diagnosis
- If the bug reveals a missing Joi validation, add it at the route entry
