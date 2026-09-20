# KhataBabu API (backbone)

FastAPI + PostgreSQL foundation with optional Redis and Kafka, fully driven by environment variables.

**Python:** 3.9+ (3.11+ recommended for production).

## Layout

```
app/
  main.py              # App factory
  core/                # Config, logging, lifespan
  api/v1/platform/     # Super-admin auth + owner onboarding (not owner/POS app)
  db/                  # Async SQLAlchemy engine & sessions
  integrations/        # Redis, Kafka (toggle via env)
  middleware/          # Request ID + access logs
  models/              # ORM models (future)
alembic/               # DB migrations
```

## Quick start (local)

```bash
cd khataBabu
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
docker compose up -d postgres   # optional: redis, redpanda
alembic upgrade head
python -m app.scripts.create_platform_admin
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- API docs: http://localhost:8000/docs  
- Liveness: `GET /api/v1/health/live`  
- Readiness: `GET /api/v1/health/ready` (checks Postgres; Redis/Kafka when enabled)

### Platform super-admin (internal onboarding)

Browser-only console uses `/api/v1/platform/*` (not exposed in owner/POS apps).

1. `POST /api/v1/platform/auth/login` — username + password → Bearer `access_token` (mobile OTP step will be added later)
2. `POST /api/v1/platform/onboarding/tenants` — create business + outlet + owner (returns **one-time** owner username + temporary password)
3. `GET /api/v1/platform/onboarding/tenants` — list onboarded tenants
4. `PATCH /api/v1/platform/onboarding/tenants/{business_id}/status` — draft / active / suspended

Security: Argon2 password hashes, JWT audience `khatababu-platform`, lockout after failed logins, audit log for onboarding actions. Owner passwords are never stored in plain text; temporary password is shown only in the create-tenant response once.

Suspending a tenant requires `confirm_username` + `confirm_password` in the PATCH body.

### Owner app (separate from platform)

- `POST /api/v1/owner/auth/login` — owner JWT (`aud=khatababu-owner`, default **24h**)
- `GET /api/v1/owner/auth/me`, `POST /api/v1/owner/auth/change-password`
- `GET /api/v1/owner/outlets` — outlets for owner's business
- Areas/tables: `/api/v1/owner/outlets/{outlet_id}/areas`, `.../areas/{area_id}/tables`, etc.
- Menu: `/api/v1/owner/outlets/{outlet_id}/menu/categories` and `.../items`
- **POS / billing** (Pet Pooja–style flow, persisted in Postgres):

  | Step | Method | Path |
  |------|--------|------|
  | Floor (occupied tables) | `GET` | `/api/v1/owner/outlets/{outlet_id}/pos/floor` |
  | Open order on table | `POST` | `/api/v1/owner/outlets/{outlet_id}/pos/orders` |
  | Add items | `POST` | `.../pos/orders/{order_id}/lines` |
  | Send KOT | `POST` | `.../pos/orders/{order_id}/kot` |
  | Bill / tax / discount preview | `POST` | `.../pos/orders/{order_id}/bill` |
  | Settle (mixed payments) | `POST` | `.../pos/bills/{bill_id}/settle` |

  Also: list/get orders, edit/remove lines (before KOT), cancel line, transfer table, cancel order, list KOTs. Daily order/KOT/bill numbers per outlet.

Suspended businesses cannot owner-login.

## Configuration

Point the app at any environment by changing `.env` or process env — no code changes.

| Concern | Variables |
|--------|-----------|
| Postgres | `DATABASE_URL` **or** `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` |
| Pool / perf | `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT`, `DB_POOL_RECYCLE` |
| Redis | `REDIS_ENABLED=true`, `REDIS_URL` |
| Kafka | `KAFKA_ENABLED=true`, `KAFKA_BOOTSTRAP_SERVERS` (e.g. `localhost:19092` with compose Redpanda) |
| Logging | `LOG_LEVEL`, `LOG_FILE=logs/kblogs.log` (single file for all backend logs), `LOG_JSON=true` in production, `LOG_TO_CONSOLE=false` to file-only |

Example production database URL:

```env
DATABASE_URL=postgresql://user:pass@db.example.com:5432/khatababu?sslmode=require
```

## Migrations

```bash
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

## Scaling notes

- Run multiple Uvicorn workers or Gunicorn + Uvicorn workers behind a load balancer.
- Tune `DB_POOL_SIZE` × workers so total connections stay within Postgres limits.
- Enable `LOG_JSON` and ship logs to your aggregator; use `X-Request-ID` for tracing.
- Turn on Redis for caching/sessions and Kafka for async domain events when modules need them.

## Docker

```bash
docker compose up -d
docker build -t khatababu-api .
```
