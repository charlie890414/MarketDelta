# Market Changes Engine

Deterministic market-state diff engine for Taiwan and US equities.

## Run locally

```bash
cp .env.example .env
docker compose up --build
```

Backend: `http://localhost:8000/docs`  
Dashboard: `http://localhost:3001` (host port 3000 is used by another local service)

For local Python development:

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run python -m app.seed
uv run pytest
uv run uvicorn app.main:app --reload
```

The system boundary is intentionally deterministic:

```text
source → raw ingestion → normalized snapshot → diff → score → API/UI
```

LLM interpretation is deferred until the objective pipeline is stable.

To use the HTTP adapters instead of fixtures, set `MCE_USE_LIVE=true` and provide
`ALPHA_VANTAGE_API_KEY`. TWSE price collection does not require a key; Alpha
Vantage availability depends on the account's endpoint quota/entitlements.
