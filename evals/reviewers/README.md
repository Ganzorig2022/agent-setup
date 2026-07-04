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

## Growing the set

Best source of new tasks: real production bugs. After fixing one, distill it
into `<task-id>/task/` + `truth.json` (5 minutes while it's fresh — the
"/retro for bugs" habit). Synthetic tasks measure the checklist; mined tasks
measure reality.
