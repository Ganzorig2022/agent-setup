# QPay Frontend — Standing Facts

## Three Frontend Generations

### Gen 1 — Ant Design / Redux (older QPay projects)
Identify: has `antd` ≤ 4.x + `redux` in package.json

- **Next.js 12** + **React 17** + **TypeScript 4**
- UI: **Ant Design 4** + `@ant-design/icons`
- State: **Redux** + `redux-thunk` + `redux-persist`
- Forms: **Formik** + **Yup** (some forms use `react-hook-form`)
- Data fetching: **SWR** + `axios`
- Realtime: `socket.io-client` 2.x
- Styling: `styled-components`
- Lint: standalone `.prettierrc` — run `prettier --write` then `eslint --fix`
- Package manager: **yarn** (check `yarn.lock`)

### Gen 2 — Tailwind / Zustand (mid-gen QPay projects)
Identify: has `tailwindcss` + `zustand`, no Radix/Base UI, no `@tanstack/react-query`

- **Next.js** (13–14) + **TypeScript**
- UI: **Tailwind CSS** — no Ant Design
- State: **Zustand**
- Lint: standalone `.prettierrc` — run `prettier --write` then `eslint --fix`
- Package manager: **pnpm** (check `pnpm-lock.yaml`)

### Gen 3 — React 19 / shadcn primitives (SYSTEM_EASY merchant web, SYSTEM_TICKET web)
Identify: has `@radix-ui/react-*` **or** `@base-ui/react`, or `next` ≥ 15 in package.json

