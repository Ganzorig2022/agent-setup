#!/usr/bin/env bash
# agent-setup installer — symlinks portable AI-agent config into place.
# Idempotent: safe to re-run. Existing real files are backed up first.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP="$HOME/.agent-setup-backup/$(date +%Y%m%d-%H%M%S)"

backup_existing() {
  local dst="$1" rel
  rel="${dst#"$HOME"/}"
  mkdir -p "$BACKUP/$(dirname "$rel")"
  mv "$dst" "$BACKUP/$rel"
  echo "backed up: $dst → $BACKUP/$rel"
}

# link <repo-relative-path> <absolute-destination>  (whole file or dir)
link() {
  local src="$REPO/$1" dst="$2"
  if [ ! -e "$src" ] && [ ! -L "$src" ]; then echo "skip (missing in repo): $1"; return; fi
  mkdir -p "$(dirname "$dst")"
  if [ -L "$dst" ]; then
    [ "$(readlink "$dst")" = "$src" ] && { echo "ok: $dst"; return; }
    rm "$dst"                                     # stale symlink → replace
  elif [ -e "$dst" ]; then
    backup_existing "$dst"
  fi
  ln -s "$src" "$dst"
  echo "linked: $dst → $src"
}

# link_skills <repo-skills-subdir> <live-skills-dir>
# Tool skill dirs mix real skills with symlinks into ~/.agents/skills. Keep the live
# dir REAL and reproduce each entry so the relative ../../.agents/skills/* links resolve.
link_skills() {
  local sub="$1" live="$2" src="$REPO/$1"
  [ -d "$src" ] || { echo "skip (missing): $1"; return; }
  mkdir -p "$live"
  local entry name dst tgt
  for entry in "$src"/* "$src"/.[!.]*; do
    [ -e "$entry" ] || [ -L "$entry" ] || continue
    name="$(basename "$entry")"; dst="$live/$name"
    if [ -L "$entry" ]; then                       # shared skill → identical relative link
      tgt="$(readlink "$entry")"
      if [ -L "$dst" ] && [ "$(readlink "$dst")" = "$tgt" ]; then echo "ok: $dst"; continue; fi
      [ -L "$dst" ] && rm "$dst"
      [ -e "$dst" ] && backup_existing "$dst"
      ln -s "$tgt" "$dst"; echo "linked(shared): $dst → $tgt"
    else                                           # tool-specific real skill → link to repo
      link "$sub/$name" "$dst"
    fi
  done
}

echo "== Shared skill library (~/.agents) =="
link agents/skills            "$HOME/.agents/skills"
link agents/.skill-lock.json  "$HOME/.agents/.skill-lock.json"

echo "== Claude =="
link claude/CLAUDE.md             "$HOME/.claude/CLAUDE.md"
link claude/prompt-defense.md     "$HOME/.claude/prompt-defense.md"
link claude/settings.json         "$HOME/.claude/settings.json"
link claude/agent-memory/STATE.md "$HOME/.claude/agent-memory/STATE.md"
for d in agents commands hooks qpay-context; do
  link "claude/$d"                "$HOME/.claude/$d"
done
link_skills claude/skills         "$HOME/.claude/skills"

echo "== Codex =="
link codex/AGENTS.md              "$HOME/.codex/AGENTS.md"
link codex/MIGRATION.md           "$HOME/.codex/MIGRATION.md"
for d in agents commands; do
  link "codex/$d"                 "$HOME/.codex/$d"
done
link_skills codex/skills          "$HOME/.codex/skills"
link codex/rules/common           "$HOME/.codex/rules/common"
link codex/rules/qpay             "$HOME/.codex/rules/qpay"
link codex/rules/lessons.md       "$HOME/.codex/rules/lessons.md"

echo "== OpenCode =="
link opencode/skills              "$HOME/.config/opencode/skills"
link opencode/opencode.json       "$HOME/.config/opencode/opencode.json"

echo "== home =="
link home/AGENTS.md               "$HOME/AGENTS.md"

echo
echo "Done. Backups (if any) under: $BACKUP"
echo "NOTE: machine-local secrets are NOT managed here — recreate per machine:"
echo "  • ~/.codex/auth.json                     (run Codex login)"
echo "  • ~/.claude/settings.local.json          (re-add any local model tokens)"
echo "  • ~/.codex/config.toml + default.rules   (Codex regenerates on first run)"
