# Market Changes Engine — Architecture



## 1. Purpose



Market Changes Engine is a market-state change detection system for US and Taiwan equities.



Its primary job is not to provide another market dashboard. Its job is to answer:



> What changed, how important is it, and what should be watched next?



The system periodically collects market and company data, preserves historical snapshots, detects changes between states, scores their significance, and optionally asks an LLM to explain the already-computed changes.



The core architecture principle is:



> Deterministic data and change detection first. AI interpretation second.



The system must remain useful even when the LLM layer is unavailable.



---



## 2. Product Boundary



### In scope



- US equities: NYSE / NASDAQ

- Taiwan equities: TWSE / TPEx

- Watchlists and tracked instruments

- Daily / periodic data collection

- Price snapshots

- Fundamental snapshots

- US earnings estimates

- Taiwan institutional flows

- Taiwan ownership distribution

- Corporate and market events

- News metadata

- Historical snapshots

- Change detection

- Significance scoring

- Daily change feeds

- AI-generated interpretations

- Data quality and source lineage



### Out of scope for MVP



- Broker integration

- Order execution

- Tick data

- Level 2 order book

- High-frequency trading

- Full portfolio accounting

- Tax-lot accounting

- Full backtesting platform

- Automatic buy/sell execution

- Automatic trading recommendations

- Real-time streaming architecture

- Kafka / distributed event bus

- Elasticsearch

- Dedicated time-series database

- Multi-tenant SaaS billing



---



## 3. Architecture Principles



### 3.1 Preserve raw source data



Every ingestion should retain the original provider response whenever practical.



This allows:



- parser fixes without re-downloading data;

- reproducible normalization;

- source auditing;

- provider migration;

- data-quality debugging.



### 3.2 Do not overwrite historical state



Snapshots are append-oriented.



If a value changes from 6.21 to 6.48, the system stores both observations.



The system must be able to answer:



- what is the current value?

- what was the value yesterday?

- what was the value 30 days ago?

- when did the estimate change?

- what source produced the change?



### 3.3 Deterministic calculations do not depend on LLMs



The following must be pure application logic:



- normalization;

- percentage changes;

- rolling returns;

- historical rarity;

- significance score;

- thresholding;

- change classification;

- freshness;

- source-confidence scoring.



LLMs may:



- summarize;

- explain;

- connect signals;

- identify contradictions;

- suggest items to monitor;

- assign an explicitly labeled thesis-impact interpretation.



### 3.4 Provider implementations are replaceable



Provider-specific parsing must not leak into the domain layer.



The domain layer should work with normalized models such as:



```python

MetricObservation(

    instrument_id=123,

    category="expectation",

    metric="eps_estimate",

    period="FY27",

    value=6.48,

    observed_at=...,

)

```



instead of provider-specific payload structures.



### 3.5 Modular monolith first



The MVP is one codebase with clear modules, not microservices.



Runtime processes may be separated for reliability, but business logic remains in one repository.



Recommended runtime units:



- `frontend`

- `api`

- `scheduler`

- `postgres`



### 3.6 Idempotent jobs



All scheduled collectors and processors should be safe to rerun.



A retry must not create duplicate logical observations or duplicate changes.



### 3.7 Source lineage is mandatory



Every normalized observation should be traceable back to:



- source provider;

- retrieval time;

- source data date;

- raw ingestion record where applicable.



---



## 4. Technology Stack



### Backend



- Python

- FastAPI

- Pydantic

- SQLAlchemy 2

- psycopg

- Alembic

- HTTPX

- lxml / BeautifulSoup

- Playwright only as a fallback

- APScheduler

- pytest

- Ruff

- uv



### Database



- PostgreSQL

- JSONB for raw provider payloads

- Standard relational tables for normalized data



### Frontend



- Next.js

- TypeScript

- App Router

- Tailwind CSS

- shadcn/ui

- TanStack Query

- Recharts

- `openapi-typescript`

- `openapi-fetch`



### Deployment



Local:



```text

Docker Compose

```



Production:



```text

Docker images

→ k3s or standard Docker runtime

```



