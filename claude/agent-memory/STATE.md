# Agent Memory — Global State

Standing facts only. Not a session journal. Keep this lean — it loads every session.
Update via the `/retro` skill — this file is a static `@import`, never auto-written.

## Verified Facts
- QPay backends: Express 5 + Babel (NOT TypeScript) + qpay-sequelize-postgres + Bull + Joi + Sentry
- QPay frontend Gen1: Next.js 12 + React 17 + TypeScript + Ant Design 4 + Redux + SWR + Formik
- QPay frontend Gen2: Next.js + Tailwind + Zustand (e.g. qpay-fi-admin-web)
- Backend lint: eslint-airbnb + eslint-plugin-prettier — NO standalone .prettierrc; run eslint --fix only
- Frontend lint: standalone .prettierrc exists — run prettier first, then eslint --fix
- Backend qpay-micro-logging replaces console.log — always use it in backend service code
- No test framework installed in most backend services (qpay-customer-service uses babel-node for tests)
- All QPay repos at /Users/dev/QPay/
- QPay workspace handoff authority is /Users/dev/QPay/AGENT_GUIDE.md (referenced by QPay/AGENTS.md)
- Codex mirrors Claude: ~/.codex/{agents/*.toml, skills/, rules/}. Claude files (~/.claude/agents/*.md) are source of truth; Codex .toml are generated ports — prompt-defense baseline + Claude body verbatim + `## Codex Compatibility` footer, preserving each toml's effort/sandbox/nicknames (regen: agent-setup/scripts/resync-codex-agents.py). Codex also has 9 execution specialists with no Claude equivalent — roster in QPay/AGENT_GUIDE.md. Both tools have their own native reviewer agents — Claude need not review Codex's changes or vice versa.
- Canonical agent-config repo = /Users/dev/GIthub/agent-setup (private GH Ganzorig2022/agent-setup). agent-stack and agent-system-starter are superseded — do not treat them as live. After config changes: sync live files → repo → commit.
- ~/.codex/rules/qpay/{backend,frontend}.md are byte-identical copies of ~/.claude/qpay-context/ — edit the Claude file only, then cp to Codex; `diff` is the drift check.
- Executors are usually Codex and OpenCode (NOT Claude). Default flow: Claude plans/reviews/orchestrates, then hands implementation off to Codex or OpenCode via the handoff-impl skill / AGENT_GUIDE.md. Prefer a self-contained handoff brief over implementing large changes directly.
- `gh-axi` is the standard GitHub tool for ALL agents (Claude, Codex, OpenCode) — not just a `gh` substitute. Use it for issues, PRs, comments, workflow/CI runs, and releases; prefer compact structured output and targeted queries over full logs/JSON dumps.

## Lessons Learned
- `~/.claude/rules/*.md` auto-loads into EVERY session globally; `paths:` frontmatter is ignored at user level (CC bugs #16299/#21858). Keep project-specific context in project CLAUDE.md imports, not user-level rules.
- CLAUDE.md + always-on rules are the main per-turn token cost — keep them lean; push detail into skills/agents (lazy-loaded).
- Custom subagents load ~/.claude/CLAUDE.md and its `@imports` (the built-in Explore/Plan agents skip it). Share content into all agents via a file `@import`'d from CLAUDE.md, not per-agent copies — e.g. the deduped Prompt Defense baseline now lives once at ~/.claude/prompt-defense.md.
- STATE.md is a static `@import`, NOT Claude Code's subagent persistent-memory feature (that needs `memory: user|project|local` frontmatter and lives at ~/.claude/agent-memory/<agent>/MEMORY.md). Nothing auto-writes STATE.md — capture learnings with `/retro`.
- Agent `model:` frontmatter IS honored: `sonnet|opus|haiku|fable|inherit|<full-id>` (defaults to `inherit`).
- Hook output channels: top-level `systemMessage` = user-facing non-blocking; `hookSpecificOutput.additionalContext` = injected for Claude on its next request (steers next action); `decision:"block"`+`reason` (or exit 2) = blocks & feeds Claude. Stop fires every turn-end (no true session-end event) — throttle to once-per-session via a marker file; `stop_hook_active` guards recursion.
- PostToolUse can match a specific tool name and inject `additionalContext`. `ExitPlanMode` is the tool that fires on plan approval — the interception point for "plan is done". Hooks CANNOT add choices to the native plan-approval menu (those options are hardcoded).
- X/Twitter with no API token (verified 2026-06): public Nitter is dead (`nitter.net` 200-but-empty, others 403), RSSHub `/twitter` is 404. Only token-free route to real X posts is a logged-in headless browser. Bluesky RSS (`bsky.app/profile/<handle>/rss`) still works as a reliable proxy source.
- `chrome-devtools-axi` for unattended/cron browser scraping: `CHROME_DEVTOOLS_AXI_USER_DATA_DIR` gives a persistent profile (login survives runs/reboots), headless KEEPS the logged-in session, and the bridge persists across `npx -y chrome-devtools-axi` calls. Under launchd's sparse PATH, resolve npx by absolute path (glob newest `~/.nvm/versions/node/*/bin/npx`) — shell PATH isn't present. Working pattern in `~/.local/bin/x-harvest.py`.
- Automating X.com **writes** via `chrome-devtools-axi` (headless): posting a single tweet + editing profile fields works, but multi-tweet **threads** are unreliable — `/compose/post` renders duplicate composers (scope selectors to `[role="dialog"]`) and X auto-restores stale drafts (clear the box with `execCommand` selectAll+delete before inserting). Set the React/Draft.js editor via `execCommand('insertText')`, not `.value`; use REAL CDP `click @uid` for add/menu/pin buttons (synthetic `.click()` is ignored, though it works for some like profile Save). Headless stays logged in; headed can come up logged-**out** on the same profile.
- Telegram Bot API = free unattended push channel for local automations: @BotFather bot creation is free (no billing/card); the user must message the bot ONCE before it can DM them (grab `chat_id` from `getUpdates`); `token`+`chat_id` in env; `sendMessage` caps at 4096 chars so chunk long messages.
- The auto-mode classifier blocks Claude from editing `.claude/settings*.json` permissions and from `mv`/`rm` of pre-existing repos — even with in-chat user approval. Don't retry; hand the exact command to the user to run via the `!` prefix.
