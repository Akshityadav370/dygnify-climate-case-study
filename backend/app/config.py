from datetime import date
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

# NASA POWER daily data starts on 1981-01-01.
DATA_START_YEAR = 1981


def last_complete_year() -> int:
    """The most recent calendar year with a full year of data."""
    return date.today().year - 1


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "climate_hazards"
    cors_origins: list[str] = ["http://localhost:5173"]
    nominatim_user_agent: str = "climate-hazard-analyzer/0.1 (set NOMINATIM_USER_AGENT)"

    http_connect_timeout: float = 10.0
    http_read_timeout: float = 30.0
    http_retries: int = 2
    http_backoff_seconds: float = 0.5
    upstream_concurrency: int = 3

    # Number of reverse proxies in front of the app that append to X-Forwarded-For
    # (Render: 1). 0 means use the socket peer address.
    trusted_proxy_hops: int = 0

    analysis_ttl_days: int = 30
    geocode_ttl_days: int = 7


@lru_cache
def get_settings() -> Settings:
    return Settings()
