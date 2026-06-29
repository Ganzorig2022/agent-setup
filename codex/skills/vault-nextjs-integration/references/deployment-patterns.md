# Deployment Patterns

## Pattern A: Dockerfile-only runtime with Vault Agent rendered file

Use this pattern when the app container does not run Vault itself and only consumes a mounted secrets file.

### Runtime controls

```env
SECRETS_PROVIDER=env
VAULT_SECRETS_FILE=/vault/secrets/qpay-docs.env
```

### Entrypoint pattern

```sh
#!/bin/sh
set -eu

SECRETS_PROVIDER="${SECRETS_PROVIDER:-env}"
VAULT_SECRETS_FILE="${VAULT_SECRETS_FILE:-/vault/secrets/qpay-docs.env}"

if [ "${SECRETS_PROVIDER}" = "vault-agent" ]; then
  [ -f "${VAULT_SECRETS_FILE}" ] || { echo "Missing ${VAULT_SECRETS_FILE}" >&2; exit 1; }
  set -a
  . "${VAULT_SECRETS_FILE}"
  set +a
fi

exec node server.js
```

### Dockerfile hook

```dockerfile
ENV SECRETS_PROVIDER=env
ENV VAULT_SECRETS_FILE=/vault/secrets/qpay-docs.env
COPY scripts/docker-entrypoint.sh ./scripts/docker-entrypoint.sh
RUN chmod +x ./scripts/docker-entrypoint.sh
CMD ["sh", "./scripts/docker-entrypoint.sh"]
```

## Pattern B: Local POC with dev Vault + agent

Use only for local experimentation.

1. Start Vault dev server.
2. Enable KV v2 mount.
3. Write app keys into env-specific path.
4. Apply read-only runtime policy.
5. Start Vault Agent with template rendering.
6. Verify rendered file exists before app start.

## Vault key mapping template

Map Vault keys to app env names exactly to avoid app code changes.

```hcl
{{- with secret "qpay-docs/data/dev/qpay-docs" -}}
PGDB_HOST={{ .Data.data.PGDB_HOST }}
PGDB_PORT={{ .Data.data.PGDB_PORT }}
PG_USER={{ .Data.data.PG_USER }}
PG_PASSWORD={{ .Data.data.PG_PASSWORD }}
PG_DATABASE={{ .Data.data.PG_DATABASE }}
ADMIN_JWT_SECRET={{ .Data.data.ADMIN_JWT_SECRET }}
DOCS_JWT_SECRET={{ .Data.data.DOCS_JWT_SECRET }}
ADMIN_COOKIE_NAME={{ .Data.data.ADMIN_COOKIE_NAME }}
DOCS_COOKIE_NAME={{ .Data.data.DOCS_COOKIE_NAME }}
{{- end -}}
```

## Minimal read-only policy pattern

```hcl
path "qpay-docs/data/dev/qpay-docs" {
  capabilities = ["read"]
}

path "qpay-docs/metadata/dev/qpay-docs" {
  capabilities = ["read"]
}
```

## Common failure modes

- Wrong KV path level (`data/` segment mismatch for KV v2).
- Template uses wrong key names.
- Rendered file mounted read-only but path does not exist in container.
- Startup command bypasses entrypoint.
- Env mock tests missing new optional runtime control variables.
