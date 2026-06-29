---
name: vault-nextjs-integration
description: Implement HashiCorp Vault secret delivery for Next.js web applications without app-side Vault API calls. Use when users ask to secure runtime secrets, rotate JWT/DB credentials, add Vault Agent integration, support Docker or Dockerfile-only deployment, or migrate from plain environment-variable injection to Vault-backed secret management.
---

# Vault Next.js Integration

## Overview
Implement Vault integration where Next.js continues to read `process.env` while Vault Agent handles authentication and secret retrieval. Preserve a dual-mode startup path: plain env mode and Vault Agent file mode.

## Workflow

### 1. Audit current secret flow
Identify where secrets are read and injected before changing runtime behavior.

- Find app secret reads in server-only modules (`env`, auth, DB connection, route handlers).
- Confirm public variables (`NEXT_PUBLIC_*`) are not secret-bearing.
- Confirm deployment startup path (`Dockerfile`, compose, container command).
- Capture required secret inventory: DB credentials, JWT secrets, cookie names, and any API keys.

### 2. Choose runtime mode strategy
Keep one image that supports both modes.

- Keep default mode as plain env injection.
- Add Vault mode that sources a rendered secrets file before app boot.
- Avoid direct Vault client code in `src/` unless user explicitly requests that pattern.

### 3. Add Vault ops artifacts
Define policy, agent behavior, and key mapping.

- Create read-only Vault policy scoped to the app path.
- Create Vault Agent config that authenticates and renders a file.
- Create a template that maps Vault keys to exact env var names the app expects.
- Use environment path scoping (`dev`, `staging`, `prod`) to avoid cross-env access.

See `references/deployment-patterns.md` for starter templates.

### 4. Wire container startup
Update startup to optionally source rendered secrets.

- Add entrypoint script that checks `SECRETS_PROVIDER`.
- In `vault-agent` mode: fail fast if the rendered file is missing, then source it.
- In `env` mode: start app with existing environment.
- Update `Dockerfile` command to use entrypoint.
- Keep app boot command unchanged after env load (`node server.js` or `next start`).

### 5. Add local POC path
Provide a reproducible local setup for validation.

- Add local Vault dev stack only for experimentation.
- Add init/seed script that:
- starts Vault,
- enables KV v2,
- writes required keys,
- applies read-only policy,
- creates agent token or local auth material,
- starts Vault Agent,
- verifies rendered env file exists.
- Mark dev mode as non-production.

### 6. Validate behavior
Run both functional and security checks.

- Run typecheck, tests, and build.
- Boot in `env` mode and verify health endpoint.
- Boot in `vault-agent` mode and verify health endpoint.
- Remove one required secret and confirm startup fails fast.
- Confirm no secret appears in client-side bundles or `NEXT_PUBLIC_*` namespace.

## Security guardrails
Apply these rules on every implementation.

- Keep admin and docs auth secrets separate.
- Do not commit secret values or long-lived tokens.
- Keep policy capabilities minimal (`read` only for runtime identity).
- Use TLS and audit devices for non-local environments.
- Revoke bootstrap/root credentials after provisioning.
- Treat Vault dev mode as local-only.

## Output checklist
Produce these outcomes before closing the task.

- Vault policy file, agent config file, and env template added.
- Entrypoint and Dockerfile wired for dual-mode startup.
- Runtime controls documented (`SECRETS_PROVIDER`, `VAULT_SECRETS_FILE`).
- Local POC steps documented.
- Verification results reported with explicit pass/fail and gaps.

## Troubleshooting shortcuts
Use these quick checks when integration fails.

- If app fails in Vault mode, verify rendered file path and mount first.
- If agent cannot read secrets, verify policy path and auth identity.
- If app boots but auth breaks, verify JWT secret keys mapped correctly.
- If tests fail on env mocks, update mocks to include new optional env keys and helper exports.
