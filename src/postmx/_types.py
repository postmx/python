from __future__ import annotations

from typing import Literal, TypedDict

# --- Enums ---

LifecycleMode = Literal["temporary", "persistent"]
MessageIntent = Literal["login_code", "verification", "password_reset", "magic_link", "invite"]
LinkType = Literal["verification", "magic_link", "password_reset", "unsubscribe", "other"]
ContentMode = Literal["full", "otp", "links", "text_only"]
DeliveryScope = Literal["account", "inbox"]
InboxMessageAnalysisMode = Literal["all", "disabled", "allowlist", "blocklist"]
MessageAnalysisStatus = Literal["none", "queued", "complete", "failed", "skipped_quota"]

# --- Request params ---


class InboxMessageAnalysis(TypedDict):
    mode: InboxMessageAnalysisMode
    recipients: list[str]


class CreateInboxParams(TypedDict, total=False):
    label: str  # required, but total=False for convenience; validated server-side
    lifecycle_mode: LifecycleMode
    ttl_minutes: int
    message_analysis: InboxMessageAnalysis


class CreateTemporaryInboxParams(TypedDict, total=False):
    label: str  # required, but total=False for convenience; validated server-side
    ttl_minutes: int
    message_analysis: InboxMessageAnalysis


class CreateWebhookParams(TypedDict, total=False):
    label: str
    target_url: str
    inbox_id: str


# --- Response types ---


class Inbox(TypedDict):
    id: str
    label: str
    email_address: str
    lifecycle_mode: LifecycleMode
    ttl_minutes: int | None
    expires_at: str | None
    status: str
    last_message_received_at: str | None
    created_at: str
    message_analysis: InboxMessageAnalysis


class WildcardAddress(TypedDict):
    email_address: str
    inbox_id: str


class ListInboxesResult(TypedDict):
    inboxes: list[Inbox]
    page_info: PageInfo
    wildcard_address: WildcardAddress | None


class MessageSummary(TypedDict):
    id: str
    inbox_id: str
    inbox_email_address: str
    inbox_label: str
    from_email: str
    to_email: str
    subject: str | None
    preview_text: str | None
    received_at: str
    has_text_body: bool
    has_html_body: bool


class ExtractedLink(TypedDict):
    url: str
    type: LinkType


class MessageAnalysis(TypedDict):
    eligible: bool
    status: MessageAnalysisStatus
    requested_at: str | None
    completed_at: str | None
    detected_otp: str | None
    sender_name: str | None
    category: str | None
    extracted_id: str | None
    amount_mentioned: str | None
    is_urgent: bool | None
    action_required: bool | None
    summary: str | None


class MessageDetail(MessageSummary):
    text_body: str | None
    html_body: str | None
    otp: str | None
    links: list[ExtractedLink]
    intent: MessageIntent | None
    analysis: MessageAnalysis


class MessageOtpDetail(MessageSummary):
    otp: str | None
    analysis: MessageAnalysis


class MessageLinksDetail(MessageSummary):
    links: list[ExtractedLink]
    analysis: MessageAnalysis


class MessageTextOnlyDetail(MessageSummary):
    text_body: str | None
    analysis: MessageAnalysis


class PageInfo(TypedDict):
    has_more: bool
    next_cursor: str | None


class ListMessagesResult(TypedDict):
    messages: list[MessageSummary]
    page_info: PageInfo


class Webhook(TypedDict):
    id: str
    inbox_id: str | None
    label: str
    target_url: str
    delivery_scope: DeliveryScope
    subscribed_events: list[str]
    status: str
    last_delivery_at: str | None
    archived_at: str | None
    created_at: str
    updated_at: str


class CreateWebhookResult(TypedDict):
    webhook: Webhook
    signing_secret: str


# --- Webhook event ---


class WebhookEventInbox(TypedDict):
    id: str
    email_address: str
    label: str


class WebhookEventData(TypedDict):
    inbox: WebhookEventInbox
    message: MessageDetail


class WebhookEvent(TypedDict):
    id: str
    type: Literal["email.received", "email.enriched"]
    created_at: str
    data: WebhookEventData
