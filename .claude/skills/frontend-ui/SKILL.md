---
name: frontend-ui
description: Use when writing or changing frontend code in this repo (services/dashboard-web, services/web, packages/ui, Next.js pages, React components, styling, translations). Rules for data access, design tokens, i18n and roles.
---

# frontend-ui

The frontend is a thin client of the `app` API. Bring these rules in from the first file; retrofitting them later is expensive.

## Data access: no database in the UI

- `app` is the only service that reads or writes the database (`docs/architecture.md`). Next.js code, including server components, route handlers and server actions, gets data **only** over `app`'s HTTP API.
- No ORM or DB client in any frontend package: no Prisma, Drizzle, `pg`, `postgres`, Kysely and the like.
- The frontend container gets `APP_API_URL`, never `DATABASE_URL`.
- API types are **generated** from `app`'s OpenAPI schema (every endpoint has a `response_model` for this reason). Do not hand-write request or response types. Regenerate them when the API changes, in the same PR.
- Authorization lives in the API (`require_role`). The UI may hide what a role cannot do; it never is the check.

## Design tokens and theming

- Fonts are vendored (`services/dashboard-web/src/fonts`, `next/font/local`, OFL), never fetched at build time.
- Color, typography, spacing, radius and shadow come **only** from design tokens: CSS variables, mapped into the Tailwind theme.
- No hard-coded values in components: no hex/rgb/hsl/oklch/`color-mix` colors, no inline `style` attribute, no arbitrary Tailwind values such as `bg-[#123456]` or `p-[13px]`. Tailwind's default palette and radius scale are reset in `styles.css`, so only token utilities exist.
- Shared components and tokens live in `packages/ui`. If shadcn/ui is used, it reads the same tokens.
- Tokens and the working brand name (Libria) are in `docs/design/dashboard-v0.md`; they live in `packages/ui/src/styles.css`. Changing the palette or the brand must be a token edit, not a component edit.

## i18n (decided 2026-10-03)

- i18n from day one. Default and only language for now: **Turkish (`tr`)**. Adding a language means adding a messages file, not touching components.
- Library: `next-intl` (App Router). Messages in `messages/tr.json`, keys grouped by screen (`review.queue.title`).
- Turkish routes have no locale prefix (`/inceleme`); a language added later would introduce a `[locale]` segment then. Until then the locale is the single `defaultLocale` constant in `src/i18n/locale.ts` and next-intl middleware/routing is not used.
- **No user-facing string literals in components.** Every label, button, heading, empty state and error message comes from a message key. Enforce with a lint rule where possible.
- Dates, numbers, currency and sorting use `Intl` with the active locale (`tr-TR`). Case changes are locale-aware: `toLocaleUpperCase('tr')`, never plain `toUpperCase()` (`i` must become `İ`).
- **Legal content is data, not UI text.** Decision text, statute articles, summaries, court and party names are shown as stored and are never put into message files or translated.
- Enum labels from the API are ASCII `snake_case` (`duzelterek_onama`, `genel_yazi`). The UI maps them to display text through message keys (`enums.outcome.duzelterek_onama`).
- API errors: the API returns a stable error **code**; the UI shows the translated message for that code. Do not render the API's `detail` text to users.

## Responsive (decided 2026-10-05)

Every UI works from a 360 px phone to a wide desktop; mobile is part of the work, not a follow-up.

- **Mobile first.** The base classes are the phone; `md:` (768) and `lg:` (1024) widen. Only Tailwind's default breakpoints and `pointer-coarse:`; no new breakpoint values. A value the theme lacks (safe-area padding, `dvh` height, modal inset) is defined once in `packages/ui/src/styles.css` as a token or `@utility` (`pb-safe-3`, `h-viewport`, `max-h-inset`, `w-inset`), never as an arbitrary value in a component.
- **No horizontal page scroll at 360 px.** Grid columns that hold wide content are `grid-cols-1` (a bare `grid` lets content widen its column); long stored text uses `wrap-anywhere`; a wide table scrolls inside its own container, not the page.
- **Touch targets are at least 44 px** on coarse pointers (`pointer-coarse:h-11` / `min-h-11`) for buttons, inputs, selects, tabs, nav and standalone links. The sizes live in the `packages/ui` components, once. A checkbox keeps a small box inside a 44 px label row.
- **Form controls are 16 px on a phone** (`text-base md:text-sm`) so iOS does not zoom on focus. Never disable zoom (no `maximum-scale`). The `viewport` export is in the root layout (`viewport-fit=cover`; the theme color is one constant that a test ties to the `--surface` token).
- **Table from `lg`, cards below it** (two columns from `md`, one on a phone). Both views are rendered and CSS shows one (`hidden lg:block` / `lg:hidden`); `display: none` takes the other out of the accessibility tree. Both are fed by the same formatting hook, never copies. Tests that look inside the table are scoped with `within(table)`.
- **Navigation:** side column from `lg`; below it a sticky top bar and a drawer built on the shared `Dialog` (`variant="drawer"`), which keeps the focus trap, Escape and focus return. The side column and the drawer render the same component.
- **Bars pinned to the screen bottom** are `sticky bottom-0`, pad with `pb-safe-3` for the home indicator, and the page leaves room so they cover no content at the end.
- **Dialogs** are inset from the screen edges, scroll inside (`max-h-inset`, `overscroll-contain`) and stack full-width buttons on a phone (`DialogActions`).
- **Embedded PDFs:** phone browsers mostly cannot show them, so below `md` the UI offers an "open in a new tab" link and the `iframe` stays hidden and `loading="lazy"`.
- **Every UI PR shows screenshots at 360, 768 and 1440 px** (the PR description says so), and the e2e suite has a phone project that checks for horizontal scroll.

## Structure and quality

- TypeScript strict. ESLint and the type check must pass in CI, like ruff/mypy on the Python side.
- Tests are named after the module they test (`queue-table.test.tsx`), never after the task or the review round.
- Accessibility basics: real buttons and labels, keyboard reachable actions, visible focus.

## Commands

Run from the repo root (`pnpm` is pinned by `packageManager`; Node from `.nvmrc`):

- `pnpm install --frozen-lockfile`
- `pnpm lint`, `pnpm typecheck`, `pnpm test`, `pnpm build`, `pnpm format:check`
- `pnpm openapi`: regenerate `services/dashboard-web/openapi.json` and `src/lib/api/schema.d.ts` after any API change (commit both; CI checks they are current).

Next.js here is version 16 and differs from older versions (for example `middleware.ts` is now `proxy.ts`). Before using a Next API, check the docs shipped in `services/dashboard-web/node_modules/next/dist/docs/`.
