#!/usr/bin/env bash
# agent-stack installer — symlinks portable AI-agent config into place.
# Idempotent: safe to re-run. Existing real files are backed up first.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP="$HOME/.agent-stack-backup/$(date +%Y%m%d-%H%M%S)"

link() {
  local src="$REPO/$1" dst="$2"
  if [ ! -e "$src" ]; then echo "skip (missing in repo): $1"; return; fi
  mkdir -p "$(dirname "$dst")"
  if [ -L "$dst" ]; then
    if [ "$(readlink "$dst")" = "$src" ]; then echo "ok: $dst"; return; fi
    rm "$dst"                                   # stale symlink → replace
  elif [ -e "$dst" ]; then
    local rel="${dst#"$HOME"/}"
    mkdir -p "$BACKUP/$(dirname "$rel")"
    mv "$dst" "$BACKUP/$rel"
    echo "backed up: $dst → $BACKUP/$rel"
  fi
  ln -s "$src" "$dst"
  echo "linked: $dst → $src"
}

echo "== Claude =="
link claude/CLAUDE.md                  "$HOME/.claude/CLAUDE.md"
link claude/prompt-defense.md          "$HOME/.claude/prompt-defense.md"
link claude/settings.json              "$HOME/.claude/settings.json"
link claude/agent-memory/STATE.md      "$HOME/.claude/agent-memory/STATE.md"
for d in agents skills commands hooks qpay-context; do
  link "claude/$d"                     "$HOME/.claude/$d"
done

echo "== Codex =="
link codex/AGENTS.md                   "$HOME/.codex/AGENTS.md"
link codex/MIGRATION.md                "$HOME/.codex/MIGRATION.md"
for d in agents skills commands; do
  link "codex/$d"                      "$HOME/.codex/$d"
done
# rules: link the portable parts only; leave machine-local default.rules untouched
link codex/rules/common                "$HOME/.codex/rules/common"
link codex/rules/qpay                  "$HOME/.codex/rules/qpay"
link codex/rules/lessons.md            "$HOME/.codex/rules/lessons.md"

echo "== OpenCode =="
link opencode/skills                   "$HOME/.config/opencode/skills"
link opencode/opencode.json            "$HOME/.config/opencode/opencode.json"

echo "== home =="
link home/AGENTS.md                    "$HOME/AGENTS.md"

echo
echo "Done. Backups (if any) under: $BACKUP"
echo "NOTE: machine-local secrets are NOT managed here — recreate them per machine:"
echo "  • ~/.codex/auth.json         (run Codex login)"
echo "  • ~/.claude/settings.local.json  (re-add any local model tokens)"
echo "  • ~/.codex/config.toml + default.rules  (Codex regenerates on first run)"
