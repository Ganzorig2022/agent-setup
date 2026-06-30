#!/usr/bin/env bash
# Daily-decisions auto-harvest: summarize today's Claude/Codex/OpenCode work
# into the Obsidian vault, then reindex QMD so the memory is searchable.
# Designed to run under launchd (minimal env) — all paths are explicit.
set -uo pipefail

export HOME="/Users/dev"
NODE_BIN="/Users/dev/.nvm/versions/node/v22.21.1/bin"
export PATH="$HOME/.local/bin:$NODE_BIN:/usr/bin:/bin:/usr/sbin:/sbin"

CLAUDE="$HOME/.local/bin/claude"
QMD="$HOME/.local/bin/qmd"   # stable shim — survives Node version changes
HARVEST="$HOME/.local/bin/daily-decisions-harvest.py"

# Canonical vault = same one Hermes + QMD use (single source of truth).
VAULT="$(grep -E '^OBSIDIAN_VAULT_PATH=' "$HOME/.hermes/.env" 2>/dev/null | cut -d= -f2-)"
VAULT="${VAULT:-$HOME/GIthub/knowledge-base}"
DEC_DIR="$VAULT/decisions"
DATE="$(date +%Y-%m-%d)"
NOTE="$DEC_DIR/$DATE.md"
LOG="$HOME/Library/Logs/daily-decisions.log"
mkdir -p "$DEC_DIR" "$(dirname "$LOG")"

log() { printf '%s %s\n' "$(date '+%F %T')" "$*" >> "$LOG"; }
log "=== run for $DATE ==="

# Throttle: this also runs on login (catch-up for missed 21:00 runs). Skip if
# today's note was refreshed in the last 3h, so frequent logins don't re-summarize.
# Pass --force to override (e.g. the manual end-of-day run).
if [ "${1:-}" != "--force" ] && [ -f "$NOTE" ]; then
  if [ -z "$(find "$NOTE" -mmin +180 2>/dev/null)" ]; then
    log "note refreshed <3h ago; skipping (use --force to override)"
    exit 0
  fi
fi

MATERIAL="$(mktemp)"
trap 'rm -f "$MATERIAL"' EXIT

python3 "$HARVEST" > "$MATERIAL" 2>>"$LOG" || log "harvest reported an error"
BYTES="$(wc -c < "$MATERIAL" | tr -d ' ')"
log "harvested ${BYTES} bytes of session text"

if [ "${BYTES:-0}" -lt 200 ]; then
  log "no meaningful activity today; nothing written"
  exit 0
fi

read -r -d '' PROMPT <<'EOF'
You maintain an engineering decision log. The input below is raw text from
today's AI coding sessions across three tools (Claude Code, Codex, OpenCode).
Extract ONLY concrete decisions, conclusions, config/infra changes, and durable
learnings worth remembering tomorrow. Ignore chit-chat, abandoned explorations,
and tool noise. Output concise markdown bullets grouped under short "## topic"
headings; be specific with names, file paths, and the rationale behind each
choice. No preamble, no closing remarks. If there is nothing substantive worth
logging, output exactly: No significant decisions logged.
EOF

SUMMARY="$("$CLAUDE" -p "$PROMPT" < "$MATERIAL" 2>>"$LOG")" || { log "claude summarization failed"; exit 1; }
if [ -z "${SUMMARY//[[:space:]]/}" ]; then
  log "claude returned empty summary; nothing written"
  exit 1
fi

# Overwrite each run → the note always holds the best full-day summary.
{
  echo "---"
  echo "date: $DATE"
  echo "type: decision-log"
  echo "tags: [decisions, daily, auto-harvest]"
  echo "sources: [claude-code, codex, opencode]"
  echo "---"
  echo
  echo "# Decisions — $DATE"
  echo
  printf '%s\n' "$SUMMARY"
  echo
  echo "_Generated $(date '+%F %T') by daily-decisions auto-harvest._"
} > "$NOTE"
log "wrote $NOTE"

"$QMD" update >>"$LOG" 2>&1 || log "qmd update warning"
"$QMD" embed  >>"$LOG" 2>&1 || log "qmd embed warning"
log "reindexed QMD"

# Version the memory: commit just today's note if the vault is a git repo.
# Local commit only (no push) — keeps a diffable history of decisions over time.
if git -C "$VAULT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git -C "$VAULT" add "decisions/$DATE.md" >>"$LOG" 2>&1 || true
  if ! git -C "$VAULT" diff --cached --quiet 2>/dev/null; then
    if git -C "$VAULT" commit -q -m "decisions: $DATE auto-harvest" >>"$LOG" 2>&1; then
      log "committed decisions/$DATE.md to vault git"
    else
      log "git commit skipped/failed"
    fi
  fi
fi
log "done"
