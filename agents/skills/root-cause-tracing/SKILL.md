---
name: root-cause-tracing
description: Trace a bug backward through the call chain from where the error surfaces to the original trigger, then fix at the source and add defense-in-depth at each layer. Use when an error appears deep in execution, when a stack trace is long, when it is unclear where a bad value originated, or when you catch yourself about to patch the line that threw.
---

# Root Cause Tracing

Bugs surface deep in the stack — a `git init` in the wrong directory, a Sequelize query against a null id, a Bull job with an empty payload. The instinct is to fix where the error appears. That is treating a symptom.

**Core principle: trace backward through the call chain until you find the original trigger, then fix at the source.**

## When to Use

- The error happens deep in execution, not at the entry point
- The stack trace shows a long call chain
- It is unclear where an invalid value originated
- You need to find which caller, job, or test triggers the problem

If you cannot trace backward — a genuine dead end, no stack, no caller information — fixing at the symptom point is acceptable. Say explicitly that you did that and why.

## The Tracing Process

### 1. Observe the symptom precisely

Not "the payment fails" — the actual error, the actual value, the actual location.

### 2. Find the immediate cause

What single line directly produces this? Read it. Do not infer it.

### 3. Ask what called this

Walk one level up at a time. Write the chain down:

```
paymentService.charge(orderId)
  → called by chargeQueue processor
  → called by producer in src/queues/charge.producer.js
  → called by POST /v1/payments handler
```

### 4. Keep tracing — follow the *value*, not just the frames

The frames tell you the path; the bad value tells you the origin. At each level ask: what was passed, and was it already wrong here?

An empty string, a `null`, a `undefined` that stringifies to `"undefined"`, a default that silently replaced a missing config — these are the usual originals.

### 5. Find the original trigger

Stop when you reach the place where a correct input became an incorrect one. That is the root cause. Everything below it was faithfully doing its job with bad data.

## When You Cannot Trace Manually — Instrument

Log **before** the dangerous operation, not after it fails, and capture the stack:

```javascript
// Stack A/B (Express/Babel) — use the internal logger, never console.log in service code
const logger = require('qpay-micro-logging');

async function chargeOrder(orderId, amount) {
  logger.debug('TRACE chargeOrder', {
    orderId,
    amount,
    typeofOrderId: typeof orderId,
    stack: new Error().stack,
  });
  ...
}
```

Then grep the run:

```bash
npm start 2>&1 | rg 'TRACE chargeOrder'
```

Include context, not just the value: type, environment, the ids around it, a timestamp. A `TRACE` line showing `orderId: ''` with a stack is a solved bug; one showing `orderId is falsy` is a restatement of the symptom.

Remove the instrumentation before the change ships — it is a debugging tool, not a log line.

## QPay-Specific Trace Entry Points

| Symptom surface | Trace backward toward |
|---|---|
| Express 5 async throw | The route's Joi schema — did validation let a bad shape through, or is the handler receiving something the schema never checked? |
| Sequelize error on a null/undefined id | The service function's caller. Services take plain data; the bad value entered at the route or at another service |
| Bull job fails with a bad payload | The **producer** file, not the processor. The processor is where it surfaces; the producer is where the payload was built |
| Wrong config value | `src/config/` — and then whether something read `process.env` directly, bypassing it |
| Next.js hydration mismatch | Render-time non-determinism: `Date.now()`, `Math.random()`, browser-only APIs |
| Fastify/Zod (Stack C) | The `.strict()` schema at route entry — an unvalidated field means the schema, not the handler, is the root cause |

## Fix at the Source, Then Add Defense in Depth

Fixing only at the origin leaves the bug reachable by the next caller. Fixing only at the symptom leaves it live. Do both:

1. **Fix the source** — the place that produced the bad value
2. **Validate at the boundary** — the route schema (Joi/Zod) that should have caught the shape
3. **Guard the dangerous operation** — fail loudly at the point of use rather than proceeding with a default

Each layer should fail *loudly*. A layer that silently substitutes a default is how the bug becomes invisible instead of fixed — the `silent-failure-hunter` agent exists for exactly that mistake.

## Anti-Patterns

- **Fixing where the error appears.** The single most common failure of this whole process.
- **Adding a null check at the crash site and calling it done.** That converts a crash into wrong behavior.
- **Tracing frames without tracing the value.** The path is not the cause.
- **`console.log` in QPay backend service code.** Use `qpay-micro-logging`.
- **Leaving instrumentation in the diff.**
- **Stopping at the first plausible cause.** Ask once more: was the input to *this* already wrong?

## Related

- `debug` — QPay service symptom triage; use it first to localize, then this to trace
- `bug-hunter` agent — sweeps an area cold for unknown bugs; this skill traces one known bug
- `silent-failure-hunter` agent — after you add the defense layers, confirm none of them swallow

---

*Adapted from `root-cause-tracing` in obra/superpowers (MIT), with QPay stack entry points added.*
