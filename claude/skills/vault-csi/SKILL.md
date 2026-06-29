---
name: vault-csi
description: Wire a containerized Node.js/Next.js app (or any app) to HashiCorp Vault secrets in Kubernetes using the Secrets Store CSI Driver + Vault CSI Provider. Covers the image-side contract, migration away from Vault Agent sidecar, runtime entrypoint that promotes mounted files to env vars, and the sysadmin-side resources. Use when the user asks to "deploy with Vault CSI", "move off Vault Agent", "read secrets from /mnt/secrets in k8s", or sees env-validation failures in a pod that has a CSI volume mounted.
user-invocable: true
---

# Vault CSI integration (app-image side)

This skill is for the **app/image side** of a Vault CSI integration. The cluster side (CSI Driver install, Vault Provider install, Vault Kubernetes auth, policies, roles, `SecretProviderClass`) is almost always operated by a sysadmin/platform team. Do not invent cluster resources unless the user asks.

## When to use

Trigger on any of:

- User has a `Dockerfile` + pod Deployment and wants secrets from Vault, not env vars in the manifest.
- User is migrating off a **Vault Agent sidecar** pattern (consul-template `.ctmpl`, rendered `.env` file, `VAULT_SECRETS_FILE`, `SECRETS_PROVIDER=vault-agent`). That pattern does not compose well with K8s pod lifecycles.
- User sees Zod/env-validation failures inside a pod that has a CSI volume mounted at `/mnt/secrets`, `/mnt/secrets-store`, or similar.
- User references their sysadmin's terminal showing paths like `/mnt/secrets-store/<KEY>`.

Do NOT trigger on: local dev env problems, generic `.env` loading, or non-Kubernetes deployments.

## Mental model

The Secrets Store CSI Driver mounts each Vault KV key as a **read-only tmpfs file** at `<mountPath>/<KEY>`. The app can consume the secrets in one of two ways:

- **A. `secretObjects` → sync to K8s `Secret` → `envFrom: secretRef`.** App reads `process.env` with zero code changes. Cleanest if the sysadmin is willing to create the synced Secret.
- **B. File-mount only → entrypoint reads files → exports as env vars → execs app.** No K8s Secret, no extra RBAC. Works when sysadmins only expose the CSI volume. **Pick B when the sysadmin's existing pattern is `/mnt/<something>/<KEY>` files** — that's the signal they've standardized on file-mount.

This skill focuses on pattern B because that's the common sysadmin convention in shops that prefer the CSI volume to be the single source of truth.

## The image-side contract

Four pieces together:

1. `Dockerfile` — two env vars declaring the CSI runtime contract.
2. `scripts/docker-entrypoint.sh` — reads files, exports env vars, execs the real command.
3. `src/lib/env.ts` (or equivalent) — app-level env schema. **Must not** contain `SECRETS_PROVIDER`, `VAULT_SECRETS_FILE`, or CSI-path variables. Those are infra concerns.
4. `CMD ["sh", "./scripts/docker-entrypoint.sh"]`.

### Dockerfile (runner stage)

```dockerfile
ENV SECRETS_PROVIDER=vault-csi
ENV VAULT_CSI_MOUNT_PATH=/mnt/secrets   # match the cluster's mountPath convention
...
COPY --from=builder /app/scripts/docker-entrypoint.sh ./scripts/docker-entrypoint.sh
RUN chmod +x ./scripts/docker-entrypoint.sh
CMD ["sh", "./scripts/docker-entrypoint.sh"]
```

**Pick the default `VAULT_CSI_MOUNT_PATH` to match the cluster convention** (`/mnt/secrets`, `/mnt/secrets-store`, etc.). That way the Deployment does not need to override it. Confirm the path by asking for the actual Deployment YAML — do not guess.

Default `SECRETS_PROVIDER=vault-csi` is a trade-off: K8s works out of the box, but running the image outside K8s (e.g., `docker run` for debugging) requires `-e SECRETS_PROVIDER=env`. That's intentional — failing fast beats booting with empty secrets.

### Entrypoint

```sh
#!/bin/sh
set -eu

SECRETS_PROVIDER="${SECRETS_PROVIDER:-env}"
VAULT_CSI_MOUNT_PATH="${VAULT_CSI_MOUNT_PATH:-/mnt/secrets-store}"

if [ "${SECRETS_PROVIDER}" = "vault-csi" ]; then
  if [ ! -d "${VAULT_CSI_MOUNT_PATH}" ]; then
    echo "Vault CSI mount not found: ${VAULT_CSI_MOUNT_PATH}" >&2
    exit 1
  fi

  for file in "${VAULT_CSI_MOUNT_PATH}"/*; do
    [ -f "${file}" ] || continue
    name="$(basename "${file}")"
    case "${name}" in
      .*) continue ;;
    esac
    value="$(cat "${file}")"
    export "${name}=${value}"
  done
fi

exec node server.js   # or whatever the real command is
```

Key rules:

- Use **POSIX `sh`**, not `bash`. Node Alpine images may not have bash.
- Iterate files, **skip dotfiles**, basename-as-env-var-name (case-sensitive match with Zod keys).
- `exec` the real command so signals reach it (PID 1 behavior).
- Fail fast if the mount isn't there — do NOT silently fall through to empty env.

### App env schema (Zod, 12-factor)

```ts
// src/lib/env.ts
const envSchema = z.object({
  NODE_ENV: z.enum(["development", "test", "production"]).default("development"),
  // ... required runtime secrets, each matching a Vault KV key exactly by name
});
```

