"""Tests for IRP frame schemas and wire-format encoding."""

import json
import struct

import pytest

from irp.frame import (
    FrameHeader,
    FrameType,
    IRPRequestFrame,
    IRPResponseFrame,
    decode_frame_from_bytes,
    encode_frame_to_bytes,
    request_frame_to_http_headers,
    response_frame_to_http_headers,
)


def _make_request_frame() -> IRPRequestFrame:
    return IRPRequestFrame(
        header=FrameHeader(
            version="0.1",
            frame_type=FrameType.REQUEST,
            stream_id=7,
            flags=0,
            length=0,
        ),
        method="chat.completions",
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello!"},
        ],
        qos_class="standard",
        capabilities=["streaming", "tool_use"],
        client_id="client-abc",
        nonce="nonce-xyz",
    )


def _make_response_frame(with_receipt: bool = False) -> IRPResponseFrame:
    return IRPResponseFrame(
        header=FrameHeader(
            version="0.1",
            frame_type=FrameType.RESPONSE,
            stream_id=7,
        ),
        request_id="req-123",
        status=0,
        body={
            "choices": [
                {"index": 0, "message": {"role": "assistant", "content": "Hi!"}}
            ]
        },
        receipt={"request_id": "req-123", "input_tokens": 10} if with_receipt else None,
    )


def test_frame_type_values():
    assert FrameType.REQUEST == 1
    assert FrameType.RESPONSE == 2
    assert FrameType.RECEIPT == 3
    assert FrameType.ERROR == 4
    assert FrameType.PING == 5
    assert FrameType.PONG == 6


def test_irp_request_frame_to_json_roundtrip():
    frame = _make_request_frame()
    data = frame.to_json_dict()

    # Sanity: dict is JSON-serializable.
    json.dumps(data)

    rebuilt = IRPRequestFrame.from_json_dict(data)
    assert rebuilt == frame


def test_irp_response_frame_to_json_roundtrip():
    frame = _make_response_frame(with_receipt=True)
    data = frame.to_json_dict()

    json.dumps(data)

    rebuilt = IRPResponseFrame.from_json_dict(data)
    assert rebuilt == frame


def test_encode_frame_to_bytes_length_prefix():
    frame = _make_request_frame()
    encoded = encode_frame_to_bytes(frame)

    assert len(encoded) >= 4
    (declared_length,) = struct.unpack(">I", encoded[:4])
    body = encoded[4:]
    assert declared_length == len(body)

    # Body must round-trip through JSON.
    parsed = json.loads(body.decode("utf-8"))
    assert parsed["method"] == "chat.completions"
    # The length field in the header is informational; the length prefix is the
    # authoritative source of the body size.


@pytest.mark.parametrize(
    "factory, frame_cls",
    [
        (_make_request_frame, IRPRequestFrame),
        (lambda: _make_response_frame(with_receipt=True), IRPResponseFrame),
        (lambda: _make_response_frame(with_receipt=False), IRPResponseFrame),
    ],
)
def test_decode_frame_from_bytes(factory, frame_cls):
    frame = factory()
    encoded = encode_frame_to_bytes(frame)
    decoded = decode_frame_from_bytes(encoded, frame_cls)

    assert isinstance(decoded, frame_cls)
    assert decoded == frame


def test_decode_frame_truncated_raises():
    frame = _make_request_frame()
    encoded = encode_frame_to_bytes(frame)

    truncated = encoded[: len(encoded) - 5]
    with pytest.raises(ValueError):
        decode_frame_from_bytes(truncated, IRPRequestFrame)


def test_decode_frame_too_short_for_prefix_raises():
    with pytest.raises(ValueError):
        decode_frame_from_bytes(b"\x00", IRPRequestFrame)


def test_decode_frame_invalid_json_raises():
    body = b"not-a-json-object"
    raw = struct.pack(">I", len(body)) + body
    with pytest.raises(ValueError):
        decode_frame_from_bytes(raw, IRPRequestFrame)


def test_decode_frame_non_object_json_raises():
    body = b"[1, 2, 3]"
    raw = struct.pack(">I", len(body)) + body
    with pytest.raises(ValueError):
        decode_frame_from_bytes(raw, IRPRequestFrame)


def test_request_frame_to_http_headers():
    frame = _make_request_frame()
    headers = request_frame_to_http_headers(frame)

    assert headers["X-IRP-Version"] == "0.1"
    assert headers["X-IRP-Frame-Type"] == str(int(FrameType.REQUEST))
    assert headers["X-IRP-Stream-Id"] == "7"
    assert headers["X-IRP-QoS"] == "standard"
    assert headers["X-IRP-Method"] == "chat.completions"
    assert headers["X-IRP-Model"] == "gpt-4o-mini"
    # Capabilities serialize as CSV.
    assert headers["X-IRP-Capabilities"] == "streaming,tool_use"
    assert headers["X-IRP-Client-Id"] == "client-abc"
    assert headers["X-IRP-Nonce"] == "nonce-xyz"


def test_request_frame_headers_omit_optional_when_unset():
    frame = _make_request_frame()
    frame.client_id = None
    frame.nonce = None
    frame.capabilities = []

    headers = request_frame_to_http_headers(frame)
    assert headers["X-IRP-Capabilities"] == ""
    assert "X-IRP-Client-Id" not in headers
    assert "X-IRP-Nonce" not in headers


def test_response_frame_to_http_headers():
    frame = _make_response_frame(with_receipt=True)
    headers = response_frame_to_http_headers(frame)

    assert headers["X-IRP-Version"] == "0.1"
    assert headers["X-IRP-Frame-Type"] == str(int(FrameType.RESPONSE))
    assert headers["X-IRP-Request-Id"] == "req-123"
    assert headers["X-IRP-Status"] == "0"
    assert headers["X-IRP-Receipt"] == "1"


def test_response_frame_headers_without_receipt():
    frame = _make_response_frame(with_receipt=False)
    headers = response_frame_to_http_headers(frame)

    assert "X-IRP-Receipt" not in headers
    assert headers["X-IRP-Status"] == "0"
