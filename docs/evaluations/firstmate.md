# firstmate — evaluation

- **Repo:** github.com/kunchenguid/firstmate
- **Evaluated:** 2026-08-05 at commit `ef2c3a2`
- **Verdict:** **SKIP**
- **Do not re-evaluate before:** ~2027-02

## What it is

A multi-agent "agent distro" — `AGENTS.md` + `bin/` + skills. There is no app to install.

## Disqualifiers

All three were read from the code, not the docs.

1. **It disables this setup's agent-trigger table.** It ships a PreToolUse guard (`bin/fm-subagent-pretool-check.sh`) that **denies the `Agent`/`Task` tool** inside its home — plus any tool matching `delegate|spawn|dispatch|handoff|remote|sendmessage|monitor`. That kills the entire reviewer/planner trigger table.

2. **Every crewmate launches with permission gates off.** At `bin/fm-spawn.sh:823-851`: `claude --dangerously-skip-permissions`, `codex --dangerously-bypass-approvals-and-sandbox`, `grok --always-approve`. This is **not gated on its `+yolo` flag** and is **documented nowhere** in README/AGENTS.md/docs. Its `cd`-guard is explicitly inert in crewmate worktrees, so worktree isolation is a prompt convention, not a sandbox.

3. **Hard-requires 6 same-author tools** — `no-mistakes`, `treehouse`, `lavish-axi`, `tasks-axi`, `quota-axi`, `chrome-devtools-axi` (2 installed via `curl | sh`) — on a stated policy of pinning floors to "the CURRENT LATEST published version".

## Other friction

- Clones projects into its own `projects/` directory: duplicate checkouts, plus an unconditional fetch at session start, which breaks off-VPN for QPay old-core.
- Auto-detects cmux as an **experimental** backend.
- `defaultMode: "plan"` blocks its own bootstrap.

## Genuinely good parts (none adoptable standalone)

- **Zero-token Stop-hook watcher** — Claude only. On tmux it degrades to a blind `sleep 15`; the "event-driven" path is herdr-only, and Codex costs ~20 model turns/hr.
- **Fail-closed teardown** with real landed-work proofs.
- **Whole-home remote secondmates over SSH** (encoded-argv-only transport, no agent forwarding) — but that path is fixture-tested only, per its own `docs/remote-secondmates.md:220`.

## Explicitly not worth porting

Its `cd`-guard. It fixes firstmate's own invariant — a home directory distinct from the work directory, with home-relative writes — which this per-repo absolute-path setup does not have.
