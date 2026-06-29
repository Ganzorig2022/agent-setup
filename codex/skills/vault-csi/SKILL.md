---
name: vault-csi
description: Wire a containerized Node.js or Next.js app to HashiCorp Vault secrets in Kubernetes through the Secrets Store CSI Driver and Vault CSI Provider.
origin: agent-stack
---

# Vault CSI Integration

This skill is for the app-image side of a Vault CSI integration.

Use it when the user wants to:

- deploy with Vault CSI
- move off a Vault Agent sidecar pattern
- read secrets from a mounted path such as `/mnt/secrets`
- fix env-validation failures in a pod that already has a CSI volume

## Mental Model

The CSI driver mounts Vault keys as read-only files at `<mountPath>/<KEY>`.

There are two common consumption patterns:

1. sync to a Kubernetes `Secret` and use `envFrom`
2. read mounted files in the container entrypoint, export env vars, then `exec` the app

Prefer the second pattern when the cluster convention is already file-mount based.

## Image-Side Contract

The app side normally needs four pieces:

1. `Dockerfile` env vars that describe the CSI runtime contract
2. a POSIX `sh` entrypoint that reads files and exports env vars
3. an app env schema that validates only application-facing env vars
4. a final `CMD` that runs through the entrypoint

## Entry Point Rules

- use POSIX `sh`, not `bash`
- fail fast if the mount path is missing
- skip dotfiles
- export one env var per mounted file
- `exec` the real process so signals propagate correctly

## App Schema Rules

- keep Vault transport details out of the app schema
- do not require CSI-specific helper vars in Zod or equivalent validation
- validate the actual runtime secrets the app needs

## Migration Guidance

When moving off Vault Agent sidecar patterns:

- remove rendered `.env` workflows
- remove `VAULT_SECRETS_FILE` style plumbing
- simplify the entrypoint to file-read plus export
- align the default mount path with the cluster convention
- update tests and docs to the new contract

Do not keep a half-migrated dual-mode secret bootstrap unless the user explicitly asks for it.

## Common Failures

- deployment overrides `SECRETS_PROVIDER=env`
- image expects a different mount path than the pod uses
- mounted filenames do not match expected env var names
- stale Vault Agent env vars remain in deployment manifests
- runtime-only app assets are missing and get blamed on the Vault migration

## Verification

Before declaring success, verify:

- typecheck passes after env-schema changes
- tests pass after fixture updates
- the image rebuilds cleanly
- the mounted secret files exist in the running pod
- the app can see exported env vars
- health checks pass after deploy

If the image-side contract is correct and secrets still do not appear, ask for deployment YAML and `SecretProviderClass` details instead of guessing cluster-side fixes.