No Redis, Celery, Kafka, TimescaleDB, or Elasticsearch in MVP.



---



## 5. High-Level Architecture



```text

                    ┌─────────────────────┐

                    │   External Sources  │

                    │                     │

                    │ TWSE / TPEx / MOPS  │

                    │ TDCC / SEC / AV     │

                    │ GDELT / FRED / ...  │

                    └──────────┬──────────┘

                               │

                               ▼

                    ┌─────────────────────┐

                    │      Collectors     │

                    │ HTTPX / HTML / CSV  │

                    │ Browser fallback    │

                    └──────────┬──────────┘

                               │

                               ▼

                    ┌─────────────────────┐

                    │    Raw Ingestion    │

                    │ JSONB + metadata    │

                    └──────────┬──────────┘

                               │

                               ▼

                    ┌─────────────────────┐

                    │    Normalization    │

                    │ provider → domain   │

                    └──────────┬──────────┘

                               │

                               ▼

                    ┌─────────────────────┐

                    │  Snapshot Storage   │

                    │ normalized history  │

                    └──────────┬──────────┘

                               │

                               ▼

                    ┌─────────────────────┐

                    │  Change Detection   │

                    │ previous vs current │

                    └──────────┬──────────┘

                               │

                               ▼

                    ┌─────────────────────┐

                    │ Significance Score  │

                    │ deterministic       │

                    └──────────┬──────────┘

                               │

                ┌──────────────┴──────────────┐

                │                             │

                ▼                             ▼

      ┌──────────────────┐          ┌──────────────────┐

      │ FastAPI / UI     │          │ AI Interpreter   │

      │ objective change │          │ optional layer   │

      └──────────────────┘          └─────────┬────────┘

                                             │

                                             ▼

                                   ┌──────────────────┐

                                   │ Interpretation   │

                                   │ summary / watch  │

                                   └──────────────────┘

```



---



## 6. Repository Layout



```text

market-changes-engine/

│

├── backend/

│   ├── pyproject.toml

│   ├── uv.lock

│   ├── alembic.ini

│   │

│   ├── app/

│   │   ├── main.py

│   │   ├── config.py

│   │   │

│   │   ├── api/

│   │   │   ├── deps.py

│   │   │   ├── changes.py

│   │   │   ├── companies.py

│   │   │   ├── watchlists.py

│   │   │   ├── events.py

│   │   │   └── jobs.py

│   │   │

│   │   ├── db/

│   │   │   ├── session.py

│   │   │   ├── base.py

│   │   │   ├── models/

│   │   │   └── repositories/

│   │   │

│   │   ├── domain/

│   │   │   ├── observations.py

│   │   │   ├── changes.py

│   │   │   ├── scoring.py

│   │   │   └── enums.py

│   │   │

│   │   ├── providers/

│   │   │   ├── base.py

│   │   │   ├── twse/

│   │   │   ├── tpex/

│   │   │   ├── mops/

│   │   │   ├── tdcc/

│   │   │   ├── sec/

│   │   │   ├── alphavantage/

│   │   │   ├── gdelt/

│   │   │   └── fred/

│   │   │

│   │   ├── normalization/

│   │   │   ├── common.py

│   │   │   └── validators.py

│   │   │

│   │   ├── changes/

│   │   │   ├── detector.py

│   │   │   ├── comparator.py

│   │   │   └── rules/

│   │   │       ├── price.py

│   │   │       ├── fundamentals.py

│   │   │       ├── estimates.py

│   │   │       ├── flow.py

│   │   │       └── ownership.py

│   │   │

│   │   ├── scoring/

│   │   │   ├── scorer.py

│   │   │   ├── magnitude.py

│   │   │   ├── rarity.py

│   │   │   ├── relevance.py

│   │   │   ├── freshness.py

│   │   │   └── source_quality.py

│   │   │

│   │   ├── ai/

│   │   │   ├── provider.py

│   │   │   ├── schemas.py

│   │   │   ├── prompts.py

│   │   │   └── interpreter.py

│   │   │

│   │   ├── jobs/

│   │   │   ├── collect_prices.py

│   │   │   ├── collect_fundamentals.py

│   │   │   ├── collect_estimates.py

│   │   │   ├── collect_flows.py

│   │   │   ├── collect_events.py

│   │   │   ├── detect_changes.py

│   │   │   └── interpret_changes.py

│   │   │

│   │   └── scheduler/

│   │       ├── main.py

│   │       └── schedules.py

│   │

│   ├── migrations/

│   └── tests/

│       ├── unit/

│       ├── integration/

│       └── fixtures/

│

├── frontend/

│   ├── app/

│   │   ├── dashboard/

│   │   ├── company/[symbol]/

│   │   ├── watchlist/

│   │   ├── calendar/

│   │   └── settings/

│   ├── components/

│   ├── lib/

│   │   ├── api/

│   │   └── generated/

│   └── package.json

│

├── infra/

│   ├── docker/

│   └── k8s/

│

├── ARCHITECTURE.md

├── DATABASE_SCHEMA.md

├── docker-compose.yml

└── README.md

```