**Do NOT put `SECRETS_PROVIDER` or CSI path vars in the Zod schema.** The app should not know how secrets arrive. That is the entrypoint's job.

## Migrating OFF Vault Agent sidecar

If the repo currently has:

- `ops/vault/agent/*.hcl`, `*.ctmpl` — consul-template rendered env files
- `scripts/vault-local-init.sh`, `scripts/start-with-vault-secrets.sh`
- `docker-compose.yml` with `vault` + `vault-agent` services
- `SECRETS_PROVIDER=vault-agent` and `VAULT_SECRETS_FILE` references

Delete all of that. CSI replaces the rendering pipeline end-to-end. Do NOT keep a "transition shim" — dual-mode entrypoints rot fast. A clean cut is safer.

Concrete cleanup checklist:

- [ ] Delete `ops/vault/agent/` directory.
- [ ] Delete `scripts/vault-local-init.sh` and `scripts/start-with-vault-secrets.sh`.
- [ ] Rewrite `scripts/docker-entrypoint.sh` to the form above.
- [ ] Change `Dockerfile` envs: drop `VAULT_SECRETS_FILE`, add `VAULT_CSI_MOUNT_PATH`, flip `SECRETS_PROVIDER` default to `vault-csi`.
- [ ] Drop `vault` and `vault-agent` services from `docker-compose.yml` (and related profiles).
- [ ] Drop `SECRETS_PROVIDER` and `VAULT_SECRETS_FILE` from the app Zod schema.
- [ ] Update test fixtures/mocks that reference those fields.
- [ ] Drop `.vault-local/` from `.gitignore` if nothing else writes there.
- [ ] Rewrite README: short "Vault Secrets (CSI)" section describing the runtime contract only. Do not document cluster-side resources in the app repo unless the app team owns them.
- [ ] Drop stale keys from `.env.example`.

## Common pitfalls (observed in real migrations)

1. **Deployment still sets `SECRETS_PROVIDER=env`.** Entrypoint skips the CSI branch and the app boots with an empty `process.env`. Zod throws `Invalid environment variables: [ 'PGDB_HOST', 'PG_USER', ... ]`. Fix: sysadmin removes the env override or changes it to `vault-csi`.
2. **Mount path mismatch.** Image defaults to `/mnt/secrets-store`; cluster mounts at `/mnt/secrets` (or vice versa). Entrypoint fails with "Vault CSI mount not found". Fix: align the Dockerfile default with the cluster's convention, or set `VAULT_CSI_MOUNT_PATH` in the Deployment env.
3. **Case-sensitive filename mismatch.** `SecretProviderClass` has `objectName: pgdb_host` but Zod expects `PGDB_HOST`. Fix: filenames on disk must match env var names exactly.
4. **Stale `VAULT_SECRETS_FILE` env var in the Deployment.** Harmless but confusing — it's a leftover from the Vault Agent era. Remove it.
5. **Forgetting non-secret files in the runner stage.** Next.js standalone builds only copy `public`, `.next/standalone`, `.next/static`. If the app reads from `docs-content/`, `templates/`, or similar at runtime, add an explicit `COPY --from=builder /app/<dir> ./<dir>` in the runner stage. Unrelated to Vault, but easily blamed on the migration because it surfaces on the same redeploy.
6. **Secret rotation and Node caching.** CSI rewrites files at the mount path on rotation, but Node has already read `process.env` into memory at startup. Rotation requires a rolling restart of the Deployment. Document this.
7. **`.DS_Store` and other noise inside secret mounts.** The entrypoint's dotfile skip handles this, but be aware.

## Verification checklist (before declaring done)

Run through with the user:

1. `pnpm run typecheck` ✓ clean after schema changes.
2. `pnpm run test` ✓ tests that mock the env module updated.
3. Image rebuilds without errors.
4. After redeploy, on the pod:
   - `ls -la <VAULT_CSI_MOUNT_PATH>/` shows a file per required Zod key, filenames match exactly, content non-empty.
   - `env | grep -E '<some secret key>'` shows the exported value.
   - App's `/health` or equivalent returns 200.
5. Pod logs contain no `Invalid environment variables: [...]` entries.

## What to ask the sysadmin (not do yourself)

If the image-side contract is correct and secrets still aren't arriving, the issue is cluster-side. Ask the sysadmin for:

- The Deployment YAML (`kubectl get deploy <name> -o yaml`) — to confirm `volumeMounts`, `env`, and that no leftover `SECRETS_PROVIDER=env` overrides the image default.
- The `SecretProviderClass` YAML — to confirm `objects` list uses the correct `objectName` values (== Zod keys) and the right Vault KV path.
- Vault role/policy — is the pod's ServiceAccount bound to a Vault role with read on the KV path?
- `kubectl describe pod <name>` — CSI-related events often surface here (auth failures, missing provider, etc.).

Do NOT write `SecretProviderClass`, `ServiceAccount`, or Vault policy files into the app repo unless the user explicitly asks for reference examples. Cluster resources belong in the sysadmin's repo.

## Local development

No Vault locally. The image's entrypoint with `SECRETS_PROVIDER=env` sources `process.env` normally; for `pnpm dev` outside Docker, `.env` / `.env.local` work as usual. Do not try to reproduce CSI locally — dev-mode Vault + sidecar simulation is exactly the anti-pattern this skill replaces.
