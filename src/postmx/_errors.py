from __future__ import annotations


class PostMXError(Exception):
    """Base exception for all PostMX SDK errors."""

    def __init__(self, message: str, request_id: str | None = None) -> None:
        super().__init__(message)
        self.request_id = request_id


class PostMXApiError(PostMXError):
    """Raised when the API returns a non-2xx response."""

    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        request_id: str | None = None,
        retry_after_seconds: int | None = None,
    ) -> None:
        super().__init__(message, request_id)
        self.status = status
        self.code = code
        self.retry_after_seconds = retry_after_seconds

    def __str__(self) -> str:
        parts = [f"PostMXApiError: {self.code} - {super().__str__()}"]
        if self.request_id:
            parts.append(f"request_id={self.request_id}")
        parts.append(f"status={self.status}")
        return f"{parts[0]} ({', '.join(parts[1:])})" if len(parts) > 1 else parts[0]


class PostMXNetworkError(PostMXError):
    """Raised when a network-level error occurs (connection refused, timeout, etc.)."""

    def __init__(self, cause: Exception, request_id: str | None = None) -> None:
        super().__init__(f"Network error: {cause}", request_id)
        self.__cause__ = cause


class PostMXWebhookVerificationError(PostMXError):
    """Raised when webhook signature verification fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
