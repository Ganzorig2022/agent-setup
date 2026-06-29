# SQL Optimization — Reference

Detailed patterns and runbooks. Read the relevant section when applying the
matching part of SKILL.md.

## 1. Find the worst-case input

Benchmark on the heaviest row, not an average one:

```sql
SELECT package_id, COUNT(*) AS n
FROM invoice
WHERE status = true
GROUP BY package_id
ORDER BY n DESC
LIMIT 10;
```

Plug the top key into `EXPLAIN (ANALYZE, BUFFERS)`.

## 2. Anti-pattern → fix: global aggregate before filter

**Slow (real example, ~2.7s for a 20-row page):** a derived table aggregates the
*entire* `invoice` + `sms_history` tables, *then* the outer query filters by
package. Plus `json_agg` of every payment row per invoice, plus `SELECT INV.*`,
plus a `GROUP BY`. Cost scales with total DB size, not page size.

```sql
SELECT ROW_NUMBER() OVER (ORDER BY INV.invoice_no), INV.*,
  COALESCE(history.history_count::int,0) AS history_count,
  COALESCE(json_agg(payment_data) FILTER (WHERE payment_data.invoice_id IS NOT NULL),'[]') AS payment_history,
  COALESCE((jsonb_agg(payment_data ORDER BY payment_data.payment_status_date DESC)->0),'{}') AS last_payment_object
FROM invoice INV
LEFT JOIN (SELECT I.id, count(SH.history_id) AS history_count
           FROM invoice I LEFT JOIN sms_history SH ON I.id::text = SH.group_id AND SH.status=true
           GROUP BY I.id) history ON history.id::text = INV.id::text          -- whole table!
LEFT JOIN (SELECT PH.* FROM payment_history PH) payment_data
       ON payment_data.invoice_id::text = INV.id::text                        -- whole table!
WHERE INV.status=true AND INV.package_id = '<id>'
GROUP BY INV.id, history.history_count
ORDER BY INV.invoice_no LIMIT 20 OFFSET 0;
```

**Fast (~0.014s, ~190× faster):** paginate first in a CTE, then enrich the 20
rows with correlated `LATERAL` subqueries. No global `GROUP BY`, explicit columns,
`count` + latest-object instead of a full array.

```sql
WITH inv_page AS (
    SELECT inv.*
    FROM invoice inv
    WHERE inv.status = true
      AND inv.package_id = :package_id        -- + any optional search/status filters
    ORDER BY inv.invoice_no ASC
    LIMIT :limit OFFSET :offset
)
SELECT
    ROW_NUMBER() OVER (ORDER BY inv.invoice_no ASC) AS row_num,
    inv.id, inv.created_date, inv.invoice_no, inv.invoice_total_amount,
    inv.invoice_status, inv.sms_status, inv.payment_status, inv.msg_text,   -- only what's used
    COALESCE(sh.history_count, 0)  AS history_count,
    COALESCE(pay.payment_count, 0) AS payment_count,
    pay.last_payment_object
FROM inv_page inv
LEFT JOIN LATERAL (
    SELECT count(*)::int AS history_count
    FROM sms_history sh
    WHERE sh.group_id = inv.id::text AND sh.status = true
) sh ON true
LEFT JOIN LATERAL (
    SELECT count(*)::int AS payment_count,
           (SELECT to_jsonb(p2) FROM payment_history p2
             WHERE p2.invoice_id = inv.id
             ORDER BY p2.payment_status_date DESC LIMIT 1) AS last_payment_object
    FROM payment_history ph
    WHERE ph.invoice_id = inv.id
) pay ON true
ORDER BY inv.invoice_no ASC;
```

Why the CTE matters: it *forces* "filter+sort+limit, then enrich," so LATERAL
runs N times (page size) instead of once per matching row. Don't rely on the
planner to push the LIMIT below the joins — pin it.

Keep the outer `ORDER BY` — joining onto the CTE does not guarantee row order.

## 3. Parameterization gotchas

- Use named params (`:name`) or positional (`?`) — never interpolate user input.
- Extra keys in a replacements object are ignored; a referenced key that is
  **missing or `undefined`** throws. `null` is fine and binds as `NULL`.
- **Postgres `::` casts are safe** with named replacements in mature drivers
  (e.g. Sequelize 6 skips `::text`, `::int`, `::jsonb` and `'strings'`/`-- comments`).
  A green build does not prove this — only running the query does. Test once.
- Trusted server constants (status enums) can also be bound for plan stability.

## 4. Write-on-read removal — verify before deleting

Before deleting a persisted/denormalized value's writer, confirm **no consumer
reads it** (grep the frontend AND sibling services/admin/reports). If a reader
exists, move the recompute to where the data changes, or compute on demand.
If nothing reads it, just delete the write — it was pure overhead (and often
carries latent bugs, e.g. writing an `undefined`/missing field).

## 5. Index production rollout (PostgreSQL)

Plain `CREATE INDEX` locks out writes for the whole build → unacceptable on big
live tables. Use `CONCURRENTLY`:

```sql
-- Run ONE AT A TIME. CONCURRENTLY cannot run inside a transaction or a
-- multi-statement pipeline (error 25001). In a GUI: set AUTO-COMMIT, execute
-- each statement individually (NOT "run script"). Non-prod/small tables: you may
-- drop CONCURRENTLY and run as a normal script.

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_invoice_package_id_invoice_no
  ON invoice (package_id, invoice_no);                 -- filter + sort + pagination
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_payment_history_invoice_id_date
  ON payment_history (invoice_id, payment_status_date DESC);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sms_history_group_id
  ON sms_history (group_id) WHERE status = true;       -- partial: smaller + cheaper writes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sms_history_package_id
  ON sms_history (package_id);
```

Operational notes:
- Off-peak; the table stays fully readable/writable during the build (this is
  wall-clock build time, not downtime). Biggest table = longest.
- A long-running open transaction stalls a CONCURRENTLY build until it finishes.
- Watch progress (PG 12+): `SELECT * FROM pg_stat_progress_create_index;`
- Rough build time: ~1M rows → 1–2 min; ~10M → 5–15 min; ~50–100M → 30–90 min.

Verify validity (a failed CONCURRENTLY build leaves an INVALID index):

```sql
SELECT indexrelid::regclass AS index, indisvalid
FROM pg_index WHERE NOT indisvalid;
-- if any: DROP INDEX CONCURRENTLY <name>;  then re-run its CREATE
```

Confirm the planner uses it: `EXPLAIN` the real query → expect `Index Scan using <name>`.

## 6. Prune unused indexes (write-cost hygiene)

After real traffic, drop indexes that never get scanned:

```sql
SELECT relname, indexrelname, idx_scan
FROM pg_stat_user_indexes
WHERE indexrelname LIKE 'idx_%'
ORDER BY idx_scan;          -- idx_scan = 0 ⇒ candidate to DROP
```

## 7. Substring search

`LIKE '%term%'` (leading wildcard) can't use a B-tree. Options:
- If the search is already scoped (e.g. by `package_id`), the scan is over the
  small filtered set — usually fine, no extra index needed.
- For large unscoped substring search, add `CREATE EXTENSION pg_trgm;` + a GIN
  trigram index (needs DB privileges).
- Prefix-only search (`term%`) can use a plain B-tree — cheapest if acceptable.
