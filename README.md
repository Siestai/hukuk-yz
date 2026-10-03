# hukuk-agent

Türk iş ve sosyal güvenlik hukuku için yapay zekâ araştırma asistanı. Bağlam: [AGENTS.md](AGENTS.md), mimari: [docs/architecture.md](docs/architecture.md), kararlar: [docs/decisions.md](docs/decisions.md).

Ayağa kaldırma (uv ve Docker gerekir):

1. `git clone` ve repo köküne geç.
2. `make install` — bağımlılıkları kurar (`uv sync`).
3. `make up` — `.env` yoksa `.env.example`'dan oluşturur; postgres, app ve worker'ı başlatır.
4. `make migrate` — Alembic migration'larını uygular.
5. `curl localhost:8000/healthz` ve `curl localhost:8000/readyz` — 200 dönmeli.
6. `make lint typecheck test` — Postgres testleri için `DATABASE_URL` tanımlayın, yoksa atlanır.
7. `make down` — durdurur.

Frontend (Node 24 ve pnpm gerekir): `pnpm install`, sonra `pnpm lint typecheck test build format:check` ayrı ayrı; API değişince `pnpm openapi`.
