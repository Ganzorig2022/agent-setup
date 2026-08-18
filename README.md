# agent-setup

Portable configuration for my AI coding agents — **Claude Code**, **Codex**, and **OpenCode** —
synced across machines via one private repo + symlinks.

> Private repo on purpose: it contains QPay-internal architecture context. Do not make public.

## What's here

```
agents/    skills/ (.agents shared skill library — real content) + .skill-lock.json
claude/    CLAUDE.md, prompt-defense.md, settings.template.json (portable prefs),
           agent-memory/STATE.md, agents/ skills/ commands/ hooks/ qpay-context/
codex/     AGENTS.md, MIGRATION.md, agents/ skills/ commands/, rules/{common,qpay,lessons.md},
           hooks/, config.template.toml (portable prefs — safely merged into live config)
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
git clone git@github.com:Ganzorig2022/agent-setup.git ~/agent-setup
~/agent-setup/install.sh
```

`install.sh` symlinks static repo files into `~/.claude`, `~/.codex`, `~/.config/opencode`, and `~`.
Any pre-existing real file is moved to the owner-only `~/.agent-setup-backup/<timestamp>/`
first. Re-running
is a no-op for already-linked paths. Hook paths in `settings.json` use `$HOME`, so they work
under any username.

Mutable `~/.claude/settings.json` and `~/.codex/config.toml` are deliberately regular files.
The installer runs an allowlisted merge from the two portable templates, validates the result,
makes an owner-only backup when a live file changes, and preserves machine-local sections.

Managed hook scripts are linked entry-by-entry instead of linking the whole hooks directory.
This keeps runtime-only hook logs and caches local and out of the repository.

Then install Claude Code plugins (machine-local state, not synced by this repo):

```sh
claude plugin marketplace add openai/codex-plugin-cc
claude plugin install codex@openai-codex   # /codex:rescue|review|transfer — drives the local codex CLI
```

## Day-to-day sync

Static managed files are symlinks back into this repo, so intentional edits land in the repo.
Mutable live settings do not: update their portable templates and apply them explicitly.

```sh
python3 scripts/apply-portable-config.py --dry-run
python3 scripts/apply-portable-config.py --apply

cd ~/agent-setup && git add -A && git commit -m "update: …" && git push
# on the other Mac:
cd ~/agent-setup && git pull
```

## NOT in this repo (recreate per machine — never commit)

These are secrets or machine-local state, deliberately excluded (see `.gitignore`):

| File | Why excluded | How to restore |
|------|--------------|----------------|
| `~/.codex/auth.json` | OAuth credentials | run Codex login |
| `~/.claude/settings.json` | mutable live settings; receives only allowlisted portable keys | run the portable merge |
| `~/.claude/settings.local.json` | local permissions or model tokens | re-add locally; keep mode `0600` |
| `~/.codex/config.toml` | portable prefs plus machine-specific trust/MCP/plugin paths | run the portable merge, then configure integrations locally |
| `~/.codex/rules/default.rules` | accumulated approval decisions; may embed complete commands | rebuild deliberately; keep mode `0600` |
| `~/.codex/skills/.system` | Codex-managed built-in skills, refreshed by the CLI | Codex recreates it on startup |
| `*.sqlite`, `history.jsonl`, sessions, caches | runtime state, large | regenerated automatically |

Concrete project trust, MCP servers, plugin/cache paths, notification commands, authentication,
approval history, runtime databases, logs, sessions, and NUX state are never imported into a
portable template. Desired integrations should be documented with placeholders, then configured
per machine.

## Secret hygiene

Before any commit, confirm nothing sensitive is staged:

```sh
git grep -nE '(omlx-|Bearer eyJ|ghp_|sk-[A-Za-z0-9]{20}|-----BEGIN)' -- . && echo "LEAK!" || echo clean
```

Run the deterministic repository and live-config audit as the stronger gate:

```sh
python3 scripts/config-hygiene-audit.py
```

If a token ever reaches an approval rule or session transcript, remove the local plaintext copy
without preserving it in a normal backup and rotate/revoke the credential. Redaction alone does
not invalidate a credential that may already have been exposed.