---



## 7. Module Responsibilities



## 7.1 Providers



A provider knows how to communicate with one external data source.



Responsibilities:



- HTTP requests;

- authentication;

- rate-limit handling;

- pagination;

- response decoding;

- retrieval metadata;

- basic provider-specific validation.



A provider should not:



- calculate significance scores;

- compare historical values;

- decide whether a change matters;

- call the LLM;

- directly format UI models.



Suggested interface:



```python

from typing import Protocol



class Provider(Protocol):

    name: str



    async def fetch(self, request: object) -> object:

        ...

```



Provider outputs should be stored in `raw_ingestions` before normalization when practical.



---



## 7.2 Raw ingestion layer



The raw layer preserves source payloads.



Responsibilities:



- retain original payload;

- calculate content hash;

- record HTTP/source metadata;

- make retries auditable;

- support re-normalization.



Raw data is not directly exposed to normal dashboard endpoints.



---



## 7.3 Normalization layer



Converts provider-specific payloads into stable domain models.



Examples:



```text

TWSE price payload

→ PriceObservation



Alpha Vantage estimates payload

→ EstimateObservation



TDCC distribution payload

→ OwnershipObservation

```



Normalization should handle:



- currencies;

- units;

- percentages;

- fiscal periods;

- timezone normalization;

- symbol mapping;

- missing values;

- duplicate provider records.



---



## 7.4 Snapshot layer



Normalized snapshots are the system of record for market state.



Each domain gets a dedicated table.



Examples:



- `price_daily`

- `fundamentals`

- `estimate_snapshots`

- `flow_daily`

- `ownership_snapshots`



The latest snapshot is derived from history rather than maintained as a separate mutable object unless later profiling proves this necessary.



---



## 7.5 Change detection



Change detection compares current observations with a defined baseline.



Supported baseline types:



- previous observation;

- 1 day;

- 5 trading days;

- 20 trading days;

- 30 calendar days;

- 90 calendar days;

- prior quarter;

- prior year;

- configurable domain-specific comparison.



Output:



```python

ChangeCandidate(

    instrument_id=...,

    category="expectation",

    metric="eps_estimate",

    period="FY27",

    previous_value=6.21,

    current_value=6.48,

    percentage_change=4.35,

    lookback="30d",

)

```



Change detection must be deterministic and independently testable.



---



## 7.6 Significance scoring



Every material change receives a score from 0 to 100.



Recommended dimensions:



```text

Magnitude            30%

Historical rarity    20%

Fundamental relevance 25%

Freshness            15%

Source quality       10%

```



Weights should be configuration-driven and may differ by domain.



Example:



```yaml

expectation:

  magnitude: 0.30

  rarity: 0.20

  relevance: 0.25

  freshness: 0.15

  source_quality: 0.10

```



Severity mapping:



```text

0–29   Noise

30–49  Minor

50–69  Notable

70–84  Important

85–100 Critical

```



The UI default filter should generally hide scores below 50.



---



## 7.7 AI interpretation



AI receives structured changes, not raw market payloads.



Input example:



