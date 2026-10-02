# Görev 01: Monorepo iskeleti

Durum: taslak. Sahip: Themis (Claude Code çalıştırır). Onay: Orhan.
Bağlam: `docs/architecture.md` §2-3, §6-7. Bu görev kod davranışı eklemez; sonraki dilimlerin üstüne oturacağı yapıyı kurar.

## Hedef

`git clone` + `docker compose up` + `make test` ile çalışan, boş ama bütün bir monorepo.

## Kapsam (yapılacaklar)

1. **Kök**
   - `pyproject.toml`: uv workspace; members `services/app`, `packages/*`. Python `>=3.12`. Ortak dev bağımlılıklar: ruff, mypy, pytest, pytest-asyncio.
   - `ruff.toml` (line-length 100, isort), `mypy.ini` (strict, per-package override yok), `.editorconfig`, `.gitignore` (mevcut `data/` kuralı korunur), `.env.example`.
   - `Makefile`: `install`, `lint`, `typecheck`, `test`, `up`, `down`, `migrate`.
   - `README.md`: 10 satır, nasıl ayağa kalkar.
2. **`services/app`**
   - FastAPI uygulaması, `app/main.py`; `GET /healthz` (200, `{"status":"ok"}`), `GET /readyz` (DB'ye `SELECT 1`, başarısızsa 503).
   - `app/settings.py`: pydantic-settings, `DATABASE_URL`, `LOG_LEVEL`, `ENV`. Sadece env'den.
   - `app/db.py`: SQLAlchemy 2 async engine + session factory.
   - `app/worker.py`: ikinci giriş noktası, şimdilik `while True: sleep` + log; `python -m app.worker` ile çalışır. Graceful shutdown (SIGTERM).
   - `alembic/`: başlatılmış, **tek boş migration** (`0001_init`, sadece `alembic_version`). Şema sonraki görev.
   - `Dockerfile` (multi-stage, uv, non-root), `pyproject.toml`.
   - Log: stdout, JSON (structlog ya da std logging + json formatter), `request_id` middleware.
3. **`packages/models`**: boş Pydantic paketi, `__init__.py` + bir `HealthResponse` modeli (app bunu import etsin, workspace bağı test edilsin).
4. **`infra/compose/docker-compose.yml`**: `postgres:16` (pgvector'lu image, ör. `pgvector/pgvector:pg16`), `app`, `worker`. Volume, healthcheck, `.env` okuma. `make up` ile ayağa kalkar.
5. **CI**: `.github/workflows/ci.yml`; push ve PR'da `make lint typecheck test`. Postgres service container ile `readyz` testi.
6. **Testler**: `services/app/tests/test_health.py` (`/healthz` 200; `/readyz` DB varken 200). pytest-asyncio + httpx.

## Kapsam dışı (dokunma)

- `docs/`, `AGENTS.md`, `CLAUDE.md` içerik değişikliği (sadece README'den link verilebilir).
- Şema tabloları, parser, ingest, frontend (`services/web`, `services/dashboard-web`), `services/agent`, `services/memory`, Traefik, Helm.
- `data/` altındaki hiçbir şey.

## Kabul kriterleri (Themis koşar, PR'a çıktı eklenir)

- [ ] `uv sync` temiz; `make lint`, `make typecheck`, `make test` sıfır hata.
- [ ] `make up` sonrası `curl localhost:8000/healthz` → 200, `/readyz` → 200; `docker compose logs worker` düzenli heartbeat.
- [ ] `make migrate` çalışır, `alembic_version` tablosu oluşur.
- [ ] Container non-root, image boyutu < 300 MB.
- [ ] CI yeşil.
- [ ] Repo'da secret yok (`.env` gitignored, `.env.example` var).

## Notlar Claude Code için

- Türkçe doküman, İngilizce kod/commit. Yorumlar İngilizce.
- Gereksiz soyutlama yok: repository pattern, DI container, event bus **ekleme**. Sonraki görevler ihtiyaç oldukça ekler.
- Her dosyanın bir sebebi olsun; "ileride lazım olur" diye dosya açma.
- Tek commit yeter; mesaj: `chore: monorepo scaffold (app, worker, compose, ci)`.
