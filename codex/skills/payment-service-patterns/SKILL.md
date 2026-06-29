---
name: payment-service-patterns
description: Money handling, idempotency, transaction consistency, and webhook patterns for fintech services on Node/Express with Mongoose (MongoDB) and Sequelize (PostgreSQL). Use for qpay/qcard/qp2p-style payment, wallet, settlement, and transaction code.
origin: agent-stack
---

# Payment Service Patterns

Conventions for correctness-critical money movement in Node/Express services backed by
Mongoose (MongoDB) and Sequelize (PostgreSQL). These rules exist because the failure
modes here are not "a bug" — they are lost, duplicated, or corrupted money.

## When to Activate

- Writing or reviewing wallet, transaction, settlement, transfer, or ledger code
- Handling external payment/bank callbacks or webhooks
- Anything that creates, mutates, or reconciles a balance or a money amount
- Retried, queued, or at-least-once-delivered operations
- Code touching both MongoDB and PostgreSQL in one logical operation

## 1. Money Representation

- **Never use floating point for money.** `0.1 + 0.2 !== 0.3`. Store amounts as
  **integer minor units** (e.g. tugrik/cents) or a fixed-precision decimal.
  - Postgres (Sequelize): `DECIMAL(20,4)` or `BIGINT` minor units — never `FLOAT`/`DOUBLE`/`REAL`.
  - Mongo (Mongoose): `Decimal128` or integer minor units — never `Number` for amounts.
- Do arithmetic in integer minor units, or with a decimal library — not native `+`/`*` on currency floats.
- Always pair an amount with an explicit `currency` field. Reject mixed-currency arithmetic.
- Round only at well-defined boundaries with a documented rounding mode; never let rounding silently create or destroy value.

## 2. Idempotency (mandatory for money-moving endpoints)

At-least-once delivery is the default for webhooks, retries, and client re-submits.
Every money-moving operation must be safe to run twice.

- Require an **idempotency key** (client-supplied or derived from a stable external id,
  e.g. provider transaction id). Persist it with a **unique index**.
- On duplicate key: return the **stored original result**, do not re-execute.
  ```js
  // unique index on { idempotencyKey: 1 }
  try {
    await Txn.create([{ idempotencyKey, amount, currency }], { session });
  } catch (e) {
    if (e.code === 11000) return loadExistingResult(idempotencyKey); // replay-safe
    throw e;
  }
  ```
- Make the **uniqueness the guard**, not a read-then-write check (that races).
- Webhook handlers: dedupe on the provider's event id before applying effects.

## 3. Transaction Consistency

- Wrap multi-document/multi-row money mutations in a real transaction.
  - **Mongoose**: use a `session` + `withTransaction`; pass `{ session }` to *every*
    read and write inside it. A write without the session silently escapes the transaction.
  - **Sequelize**: pass the `transaction` to every query; prefer `sequelize.transaction(async (t) => …)`
    so commit/rollback is automatic.
- **Dual-store writes (Mongo + Postgres) are NOT atomic.** There is no 2-phase commit.
  Do not "write to Postgres then Mongo" and hope. Use one of:
  - a **transactional outbox** (commit the state change + an outbox row in the same DB tx,
    then relay the event), or
  - a **saga** with explicit compensating actions, or
  - designate **one store as the source of truth** for the balance and treat the other as a projection.
- Make the relay/projection **idempotent** (see §2) so replays converge.

## 4. Concurrency on Balances

- Concurrent debits/credits on the same wallet race. Protect with one of:
  - **Optimistic locking**: a `version` field; reject on stale version and retry.
    (Mongoose: `optimisticConcurrency: true` / `__v`; Sequelize: `version: true`.)
  - **Atomic conditional update** instead of read-modify-write:
    ```js
    // debit only if sufficient funds, atomically — no read-then-write window
    const res = await Wallet.updateOne(
      { _id, balance: { $gte: amount } },
      { $inc: { balance: -amount } },
      { session }
    );
    if (res.modifiedCount === 0) throw new InsufficientFundsError();
    ```
- Never compute `newBalance = current - amount` in JS and write it back without a guard.

## 5. Webhooks / External Callbacks

- **Verify the signature** before doing anything else; reject unverified payloads.
- Treat the body as untrusted: validate against a schema (zod/joi) before use.
- Process **idempotently** (§2) — providers retry, and you will receive duplicates.
- Acknowledge fast (2xx) only after the effect is durably recorded; if you ack before
  persisting, a crash loses the event. If you can't process synchronously, persist the
  raw event first, ack, then process from the stored record.
- Be tolerant of **out-of-order** delivery; reconcile by state, not by arrival order.

## 6. Audit & Immutability

- Financial records are **append-only**. Don't mutate or delete a posted transaction —
  post a reversing/adjusting entry instead. (Aligns with the immutability rule in coding-style.)
- Record who/what/when for every state transition; keep a status history, not just a current status.
- Reconciliation jobs compare ledger vs. provider; surface drift loudly.

## 7. Security & Logging

- Never log full PANs, CVVs, tokens, secrets, or full request bodies of payment calls.
- Mask sensitive identifiers in logs and errors.
- Validate all external input at the boundary; never spread raw `req.body` into a query
  (NoSQL injection) or into a model `.create()` (mass assignment of e.g. `balance`/`status`).

## Review Checklist

- [ ] No float used for any monetary amount; amount always paired with currency
- [ ] Money-moving endpoints/webhooks are idempotent via a unique key, not read-then-write
- [ ] Every read/write inside a transaction carries the session/transaction handle
- [ ] No naked dual-store write assumed atomic (outbox/saga/source-of-truth instead)
- [ ] Balance changes use optimistic lock or atomic conditional update, never read-modify-write
- [ ] Webhook signature verified + schema-validated + deduped before effects
- [ ] Effects durably recorded before 2xx ack
- [ ] Financial records append-only; reversals instead of edits/deletes
- [ ] No secrets/PANs in logs; no raw `req.body` into queries or `.create()`

## Related

- Agents: `typescript-reviewer` (Node/async/NoSQL-injection lanes), `security-reviewer`, `database-reviewer` (Postgres/Sequelize)
- Skills: `backend-patterns`
