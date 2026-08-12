# Market Changes Engine

Deterministic market-state diff engine for Taiwan and US equities.

## Documentation

- [Architecture](docs/ARCHITECTURE.md) explains the system boundary, data flow,
  and design principles.
- [Product requirements](docs/PRD.md) records the product scope and MVP goals.
- [Database schema](docs/Database_Schema.md) describes the relational model and
  its historical design rationale.

The documents in `docs/` include both implemented behavior and forward-looking
design material. For the exact API contract, use the running service's
interactive specification at `/docs`; for the exact database shape, use the
Alembic migrations in `backend/alembic/versions/`.

## Current implementation

The application runs as a modular monolith with four Docker Compose services:
PostgreSQL, the FastAPI backend, the scheduler, and the Next.js frontend. The
pipeline supports fixtures for deterministic development and optional live
collection for prices, Taiwan market data, SEC filings, and Google News.

Collected data is retained with source lineage, normalized into historical
snapshots, compared against prior observations, and scored deterministically.
AI-powered news classification, company interpretations, and daily briefs are
optional enhancements; each has a persisted deterministic fallback and never
changes the underlying market-change calculations.

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
fallback (`POST /companies/{symbol}/interpretations/generate`). Its v2 response
also persists evidence references, confidence, and data gaps. External LLM
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
`/news/{news_id}/enrich`, `/companies/{symbol}/ownership`,
`/companies/{symbol}/interpretations`, `/companies/{symbol}/thesis`,
`/reports/daily` and `/watchlists`.

## AI research workflow

News collection retains the RSS headline but also fetches the linked article
body with `httpx`. When a publisher page cannot be extracted with ordinary HTTP,
it falls back to Camoufox. The persisted record marks the retrieval method and
status; a failed article fetch never removes the original headline observation.

Set `LLM_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL` to enable structured news
classification, grounded company interpretations, and the AI daily brief. Without
an LLM, all three retain deterministic fallbacks. AI output is constrained to
persisted changes, events, and the user's saved thesis; it does not calculate
market changes or issue trading recommendations.

## Data-source coverage

`GET /data-sources` exposes the source registry, including its covered markets,
domains, cadence, access method, confidence, and enabled state. Filter it with
`?market=TW` or `?market=US`, and optionally `&domain=prices` (or
`fundamentals`, `events`, `ownership`, `macro`, and so on). This makes disabled
or not-yet-integrated feeds visible rather than silently reporting no data.

With `MCE_USE_LIVE=true` and a `SEC_CIK_MAP`, the SEC submissions API now also
records 8-K, 10-Q, 10-K, Form 4, 13F-HR, Schedule 13D, and Schedule 13G filings
as events. The normal pipeline preserves their `sec_filings` provenance.