```json

{

  "instrument": "AMD",

  "changes": [

    {

      "metric": "FY27 EPS",

      "previous": 6.21,

      "current": 6.48,

      "change_pct": 4.35,

      "score": 91

    }

  ]

}

```



Structured output:



```json

{

  "summary": "...",

  "why_it_matters": "...",

  "supporting_signals": ["..."],

  "contradictions": ["..."],

  "watch_next": ["..."],

  "thesis_impact": "strengthened"

}

```



The LLM must not be allowed to modify objective numeric fields.



Every interpretation stores:



- provider/model;

- prompt version;

- generation timestamp;

- source change IDs.



---



## 8. Data Flow



A typical scheduled collection run:



```text

1. Scheduler starts collect_estimates

2. job_runs row created

3. Provider fetches remote source

4. raw_ingestions row saved

5. Normalizer converts payload

6. normalized snapshots upserted idempotently

7. job_runs updated

8. change detector compares new snapshots

9. changes persisted

10. scorer assigns significance

11. high-value changes optionally queued for AI interpretation

12. dashboard reads changes from API

```



---



## 9. Scheduling Model



MVP scheduling should use APScheduler in a dedicated runtime process.



Do not embed the scheduler in every FastAPI worker.



Suggested categories:



### Taiwan



```text

Post-close

- daily prices



Later afternoon

- institutional flow



Evening

- announcements

- monthly revenue

- ownership updates when available

```



### US



```text

Post-close

- daily prices



After-hours

- earnings / filings

- estimate refresh

- news refresh

```



Exact schedules belong in configuration, not business logic.



---



## 10. Runtime Processes



### `frontend`



Responsibilities:



- UI rendering;

- filters;

- navigation;

- charts;

- user interaction.



### `api`



Responsibilities:



- REST API;

- validation;

- watchlist CRUD;

- reading changes/snapshots/events;

- admin/status endpoints.



### `scheduler`



Responsibilities:



- scheduled collectors;

- normalization;

- change detection;

- scoring;

- AI interpretation jobs.



### `postgres`



Responsibilities:



- raw source storage;

- normalized snapshots;

- changes;

- job status;

- AI interpretation;

- configuration/reference data.



---



## 11. API Boundaries



Minimum endpoints:



```http

GET  /health

GET  /changes

GET  /changes/{change_id}



GET  /companies

GET  /companies/{symbol}

GET  /companies/{symbol}/changes

GET  /companies/{symbol}/history

GET  /companies/{symbol}/events



GET  /watchlists

POST /watchlists

GET  /watchlists/{watchlist_id}

POST /watchlists/{watchlist_id}/items

DELETE /watchlists/{watchlist_id}/items/{instrument_id}



GET  /events

GET  /jobs

GET  /jobs/{job_run_id}

```



Example:



```http

GET /changes?hours=24&min_score=70&market=US

```



FastAPI OpenAPI output is the source of truth for the frontend client.



Do not hand-maintain duplicated TypeScript API types.



---



## 12. Error Handling



### Provider failures



Record:



- provider;

- endpoint;

- timestamp;

- HTTP status;

- error category;

- retry count.



A provider failure must not break unrelated providers.



### Normalization failures



Do not silently discard malformed data.



Record enough context to reproduce the failure.



### Partial jobs



`job_runs.status` should support:



- `running`

- `success`

- `partial`

- `failed`

- `skipped`



A run is `partial` if some symbols succeed while others fail.



---



## 13. Idempotency



Recommended unique keys should prevent duplicate logical observations.



Examples:



```text

price_daily:

(instrument_id, trading_date)



estimate_snapshots:

(instrument_id, metric, fiscal_period, observed_at, source_id)



flow_daily:

(instrument_id, trading_date, flow_type, source_id)

```



Collectors should use deterministic upserts where the source has stable identity.



---



## 14. Time Handling



All backend timestamps:



```text

TIMESTAMPTZ in PostgreSQL

UTC internally

```



Market dates remain explicit local-market dates where appropriate.



Examples:



- `trading_date`: `DATE`

- `published_at`: `TIMESTAMPTZ`

- `fetched_at`: `TIMESTAMPTZ`



Do not infer trading dates from UTC timestamps in application code when the source already provides the market date.



