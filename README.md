# agent-setup

Portable configuration for my AI coding agents — **Claude Code**, **Codex**, and **OpenCode** —
synced across machines via one private repo + symlinks.

> Private repo on purpose: it contains QPay-internal architecture context. Do not make public.

## What's here

```
agents/    skills/ (.agents shared skill library — real content) + .skill-lock.json
claude/    CLAUDE.md, prompt-defense.md, settings.json ($HOME-relative),
           agent-memory/STATE.md, agents/ skills/ commands/ hooks/ qpay-context/
codex/     AGENTS.md, MIGRATION.md, agents/ skills/ commands/, rules/{common,qpay,lessons.md},
           config.template.toml  (portable prefs — seeded to ~/.codex/config.toml if absent)
opencode/  skills/, opencode.json
home/      AGENTS.md  (→ ~/AGENTS.md)
install.sh symlinks all of the above into place (idempotent, backs up existing files)
```

Some skills in `claude/skills` and `codex/skills` are symlinks into the shared
`~/.agents/skills` library (vendored here under `agents/`). `install.sh` links
`~/.agents/skills → agents/skills` and reproduces those relative symlinks so they
resolve on any machine.

## Install on a new machine

```sh
git clone git@github.com:Ganzorig2022/agent-setup.git ~/agent-stack
~/agent-stack/install.sh
```

`install.sh` symlinks repo files into `~/.claude`, `~/.codex`, `~/.config/opencode`, and `~`.
Any pre-existing real file is moved to `~/.agent-stack-backup/<timestamp>/` first. Re-running
is a no-op for already-linked paths. Hook paths in `settings.json` use `$HOME`, so they work
under any username.

## Day-to-day sync

Because files are symlinks back into this repo, edits made by any tool land in the repo:

```sh
cd ~/agent-stack && git add -A && git commit -m "update: …" && git push
# on the other Mac:
cd ~/agent-stack && git pull
```

## NOT in this repo (recreate per machine — never commit)

These are secrets or machine-local state, deliberately excluded (see `.gitignore`):

| File | Why excluded | How to restore |
|------|--------------|----------------|
| `~/.codex/auth.json` | OAuth credentials | run Codex login |
| `~/.claude/settings.local.json` | contains local model API token | re-add local tokens by hand |
| `~/.codex/config.toml` | machine-specific project-trust paths | Codex regenerates / edit locally |
| `~/.codex/rules/default.rules` | per-machine approval allowlist (had a live JWT) | Codex regenerates on first run |
| `*.sqlite`, `history.jsonl`, sessions, caches | runtime state, large | regenerated automatically |

## Secret hygiene

Before any commit, confirm nothing sensitive is staged:

```sh
git grep -nE '(omlx-|Bearer eyJ|ghp_|sk-[A-Za-z0-9]{20}|-----BEGIN)' -- . && echo "LEAK!" || echo clean
```
