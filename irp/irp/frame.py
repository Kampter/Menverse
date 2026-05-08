"""IRP wire-format frame schemas.

Defines request/response frame dataclasses, JSON serialization helpers,
length-prefixed binary encoding, and HTTP header mappings.

The IRP wire format frames inference traffic so that requests, responses,
receipts, and control messages share a common envelope (header + body).
"""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass, field
from enum import IntEnum


# Default protocol version emitted by the reference implementation.
IRP_VERSION = "0.1"

# Length-prefix format: 4-byte big-endian unsigned integer.
_LENGTH_PREFIX = ">I"
_LENGTH_PREFIX_SIZE = struct.calcsize(_LENGTH_PREFIX)


class FrameType(IntEnum):
    """IRP frame type codes."""

    REQUEST = 1
    RESPONSE = 2
    RECEIPT = 3
    ERROR = 4
    PING = 5
    PONG = 6


@dataclass
class FrameHeader:
    """IRP frame header — present in every frame."""

    version: str  # e.g. "0.1"
    frame_type: FrameType
    stream_id: int  # like HTTP/2 stream id; 0 for control frames
    flags: int = 0  # bitmask, reserved
    length: int = 0  # body length in bytes (informational)

    def to_json_dict(self) -> dict:
        """Serialize header to a JSON-safe dict."""
        return {
            "version": self.version,
            "frame_type": int(self.frame_type),
            "stream_id": self.stream_id,
            "flags": self.flags,
            "length": self.length,
        }

    @classmethod
    def from_json_dict(cls, data: dict) -> "FrameHeader":
        """Construct a FrameHeader from a JSON-decoded dict."""
        return cls(
            version=data["version"],
            frame_type=FrameType(int(data["frame_type"])),
            stream_id=int(data["stream_id"]),
            flags=int(data.get("flags", 0)),
            length=int(data.get("length", 0)),
        )


@dataclass
class IRPRequestFrame:
    """A request frame from client to provider."""

    header: FrameHeader
    method: str  # e.g. "chat.completions"
    model: str
    messages: list[dict]  # OpenAI-style messages
    qos_class: str = "standard"
    capabilities: list[str] = field(default_factory=list)
    client_id: str | None = None
    nonce: str | None = None

    def to_json_dict(self) -> dict:
        """Serialize the frame to a JSON-safe dict."""
        return {
            "header": self.header.to_json_dict(),
            "method": self.method,
            "model": self.model,
            "messages": self.messages,
            "qos_class": self.qos_class,
            "capabilities": list(self.capabilities),
            "client_id": self.client_id,
            "nonce": self.nonce,
        }

    @classmethod
    def from_json_dict(cls, data: dict) -> "IRPRequestFrame":
        """Construct an IRPRequestFrame from a JSON-decoded dict."""
        return cls(
            header=FrameHeader.from_json_dict(data["header"]),
            method=data["method"],
            model=data["model"],
            messages=list(data.get("messages", [])),
            qos_class=data.get("qos_class", "standard"),
            capabilities=list(data.get("capabilities", []) or []),
            client_id=data.get("client_id"),
            nonce=data.get("nonce"),
        )


@dataclass
class IRPResponseFrame:
    """A response frame from provider to client."""

    header: FrameHeader
    request_id: str
    status: int  # 0 = success, non-zero = error code
    body: dict  # response body (e.g., chat completion choices)
    receipt: dict | None = None  # IRP receipt as dict; full Receipt schema in metering spec

    def to_json_dict(self) -> dict:
        """Serialize the frame to a JSON-safe dict."""
        return {
            "header": self.header.to_json_dict(),
            "request_id": self.request_id,
            "status": self.status,
            "body": self.body,
            "receipt": self.receipt,
        }

    @classmethod
    def from_json_dict(cls, data: dict) -> "IRPResponseFrame":
        """Construct an IRPResponseFrame from a JSON-decoded dict."""
        return cls(
            header=FrameHeader.from_json_dict(data["header"]),
            request_id=data["request_id"],
            status=int(data["status"]),
            body=dict(data.get("body") or {}),
            receipt=data.get("receipt"),
        )


