#!/bin/bash
# PreToolUse safety gate — blocks destructive commands before they run.
# Exit code 2 = block the call entirely (model cannot override).

INPUT=$(cat)
CMD=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    cmd = (d.get('tool_input') or d.get('input') or {}).get('command', '')
    print(cmd)
except:
    print('')
" 2>/dev/null || echo "")

# rm -rf (any flag order: -rf, -fr, --recursive --force, etc.)
if echo "$CMD" | grep -qE 'rm\s+.*-[a-zA-Z]*r[a-zA-Z]*f|rm\s+.*-[a-zA-Z]*f[a-zA-Z]*r|rm\s+.*--recursive'; then
  echo "BLOCKED: recursive force delete is not allowed. Do it manually if intentional." >&2
  exit 2
fi

# git push --force / -f
if echo "$CMD" | grep -qE 'git\s+push\s+.*(\s-f\b|\s--force\b)'; then
  echo "BLOCKED: git push --force is not allowed. Do it manually if intentional." >&2
  exit 2
fi

# git reset --hard
if echo "$CMD" | grep -qE 'git\s+reset\s+--hard'; then
  echo "BLOCKED: git reset --hard is not allowed. Do it manually if intentional." >&2
  exit 2
fi

# Reading .env files via cat/bash (deny list covers Read() tool, this covers bash)
if echo "$CMD" | grep -qE 'cat\s+.*\.env(\s|$)|cat\s+.*\.env\.'; then
  echo "BLOCKED: reading .env files via bash is not allowed." >&2
  exit 2
fi

exit 0