---



## 15. Configuration



Environment variables:



```text

DATABASE_URL

ALPHA_VANTAGE_API_KEY

LLM_BASE_URL

LLM_API_KEY

LLM_MODEL

LOG_LEVEL

ENVIRONMENT

```



Non-secret configuration:



```text

config/

  scoring.yaml

  schedules.yaml

  providers.yaml

```



Provider enable/disable state should eventually be stored in DB or config, but MVP can use configuration files.



---



## 16. Observability



Minimum logging fields:



```text

timestamp

level

job_run_id

provider

instrument

operation

duration_ms

status

```



Recommended metrics later:



- collector success rate;

- provider latency;

- rows ingested;

- normalization failure count;

- number of changes detected;

- score distribution;

- stale-data count;

- LLM generation failure rate.



MVP does not require a dedicated telemetry platform if structured logs are sufficient.



---



## 17. Data Quality Rules



Every snapshot should be able to expose:



```text

source

source_data_date

retrieved_at

confidence

```



Recommended source confidence:



```text

official

high

medium

low

```



Suggested hierarchy:



```text

Official filing

> Exchange

> Company IR

> Structured data provider

> Reputable news

> Aggregator

```



Examples of data-quality checks:



- stale dates;

- impossible negative values;

- extreme unit jumps;

- symbol mapping mismatch;

- duplicate reports;

- fiscal period mismatch;

- missing required fields;

- split-adjustment mismatch.



---



## 18. Security



MVP assumptions:



- private / single-user deployment;

- no broker credentials;

- no trading permissions.



Still required:



- secrets only in environment/secret store;

- do not commit API keys;

- sanitize URLs and provider inputs;

- timeouts on external HTTP calls;

- limit browser automation;

- basic request validation;

- prevent arbitrary URL fetching through public API parameters.



---



## 19. Testing Strategy



### Unit tests



Highest priority:



- normalizers;

- change comparison;

- score calculations;

- fiscal-period parsing;

- unit conversions;

- symbol mapping.



### Provider fixture tests



Never depend on live external services in CI.



Store provider fixtures:



```text

tests/fixtures/twse/

tests/fixtures/sec/

tests/fixtures/alphavantage/

tests/fixtures/tdcc/

```



### Integration tests



Use a temporary PostgreSQL database for:



- migrations;

- repositories;

- idempotent upserts;

- lineage relationships;

- change creation.



### Contract tests



Validate that frontend-generated types match the current OpenAPI schema.



---



## 20. Development Milestones



### M1 — Data Foundation



Deliver:



- database;

- migrations;

- instruments;

- watchlists;

- data sources;

- raw ingestion;

- job runs;

- price collector;

- at least one Taiwan provider;

- at least one US provider.



No AI.



### M2 — Change Engine



Deliver:



- normalized snapshots;

- deterministic comparisons;

- scoring;

- `GET /changes`.



### M3 — Dashboard



Deliver:



- Next.js dashboard;

- filter by market/category/severity;

- company change page;

- source metadata display;

- job status view.



### M4 — AI Interpretation



Deliver:



- LLM adapter;

- structured output;

- interpretation persistence;

- explicit AI labels;

- regenerate capability.



---



## 21. Architecture Decision Summary



### Chosen



```text

Python + FastAPI

PostgreSQL

SQLAlchemy sync

HTTPX async for collectors

APScheduler

Next.js + TypeScript

Tailwind + shadcn/ui

TanStack Query

Recharts

OpenAPI-generated frontend types

Docker Compose → k3s

```



### Intentionally deferred



```text

Redis

Celery

Kafka

TimescaleDB

Elasticsearch

Microservices

Agent frameworks

Realtime streaming

```



These should only be introduced when a measured bottleneck justifies them.



---



## 22. Core Invariant



The most important invariant in the project is:



```text

Raw source

    ↓

Normalized snapshot

    ↓

Deterministic diff

    ↓

Deterministic score

    ↓

Objective change record

    ↓

Optional AI interpretation

```



If an implementation bypasses this flow and lets the LLM infer market changes directly from raw content, it violates the architecture.

