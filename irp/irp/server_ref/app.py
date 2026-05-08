"""IRP reference server skeleton — stdlib-only HTTP server.

This is a SKELETON implementation for demonstration and protocol validation.
It does NOT call any real AI model.  All chat-completion responses are canned.
The Ed25519 signing key is fixed per-process (deterministic when a seed is
supplied, otherwise generated at startup).  This is dev-only — a production
server must use a proper key-management system.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from irp.signer import ReceiptSigner


@dataclass
class ServerConfig:
    """Configuration for the IRP reference server."""

    bind_host: str = "127.0.0.1"
    bind_port: int = 8765
    issuer: str = "https://reference.irp.example"
    deterministic_seed: bytes | None = None  # for testing; dev-only


DEFAULT_ROUTES = {
    "GET /.well-known/irp-configuration": "_handle_discovery",
    "POST /v1/chat/completions": "_handle_chat",
    "GET /v1/irp/log/root": "_handle_log_root",
    "GET /v1/irp/log/proof": "_handle_log_proof",
}


def _approximate_token_count(text: str) -> int:
    """Rough token count: ~4 chars per token for English-ish text."""
    return max(1, len(text) // 4)


def make_handler(config: ServerConfig) -> type[BaseHTTPRequestHandler]:
    """Build an http.server BaseHTTPRequestHandler subclass bound to *config*."""

    signer = ReceiptSigner(config.deterministic_seed)
    public_key_b64 = signer.public_key

    # Print public key on startup (requirement)
    print(f"[IRPReferenceServer] Public key (base64): {public_key_b64}")

    class _Handler(BaseHTTPRequestHandler):
        # Silence default request logging to stderr
        def log_message(self, _format: str, *args) -> None:  # noqa: ARG002
            pass

        def do_GET(self) -> None:  # noqa: N802
            self._route("GET")

        def do_POST(self) -> None:  # noqa: N802
            self._route("POST")

        def _route(self, method: str) -> None:
            parsed = urlparse(self.path)
            route_key = f"{method} {parsed.path}"
            handler_name = DEFAULT_ROUTES.get(route_key)
            if handler_name is None:
                self._send_json(404, {"error": "not found"})
                return
            getattr(self, handler_name)(parsed)

        def _read_body(self) -> bytes:
            length = self.headers.get("Content-Length")
            if length is None:
                return b""
            return self.rfile.read(int(length))

        def _send_json(self, status: int, data: dict) -> None:
            body = json.dumps(data).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        # ------------------------------------------------------------------
        # Discovery
        # ------------------------------------------------------------------
        def _handle_discovery(self, _parsed: urlparse) -> None:
            self._send_json(
                200,
                {
                    "issuer": config.issuer,
                    "irp_versions_supported": ["0.1.0"],
                    "capabilities": [
                        "irp.metering.token-count.v1",
                        "irp.audit.merkle.v1",
                        "irp.qos.5class.v1",
                        "irp.auth.bearer",
                    ],
                    "endpoints": {
                        "chat_completions": "/v1/chat/completions",
                        "log_root": "/v1/irp/log/root",
                        "log_proof": "/v1/irp/log/proof",
                    },
                    "qos_classes_supported": ["standard", "interactive"],
                    "public_keys": [
                        {
                            "kid": "ref-1",
                            "alg": "ed25519",
                            "key_b64": public_key_b64,
                        }
                    ],
                },
            )

        # ------------------------------------------------------------------
        # Chat completions (canned)
        # ------------------------------------------------------------------
        def _handle_chat(self, _parsed: urlparse) -> None:
            body_bytes = self._read_body()
            try:
                body = json.loads(body_bytes) if body_bytes else {}
            except json.JSONDecodeError:
                body = {}

            model = body.get("model", "unknown")
            messages = body.get("messages", [])
            input_text = ""
            for msg in messages:
                content = msg.get("content", "")
                if isinstance(content, str):
                    input_text += content

            input_tokens = _approximate_token_count(input_text)
            output_tokens = 12
            total_tokens = input_tokens + output_tokens

            request_id = str(uuid.uuid4())
            timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            provider = "reference.irp.example"

            # Minimal receipt: only the 7 mandatory fields per irp-core.md §6.4.
            # A production server should also include nonce, version, input_hash,
            # output_hash, latency, cost, and signature_alg per irp-metering.md §4.1.
            receipt_data = {
                "request_id": request_id,
                "timestamp": timestamp,
                "provider": provider,
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
            }
            signature_b64 = signer.sign_receipt(receipt_data)

            response_body = {
                "id": f"chatcmpl-ref-{uuid.uuid4().hex[:12]}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "This is the IRP reference server responding.",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": input_tokens,
                    "completion_tokens": output_tokens,
                    "total_tokens": total_tokens,
                },
            }

            resp_bytes = json.dumps(response_body).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(resp_bytes)))
            self.send_header("X-IRP-Version", "0.1.0")
            self.send_header("X-IRP-Request-Id", request_id)
            self.send_header("X-IRP-Timestamp", timestamp)
            self.send_header("X-IRP-Provider", provider)
            self.send_header("X-IRP-Model", model)
            self.send_header("X-IRP-Input-Tokens", str(input_tokens))
            self.send_header("X-IRP-Output-Tokens", str(output_tokens))
            self.send_header("X-IRP-Total-Tokens", str(total_tokens))
            self.send_header("X-IRP-Signature", signature_b64)
            self.send_header("X-IRP-Public-Key", public_key_b64)
            self.end_headers()
            self.wfile.write(resp_bytes)

        # ------------------------------------------------------------------
        # Log root (skeleton)
        # ------------------------------------------------------------------
        def _handle_log_root(self, _parsed: urlparse) -> None:
            # Per irp-metering.md §8.3 root publication format.
            self._send_json(
                200,
                {
                    "tree_size": 0,
                    "root_hash": "0" * 64,
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "signature": "0" * 128,
                    "public_key": public_key_b64,
                    "signature_alg": "ed25519",
                },
            )

        # ------------------------------------------------------------------
        # Log proof (skeleton)
        # ------------------------------------------------------------------
        def _handle_log_proof(self, parsed: urlparse) -> None:
            params = parse_qs(parsed.query)
            request_id = params.get("request_id", [""])[0]
            if not request_id or request_id == "unknown":
                self._send_json(404, {"error": "proof not found"})
                return
            # Per irp-metering.md §8.4.2 proof response format.
            self._send_json(
                200,
                {
                    "request_id": request_id,
                    "tree_size": 0,
                    "leaf_index": 0,
                    "leaf_hash": "0" * 64,
                    "audit_path": ["0" * 64],
                    "root_hash": "0" * 64,
                },
            )

    return _Handler


class IRPReferenceServer:
    """Wraps an HTTPServer with the IRP reference handler."""

    def __init__(self, config: ServerConfig | None = None):
        self.config = config if config is not None else ServerConfig()
        handler_class = make_handler(self.config)
        self._server = HTTPServer(
            (self.config.bind_host, self.config.bind_port), handler_class
        )
        # If port was 0, read back the actual port
        self.actual_port: int = self._server.server_address[1]

    def serve_forever(self) -> None:
        """Start blocking serve loop."""
        self._server.serve_forever()

    def shutdown(self) -> None:
        """Stop the server."""
        self._server.shutdown()
