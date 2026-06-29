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
Identify: has `tailwindcss` + `zustand`, no Radix UI, no `@tanstack/react-query`

- **Next.js** (13–14) + **TypeScript**
- UI: **Tailwind CSS** — no Ant Design
- State: **Zustand**
- Lint: standalone `.prettierrc` — run `prettier --write` then `eslint --fix`
- Package manager: **pnpm** (check `pnpm-lock.yaml`)

### Gen 3 — React 19 / Radix UI (EASY_SYSTEM merchant web, TICKET web)
Identify: has `@radix-ui/react-*` or `next` ≥ 15 in package.json

- **Next.js 15–16** + **React 19** + **TypeScript 5**
- UI: **Tailwind CSS 3/4** + **Radix UI** primitives (shadcn-style component library)
- State: **Zustand**
- Data fetching: **TanStack Query v5** (`@tanstack/react-query`)
- Forms: **react-hook-form** + Zod for schema validation
- Tests: **vitest**
- Lint: **ESLint flat config** (`eslint.config.mjs`) — no `.eslintrc*`, no standalone `.prettierrc`
- Package manager: **pnpm** (check `pnpm-lock.yaml`)

### Gen 1.5 — Ant Design 5 hybrid (EASY_SYSTEM admin web)
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
