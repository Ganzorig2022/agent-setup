---
name: agent-prompt-tuning
description: Revise the prompt body or frontmatter of an agent or skill, then prove the revision with the reviewer evals instead of guessing. Use when an agent misfires, never fires, is too noisy, misses a bug class, or when porting a new agent — and whenever editing files under ~/.claude/agents/ or ~/.agents/skills/.
---

# Agent Prompt Tuning

Editing an agent prompt is a code change to a component with no type checker. The only thing standing between "I improved it" and "I regressed it" is the eval harness. Use it.

## When to Use

- An agent fires when it shouldn't, or never fires when it should
- A reviewer misses a bug class, or floods the report with noise
- Porting a new agent from `ecc` and adapting it to this setup
- Changing `model:`, tools, or the description of an existing agent

## Do Not Use When

- Writing a **new skill** from scratch → `write-a-skill`
- Auditing always-loaded context size → `context-budget`

## The Layout You Are Editing

| File | Role |
|------|------|
| `~/.claude/agents/<name>.md` | **Source of truth** for every agent |
| `~/.codex/agents/<name>.toml` | Generated port — never hand-edit |
| `~/.agents/skills/<name>/SKILL.md` | Shared skill body, symlinked into Claude + Codex + opencode |
| `~/.claude/skills/<name>/SKILL.md` | Claude-only skill (not shared) |
| `/Users/dev/GIthub/agent-setup` | Canonical repo — live files sync here after any change |

## Rules That Are Easy to Get Wrong

- **Do not add a per-agent Prompt Defense block.** It is `@import`ed once from `~/.claude/CLAUDE.md` (`~/.claude/prompt-defense.md`) and reaches every custom subagent. A per-agent copy is pure duplicated tokens.
- **`model:` frontmatter is honored** — `sonnet | opus | haiku | fable | inherit | <full-id>`, defaulting to `inherit`. Reviewer-type agents get **sonnet + read-only tools** (`Read`, `Grep`, `Glob`, `Bash`) — they report, executors fix.
- **The `description` is the trigger surface.** The most common agent failure is not a bad body, it is a description that never matches. Write it with explicit trigger and non-trigger phrasing, in the vocabulary the user actually types.
- **Custom subagents load `~/.claude/CLAUDE.md` and its `@import`s.** Built-in Explore/Plan agents do not. Do not restate global rules in an agent body.
- **Headless runs need `--permission-mode default`.** With the global mode set to plan, an agent writes findings to a plan file and stdout looks empty.

## The Loop

### 1. Baseline before you touch anything

```bash
~/.local/bin/agent-evals.py --agent <name>
```

Record the score. A tuning session with no before-number is a guess. Tasks and calibration rules live in `agent-setup/evals/reviewers/README.md`.

### 2. Change one class of thing at a time

Trigger wording, or body structure, or tool/model — never all three in one pass. When the score moves you need to know which edit moved it.

Ordered by how often it is the actual fix:

1. **Description / trigger** — agent never fires, or fires on the wrong tasks
2. **Output contract** — what to report, severity scale, evidence required. Fixes noise and un-actionable findings
3. **Body checklist** — the specific bug classes to look for. Fixes misses
4. **Tools / model** — last resort; usually a symptom of the body asking for something the tools cannot do

### 3. Re-run and compare

```bash
~/.local/bin/agent-evals.py --agent <name>          # 1 rep per pair
~/.local/bin/agent-evals.py --agent <name> --full   # 3 reps — use before committing a real change
```

Score dropped → revert. Do not "fix the fix" on top of a regression.

**Audit the raw output, do not just read the score.** The standing grader lesson: *mention ≠ flag*. An agent that name-drops the vulnerable function in passing is not the same as one that reports it as a finding, and a lenient grader scores both as a hit.

### 4. Save the new baseline only when it is genuinely better

```bash
~/.local/bin/agent-evals.py --agent <name> --save-baseline
```

### 5. Confirm the alarm still works

```bash
~/.local/bin/agent-evals.py --drill <name>
```

Runs a deliberately gutted inline agent and expects failure. If a drill passes, the harness is not actually testing anything and every green run above was meaningless.

### 6. Mirror to Codex

```bash
/opt/homebrew/bin/python3.12 /Users/dev/GIthub/agent-setup/scripts/resync-codex-agents.py
```

System `python3` is 3.9 and lacks `tomllib`. The roster is **hardcoded** in the script's `AGENTS` list plus `NEW_AGENT_DEFAULTS` — a new agent not added there is silently skipped, with no error. Adding a new agent means editing that list in the same change.

The generated `.toml` is: prompt-defense baseline + the Claude body verbatim + a `## Codex Compatibility` footer, preserving each toml's effort/sandbox/nicknames.

### 7. Sync live → repo

```bash
cd /Users/dev/GIthub/agent-setup && git status --short
```

Copy the changed live files into the repo and commit. Live files are the ones that run; the repo is the backup that survives a machine.

## Writing the Body

- **Say what to do, not what a good agent is.** "Report file:line for every finding" beats "be thorough and precise."
- **Give the output contract explicitly** — sections, severity levels, and what evidence a finding must carry. Most reviewer noise is an unspecified contract, not a weak model.
- **Include the refuse list.** What the agent should *not* report is as load-bearing as what it should.
- **Anti-patterns beat examples** for reviewers. A worked example teaches the shape of the answer and invites pattern-matching on that one case; a named anti-pattern generalizes.
- **Keep agent bodies lazy-loaded.** Detail belongs in the agent or skill, never pushed up into `CLAUDE.md` or `~/.claude/rules/` — those load into every session.

## Anti-Patterns

- **Rewriting the whole prompt in one pass.** You lose attribution for the score change and usually regress the trigger.
- **Tuning until the eval passes.** Six seeded-bug tasks is a smoke test, not a benchmark. If a change only helps the eval set, it is overfitting — check it against a real diff.
- **Editing `~/.codex/agents/*.toml` by hand.** The next resync silently overwrites it.
- **Adding a new agent without touching `resync-codex-agents.py`.** It will never reach Codex, and nothing will tell you.
- **Skipping the baseline because "this edit is obviously an improvement."**

## Related

- `write-a-skill` — new skills from scratch
- `context-budget` — when the cost of always-loaded context is the problem
- `retro` — capture the durable lesson from a tuning session into STATE.md
- `agent-setup/evals/reviewers/README.md` — task schema and calibration rules
