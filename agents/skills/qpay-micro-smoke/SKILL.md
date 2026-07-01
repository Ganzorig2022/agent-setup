---
name: qpay-micro-smoke
description: Use when testing QPay old-core qpay-micro-service endpoints manually or writing smoke scripts, especially /micro routes, multipart uploads, service-to-service JWT auth, DB_SESSION/MS_SESSION construction, and interpreting smoke failures.
---

# QPay Micro Smoke

## Purpose

Use this skill for QPay old-core services that expose routes through `qpay-micro-service`, especially `POST /micro/...` calls and multipart upload smoke tests.

The fragile parts are the `Authorization: Micro <JWT>` header and the `session` array. A bare `session: ["MICRO"]` is not enough when `qpay-micro-logging` or Sequelize audit fields are active.

## Checklist

1. Read the target repo's `src/services/index.js` and confirm the route path loaded by `micro.service(...).routes(__dirname, "/vN")`.
2. Confirm whether the endpoint is JSON or multipart.
3. Use `Authorization: Micro <token>` where `<token>` is a JWT signed with `JWT_SECRET_MICRO`; if the operator provides a JWT-shaped value, pass it through.
4. Send a full micro session shape:

```js
[
  "MICRO",
  ["DB_SESSION", dbSession],
  ["MS_SESSION", msId, true, null, msId],
  null,
  user,
  null,
  "127.0.0.1",
  "POST",
  "v2/file/upload"
]
```

5. For DB-backed creates, include DB audit defaults in `dbSession.create`; otherwise models with `created_by`, `created_date`, `updated_by`, and `updated_date` will fail validation.
6. For multipart endpoints, send regular file fields plus a `multipart` JSON field:

```js
{
  session,
  body: { /* service payload */ }
}
```

## Common Failures

- `401 NO_CREDENTIALS`: missing `Authorization: Micro ...`, token is not a JWT, wrong secret, or wrong environment token.
- `TypeError: Cannot read properties of undefined (reading '1')` in `qpay-micro-service/lib/core/micro.js`: `session[2]` / `MS_SESSION` is missing while micro logging is enabled.
- Sequelize `notNull Violation` for `created_by`, `created_date`, `updated_by`, `updated_date`: `session[1]` / `DB_SESSION` is missing or malformed.
- `fetch failed` with `UND_ERR_CONNECT_TIMEOUT`: network/routing issue, not an application result.
- `500 SYSTEM_BUSY`: check service logs; public response is intentionally generic.
- Successful smoke response still has old behavior: target probably has not deployed the current branch yet.

## Script Template

Use `scripts/qpay_micro_smoke_template.js` as the starting point when adding a repo-local smoke script. Copy it into the target repo and adapt the payload/file field names.

The template auto-loads `.env.smoke` if present, but shell environment overrides win. Keep `.env.smoke` ignored and commit only `.env.smoke.example`.

