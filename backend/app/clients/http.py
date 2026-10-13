import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import urlparse

import httpx

from app.config import Settings
from app.errors import UpstreamError, UpstreamTimeout

logger = logging.getLogger(__name__)

NOMINATIM_MIN_INTERVAL_SECONDS = 1.0


class UpstreamClient:
    """Shared HTTP client for all external APIs: timeouts, retries, throttles."""

    def __init__(self, settings: Settings):
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.http_read_timeout, connect=settings.http_connect_timeout),
            headers={"User-Agent": settings.nominatim_user_agent},
            follow_redirects=False,
        )
        self._retries = settings.http_retries
        self._backoff = settings.http_backoff_seconds
        self.concurrency = asyncio.Semaphore(settings.upstream_concurrency)
        self._nominatim_lock = asyncio.Lock()
        self._nominatim_last = 0.0

    async def get_json(self, url: str, params: dict[str, Any]) -> Any:
        host = urlparse(url).hostname
        last_error: UpstreamError = UpstreamError("Weather data provider is unavailable.")
        for attempt in range(self._retries + 1):
            try:
                response = await self._client.get(url, params=params)
            except httpx.TimeoutException:
                logger.warning("Timeout calling %s (attempt %d)", host, attempt + 1)
                last_error = UpstreamTimeout("Weather data provider did not respond in time. Try again shortly.")
            except httpx.TransportError as exc:
                logger.warning("Transport error calling %s: %s", host, exc)
                last_error = UpstreamError("Could not reach the weather data provider.")
            else:
                if response.status_code == 200:
                    try:
                        return response.json()
                    except ValueError as exc:
                        raise UpstreamError("Weather data provider returned invalid JSON.") from exc
                logger.warning("%s returned HTTP %d", host, response.status_code)
                if response.status_code != 429 and response.status_code < 500:
                    raise UpstreamError("Weather data provider rejected the request.")
                last_error = UpstreamError("Weather data provider returned an error.")
            if attempt < self._retries:
                await asyncio.sleep(self._backoff * 2**attempt)
        raise last_error

    @asynccontextmanager
    async def nominatim_slot(self):
        """Serialize Nominatim calls and keep them at least 1 s apart (usage policy)."""
        async with self._nominatim_lock:
            wait = self._nominatim_last + NOMINATIM_MIN_INTERVAL_SECONDS - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            try:
                yield
            finally:
                self._nominatim_last = time.monotonic()

    async def aclose(self) -> None:
        await self._client.aclose()
