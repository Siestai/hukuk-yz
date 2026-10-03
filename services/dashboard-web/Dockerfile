# Build context is the repo root (the pnpm workspace and packages/ui are copied into the image):
#   docker build -f services/dashboard-web/Dockerfile .
# Fonts are local files, so `next build` needs no network; the pnpm install does.
FROM node:24.21-slim AS build
ENV NEXT_TELEMETRY_DISABLED=1 CI=true
# The pnpm version comes from the `packageManager` field of the root package.json.
RUN corepack enable
WORKDIR /repo
# Manifests first: the install layer is rebuilt only when dependencies change.
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY services/dashboard-web/package.json services/dashboard-web/package.json
COPY packages/ui/package.json packages/ui/package.json
RUN --mount=type=cache,target=/root/.local/share/pnpm/store \
    pnpm install --frozen-lockfile --filter "dashboard-web..."
COPY services/dashboard-web services/dashboard-web
COPY packages/ui packages/ui
# Not `pnpm build`: its copy step is for running outside Docker; the runtime stage copies
# `.next/static` and `public` itself.
RUN pnpm --filter dashboard-web exec next build

FROM node:24.21-slim AS runtime
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
RUN useradd --system --uid 10001 --no-create-home web
WORKDIR /app
# outputFileTracingRoot is the repo root, so server.js sits under services/dashboard-web/ in the
# standalone directory; `.next/static` and `public` go next to it (standalone leaves them out).
COPY --from=build --chown=web:web /repo/services/dashboard-web/.next/standalone ./
COPY --from=build --chown=web:web /repo/services/dashboard-web/.next/static services/dashboard-web/.next/static
COPY --from=build --chown=web:web /repo/services/dashboard-web/public services/dashboard-web/public
USER web
EXPOSE 3000
# /healthz needs neither a session nor the API. node:24.21-slim has no curl.
HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=5 \
    CMD ["node", "-e", "fetch('http://127.0.0.1:3000/healthz').then(r => process.exit(r.ok ? 0 : 1), () => process.exit(1))"]
CMD ["node", "services/dashboard-web/server.js"]
