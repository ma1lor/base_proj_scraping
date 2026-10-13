import asyncio
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from time import monotonic
from typing import Self

from curl_cffi.requests import AsyncSession, Response
from curl_cffi.requests.exceptions import ConnectionError, SSLError, Timeout


class HttpClient:
    retry_statuses = {429, 502, 503, 504}

    def __init__(
        self,
        logger,
        *,
        timeout: float = 30,
        max_connections: int = 10,
        max_attempts: int = 3,
        headers: dict[str, str] | None = None,
        cookies: dict[str, str] | None = None,
        proxy: str | None = None,
        impersonate: str | None = None,
    ):
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if max_connections < 1:
            raise ValueError("max_connections must be at least 1")
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")

        self.logger = logger
        self.max_attempts = max_attempts
        self.session: AsyncSession | None = None
        self._semaphore = asyncio.Semaphore(max_connections)
        self._session_options = {
            "timeout": timeout,
            "max_clients": max_connections,
            "headers": headers,
            "cookies": cookies,
            "proxies": {"all": proxy or ""},
            "impersonate": impersonate,
            "verify": True,
            "trust_env": False,
            "retry": 0,
            "raise_for_status": False,
        }

    async def open(self) -> None:
        if self.session is None:
            self.session = AsyncSession(**self._session_options)
            self.logger.debug("HTTP session opened")

    async def close(self) -> None:
        if self.session is not None:
            await self.session.close()
            self.logger.debug("HTTP session closed")

    async def __aenter__(self) -> Self:
        await self.open()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        await self.close()

    def _retry_delay(self, response: Response | None, attempt: int) -> float:
        delay = float(min(attempt, 60))
        if response is None:
            return delay

        retry_after = response.headers.get("Retry-After")
        if not retry_after:
            return delay

        try:
            if retry_after.strip().isdigit():
                delay = float(int(retry_after))
            else:
                retry_at = parsedate_to_datetime(retry_after)
                if retry_at.tzinfo is None:
                    retry_at = retry_at.replace(tzinfo=timezone.utc)
                delay = (retry_at - datetime.now(timezone.utc)).total_seconds()
        except (ValueError, TypeError, OverflowError):
            return float(min(attempt, 60))

        return max(0.0, min(delay, 60.0))

    async def request(
        self,
        method: str,
        url: str,
        *,
        raise_for_status: bool = True,
        **kwargs,
    ) -> Response:
        if self.session is None:
            raise RuntimeError("HTTP client is not open; call open() first")
        if kwargs.get("stream"):
            raise ValueError("Use session.stream() for streaming requests")
        if "proxy" in kwargs:
            if "proxies" in kwargs:
                raise ValueError("Pass either proxy or proxies, not both")
            kwargs["proxies"] = {"all": kwargs.pop("proxy") or ""}

        method = method.upper()
        attempts = self.max_attempts if method in {"GET", "HEAD"} else 1

        for attempt in range(1, attempts + 1):
            response = None
            try:
                async with self._semaphore:
                    started = monotonic()
                    response = await self.session.request(method, url, **kwargs)
                    self.logger.debug(
                        "HTTP {} status={} attempt={}/{} duration={:.3f}s",
                        method,
                        response.status_code,
                        attempt,
                        attempts,
                        monotonic() - started,
                    )
            except SSLError:
                raise
            except (ConnectionError, Timeout) as error:
                if attempt == attempts:
                    raise
                self.logger.warning(
                    "HTTP {} attempt={}/{} failed: {}",
                    method,
                    attempt,
                    attempts,
                    type(error).__name__,
                )
            else:
                should_retry = response.status_code in self.retry_statuses
                if not should_retry or attempt == attempts:
                    if raise_for_status:
                        response.raise_for_status()
                    return response
                self.logger.warning(
                    "HTTP {} status={} attempt={}/{}; retrying",
                    method,
                    response.status_code,
                    attempt,
                    attempts,
                )

            await asyncio.sleep(self._retry_delay(response, attempt))

        raise RuntimeError("HTTP request completed without a response")

    async def get(self, url: str, **kwargs) -> Response:
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs) -> Response:
        return await self.request("POST", url, **kwargs)
