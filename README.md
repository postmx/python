# PostMX Python SDK

Official Python SDK for the [PostMX](https://postmx.co) API.

Think about PostMX in one simple flow: create a temporary inbox, wait for the next email, then read extracted fields like the OTP or first link.

Requires Python 3.9+.

## Install

```bash
pip install postmx
```

## Quick Start

### Async

```python
import asyncio

from postmx import PostMX

async def main():
    async with PostMX("pmx_live_...") as postmx:
        inbox = await postmx.create_temporary_inbox({
            "label": "signup-test",
        })
        print(inbox["email_address"])
        message = await postmx.wait_for_message(inbox["id"], timeout=30.0)
        print(message["otp"])
        print(message["links"][0]["url"] if message["links"] else None)

asyncio.run(main())
```

### Sync

```python
from postmx import PostMXSync

postmx = PostMXSync("pmx_live_...")
inbox = postmx.create_temporary_inbox({"label": "test"})
print(inbox["email_address"])
message = postmx.wait_for_message(inbox["id"], timeout=30.0)
print(message["otp"])
```

`wait_for_message()` returns the latest existing message immediately if the inbox already has one; otherwise it waits for the next incoming email until the timeout.

If you already have a message ID, `content_mode` is just a "what do you want back?" choice:

```python
otp_only = await postmx.get_message("msg_123", content_mode="otp")
print(otp_only["otp"])
```

## API Reference

### `PostMX(api_key, *, base_url, max_retries, timeout)`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `base_url` | `str` | `https://api.postmx.co` | API base URL |
| `max_retries` | `int` | `2` | Max retry attempts on 429/5xx |
| `timeout` | `float` | `30.0` | Request timeout in seconds |

### Methods

```python
await postmx.list_inboxes(*, limit=None, cursor=None)         # → ListInboxesResult
await postmx.create_inbox(params, *, idempotency_key=None)    # → Inbox
await postmx.create_temporary_inbox(params, *, idempotency_key=None)  # → Inbox
await postmx.list_messages(inbox_id, *, limit=None, cursor=None)  # → ListMessagesResult
await postmx.list_messages_by_recipient(recipient_email, *, limit=None, cursor=None)  # → ListMessagesResult
await postmx.get_message(message_id)                          # → MessageDetail
await postmx.create_webhook(params, *, idempotency_key=None)  # → CreateWebhookResult
await postmx.wait_for_message(inbox_id, *, interval=1.0, timeout=60.0)  # → MessageDetail
```

## Advanced

- Use `create_inbox()` when you need lifecycle controls like `persistent` inboxes or a custom `ttl_minutes`.
- Use `list_inboxes()` when you need wildcard address information or pagination.
- Use `create_webhook()` and `verify_webhook_signature()` when you want push delivery instead of polling.
- POST methods accept an optional `idempotency_key`. If not provided, one is auto-generated to make retries safe.

## Error Handling

```python
from postmx import PostMXApiError, PostMXNetworkError

try:
    await postmx.get_message("bad_id")
except PostMXApiError as err:
    print(err.status)              # 404
    print(err.code)                # "not_found"
    print(err.request_id)          # "req_abc123"
    print(err.retry_after_seconds) # None or int
except PostMXNetworkError as err:
    print(err.__cause__)           # original httpx error
```

## Webhook Verification

```python
from postmx import verify_webhook_signature, PostMXWebhookVerificationError

# In your webhook handler (e.g., FastAPI)
@app.post("/webhooks/postmx")
async def handle_webhook(request: Request):
    body = await request.body()
    try:
        event = verify_webhook_signature(
            payload=body,
            signature=request.headers["x-postmx-signature"],
            timestamp=request.headers["x-postmx-timestamp"],
            signing_secret=os.environ["POSTMX_WEBHOOK_SECRET"],
        )
        print(event["data"]["message"]["otp"])
        return {"ok": True}
    except PostMXWebhookVerificationError:
        raise HTTPException(400)
```

## License

MIT
