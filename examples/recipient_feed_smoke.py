import asyncio
import httpx

from postmx import PostMX


def handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "success": True,
            "request_id": "req_smoke",
            "messages": [{"id": "msg_smoke"}],
            "page_info": {"has_more": False, "next_cursor": None},
        },
    )


async def main() -> None:
    transport = httpx.MockTransport(handler)
    async with PostMX("pmx_live_test", base_url="") as client:
        client._client = httpx.AsyncClient(transport=transport)
        result = await client.list_messages_by_recipient("smoke@test.postmx.email", limit=1)
    print(
        {
            "ok": True,
            "message_count": len(result["messages"]),
            "first_message_id": result["messages"][0]["id"],
        }
    )


asyncio.run(main())
