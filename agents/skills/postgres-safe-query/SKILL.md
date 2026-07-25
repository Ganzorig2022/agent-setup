---
name: postgres-safe-query
description: Run guarded read-only SQL against a QPay PostgreSQL database — resolve the connection from src/config, force a read-only transaction with timeouts, mask PII in output, and refuse writes. Use when you need to inspect real data to answer a question, verify a bug, check row counts, or read a schema. Not for tuning (use sql-query-optimization) or schema changes (use database-reviewer).
---

# Postgres Safe Query

Reading production-shaped payment data is a real action with real blast radius. This skill is the guarded path: read-only by construction, timeout-bounded, PII-masked, and explicit about which database you are pointed at.

## When to Use

- A bug hypothesis needs a row count, a distribution, or one concrete record
- Verifying a migration landed, or what a column actually contains
- Reading schema/index reality instead of trusting the Sequelize model
- Confirming a Bull job's side effects actually persisted

## Do Not Use When

- The task is making a slow query fast → `sql-query-optimization`
- The task is a schema change, migration, or index design → `database-reviewer` agent
- You need to **write** anything. This skill has no write path. Writes go to the user or to a migration, never to an ad-hoc session

## Step 1 — Resolve the connection, and say it out loud

Never guess a connection string. Resolve it, then state which database you are about to query and wait for confirmation if it is anything other than local.

```bash
# QPay Stack A/B: config is centralized, services never read process.env directly
fd -g '*.js' src/config | head
rg -n 'DB_HOST|DB_NAME|POSTGRES|DATABASE_URL' src/config .env* 2>/dev/null
```

**Never echo the password.** Read the config to build the connection, print only `host/db/user` — mask everything else. If you need the URL in a command, put it in an env var, do not inline it into a command line that gets logged.

Classify before connecting:

| Target | Rule |
|--------|------|
| Local / docker | Proceed |
| Dev / staging | Proceed, state the target first |
| **Production** | **Stop. Ask for explicit confirmation naming the database.** Then read-only only, always with `LIMIT` |

If a dedicated read-only role exists, use it. A read-only role beats every guard below, because it does not depend on you remembering them.

## Step 2 — The guarded session preamble

Every session starts with this. Not optional, including for "just one quick select".

```sql
SET default_transaction_read_only = on;
SET statement_timeout = '30s';
SET idle_in_transaction_session_timeout = '30s';
SET lock_timeout = '5s';
BEGIN READ ONLY;
  -- your query here, always with LIMIT
ROLLBACK;
```

Invoked as:

```bash
psql "$PGURL" -v ON_ERROR_STOP=1 --no-psqlrc -P pager=off -f query.sql
```

What each guard buys you:

- `default_transaction_read_only` + `BEGIN READ ONLY` — the server rejects INSERT/UPDATE/DELETE/DDL. Two layers because a stray `COMMIT` mid-script can end the block
- `statement_timeout` — a runaway seq scan on a payments table dies in 30s instead of holding resources
- `lock_timeout` — you never queue behind a writer
- `idle_in_transaction_session_timeout` — an abandoned session cannot pin a snapshot and block vacuum
- `ON_ERROR_STOP=1` — the script halts on first error instead of ploughing on
- `--no-psqlrc` — the user's `.psqlrc` cannot change your session settings underneath you

`EXPLAIN (ANALYZE, BUFFERS)` **executes** the statement. Inside a read-only transaction it is safe for `SELECT`. Never run it on DML.

## Step 3 — Query discipline

- **Always `LIMIT`.** Even for counts, prefer a bounded probe before a full aggregate on a large table
- **Never `SELECT *` on a customer/payment table.** Name the columns you actually need — that alone prevents most accidental PII dumps
- **Aggregate before you inspect.** `count(*) GROUP BY status` answers most questions without touching a single personal record
- **`\x auto`** for wide rows; **`\timing on`** so you notice when a "quick check" costs 8 seconds

## Step 4 — PII and payment-data handling

QPay is a payment system. Query output lands in a transcript that may be summarized, logged, or pasted.

Mask at the query level, not after:

```sql
SELECT id,
       left(phone, 4) || '****'            AS phone_masked,
       right(card_number, 4)               AS pan_last4,
       regexp_replace(email, '(.).*(@.*)', '\1***\2') AS email_masked,
       amount, status, created_at
FROM transactions
WHERE created_at > now() - interval '1 day'
LIMIT 20;
```

Hard rules:

- Never output a full PAN, full phone, national ID, or auth token — masked or not at all
- Never dump whole customer rows to illustrate a point. One masked example row is enough
- If the answer only needs a shape, return the shape: counts, distributions, min/max, null rates

## Step 5 — Sequelize model → real table

The model file is a claim; the database is the fact. Bridge them before trusting either:

```bash
rg -n 'tableName|freezeTableName|underscored' src/models/<model>.js
```

Sequelize pluralizes and (with `underscored`) snake_cases by default, so `PaymentOrder` may be `payment_orders` or `PaymentOrders`. Confirm against reality:

```sql
\d+ payment_orders                                    -- columns, indexes, defaults
SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'payment_orders';
```

The single highest-value check when something is slow — foreign keys with no index:

```sql
SELECT conrelid::regclass AS table_name, a.attname AS column_name
FROM pg_constraint c
JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY(c.conkey)
WHERE c.contype = 'f'
  AND NOT EXISTS (
    SELECT 1 FROM pg_index i
    WHERE i.indrelid = c.conrelid AND a.attnum = ANY(i.indkey)
  );
```

## Refuse List

Decline these in this skill, and say why:

- Any `INSERT` / `UPDATE` / `DELETE` / `TRUNCATE` / DDL, including "just to test"
- `pg_terminate_backend` / `pg_cancel_backend` on anything you did not start
- `VACUUM` / `REINDEX` / `ALTER SYSTEM`
- Disabling the read-only guards "for one query"
- Copying a production table to a local one

The correct response is a written statement or migration handed to the user, with the exact SQL, so a human executes it.

## Anti-Patterns

- **Connecting before saying which database.** The whole guard chain is worthless if you are pointed at prod and nobody noticed
- **`SELECT *` "to see what's there".** Use `\d+` for structure; select named columns for data
- **Unbounded aggregates on payment tables** — `statement_timeout` will save the database, but it won't save the 30 seconds
- **Pasting the connection string into a command line.** Env var only
- **Trusting the Sequelize model for index existence.** Models describe intent; `pg_indexes` describes reality

## Related

- `sql-query-optimization` — once the query is correct but slow
- `database-reviewer` agent — schema changes, migrations, transaction correctness
- `debug` — QPay service symptom triage that usually precedes needing this
