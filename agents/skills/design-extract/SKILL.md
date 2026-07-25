---
name: design-extract
description: Extract a design system from a screenshot, a live URL, a Figma export, or an existing repo, and write it as a per-repo design.md (plus token file) that inherits the QPay qcore brand core. Use when onboarding a new frontend repo, reconstructing an unspecced UI, capturing a competitor or reference design, or when asked to "write the design.md" / "extract the design system" / "what tokens does this UI use".
---

# Design Extract

Turn a visual source into a written design spec. Output is a **thin per-repo `design.md`**, not a essay — the global brand core already lives at `~/.claude/qpay-context/design.md` and the per-repo file only states what differs.

## When to Use

- A frontend repo has no `design.md` and you need one before generating any branded artifact
- You have a screenshot, Figma file, or live URL and need the tokens behind it
- Onboarding an inherited UI with no design documentation
- Auditing whether a repo's actual CSS matches its declared design system

## Do Not Use When

- The repo already has `design.md` — read it, don't regenerate it
- You need to *apply* a direction to new UI → `frontend-design-direction`
- You need a branded social artifact → `artifact`

## Step 0 — Know the brand core before you extract

QPay's canonical design system is **qcore**. Source of truth:
`qpay-docs-web-v2/src/styles/qcore-tokens.css`.

| Role | Value |
|------|-------|
| Primary | `#004fff` |
| Secondary (navy) | `#002148` |
| Font | Manrope |
| Success | `#00c950` |
| Warning | `#f0b100` |
| Danger | `#fb2c36` |
| Themes | light + dark, both shipped |

Two standing exceptions — do **not** "correct" either:

- **`qpay-ticket-web-v2` deliberately overrides primary to indigo `#615fff`** in its own `src/styles/globals.css`, while keeping Manrope, navy secondary, and the qcore semantic scales.
- The `design-tokens.tokens.json` files in `qpay-deps-web` and `qpay-qpaymn-web` are **Figma DTCG export snapshots with different schemas** — historical, not live. Prefer qcore.

## Step 1 — Identify the source and pull the raw material

| Source | How to read it |
|--------|----------------|
| Screenshot / image file | Read the image directly (Claude Read tool renders it; Codex: describe from the file the user attached) |
| Live URL | `chrome-devtools-axi` skill — navigate, screenshot, then pull computed styles via the JS evaluate step |
| Existing repo | Grep the token/style layer first (below) |
| Figma | Ask for a DTCG token export or a full-frame PNG. Do not guess Figma internals |

Repo extraction order — stop at the first that exists:

```bash
# 1. explicit token layer
fd -e css . src/styles | head          # qcore-tokens.css, globals.css
# 2. tailwind config
fd -g 'tailwind.config.*'
# 3. component-level truth (last resort — means there is no system)
rg -o '#[0-9a-fA-F]{6}' --no-filename src | sort | uniq -c | sort -rn | head -30
```

That last command doubles as the **consistency signal**: a healthy system shows a handful of hexes with high counts. Thirty one-off hexes means the "system" is decoration, and your `design.md` should say so.

## Step 2 — Extract these nine dimensions

Work through all nine. Record "not present" explicitly — an absent dark theme is a finding, not a blank.

1. **Color roles** — primary, secondary, surface/background layers, border, text (primary/muted/inverse), semantics (success/warning/danger/info)
2. **Type scale** — family, weights actually used, size ramp, line-heights
3. **Spacing** — the base unit and the ramp (4/8/16? or arbitrary?)
4. **Radii** — per component class, not one global value
5. **Elevation** — shadow ramp, or borders-instead-of-shadows
6. **Breakpoints** — and whether layout actually changes at them
7. **Component inventory** — buttons, inputs, cards, tables, modals, nav; note variants per component
8. **States** — hover, focus-visible, active, disabled, loading, empty, error. Missing focus-visible is an accessibility finding
9. **Theming** — light/dark completeness; which values are token-driven vs hardcoded

## Step 3 — Map to existing tokens, don't mint new ones

For every extracted value, find the nearest qcore token before writing a raw hex. A `design.md` full of hexes that shadow existing tokens is worse than no `design.md` — it creates a second source of truth.

- Value within ~2% of a qcore token → record it as that token
- Value genuinely distinct → record it, and flag it as an intentional override or as drift, explicitly
- Never introduce a new semantic name for a color that already has one

Run contrast on every text-on-surface pair you record. Anything under 4.5:1 for body text is a finding, and it goes in the output — do not silently round it up.

## Step 4 — Write the output

**Per-repo `design.md`** — thin, at the repo root. This is the convention already used by `qpay-docs-web-v2` and `qpay-ticket-web-v2`:

```markdown
# <repo> — Design

Inherits the QPay brand core: ~/.claude/qpay-context/design.md

- **Primary:** #004fff (qcore default)   ← or the deliberate override, with a one-line reason
- **Render target:** web / Next.js <version>, Gen <1|1.5|2|3>
- **Token file:** src/styles/<file>.css

## Deviations from qcore
- (only real deviations; empty section is a good outcome)
```

**Extraction report** — separate, for anything the repo file shouldn't carry: the nine-dimension findings, the component inventory, contrast failures, and drift. Put it in the scratchpad or hand it to the user; do not bloat `design.md` with it.

**Token file** — only when the repo has no token layer at all, and only after confirming with the user. Generating tokens into a repo that already has a system is how you get two systems.

## Anti-Patterns

- **Inventing a token layer for a repo that has one.** Extract, then map. The existing file wins.
- **"Correcting" the ticket-web indigo.** It is intentional and documented.
- **Treating the DTCG snapshots as live.** They are stale Figma exports with mismatched schemas.
- **Reporting AI-slop defaults as the extracted system** — purple-to-blue gradients, glass cards, uniform 12px radii on everything. If the source UI genuinely looks like that, say so as a finding rather than encoding it as the system.
- **Skipping the states pass.** Hover/focus/disabled/loading/empty is where inherited UIs are actually broken, and it's the part a screenshot won't show you — check the code.

## Related

- `frontend-design-direction` — apply a direction to new UI (this skill only extracts)
- `artifact` — branded social/content artifacts
- `chrome-devtools-axi` — the browser side of URL extraction
- `~/.claude/qpay-context/design.md` — the brand core every per-repo file inherits
