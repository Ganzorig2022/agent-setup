#!/usr/bin/env bash
# agent-setup installer — symlinks portable AI-agent config into place.
# Idempotent: safe to re-run. Existing real files are backed up first.
set -euo pipefail
umask 077

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_ROOT="$HOME/.agent-setup-backup"
BACKUP="$BACKUP_ROOT/$(date +%Y%m%d-%H%M%S)"

backup_existing() {
  local dst="$1" rel
  rel="${dst#"$HOME"/}"
  mkdir -p -m 700 "$BACKUP/$(dirname "$rel")"
  chmod 700 "$BACKUP_ROOT" "$BACKUP"
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

# link_entries <repo-subdir> <live-dir>
# Keep the live directory real and reproduce each managed entry. This preserves
# live-only runtime files (for example hook logs/caches) and also keeps relative
# symlink targets valid for shared skills.
link_entries() {
  local sub="$1" live="$2" skip_name="${3:-}" src="$REPO/$1"
  [ -d "$src" ] || { echo "skip (missing): $1"; return; }
  # Older installer versions linked some whole directories (notably hooks).
  # Detach that symlink before addressing entries beneath it, or src and dst
  # can resolve to the same file and produce a destructive self-link.
  if [ -L "$live" ]; then
    backup_existing "$live"
  fi
  mkdir -p "$live"
  local entry name dst tgt skip_dst old_managed
  if [ -n "$skip_name" ]; then
    skip_dst="$live/$skip_name"
    old_managed="$src/$skip_name"
    if [ -L "$skip_dst" ] && [ "$(readlink "$skip_dst")" = "$old_managed" ]; then
      rm "$skip_dst"
      echo "detached legacy managed symlink: $skip_dst"
    fi
  fi
  for entry in "$src"/* "$src"/.[!.]*; do
    [ -e "$entry" ] || [ -L "$entry" ] || continue
    name="$(basename "$entry")"; dst="$live/$name"
    if [ -n "$skip_name" ] && [ "$name" = "$skip_name" ]; then
      echo "kept machine-managed: $dst"
      continue
    fi
    if [ -L "$entry" ]; then                       # repo symlink → identical relative link
      tgt="$(readlink "$entry")"
      if [ -L "$dst" ] && [ "$(readlink "$dst")" = "$tgt" ]; then echo "ok: $dst"; continue; fi
      [ -L "$dst" ] && rm "$dst"
      [ -e "$dst" ] && backup_existing "$dst"
      ln -s "$tgt" "$dst"; echo "linked(shared): $dst → $tgt"
    else                                           # managed real entry → link to repo
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
for d in agents commands qpay-context content; do
  link "claude/$d"                "$HOME/.claude/$d"
done
link_entries claude/hooks         "$HOME/.claude/hooks"
link_entries claude/skills        "$HOME/.claude/skills"

echo "== Codex =="
link codex/AGENTS.md              "$HOME/.codex/AGENTS.md"
link codex/MIGRATION.md           "$HOME/.codex/MIGRATION.md"
for d in agents commands; do
  link "codex/$d"                 "$HOME/.codex/$d"
done
link_entries codex/skills         "$HOME/.codex/skills" .system
link codex/rules/common           "$HOME/.codex/rules/common"
link codex/rules/qpay             "$HOME/.codex/rules/qpay"
link codex/rules/lessons.md       "$HOME/.codex/rules/lessons.md"
seed codex/config.template.toml   "$HOME/.codex/config.toml"   # copy-if-absent (Codex owns this file)

echo "== OpenCode =="
# Keep the live dir REAL and reproduce each entry (like Claude/Codex): the shared
# skills are relative symlinks (../../../.agents/skills/* — one level deeper than
# ~/.claude, ~/.codex). A whole-dir symlink would resolve those against the repo and dangle.
link_entries opencode/skills      "$HOME/.config/opencode/skills"
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

echo "== Automation (weekly Claude/Codex configuration audit) =="
# One-time migration from the deleted agent-stack repository. Only remove the
# legacy script when its symlink points into that exact repository, and preserve
# the old plist in the normal installer backup.
legacy_audit_script="$HOME/.local/bin/agent-stack-audit.py"
legacy_audit_plist="$HOME/Library/LaunchAgents/com.dev.agent-stack-audit.plist"
if [ -L "$legacy_audit_script" ]; then
  case "$(readlink "$legacy_audit_script")" in
    "$HOME/GIthub/agent-stack/"*)
      rm "$legacy_audit_script"
      echo "removed legacy managed symlink: $legacy_audit_script"
      ;;
  esac
fi
if { [ -e "$legacy_audit_plist" ] || [ -L "$legacy_audit_plist" ]; } \
  && grep -q '<string>com.dev.agent-stack-audit</string>' "$legacy_audit_plist" 2>/dev/null; then
  launchctl bootout "gui/$(id -u)/com.dev.agent-stack-audit" >/dev/null 2>&1 || true
  backup_existing "$legacy_audit_plist"
fi
link home/.local/bin/agent-setup-audit.py         "$HOME/.local/bin/agent-setup-audit.py"
link home/Library/LaunchAgents/com.dev.agent-setup-audit.plist \
                                                 "$HOME/Library/LaunchAgents/com.dev.agent-setup-audit.plist"

echo "== Automation (review-intelligence harvest only) =="
link scripts/review-intel-harvest.py              "$HOME/.local/bin/review-intel-harvest.py"
link scripts/review_intel                         "$HOME/.local/bin/review_intel"
link home/Library/LaunchAgents/com.dev.review-intelligence-harvest.plist \
                                                 "$HOME/Library/LaunchAgents/com.dev.review-intelligence-harvest.plist"

echo
echo "Done. Backups (if any) under: $BACKUP"
echo "NOTE: after install, load the schedules once:"
echo "  launchctl bootstrap gui/\$(id -u) ~/Library/LaunchAgents/com.dev.daily-decisions.plist"
echo "  launchctl bootstrap gui/\$(id -u) ~/Library/LaunchAgents/com.dev.x-draft-factory.plist"
echo "  launchctl bootstrap gui/\$(id -u) ~/Library/LaunchAgents/com.dev.tech-brief.plist"
echo "  launchctl bootstrap gui/\$(id -u) ~/Library/LaunchAgents/com.dev.agent-setup-audit.plist"
echo "  launchctl bootstrap gui/\$(id -u) ~/Library/LaunchAgents/com.dev.review-intelligence-harvest.plist"
echo "See CONTENT.md for the content stack + morning workflow."
echo "NOTE: machine-local secrets are NOT managed here — recreate per machine:"
echo "  • ~/.codex/auth.json                     (run Codex login)"
echo "  • ~/.claude/settings.local.json          (re-add any local model tokens)"
echo "  • ~/.codex/config.toml + default.rules   (Codex regenerates on first run)"
