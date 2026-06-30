# Content Stack — build-in-public on X (@n_ganzo)

An automated, human-in-the-loop pipeline that turns real engineering work into on-brand
X posts. It **drafts** while you sleep; **you** approve and schedule. Nothing posts itself.

## The daily loop

```
21:00  daily-decisions  → logs what you built today into the vault   (memory)
06:00  x-draft-factory   → drafts 2-3 X posts from the vault          (content)
 you   review (~2 min)   → approve + schedule the good ones           (human gate)
US-prime  X native scheduler publishes while you work your 9-5        (reach)
```

The memory system feeds the content system: the more you build, the better tomorrow's drafts.
All on subscriptions (headless `claude`) — no API bills.

## Pieces

| File | Role |
|------|------|
| `~/.claude/content/brand.md` | Personal content brand — dark canvas `#0A0C10`, mint accent `#2EE6A6`, Manrope + JetBrains Mono. Separate from QPay's qcore. |
| `~/.claude/skills/artifact/SKILL.md` | `/artifact` skill — generate an on-brand card from a plain-language ask (interactive). |
| `~/.local/bin/x-draft-factory.py` | Nightly factory — reads vault → `claude -p` drafts → fills the proven card template → renders PNGs → drops a review packet on the Desktop. |
| `~/Library/LaunchAgents/com.dev.x-draft-factory.plist` | Schedule: 06:00 daily + login catch-up + 6h throttle. |

## Your morning workflow

1. Open `~/Desktop/x-drafts/<today>/drafts.md`.
2. Skim the 2-3 captions. Pick the good one(s); tweak freely — you're the editor.
3. For each keeper, in the X composer:
   - paste the caption,
   - drag in the matching `draftN.png`,
   - click the **calendar (schedule) icon**, set the suggested US window, **Schedule**.
4. After posts go live, reply to 3-4 AI/dev accounts — early engagement is the growth lever at a small following.

## Principles (do not break)

- **Never auto-post.** The factory only drafts; the human approves and schedules. This protects
  credibility and stays within X's authenticity rules.
- **One accent per artifact**, fixed template — guarantees clean cards from AI-written text.
- **Authentic > generic.** Drafts come from real work in the vault, not generic AI tips.

## Honest stage

Audience-building, not monetization. X ads-rev-share needs **500 verified followers +
5M impressions / 90 days**; currently ~37 followers. The job now is **consistency + engagement**,
not chasing payouts. Money (subscriptions / product / leads) comes after the audience.

## Regenerate on demand

```bash
python3 ~/.local/bin/x-draft-factory.py --force   # re-draft today now
```
