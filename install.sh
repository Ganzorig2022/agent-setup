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

# seed <repo-relative-path> <absolute-destination>  (copy ONLY if dest is absent)
# For files the tool rewrites itself (e.g. Codex config.toml) — never symlink/overwrite.
seed() {
  local src="$REPO/$1" dst="$2"
  if [ -e "$dst" ]; then echo "kept existing: $dst"; return; fi
  mkdir -p "$(dirname "$dst")"
  cp "$src" "$dst"
  echo "seeded: $dst (from $1)"
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
for d in agents commands hooks qpay-context content; do
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
seed codex/config.template.toml   "$HOME/.codex/config.toml"   # copy-if-absent (Codex owns this file)

echo "== OpenCode =="
# Keep the live dir REAL and reproduce each entry (like Claude/Codex): the shared
# skills are relative symlinks (../../../.agents/skills/* — one level deeper than
# ~/.claude, ~/.codex). A whole-dir symlink would resolve those against the repo and dangle.
link_skills opencode/skills       "$HOME/.config/opencode/skills"
link opencode/opencode.json       "$HOME/.config/opencode/opencode.json"

echo "== home =="
link home/AGENTS.md               "$HOME/AGENTS.md"

echo "== Automation (daily-decisions memory harvester) =="
link home/.local/bin/daily-decisions.sh         "$HOME/.local/bin/daily-decisions.sh"
link home/.local/bin/daily-decisions-harvest.py "$HOME/.local/bin/daily-decisions-harvest.py"
link home/.local/bin/qmd                         "$HOME/.local/bin/qmd"   # stable qmd shim
link home/Library/LaunchAgents/com.dev.daily-decisions.plist \
                                                 "$HOME/Library/LaunchAgents/com.dev.daily-decisions.plist"

echo "== Automation (x-draft-factory — nightly X content drafts) =="
link home/.local/bin/x-draft-factory.py          "$HOME/.local/bin/x-draft-factory.py"
link home/.local/bin/qpay-gem-harvest.py         "$HOME/.local/bin/qpay-gem-harvest.py"
link home/Library/LaunchAgents/com.dev.x-draft-factory.plist \
                                                 "$HOME/Library/LaunchAgents/com.dev.x-draft-factory.plist"

echo "== Automation (tech-brief — 8am AI/dev news + X-feed digest) =="
link home/.local/bin/tech-brief.py               "$HOME/.local/bin/tech-brief.py"
link home/.local/bin/x-harvest.py                "$HOME/.local/bin/x-harvest.py"
link home/Library/LaunchAgents/com.dev.tech-brief.plist \
                                                 "$HOME/Library/LaunchAgents/com.dev.tech-brief.plist"
# One-time after install: log the X-only Chrome profile into X so the headless
# 8am harvest has a session:  x-harvest.py --login

echo
echo "Done. Backups (if any) under: $BACKUP"
echo "NOTE: after install, load the schedules once:"
echo "  launchctl bootstrap gui/\$(id -u) ~/Library/LaunchAgents/com.dev.daily-decisions.plist"
echo "  launchctl bootstrap gui/\$(id -u) ~/Library/LaunchAgents/com.dev.x-draft-factory.plist"
echo "  launchctl bootstrap gui/\$(id -u) ~/Library/LaunchAgents/com.dev.tech-brief.plist"
echo "See CONTENT.md for the content stack + morning workflow."
echo "NOTE: machine-local secrets are NOT managed here — recreate per machine:"
echo "  • ~/.codex/auth.json                     (run Codex login)"
echo "  • ~/.claude/settings.local.json          (re-add any local model tokens)"
echo "  • ~/.codex/config.toml + default.rules   (Codex regenerates on first run)"
