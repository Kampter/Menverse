"""Tests for the IRP reference server skeleton."""

from __future__ import annotations

import base64
import json
import threading
import time

import httpx
import pytest
from nacl.signing import VerifyKey

from irp.server_ref import IRPReferenceServer, ServerConfig


@pytest.fixture
def server():
    """Spin up the reference server on a free port, yield base URL, then shut down."""
    config = ServerConfig(bind_host="127.0.0.1", bind_port=0)
    srv = IRPReferenceServer(config)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    # Give the server a moment to start listening
    time.sleep(0.1)
    base_url = f"http://127.0.0.1:{srv.actual_port}"
    yield base_url
    srv.shutdown()
    thread.join(timeout=2)


def test_discovery_endpoint(server):
    """GET .well-known/irp-configuration returns 200 + valid JSON."""
    r = httpx.get(f"{server}/.well-known/irp-configuration")
    assert r.status_code == 200
    data = r.json()
    assert data["issuer"] == "https://reference.irp.example"
    assert "irp.metering.token-count.v1" in data["capabilities"]
    assert "public_keys" in data
    assert len(data["public_keys"]) >= 1
    pk = data["public_keys"][0]
    assert pk["kid"] == "ref-1"
    assert pk["alg"] == "ed25519"
    assert pk["key_b64"]


def test_chat_completions_returns_irp_headers(server):
    """POST /v1/chat/completions returns 200 with IRP headers."""
    payload = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": "Hello"}],
    }
    r = httpx.post(f"{server}/v1/chat/completions", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert "choices" in body
    assert body["choices"][0]["message"]["role"] == "assistant"

    headers = r.headers
    assert "x-irp-request-id" in headers
    assert "x-irp-signature" in headers
    assert "x-irp-public-key" in headers
    assert headers["x-irp-version"] == "0.1.0"
    assert headers["x-irp-provider"] == "reference.irp.example"
    assert headers["x-irp-model"] == "gpt-4o-mini"


def test_chat_completions_signature_verifies(server):
    """Build canonical receipt from headers and verify Ed25519 signature."""
    payload = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": "Hello"}],
    }
    r = httpx.post(f"{server}/v1/chat/completions", json=payload)
    assert r.status_code == 200

    h = r.headers
    public_key_b64 = h["x-irp-public-key"]
    signature_b64 = h["x-irp-signature"]

    receipt_data = {
        "request_id": h["x-irp-request-id"],
        "timestamp": h["x-irp-timestamp"],
        "provider": h["x-irp-provider"],
        "model": h["x-irp-model"],
        "input_tokens": int(h["x-irp-input-tokens"]),
        "output_tokens": int(h["x-irp-output-tokens"]),
        "total_tokens": int(h["x-irp-total-tokens"]),
    }
    canonical = json.dumps(receipt_data, sort_keys=True, separators=(",", ":"))
    message = canonical.encode("utf-8")
    signature = base64.b64decode(signature_b64)

    verify_key = VerifyKey(base64.b64decode(public_key_b64))
    verify_key.verify(message, signature)  # raises BadSignatureError on failure


def test_log_root_endpoint(server):
    """GET /v1/irp/log/root returns 200 + JSON matching spec format."""
    r = httpx.get(f"{server}/v1/irp/log/root")
    assert r.status_code == 200
    data = r.json()
    assert "root_hash" in data
    assert "tree_size" in data
    assert "timestamp" in data
    assert "signature" in data
    assert "public_key" in data
    assert "signature_alg" in data


def test_log_proof_unknown_id(server):
    """GET /v1/irp/log/proof?request_id=unknown returns 404."""
    r = httpx.get(f"{server}/v1/irp/log/proof?request_id=unknown")
    assert r.status_code == 404


def test_uses_deterministic_seed_when_provided():
    """With the same deterministic seed, two server instances share the same public key."""
    seed = b"\x00" * 32
    config1 = ServerConfig(bind_host="127.0.0.1", bind_port=0, deterministic_seed=seed)
    config2 = ServerConfig(bind_host="127.0.0.1", bind_port=0, deterministic_seed=seed)

    srv1 = IRPReferenceServer(config1)
    srv2 = IRPReferenceServer(config2)

    # Fetch public key from discovery endpoint for each server
    thread1 = threading.Thread(target=srv1.serve_forever, daemon=True)
    thread2 = threading.Thread(target=srv2.serve_forever, daemon=True)
    thread1.start()
    thread2.start()
    time.sleep(0.1)

    try:
        url1 = f"http://127.0.0.1:{srv1.actual_port}"
        url2 = f"http://127.0.0.1:{srv2.actual_port}"

        r1 = httpx.get(f"{url1}/.well-known/irp-configuration")
        r2 = httpx.get(f"{url2}/.well-known/irp-configuration")

        pk1 = r1.json()["public_keys"][0]["key_b64"]
        pk2 = r2.json()["public_keys"][0]["key_b64"]
        assert pk1 == pk2
    finally:
        srv1.shutdown()
        srv2.shutdown()
        thread1.join(timeout=2)
        thread2.join(timeout=2)
