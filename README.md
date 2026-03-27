# PostMX Python SDK

Official Python SDK for the [PostMX](https://postmx.co) API.

- Async-first with sync wrapper
- Full type hints (PEP 561)
- Single dependency (`httpx`)
- Automatic retries with exponential backoff
- Webhook signature verification

Requires Python 3.9+.

## Install

```bash
pip install postmx
```

## Quick Start

### Async

```python
from postmx import PostMX

async def main():
    async with PostMX("pmx_live_...") as postmx:
        # Create a temporary inbox
        inbox = await postmx.create_inbox({
            "label": "signup-test",
            "lifecycle_mode": "temporary",
            "ttl_minutes": 15,
        })
        print(inbox["email_address"])

        # List active inboxes
        result = await postmx.list_inboxes()
        print(result["inboxes"])

        # List messages
        result = await postmx.list_messages(inbox["id"])

        # Or list messages by exact recipient email
        recipient_feed = await postmx.list_messages_by_recipient(inbox["email_address"])

        # Get full message detail with OTP extraction
        detail = await postmx.get_message(result["messages"][0]["id"])
        print(detail["otp"])    # "482910"
        print(detail["intent"]) # "login_code"
```

### Sync

```python
from postmx import PostMXSync

postmx = PostMXSync("pmx_live_...")
inbox = postmx.create_inbox({"label": "test", "lifecycle_mode": "temporary"})
print(inbox["email_address"])
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
await postmx.list_messages(inbox_id, *, limit=None, cursor=None)  # → ListMessagesResult
await postmx.list_messages_by_recipient(recipient_email, *, limit=None, cursor=None)  # → ListMessagesResult
await postmx.get_message(message_id)                          # → MessageDetail
await postmx.create_webhook(params, *, idempotency_key=None)  # → CreateWebhookResult
await postmx.wait_for_message(inbox_id, *, interval=1.0, timeout=60.0)  # → MessageDetail
```

POST methods accept an optional `idempotency_key`. If not provided, one is auto-generated to make retries safe.

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