def _serialize_body(frame: IRPRequestFrame | IRPResponseFrame) -> bytes:
    """Render a frame's JSON body as canonical UTF-8 bytes."""
    payload = frame.to_json_dict()
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def encode_frame_to_bytes(frame: IRPRequestFrame | IRPResponseFrame) -> bytes:
    """Encode frame as length-prefixed JSON: [4-byte big-endian length][JSON bytes]."""
    body = _serialize_body(frame)
    return struct.pack(_LENGTH_PREFIX, len(body)) + body


def decode_frame_from_bytes(
    raw: bytes, expected_type: type[IRPRequestFrame | IRPResponseFrame]
) -> IRPRequestFrame | IRPResponseFrame:
    """Inverse: parse length-prefixed JSON back to frame.

    Raises ValueError on malformed input (truncated buffer, invalid JSON,
    or a frame class that doesn't match ``expected_type``).
    """
    if not isinstance(raw, (bytes, bytearray)):
        raise ValueError("raw frame must be bytes")
    if len(raw) < _LENGTH_PREFIX_SIZE:
        raise ValueError("frame too short to contain length prefix")

    (declared_length,) = struct.unpack(_LENGTH_PREFIX, raw[:_LENGTH_PREFIX_SIZE])
    body = raw[_LENGTH_PREFIX_SIZE : _LENGTH_PREFIX_SIZE + declared_length]
    if len(body) < declared_length:
        raise ValueError(
            f"frame truncated: declared {declared_length} bytes, got {len(body)}"
        )

    try:
        data = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid JSON body: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("frame body must be a JSON object")

    if expected_type is IRPRequestFrame:
        return IRPRequestFrame.from_json_dict(data)
    if expected_type is IRPResponseFrame:
        return IRPResponseFrame.from_json_dict(data)
    raise ValueError(f"unsupported expected_type: {expected_type!r}")


def _header_to_http_headers(header: FrameHeader) -> dict[str, str]:
    """Map shared FrameHeader fields to X-IRP-* HTTP headers."""
    return {
        "X-IRP-Version": header.version,
        "X-IRP-Frame-Type": str(int(header.frame_type)),
        "X-IRP-Stream-Id": str(header.stream_id),
        "X-IRP-Flags": str(header.flags),
        "X-IRP-Length": str(header.length),
    }


def request_frame_to_http_headers(frame: IRPRequestFrame) -> dict[str, str]:
    """Map header fields to X-IRP-* HTTP headers (for HTTP/1.1+ transport)."""
    headers = _header_to_http_headers(frame.header)
    headers["X-IRP-Method"] = frame.method
    headers["X-IRP-Model"] = frame.model
    headers["X-IRP-QoS"] = frame.qos_class
    # CSV-encode capabilities so they survive HTTP/1.1 single-line headers.
    headers["X-IRP-Capabilities"] = ",".join(frame.capabilities)
    if frame.client_id is not None:
        headers["X-IRP-Client-Id"] = frame.client_id
    if frame.nonce is not None:
        headers["X-IRP-Nonce"] = frame.nonce
    return headers


def response_frame_to_http_headers(frame: IRPResponseFrame) -> dict[str, str]:
    """Map header fields to X-IRP-* HTTP headers."""
    headers = _header_to_http_headers(frame.header)
    headers["X-IRP-Request-Id"] = frame.request_id
    headers["X-IRP-Status"] = str(frame.status)
    if frame.receipt is not None:
        # Surface only that a receipt is attached; the receipt body itself
        # rides in the JSON payload, not in headers.
        headers["X-IRP-Receipt"] = "1"
    return headers


__all__ = [
    "IRP_VERSION",
    "FrameType",
    "FrameHeader",
    "IRPRequestFrame",
    "IRPResponseFrame",
    "encode_frame_to_bytes",
    "decode_frame_from_bytes",
    "request_frame_to_http_headers",
    "response_frame_to_http_headers",
]
