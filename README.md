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
`DATABASE_URL` with the same password, then start the production stack:

```bash
docker compose up -d --build
```

The production compose file does not mount source directories or expose
PostgreSQL to the host. Backend migrations run before the API starts, and the
frontend is built with `next build` before serving with `next start`.
The frontend proxies same-origin `/api` requests to the internal backend
service, so `API_INTERNAL_URL` should remain `http://backend:8000` in Docker.
For direct local frontend development, set it to `http://localhost:8000`.

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

To use the HTTP adapters instead of fixtures, set `MCE_USE_LIVE=true`. US price
collection uses the `yfinance` package, while TWSE and TPEx price collection
also does not require a key. News uses Google News RSS. Provide
`ALPHA_VANTAGE_API_KEY` only when estimates and earnings events are needed.

Additional runtime settings:

- `PIPELINE_INTERVAL_HOURS`: scheduler interval, default `6`.
- `PIPELINE_RUN_ON_START`: run the fixture/live pipeline immediately at scheduler startup, default `true`.
- `SEC_CIK_MAP`: optional JSON object such as `{"AAPL":"320193"}` for SEC Company Facts.
- `SEC_USER_AGENT`: required descriptive User-Agent for SEC requests.
- `MOPS_API_URL`: optional normalized MOPS JSON endpoint.
- `TDCC_API_URL`: optional normalized TDCC JSON endpoint.
- `BENCHMARK_SYMBOLS`: JSON market-to-symbol map for relative returns, default `{"US":"SPY","TW":"0050"}`.
- `INITIAL_PRICE_BACKFILL_DAYS`: on the first live pipeline run, import this many days of daily price history (default `90`; set `0` to disable).

Useful API groups include `/changes`, `/companies/{symbol}/news`,
`/companies/{symbol}/ownership`, `/companies/{symbol}/interpretations`,
`/reports/daily`, `/watchlists`, and `/alerts`.

## Data-source coverage

`GET /data-sources` exposes the source registry, including its covered markets,
domains, cadence, access method, confidence, and enabled state. Filter it with
`?market=TW` or `?market=US`, and optionally `&domain=prices` (or
`fundamentals`, `events`, `ownership`, `macro`, and so on). This makes disabled
or not-yet-integrated feeds visible rather than silently reporting no data.

With `MCE_USE_LIVE=true` and a `SEC_CIK_MAP`, the SEC submissions API now also
records 8-K, 10-Q, 10-K, Form 4, 13F-HR, Schedule 13D, and Schedule 13G filings
as events. The normal pipeline preserves their `sec_filings` provenance.
