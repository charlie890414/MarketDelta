# Market Changes Engine

Deterministic market-state diff engine for Taiwan and US equities.

## Run locally

```bash
cp .env.example .env
docker compose -f compose.dev.yml up --build
```

Backend: `http://localhost:8000/docs`  
Dashboard: `http://localhost:3001` (host port 3000 is used by another local service)

## Run in production

Copy `.env.example` to `.env`, set a strong `POSTGRES_PASSWORD`, update
`DATABASE_URL` with the same password, and set the public
`NEXT_PUBLIC_API_URL`, then start the production stack:

```bash
docker compose up -d --build
```

The production compose file does not mount source directories or expose
PostgreSQL to the host. Backend migrations run before the API starts, and the
frontend is built with `next build` before serving with `next start`.

For local Python development:

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run python -m app.seed
uv run pytest
uv run uvicorn app.main:app --reload
```

The default test suite is database-independent. With PostgreSQL running, include
the pipeline idempotency check with `MCE_INTEGRATION=1 uv run pytest -m integration`.

The system boundary is intentionally deterministic:

```text
source → raw ingestion → normalized snapshot → diff → score → API/UI
```

The current interpretation endpoint provides a persisted structured deterministic
fallback (`POST /companies/{symbol}/interpretations/generate`). External LLM
providers can be added without changing objective change fields.

To use the HTTP adapters instead of fixtures, set `MCE_USE_LIVE=true` and provide
`ALPHA_VANTAGE_API_KEY` for US estimates, news, and earnings events. TWSE and
TPEx price collection does not require a key; Alpha Vantage availability depends
on the account's endpoint quota/entitlements.

Additional runtime settings:

- `PIPELINE_INTERVAL_HOURS`: scheduler interval, default `6`.
- `PIPELINE_RUN_ON_START`: run the fixture/live pipeline immediately at scheduler startup, default `true`.
- `ALERT_WEBHOOK_URL`: optional JSON webhook for newly evaluated alert deliveries.
- `ALERT_WEBHOOK_RETRIES`: webhook attempts, default `3`.
- `ALERT_WEBHOOK_BACKOFF_SECONDS`: exponential backoff base delay, default `1`.
- `SEC_CIK_MAP`: optional JSON object such as `{"AAPL":"320193"}` for SEC Company Facts.
- `SEC_USER_AGENT`: required descriptive User-Agent for SEC requests.
- `MOPS_API_URL`: optional normalized MOPS JSON endpoint.
- `TDCC_API_URL`: optional normalized TDCC JSON endpoint.
- `BENCHMARK_SYMBOLS`: JSON market-to-symbol map for relative returns, default `{"US":"SPY","TW":"0050"}`.

Useful API groups include `/changes`, `/companies/{symbol}/news`,
`/companies/{symbol}/ownership`, `/companies/{symbol}/interpretations`,
`/reports/daily`, `/watchlists`, and `/alerts`.
