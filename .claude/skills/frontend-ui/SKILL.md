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

- Color, typography, spacing, radius and shadow come **only** from design tokens: CSS variables, mapped into the Tailwind theme.
- No hard-coded values in components: no hex/rgb colors, no arbitrary Tailwind values such as `bg-[#123456]` or `p-[13px]`.
- Shared components and tokens live in `packages/ui`. If shadcn/ui is used, it reads the same tokens.
- Tokens and the working brand name (Libria) are in `docs/design/dashboard-v0.md`; they live in `packages/ui/src/styles.css`. Changing the palette or the brand must be a token edit, not a component edit.

## i18n (decided 2026-10-03)

- i18n from day one. Default and only language for now: **Turkish (`tr`)**. Adding a language means adding a messages file, not touching components.
- Library: `next-intl` (App Router). Messages in `messages/tr.json`, keys grouped by screen (`review.queue.title`).
- Turkish routes have no locale prefix (`/inceleme`); other languages would get one (`/en/...`).
- **No user-facing string literals in components.** Every label, button, heading, empty state and error message comes from a message key. Enforce with a lint rule where possible.
- Dates, numbers, currency and sorting use `Intl` with the active locale (`tr-TR`). Case changes are locale-aware: `toLocaleUpperCase('tr')`, never plain `toUpperCase()` (`i` must become `İ`).
- **Legal content is data, not UI text.** Decision text, statute articles, summaries, court and party names are shown as stored and are never put into message files or translated.
- Enum labels from the API are ASCII `snake_case` (`duzelterek_onama`, `genel_yazi`). The UI maps them to display text through message keys (`enums.outcome.duzelterek_onama`).
- API errors: the API returns a stable error **code**; the UI shows the translated message for that code. Do not render the API's `detail` text to users.

## Structure and quality

- TypeScript strict. ESLint and the type check must pass in CI, like ruff/mypy on the Python side.
- Tests are named after the module they test (`queue-table.test.tsx`), never after the task or the review round.
- Accessibility basics: real buttons and labels, keyboard reachable actions, visible focus.

## Commands

Run from the repo root (`pnpm` is pinned by `packageManager`; Node from `.nvmrc`):

- `pnpm install --frozen-lockfile`
- `pnpm lint`, `pnpm typecheck`, `pnpm test`, `pnpm build`, `pnpm format:check`
- `pnpm openapi`: regenerate `services/dashboard-web/openapi.json` and `src/lib/api/schema.d.ts` after any API change (commit both; CI checks they are current).
