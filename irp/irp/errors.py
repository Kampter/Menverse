"""
IRP error code registry, exception type, and HTTP status mapping.

This module is the canonical source for IRP error semantics. Error codes are
grouped into ranges so that downstream consumers can switch on the high digit
to triage failures without enumerating every code:

    1xxx — Frame / protocol errors
    2xxx — Authentication / authorization
    3xxx — Quota / rate limit / billing
    4xxx — Receipt / metering / verification
    5xxx — QoS / SLA
    9xxx — Server / unavailable

Codes are stable wire identifiers; do not renumber once published.
"""

from __future__ import annotations

from enum import IntEnum


class IRPErrorCode(IntEnum):
    """IRP error code registry."""

    # 1xxx - Protocol / frame
    INVALID_FRAME = 1000
    UNSUPPORTED_VERSION = 1001
    UNKNOWN_FRAME_TYPE = 1002
    MALFORMED_BODY = 1003

    # 2xxx - Auth
    AUTH_REQUIRED = 2000
    AUTH_FAILED = 2001
    AUTH_TOKEN_EXPIRED = 2002
    AUTH_INSUFFICIENT_SCOPE = 2003

    # 3xxx - Quota / billing
    QUOTA_EXCEEDED = 3000
    RATE_LIMITED = 3001
    BILLING_REQUIRED = 3002

    # 4xxx - Receipt / metering
    RECEIPT_INVALID = 4000
    RECEIPT_SIGNATURE_INVALID = 4001
    RECEIPT_REPLAY_DETECTED = 4002
    RECEIPT_STALE = 4003
    TOKEN_DIFF_EXCEEDED = 4004
    HASH_MISMATCH = 4005

    # 5xxx - QoS / SLA
    SLA_VIOLATED = 5000
    QOS_DOWNGRADED = 5001
    QOS_UNSUPPORTED = 5002

    # 9xxx - Server
    SERVER_UNAVAILABLE = 9000
    SERVER_TIMEOUT = 9001
    INTERNAL_ERROR = 9999


# HTTP status mapping when errors are carried over an HTTP transport.
ERROR_HTTP_STATUS: dict[IRPErrorCode, int] = {
    IRPErrorCode.INVALID_FRAME: 400,
    IRPErrorCode.UNSUPPORTED_VERSION: 426,  # Upgrade Required
    IRPErrorCode.UNKNOWN_FRAME_TYPE: 400,
    IRPErrorCode.MALFORMED_BODY: 400,
    IRPErrorCode.AUTH_REQUIRED: 401,
    IRPErrorCode.AUTH_FAILED: 401,
    IRPErrorCode.AUTH_TOKEN_EXPIRED: 401,
    IRPErrorCode.AUTH_INSUFFICIENT_SCOPE: 403,
    IRPErrorCode.QUOTA_EXCEEDED: 429,
    IRPErrorCode.RATE_LIMITED: 429,
    IRPErrorCode.BILLING_REQUIRED: 402,
    IRPErrorCode.RECEIPT_INVALID: 422,
    IRPErrorCode.RECEIPT_SIGNATURE_INVALID: 422,
    IRPErrorCode.RECEIPT_REPLAY_DETECTED: 422,
    IRPErrorCode.RECEIPT_STALE: 422,
    IRPErrorCode.TOKEN_DIFF_EXCEEDED: 422,
    IRPErrorCode.HASH_MISMATCH: 422,
    IRPErrorCode.SLA_VIOLATED: 503,
    IRPErrorCode.QOS_DOWNGRADED: 200,  # informational, not an error
    IRPErrorCode.QOS_UNSUPPORTED: 400,
    IRPErrorCode.SERVER_UNAVAILABLE: 503,
    IRPErrorCode.SERVER_TIMEOUT: 504,
    IRPErrorCode.INTERNAL_ERROR: 500,
}


class IRPError(Exception):
    """Base exception for IRP errors."""

    def __init__(
        self,
        code: IRPErrorCode,
        detail: str = "",
        *,
        request_id: str | None = None,
    ):
        self.code = code
        self.detail = detail
        self.request_id = request_id
        super().__init__(f"[{code.name} {code.value}] {detail}")

    @property
    def http_status(self) -> int:
        """HTTP status code for this error when carried over HTTP."""
        return ERROR_HTTP_STATUS[self.code]

    def to_dict(self) -> dict[str, object]:
        """Serialize to a JSON-friendly dict for wire transport."""
        d: dict[str, object] = {
            "code": int(self.code),
            "name": self.code.name,
            "detail": self.detail,
        }
        if self.request_id:
            d["request_id"] = self.request_id
        return d


def code_from_int(value: int) -> IRPErrorCode:
    """Parse int to IRPErrorCode; raises ValueError on unknown."""
    try:
        return IRPErrorCode(value)
    except ValueError as e:
        raise ValueError(f"Unknown IRP error code: {value}") from e
