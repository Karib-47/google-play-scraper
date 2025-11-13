import logging
import time
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)

class RequestClient:
    """
    Lightweight HTTP client wrapper that adds timeouts, retries,
    and structured logging on top of requests.Session.
    """

    def __init__(
        self,
        user_agent: str,
        timeout: int = 15,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
    ) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": user_agent,
                "Accept-Language": "en-US,en;q=0.9",
            }
        )
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> requests.Response:
        last_exc: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.debug(
                    "HTTP %s %s (attempt %d/%d, params=%s)",
                    method,
                    url,
                    attempt,
                    self.max_retries,
                    params,
                )
                resp = self.session.request(
                    method=method,
                    url=url,
                    params=params,
                    data=data,
                    timeout=self.timeout,
                )
                if 200 <= resp.status_code < 300:
                    return resp

                logger.warning(
                    "Received non-2xx status %s for %s %s: %s",
                    resp.status_code,
                    method,
                    url,
                    resp.text[:200],
                )
            except requests.RequestException as exc:  # noqa: PERF203
                last_exc = exc
                logger.warning(
                    "Request error on %s %s (attempt %d/%d): %s",
                    method,
                    url,
                    attempt,
                    self.max_retries,
                    exc,
                )

            sleep_for = self.backoff_factor * attempt
            logger.debug("Sleeping for %.2fs before retry.", sleep_for)
            time.sleep(sleep_for)

        if last_exc is not None:
            raise RuntimeError(f"Failed to {method} {url}") from last_exc

        raise RuntimeError(f"Failed to {method} {url} with status != 2xx")

    def get(
        self,
        url: str,
        *,
        params: Optional[Dict[str, Any]] = None,
    ) -> requests.Response:
        return self._request("GET", url, params=params)

    def post(
        self,
        url: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> requests.Response:
        return self._request("POST", url, params=params, data=data)