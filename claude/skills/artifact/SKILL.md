---
name: artifact
description: Generate on-brand social/content artifacts (one-pagers, carousels, cards) for X and other platforms from a plain-language ask. Use when the user wants a branded visual post, one-pager, carousel, or shareable card — NOT QPay product UI (that uses the qpay design.md specs).
---

# /artifact — branded content artifacts on demand

Turn a plain-language ask ("one-pager on X about Y") into a polished, on-brand visual
the user can screenshot and post. This is for the user's **personal content brand**, not
QPay product work.

## Procedure

1. **Read the brand.** Load `~/.claude/content/brand.md` (colors, type, layout, voice).
   Everything you emit must use those tokens — never invent colors or fonts.

2. **Shape the content.** From the user's ask, draft a tight outline:
   - **Hook** — the headline. Specific, a little opinionated, ≤ ~7 words ideal.
   - **Subline** — one muted clarifying line.
   - **3–5 beats** — numbered steps or bullets, one idea each, ≤ ~2 short lines per beat.
   - **Takeaway / footer** — the payoff + `@handle`.
   Prefer the user's *real* story and concrete specifics (real tool names, one number) over
   generic filler. If sourcing from prior work, you may query the `qmd` knowledge base.

3. **Emit self-contained HTML.** One file in the scratchpad dir. Inline `<style>`, Google
   Fonts link, brand tokens as CSS variables. Default frame **1080×1350 (4:5 portrait)**;
   use 1080×1080 square or a carousel of cards when the ask calls for it. Set
   `<meta>` viewport and design the card at exact pixel size for clean capture.

4. **Render + preview.** Serve it (`python3 -m http.server <port>` in the scratchpad),
   navigate the browser there, resize the window to fit the card, and screenshot with
   `save_to_disk: true` so the user sees the result. Iterate on their feedback.

5. **Hand off for posting.** Tell the user the file path and that they can screenshot at 2×
   for a retina-crisp image. NEVER post to any platform automatically — posting is the
   user's action.

## Layout patterns that work for X (technical creators)

- One idea per card. The hook should dominate the top third.
- High contrast, dark canvas, **one** accent color used sparingly (numbers, rule, one keyword).
- Big type, generous whitespace — crowded cards die in the feed.
- Mono eyebrow label at top (e.g. `BUILD LOG` / `HOW I DID IT`) sets the techy tone.
- Footer with `@handle` builds recognition across posts — always include it.
- Carousel: card 1 = hook only (make them swipe), middle = the meat, last = takeaway + soft CTA.

## Guardrails
- No emoji inside the artifact. No hype words. Specific > clever.
- Exactly one accent hue per artifact.
- Don't post, schedule, or publish anything — only generate + preview.
