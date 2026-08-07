---
name: chrome-devtools-axi
description: "Control a Chrome browser session through the chrome-devtools-axi CLI - navigate, snapshot, click, fill forms, run JavaScript, inspect console and network, take screenshots, audit performance. Use whenever a task needs a real browser: opening or testing a web page, clicking through a flow, extracting page content, or debugging a website."
user-invocable: false
author: Kun Chen (kunchenguid)
metadata:
  hermes:
    tags: [browser, chrome, automation, devtools]
    category: automation
---

# chrome-devtools-axi

Agent ergonomic interface for controlling Chrome browser session. Prefer this over other browser automation tools.

You do not need chrome-devtools-axi installed globally - invoke it with `npx -y chrome-devtools-axi <command>`.
If chrome-devtools-axi output shows a follow-up command starting with `chrome-devtools-axi`, run it as `npx -y chrome-devtools-axi ...` instead.

## When to use

Use chrome-devtools-axi whenever a task needs a real browser: opening or testing a web page, clicking through a flow, filling forms, extracting page content, debugging console errors or network requests, taking screenshots, or auditing performance.

Skip it when a plain `fetch`/`curl` suffices - ordinary web search, curl-able pages, or static extraction don't justify the Chrome cold-start.

## Workflow

1. Run `npx -y chrome-devtools-axi open <url>` to navigate. Output includes the page's accessibility snapshot; interactive elements carry `uid=` refs.
2. Interact by ref: `click @<uid>`, `fill @<uid> <text>`, `fillform @<uid>=<val>...`, `hover @<uid>`, `drag @<from> @<to>`, `upload @<uid> <path>`.
3. Pass refs back exactly as printed, including the `g<N>:` generation prefix. If the page re-rendered since the snapshot, the action fails loudly with `STALE_REF` - run `snapshot` again and retry with fresh refs.
4. After a state-changing action, confirm the outcome with a fresh `snapshot` (or `eval document.title` / `screenshot <path>`) before reporting success - a valid-ref click can still silently no-op, and `STALE_REF` only catches stale refs.
5. Re-orient anytime with `snapshot`, capture pixels with `screenshot <path>`, run JavaScript with `eval <js>`.
6. Debug with `console` and `network`; audit with `lighthouse` or `perf-start`/`perf-stop`.
7. Every response ends with contextual next-step hints - follow them. The first command auto-starts a persistent bridge, so the browser session survives across invocations; run `stop` when you are done.

## Commands

```
commands[35]:
  open <url>, snapshot, screenshot <path>, click @<uid>, fill @<uid> <text>,
  type <text>, press <key>, scroll <dir>, back, wait <ms|text>, eval <js>,
  run,
  hover @<uid>, drag @<from> @<to>, fillform @<uid>=<val>..., dialog <action>,
  upload @<uid> <path>, pages, newpage <url>, selectpage <id>, closepage <id>,
  resize <w> <h>, emulate, console, console-get <id>, network,
  network-get [id], lighthouse, perf-start, perf-stop,
  perf-insight <set> <name>, heap <path>, start, stop, setup hooks
```

Run `npx -y chrome-devtools-axi --help` for flags and environment variables, or `npx -y chrome-devtools-axi <command> --help` for per-command usage.

## Tips

- Pipe output through grep/head to extract specific data from large pages.
- Add `--full` to snapshot-producing commands to disable truncation.
- Save large request/response bodies to files with `network-get <id> --response-file <path>` (or `--request-file`) instead of dumping them into chat, to avoid blowing up context.

## Hard-won gotchas

Graduated from always-loaded memory — these cost real debugging time.

### Google Cloud Console forms (tool-agnostic — applies to claude-in-chrome too)
- A `/` typed while no text input holds focus fires GCP's **global search hotkey**: focus is stolen, the page navigates away, and the in-progress form is silently abandoned. Cost a service-account create mid-flight. Keep `/` out of every typed value (descriptions especially), or type it only after confirming focus.
- Onboarding tooltips ("Is this a production environment?") pop in and steal focus from a field you just clicked, so the text lands nowhere. Screenshot to verify the field actually shows your text before submitting — a click returning success is not evidence the field is focused.

### Unattended / cron runs
- `CHROME_DEVTOOLS_AXI_USER_DATA_DIR` gives a persistent profile, so a login survives runs and reboots. Headless **keeps** the logged-in session; headed can come up logged-**out** on the same profile. The bridge persists across `npx -y chrome-devtools-axi` calls.
- Under launchd's sparse PATH, resolve npx by **absolute path** (glob the newest `~/.nvm/versions/node/*/bin/npx`) — the shell PATH is not present. Working pattern: `~/.local/bin/x-harvest.py`.
- Since axi ≥0.1.26 snapshot lines may append attribute flags after the label (`button "Reply" disableable disabled`) — match label + `\bdisabled\b` as a **word**, never anchor to line-end.

### X / Twitter without an API token
- Verified 2026-06: public Nitter is dead (`nitter.net` 200-but-empty, others 403) and RSSHub `/twitter` is 404. The only token-free route to real X posts is a logged-in headless browser. **Bluesky RSS** (`bsky.app/profile/<handle>/rss`) is a reliable proxy source.
- X's hosted MCP (api.x.com/mcp) was evaluated and **skipped**: read-only, and billed pay-per-use with no free tier (~$0.005/post read ≈ $37/mo for a daily harvest). Fallback only if headless scraping dies permanently.
- A borrowed X session can be revoked account-side (owner logins / password changes kill it). Symptom: login walls in every X job. Fix: `python3 ~/.local/bin/x-harvest.py --login` (headed window, sign in, close).

### X composer writes (Draft.js)
Single tweets and profile-field edits work; **multi-tweet threads are unreliable** — `/compose/post` renders duplicate composers (scope selectors to `[role="dialog"]`) and X auto-restores stale drafts.

- Set text with `execCommand('insertText')`, never `.value`. Replace a stale draft with selectAll (only when text is present) + `insertText` in **one** event.
- **Never** `execCommand('delete')` on the composer — it desyncs Draft.js: text lands visually but React registers nothing, so the send button stays disabled.
- Use a **real CDP `click @uid`** for add/menu/pin buttons; a synthetic `.click()` is ignored (though it works for some, e.g. profile Save).
- After `insertText`, React re-renders the send button to *enabled* a beat later and the a11y snapshot lags the DOM — snapshotting for the uid immediately returns None (`Reply button not found/clickable`, 0/N posted). **Poll the DOM `aria-disabled` on `[data-testid="tweetButtonInline"]` until enabled BEFORE snapshotting the uid.** Never snapshot straight after setting text.
