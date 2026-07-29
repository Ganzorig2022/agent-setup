# Reviewer-Agent Evals

Golden seeded-bug tasks that measure whether the reviewer agents still catch
what they're supposed to catch — run after changing an agent prompt, model
assignment, or reviewer-related hook. Grading is mechanical (keyword windows,
zero LLM-judge tokens); the only token cost is the reviews themselves.

**Manual-only by design.** No cron. Built to stay affordable if the generous
plan goes away: `--core` after a prompt change is 1–3 sonnet calls.

## Run

```sh
agent-evals.py                              # core: 1 rep per pair, vs baseline
agent-evals.py --agent security-reviewer    # after editing that agent (cheap)
agent-evals.py --task express-route-sqli    # one task (smoke)
agent-evals.py --full --save-baseline       # 3 reps per pair, rewrite baseline
```

Runner: `~/.local/bin/agent-evals.py` (copy in `scripts/`). Reports →
`~/agent-evals/<date>.md`, raw agent outputs → `~/agent-evals/raw/<date>/`,
history → `~/agent-evals/scores.jsonl`. Telegram ping on regression only.
Exit 1 = regression (a bug hit ≥67% in baseline is now missed, or trap flags
exceed `max_false_positives`).

## Drill mode

Purpose: self-test the regression alarm without touching live agent files. The
drill shadows one reviewer with an inline style-commenter that only discusses
naming and organization, so baseline bugs should be missed.

```sh
agent-evals.py --drill security-reviewer
```

Expected outcome: exit 1 plus a Telegram regression alert. Drill runs force the
selected agent and 1 rep, and keep the usual `-drill` report/raw tags plus
`mode="drill"` scores. If `AGENT_EVALS_AGENTS_JSON` is already set, that
explicit inline agent JSON wins.

## Task anatomy

```
<task-id>/
  task/        # 1–3 small QPay-flavored source files with planted bugs
  truth.json   # ground truth (see below)
```

- `agents`: which reviewers this task runs against.
- `bugs[]`: `id`, `file`, `lines`, `severity`, `keywords` — a bug is HIT when
  one sliding window (3 consecutive paragraphs of the review) mentions the
  file AND ≥1 keyword from EVERY group. Optional per-bug `agents` narrows who
  is expected to find it.
- `traps[]`: patterns that LOOK like findings but are correct per the agents'
  own skip-lists (security theater, bounded loops, documented best-effort
  fallbacks, Express-5 async semantics). A trap counts as a false positive
  only when a window matches its keywords AND carries a severity marker AND
  has no dismissal language ("not a finding", "intentional", ...).
- `max_false_positives`: trap-flag budget per review.

## Current tasks (6 tasks / 14 pairs)

| Task | Planted bugs | Agents |
|---|---|---|
| express-route-sqli | SQLi via interpolation; missing Joi validation | security, typescript, code |
| swallowed-webhook-error | 200-ack despite failed processing; empty catch | silent-failure-hunter, code |
| sequelize-txn-leak | txn never rolled back on early return; missing FK index | database, code |
| bull-processor-race | fire-and-forget charge persist; no idempotency on retry | typescript, silent-failure-hunter, code |
| react-hook-deps | stale closure in poll effect; interval never cleared | react, code |
| async-error-propagation | mutates caller's order; floating promise without catch | typescript, code |

## Calibration rules

- If an agent misses a bug in 3/3 baseline reps → fix the TASK (bug too
  subtle, keywords too narrow) before blaming the agent.
- Baseline records the model per agent + CLI version — scores move when the
  underlying model updates, without any prompt change. Re-baseline after
  model-version changes, not after every drift.

## Real-world theme harvesting (not a quality metric)

`review-intel-harvest.py` is the local, stdlib-only Stage 0A collector for
reviewer traces. It stores redacted run and finding metadata under
`~/.review-intelligence/`; it never stores raw transcripts, calls a model,
uses the network, changes a reviewer prompt, or writes `baseline.json`,
`truth.json`, or `scores.jsonl`. Its output must never be reused as few-shot
reviewer examples.
Free-form task descriptions are not persisted; the first real-data inspection
showed that even redacted titles retained too much identifying context.

Records are append-only and stamped with both `schema_version` and
`parser_version`. A parser revision creates a new record for the same stable
run ID. The collection ledger records every included or skipped source and
explicitly marks theme exclusions. Codex guardian output remains prose-only:
guardian is collapsed to one record per parent session, contributes run counts
only, and is excluded from future themes.

Parse rate only measures whether a run can be classified as findings or a
clean review. It is not sufficient evidence that extracted findings are
useful. The separate usable-finding rate requires a controlled category, an
abstract of at least five tokens, and a non-heading/non-summary source.

Stage gates are deliberately separate:

- **Stage 0A acceptance:** a clean full-line privacy inspection, an accounted
  collection ledger, exact reconciliation between normalized traces and
  stable source identities, and at least 90% usable-finding rate for every
  editable source class. Guardian may pass as session-count-only.
- **Start Stage 1 only on post-trailer evidence:** at least 20 editable
  `qri-v1` runs, with at least 90% parse rate and 90% usable-finding rate for
  every editable source class. The pre-trailer backlog is advisory input and
  counts neither for nor against this gate: its Claude half expires after 30
  days, and episode-local legacy formats have no long-run value.
- Codex `subagent-usage.log` is advisory telemetry, not a run ledger: the
  notifier writes another cumulative token snapshot whenever a live rollout
  changes. Event counts therefore exceed unique reviewer sources and are
  printed for diagnosis but do not replace source-identity reconciliation.
- **Keep Stage 1 only after three manual reports if:** at least three themes
  each recur across at least two repository hashes and two session hashes,
  and at least one is not represented by an existing `truth.json` bug ID.
  Otherwise shelve and remove the analysis layer.

The two-repository/two-session recurrence floor remains the minimum
anti-concentration guard. With roughly 49 editable runs it is demanding but
reachable; do not weaken it merely to manufacture three surviving themes.
The Stage 0A corpus had only 22 finding-bearing runs and 79 findings; 24 runs
were clean approvals. Claude covered six repository hashes and Codex three,
with only one overlap, so Stage 1 must not require or imply cross-provider
corroboration.

Before any future `qri-v1` trailer is added to editable reviewer prompts,
Stage 0B must first run and commit a fresh control:

```sh
agent-evals.py --full --save-baseline
```

Only then add the trailer, run the identical full eval again, and commit both
auditable results. This separates format effects from CLI/model drift.
Cross-provider disagreement, scheduling, analysis, clustering, embeddings,
Telegram delivery, and prompt/baseline mutation are outside Stage 0A.

## Growing the set

Best source of new tasks: real production bugs. After fixing one, distill it
into `<task-id>/task/` + `truth.json` (5 minutes while it's fresh — the
"/retro for bugs" habit). Synthetic tasks measure the checklist; mined tasks
measure reality.
