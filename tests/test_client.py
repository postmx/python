import httpx
import pytest
import respx

from postmx import PostMX

BASE_URL = "https://api.postmx.co"


def test_raises_on_empty_api_key():
    with pytest.raises(ValueError, match="api_key is required"):
        PostMX("")


def test_blank_base_url_uses_default():
    client = PostMX("pmx_live_test", base_url="   ")
    assert client._base_url == BASE_URL


def test_invalid_base_url_raises_value_error():
    with pytest.raises(ValueError, match="base_url must be a valid absolute http\\(s\\) URL"):
        PostMX("pmx_live_test", base_url="not-a-url")


@respx.mock
async def test_list_inboxes():
    inboxes = [
        {
            "id": "inb_1",
            "label": "Signup OTP",
            "email_address": "signup-otp@postmx.email",
            "lifecycle_mode": "temporary",
            "ttl_minutes": 15,
            "expires_at": "2026-03-25T18:15:00Z",
            "status": "active",
            "last_message_received_at": "2026-03-25T18:04:10Z",
            "created_at": "2026-03-25T18:00:00Z",
        },
        {
            "id": "inb_2",
            "label": "Support",
            "email_address": "support@postmx.email",
            "lifecycle_mode": "persistent",
            "ttl_minutes": None,
            "expires_at": None,
            "status": "active",
            "last_message_received_at": None,
            "created_at": "2026-03-25T17:30:00Z",
        },
    ]
    page_info = {"has_more": False, "next_cursor": None}
    route = respx.get(url__startswith=f"{BASE_URL}/v1/inboxes").mock(
        return_value=httpx.Response(
            200,
            json={"success": True, "request_id": "req_1", "inboxes": inboxes, "page_info": page_info},
        )
    )
    async with PostMX("pmx_live_test") as client:
        result = await client.list_inboxes(limit=10)
    assert result["inboxes"] == inboxes
    assert result["page_info"] == page_info
    url = str(route.calls[0].request.url)
    assert "limit=10" in url


@respx.mock
async def test_list_inboxes_no_params():
    inboxes = [{"id": "inb_1", "label": "test", "email_address": "a@b.com", "lifecycle_mode": "temporary", "ttl_minutes": None, "expires_at": None, "status": "active", "last_message_received_at": None, "created_at": "2026-01-01T00:00:00Z"}]
    page_info = {"has_more": False, "next_cursor": None}
    respx.get(url__startswith=f"{BASE_URL}/v1/inboxes").mock(
        return_value=httpx.Response(
            200,
            json={"success": True, "request_id": "req_1", "inboxes": inboxes, "page_info": page_info},
        )
    )
    async with PostMX("pmx_live_test") as client:
        result = await client.list_inboxes()
    assert len(result["inboxes"]) == 1
    assert result["inboxes"][0]["id"] == "inb_1"


@respx.mock
async def test_create_inbox():
    inbox = {
        "id": "inb_1",
        "label": "test",
        "email_address": "a@b.com",
        "lifecycle_mode": "temporary",
        "ttl_minutes": 15,
        "expires_at": None,
        "status": "active",
        "created_at": "2026-01-01T00:00:00Z",
    }
    route = respx.post(f"{BASE_URL}/v1/inboxes").mock(
        return_value=httpx.Response(
            201,
            json={"success": True, "request_id": "req_1", "inbox": inbox},
            headers={"x-request-id": "req_1"},
        )
    )
    async with PostMX("pmx_live_test") as client:
        result = await client.create_inbox({"label": "test", "lifecycle_mode": "temporary", "ttl_minutes": 15})
    assert result == inbox
    assert route.calls[0].request.headers["authorization"] == "Bearer pmx_live_test"


@respx.mock
async def test_list_messages():
    messages = [{"id": "msg_1"}]
    page_info = {"has_more": False, "next_cursor": None}
    respx.get(url__startswith=f"{BASE_URL}/v1/inboxes/inb_1/messages").mock(
        return_value=httpx.Response(
            200,
            json={"success": True, "request_id": "req_1", "messages": messages, "page_info": page_info},
        )
    )
    async with PostMX("pmx_live_test") as client:
        result = await client.list_messages("inb_1", limit=10, cursor="cur_abc")
    assert result["messages"] == messages
    assert result["page_info"] == page_info


@respx.mock
async def test_list_messages_by_recipient():
    messages = [{"id": "msg_1"}]
    page_info = {"has_more": False, "next_cursor": None}
    route = respx.get(url__startswith=f"{BASE_URL}/v1/messages").mock(
        return_value=httpx.Response(
            200,
            json={"success": True, "request_id": "req_1", "messages": messages, "page_info": page_info},
        )
    )
    async with PostMX("pmx_live_test") as client:
        result = await client.list_messages_by_recipient(
            "signup@test.postmx.email",
            limit=10,
            cursor="cur_abc",
        )
    assert result["messages"] == messages
    assert result["page_info"] == page_info
    url = str(route.calls[0].request.url)
    assert "recipient_email=signup%40test.postmx.email" in url
    assert "limit=10" in url
    assert "cursor=cur_abc" in url