- **Next.js 15–16** + **React 19** + **TypeScript 5**
- UI: **Tailwind CSS 3/4** + shadcn-style components over **one of two primitive libraries** —
  **Radix UI** (older repos) or **Base UI** (`@base-ui/react`, shadcn's default since Jul 2026).
  **package.json does NOT reliably tell you which** — read `components.json` (`style: base-*`
  means Base UI) or grep an actual `src/components/ui/*.tsx` import. Live example: in
  `qpay-docs-web-v2` all 14 UI components import `@base-ui/react` while package.json still
  lists 8 stale `@radix-ui/*` deps — trusting package.json there puts Radix components into a
  pure Base UI codebase. `qpay-deps-web` is Base-UI-only.
- State: **Zustand**
- Data fetching: **TanStack Query v5** (`@tanstack/react-query`)
- Forms: **react-hook-form** + Zod for schema validation
- Tests: **vitest**
- Lint: **ESLint flat config** (`eslint.config.mjs`) — no `.eslintrc*`, no standalone `.prettierrc`
- Package manager: **pnpm** (check `pnpm-lock.yaml`)

### Gen 1.5 — Ant Design 5 hybrid (SYSTEM_EASY admin web)
Identify: has `antd` ≥ 5.x + `redux` in package.json

- **Next.js 12** + **React 18** + **TypeScript 4**
- UI: **Ant Design 5** (token-based theming, not 4.x)
- State: **Redux** + `redux-thunk`
- Data fetching: **TanStack Query v5**
- Forms: **react-hook-form**
- Package manager: **npm** (check `package-lock.json`)

## Shared Frontend Conventions
- Next.js `pages/` directory router (not App Router) for all current projects
- API routes live in `pages/api/`
- TypeScript interfaces for API shapes — keep in `types/` or co-located `*.types.ts`
- Never import from `antd/lib/*` — use top-level named imports only
- Do not add Firebase to Gen 2/Gen 3 projects without confirmation

## Lint / Format Quick Reference
| Generation | Prettier | ESLint config file | Run order |
|------------|----------|--------------------|-----------|
| Gen 1 / 1.5 | standalone `.prettierrc` | `.eslintrc*` | prettier first, then eslint |
| Gen 2 | standalone `.prettierrc` | `.eslintrc*` | prettier first, then eslint |
| Gen 3 | none | `eslint.config.mjs` | eslint only |

## Critical Rules (executors commonly get these wrong)
- **Pin the package manager — `packageManager` in `package.json`.** Unpinned, `corepack enable` in a Dockerfile resolves the *latest* pnpm at container run time, so an untouched repo breaks when the registry moves. pnpm ≥11 also runs an implicit install before `pnpm run <script>` (`verify-deps-before-run` defaults to `install`), so `CMD ["pnpm","start"]` fails `EACCES` in a non-root app dir (qpay-vendor-web-v2 pods, exit 243, Jul 2026 — code untouched since Dec). Fix: pin `packageManager`, Next `output: "standalone"`, start with `node server.js` — no package manager at runtime. NOT a lockfile problem: pnpm 11 reads `lockfileVersion: '9.0'` fine.
- **Never mutate Redux state directly** — always use action creators / reducers
- **Never mutate Zustand state directly** — use `set()` function
- **AntD Gen 1: top-level imports only** — `import { Button } from 'antd'`, never `antd/lib/button`
- **Gen 3: TanStack Query v5 API** — `useQuery({ queryKey, queryFn })` not `useQuery(key, fn)` (v3 API)
- **Hydration errors** — no `Date.now()`, `Math.random()`, or browser-only APIs at render time
- **SWR (Gen 1)** — for data fetching; use `axios` for mutations, not `fetch`
- **Do not mix generations** — do not import Radix into Gen 1/2 or AntD into Gen 2/3
- **Do not mix primitives inside Gen 3** — a repo is Radix *or* Base UI; adding a component built
  on the other one ships a second primitive library and a second set of a11y/portal semantics.
  Confirm which one the repo uses (see Gen 3 above) before running `npx shadcn add` or hand-writing
  a component; `components.json` `style` is the authority, package.json is not.
- **Gen 3 `next/image` on Next 16** — `images.qualities` defaults to `[75]`; any other `quality` value warns at runtime. SVGs are not optimized at all, so `quality` on an SVG is a no-op — drop the prop rather than widening the config. `fill` also needs a positioned parent (`relative`).
- **`next/image` + Tailwind preflight** — preflight forces `img { height: auto }`, so `width`/`height` props that disagree with the file's intrinsic ratio trigger "width or height modified" warnings. Set them to the real ratio (read the SVG's own `width`/`height`); rendered size does not change.
- **`next/image` `remotePatterns` — never `hostname: '*'`** — a wildcard turns `/_next/image` into an open proxy that fetches and re-serves any URL, and is the surface for the recurring Image Optimization DoS advisories. If every `src` is a local `/public` path, use `[]`; otherwise list specific hosts. Note Radix `AvatarImage` renders a plain `<img>`, so remote avatars bypass the optimizer and are unaffected by this setting either way.
- **React 19 types dropped the global `JSX` namespace** — `@types/react` ≥ 19.2.17 removes it, so a bare `JSX.Element` fails typecheck with "Cannot find namespace 'JSX'". Use `React.JSX.Element` (needs `import React` / `import type React from 'react'`). Bites on an in-range `@types/react` **patch** bump, not just majors.
- **Radix `Avatar` fails silently** — `AvatarFallback` renders on *any* image load/decode failure, so a wrong URL that returns HTML (a redirect to a console/login page) looks identical to "no avatar set". Check the response content-type before suspecting the component or `next/image` config.
- **Radix controlled/uncontrolled** — `open={a || map[key]}` yields `undefined` when the key is unset, which Radix reads as uncontrolled, then flips to controlled. Coerce with `Boolean()`.

## Design System (qcore) & Brand Specs
- **qcore is the canonical QPay web design system.** Source of truth = `qpay-docs-web-v2/src/styles/qcore-tokens.css`. Brand: primary `#004fff`, secondary navy `#002148`, font **Manrope**, semantics success `#00c950` / warning `#f0b100` / danger `#fb2c36`; ships light + dark themes.
- The `design-tokens.tokens.json` files in `qpay-deps-web` & `qpay-qpaymn-web` are Figma DTCG **export snapshots with different schemas** — not the live system; prefer qcore.
- **`qpay-ticket-web-v2` deliberately overrides primary to indigo `#615fff`** (in its own `src/styles/globals.css`) while sharing Manrope + navy secondary + success/danger scales. Do not "correct" it to QPay blue.
- **Brand-spec convention:** repos carry a thin per-repo `design.md` (states only its primary + render target + token-file path) inheriting a global brand core at `~/.claude/qpay-context/design.md`. Present in `qpay-docs-web-v2`, `qpay-ticket-web-v2`, and `qpay-vendor-web-v2` (navy `#202754` + **Nunito**, not qcore blue/Manrope — another deliberate divergence; do not "correct" it). Read the per-repo `design.md` before generating any branded artifact for that repo.
