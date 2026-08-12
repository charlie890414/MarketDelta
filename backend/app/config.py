from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://market:market@localhost:5432/market_changes"
    alpha_vantage_api_key: str | None = None
    environment: str = "development"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:3000"
    mce_use_live: bool = False
    pipeline_interval_hours: int = 6
    pipeline_run_on_start: bool = True
    sec_cik_map: str = "{}"
    sec_user_agent: str = "market-changes-engine/0.1 contact@example.invalid"
    mops_api_url: str | None = None
    tdcc_api_url: str | None = None
    benchmark_symbols: str = '{"US":"SPY","TW":"0050"}'
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str = "gpt-4o-mini"
    llm_timeout_seconds: float = 20.0
    initial_price_backfill_days: int = 90
    news_max_age_days: int = 7

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