@respx.mock
async def test_get_message():
    message = {"id": "msg_1", "otp": "123456", "links": [], "intent": "login_code"}
    route = respx.get(f"{BASE_URL}/v1/messages/msg_1").mock(
        return_value=httpx.Response(
            200,
            json={"success": True, "request_id": "req_1", "message": message},
        )
    )
    async with PostMX("pmx_live_test") as client:
        result = await client.get_message("msg_1")
    assert result == message
    assert "content_mode" not in str(route.calls[0].request.url)


@respx.mock
async def test_get_message_content_mode_otp():
    message = {"id": "msg_1", "otp": "123456"}
    route = respx.get(url__startswith=f"{BASE_URL}/v1/messages/msg_1").mock(
        return_value=httpx.Response(
            200,
            json={"success": True, "request_id": "req_1", "message": message},
        )
    )
    async with PostMX("pmx_live_test") as client:
        result = await client.get_message("msg_1", content_mode="otp")
    assert result == message
    assert "content_mode=otp" in str(route.calls[0].request.url)


@respx.mock
async def test_get_message_content_mode_links():
    message = {"id": "msg_1", "links": [{"url": "https://example.com", "type": "verification"}]}
    route = respx.get(url__startswith=f"{BASE_URL}/v1/messages/msg_1").mock(
        return_value=httpx.Response(
            200,
            json={"success": True, "request_id": "req_1", "message": message},
        )
    )
    async with PostMX("pmx_live_test") as client:
        result = await client.get_message("msg_1", content_mode="links")
    assert result == message
    assert "content_mode=links" in str(route.calls[0].request.url)


@respx.mock
async def test_get_message_content_mode_text_only():
    message = {"id": "msg_1", "text_body": "Hello world"}
    route = respx.get(url__startswith=f"{BASE_URL}/v1/messages/msg_1").mock(
        return_value=httpx.Response(
            200,
            json={"success": True, "request_id": "req_1", "message": message},
        )
    )
    async with PostMX("pmx_live_test") as client:
        result = await client.get_message("msg_1", content_mode="text_only")
    assert result == message
    assert "content_mode=text_only" in str(route.calls[0].request.url)


@respx.mock
async def test_create_webhook():
    webhook = {
        "id": "wh_1",
        "label": "test",
        "target_url": "https://example.com/hook",
        "delivery_scope": "account",
        "subscribed_events": ["email.received"],
        "status": "active",
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
        "inbox_id": None,
        "last_delivery_at": None,
        "archived_at": None,
    }
    respx.post(f"{BASE_URL}/v1/webhooks").mock(
        return_value=httpx.Response(
            201,
            json={"success": True, "request_id": "req_1", "webhook": webhook, "signing_secret": "whsec_abc"},
        )
    )
    async with PostMX("pmx_live_test") as client:
        result = await client.create_webhook({"label": "test", "target_url": "https://example.com/hook"})
    assert result["webhook"] == webhook
    assert result["signing_secret"] == "whsec_abc"


@respx.mock
async def test_wait_for_message_polls_until_found():
    empty_response = {"success": True, "request_id": "req_1", "messages": [], "page_info": {"has_more": False, "next_cursor": None}}
    found_response = {"success": True, "request_id": "req_2", "messages": [{"id": "msg_1"}], "page_info": {"has_more": False, "next_cursor": None}}
    detail = {"id": "msg_1", "otp": "123456", "links": [], "intent": "login_code"}
    detail_response = {"success": True, "request_id": "req_3", "message": detail}

    call_count = 0

    def side_effect(request):
        nonlocal call_count
        call_count += 1
        if "/v1/messages/msg_1" in str(request.url):
            return httpx.Response(200, json=detail_response)
        if call_count <= 2:
            return httpx.Response(200, json=empty_response)
        return httpx.Response(200, json=found_response)

    respx.get(url__startswith=f"{BASE_URL}/v1/inboxes/inb_1/messages").mock(side_effect=side_effect)
    respx.get(f"{BASE_URL}/v1/messages/msg_1").mock(side_effect=side_effect)

    async with PostMX("pmx_live_test") as client:
        result = await client.wait_for_message("inb_1", interval=0.2, timeout=5.0)
    assert result == detail
    assert call_count >= 3


@respx.mock
async def test_wait_for_message_times_out():
    empty_response = {"success": True, "request_id": "req_1", "messages": [], "page_info": {"has_more": False, "next_cursor": None}}
    respx.get(url__startswith=f"{BASE_URL}/v1/inboxes/inb_1/messages").mock(
        return_value=httpx.Response(200, json=empty_response)
    )
    async with PostMX("pmx_live_test") as client:
        with pytest.raises(Exception, match="Timed out"):
            await client.wait_for_message("inb_1", interval=0.2, timeout=0.5)


async def test_wait_for_message_rejects_low_interval():
    async with PostMX("pmx_live_test") as client:
        with pytest.raises(Exception, match="interval must be at least 0.2s"):
            await client.wait_for_message("inb_1", interval=0.05)


@respx.mock
async def test_custom_base_url():
    respx.get("https://custom.api.com/v1/messages/msg_1").mock(
        return_value=httpx.Response(
            200,
            json={"success": True, "request_id": "req_1", "message": {}},
        )
    )
    async with PostMX("pmx_live_test", base_url="https://custom.api.com") as client:
        await client.get_message("msg_1")
