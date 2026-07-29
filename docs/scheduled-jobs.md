# Scheduled Jobs (launchd) — Reference

All unattended automation on the Mac. Plists live in `~/Library/LaunchAgents/`
(mirrored under `home/Library/LaunchAgents/` where portable); scripts in
`~/.local/bin/` (mirrored under `home/.local/bin/`).

**House rule (2026-07-04): generate always, deliver eventually.** Generation
blocks on network with long deadlines (material captured at fire time);
failed Telegram sends queue to `~/.outbox/` and `outbox-flush` retries them.
launchd never loses a calendar job to sleep — it fires once at next wake;
jobs are only lost if the Mac is shut down across the slot.

## Active jobs

| Job (label) | Schedule | Script | What it does | Needs network for | Offline behavior | Output | Delivery |
|---|---|---|---|---|---|---|---|
| **daily-decisions**<br>`com.dev.daily-decisions` | daily 21:00 + login catch-up | `daily-decisions.sh` | Harvests the day's Claude/Codex/OpenCode session logs, Claude-summarizes into a decision note, reindexes QMD, commits to vault git | Claude summarization only (harvest/embed/commit are local) | Material + date captured at fire time; waits for net up to **20h**; login catch-up re-runs if note >3h stale | `~/GIthub/knowledge-base/decisions/<date>.md` | vault git commit |
| **tech-brief**<br>`com.dev.tech-brief` | daily 08:00 + login catch-up | `tech-brief.py` | RSS + X harvest → Claude-curated daily AI/dev brief; drafts X replies + auto-posts via `x-reply.py` | Everything (feeds, X, Claude, Telegram) | Retries whole fetch every 15 min up to **20h**; skips if today's brief <4h old | `~/tech-brief/<date>.md` (symlinked onto Desktop — same TCC reason as x-deepdive; never write the Desktop subtree directly) | Telegram (outbox on failure); failed X replies degrade to manual drafts in the brief |
| **agent-setup-audit**<br>`com.dev.agent-setup-audit` | Mondays 07:00 + login catch-up (72-hour throttle) | `agent-setup-audit.py` | Read-only weekly Claude/Codex audit: official changes, evidence-backed community experiments, installed versions, active settings, agent routing, and canonical `agent-setup` symlink health | Claude web research + Telegram | Existing report suppresses duplicate catch-up; failed Telegram delivery enters `~/.outbox` | `~/agent-setup-audits/<date>.md` | macOS notification + Telegram |
| **kb-lint**<br>`com.dev.kb-lint` | Sundays 10:00 + login catch-up (5-day throttle) | `kb-lint.py` | Audits always-loaded agent memory: mechanical checks (dead paths, Claude↔Codex mirror drift, stale dated claims) + one Claude semantic pass (contradictions, staleness, journal noise). Read-only — fixes stay manual (`/retro`) | Semantic pass + Telegram (mechanical checks are local) | Waits for net up to **8h** before the semantic pass | `~/kb-lint/<date>.md` | macOS notification + Telegram (outbox on failure) |
| **x-deepdive**<br>`com.dev.x-deepdive` | 1st & 15th, 07:00 (10-day recency skip) | `x-deepdive.py` | Long-form X deep-dive content packet: harvest, 5 LLM passes, article + share cards + critique. Human posts manually (2×/month strategy) | Everything | Blocks at start until net, up to **24h**; write-probe before expensive passes | `~/x-deepdives/<date>/` (symlinked onto Desktop — never write Desktop subtrees directly, TCC blocks launchd) | Telegram notify (outbox on failure) |
| **outbox-flush**<br>`com.dev.outbox-flush` | every 30 min + login | `outbox-flush.py` | Delivery retry queue: sends queued Telegram messages oldest-first, stops at first failure (keeps multi-part order), drops after 14 days | Telegram only | That's its job — it just retries next interval | — | Telegram |

## Decommissioned (plists kept for re-enable)

| Job | Was | Why off |
|---|---|---|
| **x-draft-factory**<br>`com.dev.x-draft-factory` | daily short-form X post drafts | Short-form originals don't pay at small follower count; strategy moved to deep-dives (2×/mo) + tech-brief reply engine. Kill switch: `~/Desktop/x-drafts/.no-auto-post` |
| **x-post**<br>`com.dev.x-post` | auto-posted the drafts to X | Decommissioned with x-draft-factory (launchctl disabled) |

## Related manual-only tooling (not scheduled, by design)

| Tool | Trigger | Purpose |
|---|---|---|
| `agent-evals.py` | manual, after changing an agent prompt/hook | Reviewer-agent regression evals vs committed baseline (`evals/reviewers/`). Kept off cron so it can't burn tokens on a timer |
| `scripts/hook-smoke.py` | manual, after editing any hook in `claude/hooks/` | Zero-token pipe-tests: canned JSON payloads → every hook, asserts exit codes + output shape in a temp HOME (never touches live `~/.claude`) |
| `x-reply.py` | called by tech-brief | Posts drafted X replies via logged-in headless Chrome; safety rails: kill switch `~/Desktop/tech-brief/.no-auto-reply`, dedupe cache, 4/run cap, jittered spacing. **Fixed 2026-07-05:** the `Reply button not found/clickable` failures (0/N posted) were a race — `set_composer_text` returns before React re-renders the inline Reply button to enabled, so `click_send` snapshotted it while still disabled. `click_send` now polls the button's DOM `aria-disabled` (`reply_button_enabled`) up to 12s before snapshotting. Verified live (button found in 0.6s, send withheld); full end-to-end confirmed on the next real 08:00 run |
| `x-harvest.py` | called by tech-brief (4h cache) | Headless X scrape of ~25 builder accounts; `--login` re-auths when the borrowed session is revoked |

## Logs & health

- Every job: `~/Library/Logs/<name>.log` (own log) + `.out/.err.log` (launchd streams)
- Quick health check: `launchctl list | grep com.dev.` — second column is last exit code
- Known trap: launchd python jobs **cannot** read/write `~/Desktop` subtrees created from a terminal (per-file `com.apple.macl` TCC) — keep outputs in `~/<dir>`, symlink onto Desktop
- Subagent usage observability: `~/.claude/hooks/subagent-usage.log` (Claude) and `~/.codex/log/subagent-usage.log` (Codex, via notify wrapper)
