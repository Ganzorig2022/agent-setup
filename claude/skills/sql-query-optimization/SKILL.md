---
name: sql-query-optimization
description: Diagnose and fix slow SQL read paths (PostgreSQL-focused) — measure with EXPLAIN ANALYZE, apply the paginate-first CTE pattern, scope enrichment with LATERAL, parameterize, and add the right indexes safely in production. Use when a query/endpoint/list/report is slow, when adding DB indexes, when reviewing raw SQL, or when a read does too much (full-table scans, GROUP BY before filtering, write-on-read, json_agg of whole arrays). Agent-neutral; works for any agent.
---

# SQL Query Optimization

Library/ORM-agnostic playbook for making slow reads fast without changing behavior.
PostgreSQL-specific where noted; the patterns transfer to most engines.

## Diagnostic loop (always measure first)

1. Get the **exact** executed SQL (substitute real literal values for params).
2. Run `EXPLAIN (ANALYZE, BUFFERS) <query>` on a **worst-case row** (e.g. the
   biggest `package_id` / tenant — find it with `GROUP BY … ORDER BY count DESC LIMIT 1`).
3. Read the plan: `Seq Scan` on a big table = suspect; `HashAggregate`/`GroupAggregate`
   over millions of rows = suspect; `Buffers: shared read=<big>` = heavy disk I/O.
   Bottom-line `Execution Time` is the number to beat.
4. Change one thing, re-measure on the same input. Compare `Execution Time`.

⚠️ `ANALYZE` actually runs the query — safe for `SELECT`, mutates data for
`INSERT/UPDATE/DELETE`. If stats look stale, run `ANALYZE <table>;` so the planner sees new indexes.

## The high-leverage rewrites

- **Paginate first, enrich second.** Put `WHERE` + `ORDER BY` + `LIMIT`/`OFFSET`
  in a CTE, then join enrichment onto the page. The expensive per-row work runs
  on N page rows, not the whole filtered set. Usually the single biggest win.
- **Never aggregate the whole table before filtering.** Replace derived
  subqueries like `(SELECT … FROM big GROUP BY id)` joined-then-filtered with
  **correlated `LATERAL`** subqueries scoped to the current row id.
- **Stop shipping data nobody reads.** Drop `SELECT *`; list only used columns.
  Replace `json_agg(whole_child_array)` with a `count` + a single latest object
  (`ORDER BY … DESC LIMIT 1`) when the UI only needs "how many" + "the latest".
- **Pull writes out of read paths.** A read endpoint that `UPDATE`s on every call
  adds latency, lock contention with writers, and blocks read-replica routing.
  Recompute denormalized totals where the data changes, or compute on demand —
  but first confirm anything even reads the persisted value.
- **Parameterize.** Use bind params / named replacements, never string
  interpolation: closes SQL injection and lets the DB reuse cached plans.

See [REFERENCE.md](REFERENCE.md) for the canonical before/after query, the
parameterization gotchas (incl. Postgres `::` casts), and details.

## Indexing (the usual actual fix)

- B-tree is the default and is always present — no extension, no DBA needed.
  It serves `=`, ranges, sorting, and **prefix** (`LIKE 'x%'`) — but **not**
  leading-wildcard `LIKE '%x%'` (needs `pg_trgm` GIN).
- **Composite (filter + sort):** one index on `(filter_col, sort_col)` powers the
  `WHERE` and the `ORDER BY … LIMIT` together (e.g. `(package_id, invoice_no)`).
- **Join targets:** index the FK side used in lookups (e.g. `payment_history(invoice_id, date DESC)`).
- **Partial:** add `WHERE flag = true` to shrink an index and its write cost.
- Indexes tax writes, but indexed columns that never change let Postgres use
  **HOT updates** and skip maintenance — so status/amount updates stay cheap.

## Production rollout & verification

`CREATE INDEX CONCURRENTLY` (builds without locking writes), **auto-commit ON,
one statement at a time, off-peak**. Full runbook (validity check, recovery from
INVALID, `pg_stat_progress_create_index`, finding unused indexes with
`pg_stat_user_indexes`) → [REFERENCE.md](REFERENCE.md).

## Done checklist

- [ ] Measured before/after `Execution Time` on the same worst-case input
- [ ] Plan shows `Index Scan`, not `Seq Scan`, on the hot table
- [ ] No string-interpolated user input remains in SQL
- [ ] Response shape unchanged, or all consumers updated for the new shape
- [ ] Indexes valid in prod (`indisvalid = true`); deploy code with/after them
