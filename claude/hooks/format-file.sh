#!/bin/bash
# PostToolUse formatter — runs prettier then eslint --fix after every Edit/Write.
# Walks up from the edited file to find the project root (package.json).

FILE="$CLAUDE_FILE_PATH"

# Skip if no file path or file doesn't exist
[ -z "$FILE" ] || [ ! -f "$FILE" ] && exit 0

# Only format JS/TS/JSON/CSS/SCSS/MD files
if ! echo "$FILE" | grep -qE '\.(js|jsx|ts|tsx|json|css|scss|md)$'; then
  exit 0
fi

# Walk up directory tree to find project root (where package.json lives)
PROJECT_ROOT=""
DIR="$(cd "$(dirname "$FILE")" && pwd)"
while [ "$DIR" != "/" ]; do
  if [ -f "$DIR/package.json" ]; then
    PROJECT_ROOT="$DIR"
    break
  fi
  DIR="$(dirname "$DIR")"
done

[ -z "$PROJECT_ROOT" ] && exit 0

# 1. Run prettier if a config file exists in the project root
PRETTIER_CONFIG=$(find "$PROJECT_ROOT" -maxdepth 1 \( -name ".prettierrc" -o -name ".prettierrc.js" -o -name ".prettierrc.json" -o -name ".prettierrc.yaml" -o -name ".prettierrc.yml" -o -name "prettier.config.js" -o -name "prettier.config.cjs" \) 2>/dev/null | head -1)
if [ -n "$PRETTIER_CONFIG" ]; then
  (cd "$PROJECT_ROOT" && npx --no-install prettier --write "$FILE" 2>/dev/null)
fi

# 2. Run eslint --fix if a config file exists in the project root (legacy or flat config)
ESLINT_CONFIG=$(find "$PROJECT_ROOT" -maxdepth 1 \( -name ".eslintrc" -o -name ".eslintrc.js" -o -name ".eslintrc.json" -o -name ".eslintrc.yaml" -o -name ".eslintrc.yml" -o -name "eslint.config.js" -o -name "eslint.config.mjs" -o -name "eslint.config.cjs" \) 2>/dev/null | head -1)
if [ -n "$ESLINT_CONFIG" ]; then
  (cd "$PROJECT_ROOT" && npx --no-install eslint --fix "$FILE" 2>/dev/null)
fi

exit 0
