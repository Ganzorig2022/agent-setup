# Personal Content Brand — X / social one-pagers

> Design spec for the user's **personal** content artifacts (X posts, carousels, cards).
> Deliberately separate from QPay's qcore brand — this is the creator's own look.
> The `/artifact` skill reads this file before generating anything.

## Vibe
Clean, minimal, **bold + techy**. Dark dev/terminal energy with lots of breathing room.
High contrast, one idea per card, restraint over decoration. Should look like a sharp
engineer made it — confident, not flashy.

## Color tokens (dark theme — the default)
| Role | Hex |
|------|-----|
| Canvas (bg) | `#0A0C10` |
| Surface / card | `#12161D` |
| Border | `#232A35` |
| Text primary | `#E8EEF5` |
| Text muted | `#8B97A7` |
| **Accent (the one pop)** | `#2EE6A6` (electric mint-green) |
| Accent soft (fills) | `rgba(46,230,166,0.12)` |
| Accent text-on-dark | `#2EE6A6` |

Rules: exactly **one** accent per artifact. Never introduce a second hue. Use the accent
sparingly — eyebrow, one keyword, the rule line, numbers. Everything else is neutral.

## Type
- **Headings:** Manrope, 800 weight, tight leading. Big — the hook should dominate.
- **Body:** Manrope 400/500.
- **Eyebrow / labels / code:** JetBrains Mono, 500, uppercase, letter-spacing ~0.12em, muted or accent.
- Both load from Google Fonts.

## Layout (default artifact = 4:5 portrait, 1080×1350)
- Outer padding generous (~72px). Card fills the frame on the dark canvas.
- **Eyebrow** (mono, accent) → **Hook headline** (huge) → short **subline** (muted) →
  a short accent **rule** → **body** (numbered beats or 3–5 bullets) → **footer**.
- One idea per card. ≤ ~6 short lines per section. White space is a feature.
- Numbered beats: big mono accent number + bold line + one muted detail line.
- Footer: small mono — `@handle` on the left, a tiny credit on the right. A small
  accent square as a logo mark.

## Voice
Direct, specific, a little opinionated. Short declarative lines. Show the *how*, name real
tools, give one concrete number when you have one. No hype words, no emoji in the artifact
itself. Confidence without bragging.

## Formats
- **One-pager:** single 1080×1350 card (default).
- **Carousel:** N cards, same system; card 1 = hook, last = takeaway/CTA. Number them (1/5).
- **Square:** 1080×1080 when a tighter crop is wanted.

## Export
Render at 2× device pixel ratio for crisp retina output before screenshotting.

## TODO for the user
- Replace `@handle` in the footer with your real X handle.
