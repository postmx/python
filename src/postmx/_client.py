from __future__ import annotations

import asyncio
from typing import Any, Literal, overload
from urllib.parse import quote

import httpx

from ._errors import PostMXError
from ._http import request
from ._types import (
    ContentMode,
    CreateInboxParams,
    CreateWebhookParams,
    CreateWebhookResult,
    Inbox,
    ListInboxesResult,
    ListMessagesResult,
    MessageDetail,
    MessageLinksDetail,
    MessageOtpDetail,
    MessageTextOnlyDetail,
)

DEFAULT_BASE_URL = "https://api.postmx.co"
DEFAULT_MAX_RETRIES = 2
DEFAULT_TIMEOUT = 30.0


class PostMX:
    """Async PostMX API client."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        max_retries: int = DEFAULT_MAX_RETRIES,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        if not api_key:
            raise ValueError("PostMX: api_key is required")
        self._api_key = api_key
        self._base_url = base_url
        self._max_retries = max_retries
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient()
        return self._client

    async def _request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        query: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> Any:
        data, _ = await request(
            self._get_client(),
            method,
            path,
            api_key=self._api_key,
            base_url=self._base_url,
            max_retries=self._max_retries,
            timeout=self._timeout,
            body=body,
            query=query,
            idempotency_key=idempotency_key,
        )
        return data

    async def list_inboxes(
        self,
        *,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> ListInboxesResult:
        data = await self._request(
            "GET",
            "/v1/inboxes",
            query={"limit": limit, "cursor": cursor},
        )
        return {"inboxes": data["inboxes"], "page_info": data["page_info"], "wildcard_address": data.get("wildcard_address")}

    async def create_inbox(
        self,
        params: CreateInboxParams,
        *,
        idempotency_key: str | None = None,
    ) -> Inbox:
        data = await self._request(
            "POST", "/v1/inboxes", body=dict(params), idempotency_key=idempotency_key
        )
        return data["inbox"]

    async def list_messages(
        self,
        inbox_id: str,
        *,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> ListMessagesResult:
        data = await self._request(
            "GET",
            f"/v1/inboxes/{quote(inbox_id, safe='')}/messages",
            query={"limit": limit, "cursor": cursor},
        )
        return {"messages": data["messages"], "page_info": data["page_info"]}

    async def list_messages_by_recipient(
        self,
        recipient_email: str,
        *,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> ListMessagesResult:
        data = await self._request(
            "GET",
            "/v1/messages",
            query={
                "recipient_email": recipient_email,
                "limit": limit,
                "cursor": cursor,
            },
        )
        return {"messages": data["messages"], "page_info": data["page_info"]}

    @overload
    async def get_message(self, message_id: str) -> MessageDetail: ...
    @overload
    async def get_message(self, message_id: str, *, content_mode: Literal["full"]) -> MessageDetail: ...
    @overload
    async def get_message(self, message_id: str, *, content_mode: Literal["otp"]) -> MessageOtpDetail: ...
    @overload
    async def get_message(self, message_id: str, *, content_mode: Literal["links"]) -> MessageLinksDetail: ...
    @overload
    async def get_message(self, message_id: str, *, content_mode: Literal["text_only"]) -> MessageTextOnlyDetail: ...

    async def get_message(
        self, message_id: str, *, content_mode: ContentMode | None = None
    ) -> MessageDetail | MessageOtpDetail | MessageLinksDetail | MessageTextOnlyDetail:
        query = {"content_mode": content_mode} if content_mode else None
        data = await self._request("GET", f"/v1/messages/{quote(message_id, safe='')}", query=query)
        return data["message"]

    async def create_webhook(
        self,
        params: CreateWebhookParams,
        *,
        idempotency_key: str | None = None,
    ) -> CreateWebhookResult:
        data = await self._request(
            "POST", "/v1/webhooks", body=dict(params), idempotency_key=idempotency_key
        )
        return {"webhook": data["webhook"], "signing_secret": data["signing_secret"]}

    async def wait_for_message(
        self,
        inbox_id: str,
        *,
        interval: float = 1.0,
        timeout: float = 60.0,
    ) -> MessageDetail:
        """Poll an inbox until a message arrives, then return it.

        Args:
            inbox_id: The inbox to poll.
            interval: Seconds between polls. Default 1.0. Minimum 0.2.
            timeout: Maximum seconds to wait. Default 60.0.

        Raises:
            PostMXError: If no message arrives within the timeout.
        """
        if interval < 0.2:
            raise PostMXError("interval must be at least 0.2s to avoid excessive API calls")

        deadline = asyncio.get_event_loop().time() + timeout

        while asyncio.get_event_loop().time() < deadline:
            result = await self.list_messages(inbox_id, limit=1)

            if result["messages"]:
                return await self.get_message(result["messages"][0]["id"])

            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                break

            await asyncio.sleep(min(interval, remaining))

        raise PostMXError(
            f"Timed out after {timeout}s waiting for a message in inbox {inbox_id}"
        )

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def __aenter__(self) -> PostMX:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()


class PostMXSync:
    """Synchronous convenience wrapper around the async PostMX client."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        max_retries: int = DEFAULT_MAX_RETRIES,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self._client = PostMX(
            api_key, base_url=base_url, max_retries=max_retries, timeout=timeout
        )

    def _run(self, coro: Any) -> Any:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            raise RuntimeError(
                "PostMXSync cannot be used inside an already-running event loop. "
                "Use the async PostMX client instead."
            )
        return asyncio.run(coro)

    def list_inboxes(
        self,
        *,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> ListInboxesResult:
        return self._run(self._client.list_inboxes(limit=limit, cursor=cursor))

    def create_inbox(
        self,
        params: CreateInboxParams,
        *,
        idempotency_key: str | None = None,
    ) -> Inbox:
        return self._run(self._client.create_inbox(params, idempotency_key=idempotency_key))

    def list_messages(
        self,
        inbox_id: str,
        *,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> ListMessagesResult:
        return self._run(self._client.list_messages(inbox_id, limit=limit, cursor=cursor))

    def list_messages_by_recipient(
        self,
        recipient_email: str,
        *,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> ListMessagesResult:
        return self._run(
            self._client.list_messages_by_recipient(
                recipient_email,
                limit=limit,
                cursor=cursor,
            )
        )

    @overload
    def get_message(self, message_id: str) -> MessageDetail: ...
    @overload
    def get_message(self, message_id: str, *, content_mode: Literal["full"]) -> MessageDetail: ...
    @overload
    def get_message(self, message_id: str, *, content_mode: Literal["otp"]) -> MessageOtpDetail: ...
    @overload
    def get_message(self, message_id: str, *, content_mode: Literal["links"]) -> MessageLinksDetail: ...
    @overload
    def get_message(self, message_id: str, *, content_mode: Literal["text_only"]) -> MessageTextOnlyDetail: ...

    def get_message(
        self, message_id: str, *, content_mode: ContentMode | None = None
    ) -> MessageDetail | MessageOtpDetail | MessageLinksDetail | MessageTextOnlyDetail:
        return self._run(self._client.get_message(message_id, content_mode=content_mode))

    def create_webhook(
        self,
        params: CreateWebhookParams,
        *,
        idempotency_key: str | None = None,
    ) -> CreateWebhookResult:
        return self._run(self._client.create_webhook(params, idempotency_key=idempotency_key))

    def wait_for_message(
        self,
        inbox_id: str,
        *,
        interval: float = 1.0,
        timeout: float = 60.0,
    ) -> MessageDetail:
        return self._run(
            self._client.wait_for_message(inbox_id, interval=interval, timeout=timeout)
        )

    def close(self) -> None:
        self._run(self._client.close())
