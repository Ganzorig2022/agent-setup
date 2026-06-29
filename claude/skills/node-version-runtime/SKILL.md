---
name: node-version-runtime
description: Align Node.js runtime metadata across Dockerfiles, .nvmrc, package.json engines, and local shell auto-switching. Use when the user asks to add or fix .nvmrc, engines.node, Node version mismatches, nvm/fnm/Volta/asdf setup, or local dev server failures caused by the wrong Node version.
---

# Node Version Runtime

## Workflow

1. Inspect repository runtime sources before editing:
   - Dockerfiles: `rg -n "^FROM .*node:|NODE_VERSION" . -g "Dockerfile*" -g "*.Dockerfile"`.
   - Package metadata: `package.json` `engines.node`, `packageManager`, and scripts.
   - Existing version files: `.nvmrc`, `.node-version`, `.tool-versions`, `package.json` `volta`.
   - Sibling repos only when the user explicitly asks for cross-repo alignment.

2. Choose the source of truth conservatively:
   - Prefer the production Docker image version when present.
   - If Docker uses a major tag like `node:22-alpine`, use that major in `.nvmrc` and a compatible engine range such as `22.x`.
   - If Docker uses a pinned tag like `node:24.14.0-alpine`, use the exact version in `.nvmrc` and `engines.node`.
   - If Docker is absent, infer from existing `engines`, lockfile package manager, framework requirements, and recent repo docs; call out the inference.

3. Edit runtime metadata:
   - Add or update root `.nvmrc`.
   - Add or update `package.json`:

```json
"engines": {
  "node": "22.x"
}
```

   - Preserve existing package ordering style and do not reformat the whole file.
   - Do not change lockfiles for metadata-only edits unless the package manager requires it and the user asked for install/update work.

4. Validate:
   - Parse JSON with `node -e "JSON.parse(require('fs').readFileSync('package.json','utf8'))"`.
   - Print the resolved values from `.nvmrc` and `package.json`.
   - Use `git diff -- .nvmrc package.json` and `git status --short`.
   - For cross-repo changes, validate each repo separately.

## Shell Auto-Switching

`.nvmrc` does not switch Node by itself. When the user asks for automatic local server startup or shell behavior:

1. Check installed tools without exposing secrets:
   - `command -v nvm || true`, `command -v fnm || true`, `command -v volta || true`, `command -v asdf || true`, `command -v direnv || true`.
   - Search only relevant shell lines: `rg -n "nvm|fnm|volta|asdf|direnv|\\.nvmrc|node-version" ~/.zshrc ~/.zprofile ~/.bashrc ~/.profile 2>/dev/null`.

2. For zsh + nvm, recommend or add this hook after nvm is loaded:

```zsh
autoload -U add-zsh-hook

load-nvmrc() {
  local nvmrc_path
  nvmrc_path="$(nvm_find_nvmrc)"

  if [ -n "$nvmrc_path" ]; then
    local nvmrc_node_version
    nvmrc_node_version="$(nvm version "$(cat "$nvmrc_path")")"

    if [ "$nvmrc_node_version" = "N/A" ]; then
      nvm install
    elif [ "$nvmrc_node_version" != "$(nvm version)" ]; then
      nvm use
    fi
  fi
}

add-zsh-hook chpwd load-nvmrc
load-nvmrc
```

3. Verify with an interactive shell:

```sh
zsh -lic 'cd /path/to/repo && node -v'
```

If sandboxed shell startup emits unrelated cache or completion errors, report them separately from the Node switching result.
