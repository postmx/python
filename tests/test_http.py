import httpx
import pytest
import respx

from postmx._errors import PostMXApiError, PostMXNetworkError
from postmx._http import request

BASE_URL = "https://api.postmx.co"
API_KEY = "pmx_live_test"
COMMON = dict(api_key=API_KEY, base_url=BASE_URL, max_retries=2, timeout=5.0)


@respx.mock
async def test_returns_data_on_success():
    respx.get(f"{BASE_URL}/v1/test").mock(
        return_value=httpx.Response(
            200,
            json={"success": True, "request_id": "req_1", "inbox": {"id": "inb_1"}},
            headers={"x-request-id": "req_1"},
        )
    )
    async with httpx.AsyncClient() as client:
        data, request_id = await request(client, "GET", "/v1/test", **COMMON)
    assert data["inbox"]["id"] == "inb_1"
    assert request_id == "req_1"


@respx.mock
async def test_sends_correct_headers_on_get():
    route = respx.get(f"{BASE_URL}/v1/test").mock(
        return_value=httpx.Response(200, json={"success": True, "request_id": "req_1"})
    )
    async with httpx.AsyncClient() as client:
        await request(client, "GET", "/v1/test", **COMMON)
    req = route.calls[0].request
    assert req.headers["authorization"] == f"Bearer {API_KEY}"
    assert req.headers["accept"] == "application/json"
    assert "idempotency-key" not in req.headers


@respx.mock
async def test_sends_idempotency_key_on_post():
    route = respx.post(f"{BASE_URL}/v1/test").mock(
        return_value=httpx.Response(201, json={"success": True, "request_id": "req_1"})
    )
    async with httpx.AsyncClient() as client:
        await request(client, "POST", "/v1/test", body={"foo": "bar"}, **COMMON)
    req = route.calls[0].request
    assert "idempotency-key" in req.headers
    assert req.headers["content-type"] == "application/json"


@respx.mock
async def test_uses_provided_idempotency_key():
    route = respx.post(f"{BASE_URL}/v1/test").mock(
        return_value=httpx.Response(201, json={"success": True, "request_id": "req_1"})
    )
    async with httpx.AsyncClient() as client:
        await request(
            client, "POST", "/v1/test", body={}, idempotency_key="my-key", **COMMON
        )
    assert route.calls[0].request.headers["idempotency-key"] == "my-key"


@respx.mock
async def test_builds_query_params():
    route = respx.get(url__startswith=f"{BASE_URL}/v1/messages").mock(
        return_value=httpx.Response(200, json={"success": True, "request_id": "req_1"})
    )
    async with httpx.AsyncClient() as client:
        await request(
            client,
            "GET",
            "/v1/messages",
            query={"limit": 10, "cursor": "abc", "unused": None},
            **COMMON,
        )
    url = str(route.calls[0].request.url)
    assert "limit=10" in url
    assert "cursor=abc" in url
    assert "unused" not in url


@respx.mock
async def test_throws_api_error_on_non_retryable():
    respx.get(f"{BASE_URL}/v1/bad").mock(
        return_value=httpx.Response(
            404,
            json={
                "success": False,
                "request_id": "req_err",
                "error": {"code": "not_found", "message": "Inbox not found"},
            },
            headers={"x-request-id": "req_err"},
        )
    )
    async with httpx.AsyncClient() as client:
        with pytest.raises(PostMXApiError) as exc_info:
            await request(client, "GET", "/v1/bad", **COMMON)
    err = exc_info.value
    assert err.status == 404
    assert err.code == "not_found"
    assert err.request_id == "req_err"


@respx.mock
async def test_retries_on_429_and_succeeds():
    route = respx.get(f"{BASE_URL}/v1/test")
    route.side_effect = [
        httpx.Response(
            429,
            json={
                "success": False,
                "request_id": "r1",
                "error": {"code": "rate_limited", "message": "Slow down", "retry_after_seconds": 0},
            },
            headers={"retry-after": "0"},
        ),
        httpx.Response(200, json={"success": True, "request_id": "req_ok"}),
    ]
    async with httpx.AsyncClient() as client:
        data, request_id = await request(client, "GET", "/v1/test", **COMMON)
    assert request_id == "req_ok"
    assert len(route.calls) == 2


@respx.mock
async def test_retries_on_500_exhausts():
    route = respx.get(f"{BASE_URL}/v1/test")
    route.side_effect = [
        httpx.Response(
            500,
            json={"success": False, "request_id": f"r{i}", "error": {"code": "internal", "message": "err"}},
        )
        for i in range(3)
    ]
    async with httpx.AsyncClient() as client:
        with pytest.raises(PostMXApiError) as exc_info:
            await request(client, "GET", "/v1/test", **COMMON)
    assert exc_info.value.status == 500
    assert len(route.calls) == 3


@respx.mock
async def test_retries_on_network_error():
    call_count = 0

    def side_effect(request):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise httpx.ConnectError("Connection refused")
        return httpx.Response(200, json={"success": True, "request_id": "req_ok"})

    respx.get(f"{BASE_URL}/v1/test").mock(side_effect=side_effect)
    async with httpx.AsyncClient() as client:
        data, request_id = await request(client, "GET", "/v1/test", **COMMON)
    assert request_id == "req_ok"


@respx.mock
async def test_network_error_exhausts_retries():
    respx.get(f"{BASE_URL}/v1/test").mock(side_effect=httpx.ConnectError("fail"))
    async with httpx.AsyncClient() as client:
        with pytest.raises(PostMXNetworkError):
            await request(client, "GET", "/v1/test", **COMMON)


@respx.mock
async def test_reuses_idempotency_key_across_retries():
    route = respx.post(f"{BASE_URL}/v1/test")
    route.side_effect = [
        httpx.Response(
            500,
            json={"success": False, "request_id": "r1", "error": {"code": "internal", "message": "err"}},
        ),
        httpx.Response(201, json={"success": True, "request_id": "r2"}),
    ]
    async with httpx.AsyncClient() as client:
        await request(client, "POST", "/v1/test", body={}, **COMMON)
    key1 = route.calls[0].request.headers["idempotency-key"]
    key2 = route.calls[1].request.headers["idempotency-key"]
    assert key1 == key2
