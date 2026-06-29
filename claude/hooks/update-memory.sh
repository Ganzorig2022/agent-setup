#!/bin/bash
# Stop hook — gives Claude one final turn to write session notes to STATE.md.
# Exit code 1 injects stdout back to Claude as a prompt before the session ends.

STATE_FILE="$HOME/.claude/agent-memory/STATE.md"
TODAY=$(date '+%Y-%m-%d %H:%M')

echo "Session ending ($TODAY). Before you stop, update the '## Last Session' section in $STATE_FILE with: today's date, what was worked on, key decisions or findings, and what's next. Keep it to 2-3 lines. If this was a trivial session (e.g. a quick question), just update the date."
exit 1
