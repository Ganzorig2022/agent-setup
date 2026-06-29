---
name: office-hours
description: Interrogate a feature/change request BEFORE any plan or code — forcing questions that pressure-test the problem, scope, reuse, blast radius, and done-criteria. Use at the very start of non-trivial work, when a request is vague, or when the user says "office-hours", "challenge this", "am I solving the right thing". Produces a sharpened brief that feeds /plan or a handoff to executors — never code.
---

# Office Hours — Interrogate Before You Build

Catch the wrong problem, the wrong scope, and the rebuild-instead-of-reuse mistake *before*
a single line is planned or written. This skill asks forcing questions, pushes until the
answers are concrete, and outputs a **sharpened brief** — it never plans implementation
details and never writes code.

This sits at the front of the workflow: **office-hours → /plan (or planner agent) →
handoff to executor (Codex / OpenCode) → reviewer.**

## Hard rules

- **Never write or scaffold code.** Output is questions and a brief, nothing else.
- **One question at a time** via the AskUserQuestion tool. Wait for the answer before the next.
- **Push until concrete.** "Users want it", "it'd be cleaner", "we'll need it eventually" are
  not answers — reframe and re-ask.
- **Skip what's already answered.** If the request already nails a question, say so and move on.
  Don't interrogate a genuinely trivial change — say it's trivial and route straight to /plan.
- **Stop at gates.** Do not write the brief until the user has picked an approach.
- **Payments posture.** This is a fintech codebase — always probe money/data safety explicitly.

## Phase 1 — Load context (no questions yet)

Read the request and the relevant ground truth before challenging anything:
- Identify the target repo/stack from `package.json` (Stack A/B/C, frontend Gen) — don't assume.
- Skim the code the change would touch; check STATE.md and CLAUDE.md for standing facts.
- Note what the request leaves unstated.

## Phase 2 — The forcing questions

Ask sequentially (AskUserQuestion), pushing until each is concrete. Adapt wording; skip any
the request already answers.

1. **Real problem.** What's the actual problem, and who/what hits it? What's the evidence it's
   worth doing now — an incident, ticket, metric, user complaint — not "would be nice"?
2. **Do-nothing cost.** What happens today, and what breaks if we ship nothing? What's the
   current workaround and what does it cost? (If "nothing breaks", question whether to build it.)
3. **Narrowest slice.** What's the smallest vertical slice that delivers real value this
   iteration vs. the full build? What can be cut or deferred?
4. **Reuse first.** Does an internal QPay package, an existing service, or an established
   pattern already cover this? (Reuse over rebuild for auth/payments/uploads/webhooks.) What
   would a new external dependency buy that internal packages don't?
5. **Blast radius.** Which services, tables, and money/data flows does this touch? For
   payment/settlement/ledger paths: idempotency, transaction consistency, rollback, and which
   cross-service inputs must be validated at the receiving boundary?
6. **Done & verify.** What does "done" concretely look like, and how is it verified (which
   tests / flows)? Given executors are usually Codex/OpenCode, what must the handoff spell out
   so it can be implemented without re-asking?

## Phase 3 — Challenge the premise

Before proposing anything, push back once on the framing: Is this the right problem at the
right layer? Is there a cheaper way to get the same outcome? Surface the strongest argument
*against* doing it. If the request collapses here, say so plainly.

## Phase 4 — Approaches (decision gate)

Offer 2 distinct approaches — **minimal** (narrowest slice) and **fuller** (more complete,
more cost) — with the trade-off for each. Use AskUserQuestion for the choice. Do not proceed
until the user picks.

## Phase 5 — Sharpened brief (output)

Only after a choice, write a tight brief (not a design doc, no code):
- **Problem** — one or two sentences, concrete.
- **Scope** — the chosen slice; explicitly what's out of scope.
- **Constraints & reuse** — internal packages/patterns to use; deps ruled in/out.
- **Risks** — blast radius + the payment/data-safety items to honor.
- **Done-criteria & verification** — observable outcomes and how they're checked.

Then route: hand the brief to `/plan` (or the planner agent) for sequencing, or to the
handoff-impl skill if it's ready for a Codex/OpenCode executor. State which and why.
