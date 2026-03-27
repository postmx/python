from __future__ import annotations

import asyncio
import random
import uuid
from typing import Any

import httpx

from ._errors import PostMXApiError, PostMXNetworkError

VERSION = "0.1.0"
RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
MAX_BACKOFF_S = 30.0
BASE_DELAY_S = 0.5


def _jitter(delay: float) -> float:
    return delay * (0.5 + random.random() * 0.5)


async def request(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    *,
    api_key: str,
    base_url: str,
    max_retries: int,
    timeout: float,
    body: dict[str, Any] | None = None,
    query: dict[str, Any] | None = None,
    idempotency_key: str | None = None,
) -> tuple[Any, str]:
    """Make an HTTP request with retries. Returns (data_dict, request_id)."""
    url = base_url.rstrip("/") + path

    # Filter out None query params
    params = {k: v for k, v in (query or {}).items() if v is not None} or None

    # Auto-generate idempotency key for POST
    if method == "POST":
        idempotency_key = idempotency_key or str(uuid.uuid4())

    headers: dict[str, str] = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "User-Agent": f"postmx-python/{VERSION}",
    }
    if method == "POST":
        headers["Content-Type"] = "application/json"
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key

    last_error: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            response = await client.request(
                method,
                url,
                headers=headers,
                json=body if method == "POST" else None,
                params=params,
                timeout=timeout,
            )

            request_id = response.headers.get("x-request-id")

            if response.is_success:
                data = response.json()
                return data, data.get("request_id", request_id or "")

            # Parse error body
            try:
                error_json = response.json()
            except Exception:
                error_json = None

            error_request_id = (
                (error_json.get("request_id") if error_json else None) or request_id
            )
            error_obj = error_json.get("error", {}) if error_json else {}
            code = error_obj.get("code", f"http_{response.status_code}")
            message = error_obj.get("message", response.reason_phrase or "Unknown error")
            retry_after_seconds: int | None = error_obj.get("retry_after_seconds")

            # Check Retry-After header
            if retry_after_seconds is None:
                retry_after_header = response.headers.get("retry-after")
                if retry_after_header:
                    try:
                        retry_after_seconds = int(retry_after_header)
                    except ValueError:
                        pass

            api_error = PostMXApiError(
                status=response.status_code,
                code=code,
                message=message,
                request_id=error_request_id,
                retry_after_seconds=retry_after_seconds,
            )

            if response.status_code not in RETRYABLE_STATUS_CODES or attempt == max_retries:
                raise api_error

            last_error = api_error
            backoff = min(BASE_DELAY_S * (2**attempt), MAX_BACKOFF_S)
            retry_after_s = float(retry_after_seconds) if retry_after_seconds else 0.0
            await asyncio.sleep(max(_jitter(backoff), retry_after_s))

        except PostMXApiError:
            raise
        except Exception as exc:
            network_error = PostMXNetworkError(exc)

            if attempt == max_retries:
                raise network_error from exc

            last_error = network_error
            backoff = min(BASE_DELAY_S * (2**attempt), MAX_BACKOFF_S)
            await asyncio.sleep(_jitter(backoff))

    raise last_error or RuntimeError("Unexpected: no attempts made")
