#!/bin/bash
# Stop hook — once-per-session, user-facing nudge to run /retro.
# Fires at most once per session, and only when the session actually changed files
# (a pure Q&A session isn't worth a retro). Non-blocking: surfaces a `systemMessage`
# to the user and never forces Claude to keep going.

input=$(cat)

sid=$(printf '%s' "$input" | jq -r '.session_id // empty')
transcript=$(printf '%s' "$input" | jq -r '.transcript_path // empty')
active=$(printf '%s' "$input" | jq -r '.stop_hook_active // false')

# Loop safety: never act while a Stop-hook chain is already running.
[ "$active" = "true" ] && exit 0
[ -z "$sid" ] && exit 0

# Once-per-session marker (prune stale markers so the dir stays small).
mdir="$HOME/.claude/.cache/retro-nudge"
mkdir -p "$mdir"
find "$mdir" -type f -mtime +2 -delete 2>/dev/null
marker="$mdir/$sid"
[ -f "$marker" ] && exit 0

# Only nudge if the session modified files (worth capturing learnings).
edits=0
if [ -n "$transcript" ] && [ -f "$transcript" ]; then
  edits=$(grep -Eo '"name"[[:space:]]*:[[:space:]]*"(Edit|Write|NotebookEdit)"' "$transcript" 2>/dev/null | wc -l | tr -d ' ')
fi
[ "${edits:-0}" -lt 2 ] && exit 0

touch "$marker"
printf '%s\n' '{"suppressOutput": true, "systemMessage": "💡 This session changed files. Consider running /retro to capture any durable standing facts into memory before wrapping up."}'
exit 0
