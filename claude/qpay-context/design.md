# QPay Design Core (qcore)

> **Brand DNA shared across qpay-\* web projects.** This is the global, repo-agnostic
> design spec an agent reads before generating any branded artifact (one-pager,
> carousel, case study, ad concept, slide).
>
> Source of truth = `qpay-docs-web-v2/src/styles/qcore-tokens.css` (the qcore token set).
> A per-repo `design.md` **inherits this file** and only states what differs
> (its primary hue, render target, token file path). When the two conflict, the
> per-repo file wins for that repo.

## How to use this file
1. Read this global core first → it defines the QPay look.
2. Read the target repo's `design.md` → it overrides primary color + render target.
3. Generate the artifact using the merged spec. Never invent colors/fonts outside these.

## Brand identity
- **Voice:** clear, direct, financial-grade trust. No hype, no exclamation spam. Short
  declarative sentences. Confidence without jargon. (Mongolian or English — match the source.)
- **Feel:** clean fintech, generous whitespace, flat/soft-elevation (no heavy skeuomorphism),
  rounded corners, high contrast for legibility.

## Color — canonical palette (light theme)
Primary brand blue. **Note:** some repos override `--color-primary` (see their `design.md`);
everything else below is shared.

| Role | Token | Hex |
|------|-------|-----|
| Primary | `--color-primary` | `#004fff` |
| Primary 50 / 100 / 200 / 400 / 600 | scale | `#f0f5ff` `#d9e6ff` `#b3ccff` `#4d85ff` `#0046e6` |
| Secondary (navy) | `--color-secondary` | `#002148` |
| Secondary 600–900 | scale | `#001c3d` `#001632` `#001128` `#000a1e` |
| Success | `--color-success` | `#00c950` |
| Warning | `--color-warning` | `#f0b100` |
| Danger | `--color-danger` | `#fb2c36` |
| Page bg | `--bg-page` | `#f4f4f4` |
| Elevated bg | `--bg-elevated` | `#f0f0f0` |
| Text primary | `--text-primary` | `#000000` |
| Text secondary | `--text-secondary` | `#606060` |
| Text inverse | `--text-inverse` | `#ffffff` |
| Border default / medium / strong | | `#f0f0f0` `#e0e0e0` `#d0d0d0` |

### Dark theme (qcore also ships dark)
- Page bg `#0d0d0d`, elevated `#1f1f1f`, text primary `#f0f0f0`, text secondary `#a0a0a0`,
  text inverse `#000000`. Brand/semantic scales become translucent (e.g. `--color-primary-50:
  rgba(0,79,255,0.12)`). Default to **light** for artifacts unless asked.

## Typography
- **Font family: Manrope** (everywhere — loaded via `next/font/google`). Mono: JetBrains/Geist Mono.
- Weights: 700 headings, 600 subheads, 400/500 body.
- Header scale (from Figma tokens, px / line-height): H1 48/56 · H2 44 · H3 ~32 · H4 ~24.
- Body scale: lg 20/28 · base 16/24 · md 14/20 · xs 12/16 · xxs 10/12.
- Letter-spacing 0; no all-caps except small eyebrow labels.

## Shape & spacing
- Radius scale (qcore): 5xs `4px` · 3xs `8px` · xs `12px`; shadcn repos use `--radius: 0.625rem`
  as the base step. Cards/buttons use the medium step, pills use full.
- Spacing: 4px base grid (4 / 8 / 12 / 16 / 24 / 32 / 48 / 64).
- Elevation: soft, low-opacity shadows. Avoid hard 1px drop shadows.

## Iconography
- Icon libraries in use: `lucide-react` and `@hugeicons/react` (docs-web-v2).
  A 50-category SVG set lives in `qpay-docs-web-v2/public/icons/`.
- Style: outline/stroke icons, consistent stroke weight, primary or text-secondary color.

## Do / Don't (universal)
- ✅ Use only the tokens above; pull live values from the repo's token file, don't hardcode drift.
- ✅ Maintain WCAG AA contrast (esp. text on `--bg-page`).
- ✅ Keep one accent (primary) per artifact; navy for depth, semantic colors only for status.
- ❌ No off-brand colors, gradients-as-brand, or non-Manrope fonts.
- ❌ No stock-photo clutter; prefer flat illustration / product UI / data viz.
- ❌ Don't mix two repos' primaries in one artifact — pick the target repo's primary.

## Stack-aware output (render target matters)
QPay web spans three generations; an artifact's *code form* depends on the repo:
- **Gen 3 (Radix/shadcn + Tailwind v4):** emit Tailwind classes + CSS vars (`docs-web-v2`, `ticket-web-v2`).
- **Gen 1/1.5 (AntD + Redux):** emit AntD components + theme tokens.
- **Standalone artifact (no repo):** emit a self-contained HTML/CSS file using the hex values above.

The per-repo `design.md` declares which target applies.
