"""HTTP client with IRP receipt support."""

import json
import time
from typing import Optional, Dict, Any, List

import httpx

from .models import Receipt, LatencyMetrics
from .receipt import ReceiptValidator
from .signer import hash_content


class IRPClient:
    """
    A client that wraps OpenAI-compatible APIs with IRP receipt support.

    Usage:
        client = IRPClient(
            base_url="https://api.together.ai",
            api_key="your-key",
            provider_public_key="base64-key",
        )

        response = client.chat.completions.create(
            model="meta-llama/Llama-3-8B",
            messages=[{"role": "user", "content": "Hello"}],
        )

        # Access receipt
        print(response.irp_receipt)
        print(response.irp_verification)
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        provider_public_key: Optional[str] = None,
        verify_receipts: bool = True,
        threshold_percent: float = 5.0,
        timeout: float = 120.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.verify_receipts = verify_receipts
        self.threshold_percent = threshold_percent

        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )

        self._validator: Optional[ReceiptValidator] = None
        if provider_public_key and verify_receipts:
            self._validator = ReceiptValidator(
                provider_public_key=provider_public_key,
                threshold_percent=threshold_percent,
            )

    def _extract_receipt_from_headers(
        self, headers: httpx.Headers, request_body: dict
    ) -> Optional[Receipt]:
        """Extract IRP receipt from HTTP response headers."""
        # Look for IRP headers
        receipt_id = headers.get("x-irp-request-id")
        if not receipt_id:
            return None

        receipt = Receipt(
            request_id=receipt_id,
            timestamp=headers.get("x-irp-timestamp", ""),
            provider=headers.get("x-irp-provider", "unknown"),
            model=headers.get("x-irp-model", request_body.get("model", "unknown")),
            model_version=headers.get("x-irp-model-version"),
            input_tokens=int(headers.get("x-irp-input-tokens", "0")),
            output_tokens=int(headers.get("x-irp-output-tokens", "0")),
            total_tokens=int(headers.get("x-irp-total-tokens", "0")),
            reasoning_tokens=_parse_optional_int(headers.get("x-irp-reasoning-tokens")),
            cached_tokens=_parse_optional_int(headers.get("x-irp-cached-tokens")),
            signature=headers.get("x-irp-signature", ""),
            public_key=headers.get("x-irp-public-key", ""),
            cost_currency=headers.get("x-irp-cost-currency", "USD"),
            cost_total=float(headers.get("x-irp-cost-total", "0")),
        )

        # Parse latency headers
        latency = LatencyMetrics()
        if headers.get("x-irp-latency-total"):
            latency.total_ms = float(headers["x-irp-latency-total"])
        if headers.get("x-irp-latency-ttft"):
            latency.time_to_first_token_ms = float(headers["x-irp-latency-ttft"])
        receipt.latency = latency

        return receipt

    def _build_irp_headers(self, request_body: dict) -> Dict[str, str]:
        """Build request headers that ask for IRP receipt."""
        headers = {
            "x-irp-request": "true",
            "x-irp-version": "0.1.0",
        }
        return headers

    def _make_request(
        self,
        method: str,
        path: str,
        json_body: Optional[dict] = None,
    ) -> "IRPResponse":
        """Make an HTTP request and return IRP-enhanced response."""
        start_time = time.time()

        extra_headers = {}
        if json_body:
            extra_headers.update(self._build_irp_headers(json_body))

        response = self._client.request(
            method=method,
            url=path,
            json=json_body,
            headers=extra_headers,
        )
        response.raise_for_status()

        elapsed_ms = (time.time() - start_time) * 1000

        data = response.json()

        # Try to extract receipt from headers first
        receipt = None
        if json_body:
            receipt = self._extract_receipt_from_headers(response.headers, json_body)

        # If no IRP headers, try to build receipt from response body
        if not receipt:
            receipt = self._build_receipt_from_response(data, elapsed_ms)

        # Create IRP response
        irp_response = IRPResponse(data, receipt)

        # Verify if enabled
        if self._validator and receipt and json_body:
            messages = json_body.get("messages", [])
            output_text = irp_response.get_output_text()

            irp_response.irp_verification = self._validator.verify(
                receipt=receipt,
                local_messages=messages if messages else None,
                local_output_text=output_text,
            )

        return irp_response

    def _build_receipt_from_response(
        self, data: dict, elapsed_ms: float
    ) -> Receipt:
        """Build a best-effort receipt from standard OpenAI response format."""
        usage = data.get("usage", {})

        receipt = Receipt(
            request_id=data.get("id", ""),
            timestamp="",
            provider="unknown",
            model=data.get("model", "unknown"),
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            latency=LatencyMetrics(total_ms=elapsed_ms),
        )
        return receipt

    @property
    def chat(self) -> "ChatCompletions":
        """Access chat completions API."""
        return ChatCompletions(self)

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class ChatCompletions:
    """Wrapper for chat completions endpoint."""

    def __init__(self, client: IRPClient):
        self._client = client

    def create(self, **kwargs) -> "IRPResponse":
        """Create a chat completion with IRP support."""
        return self._client._make_request(
            method="POST",
            path="/v1/chat/completions",
            json_body=kwargs,
        )


class IRPResponse:
    """
    Response object that wraps the API response with IRP metadata.

    Provides both standard API response access and IRP-specific attributes.
    """

    def __init__(self, data: dict, receipt: Optional[Receipt] = None):
        self._data = data
        self.irp_receipt = receipt
        self.irp_verification: Optional[Any] = None

    def __getitem__(self, key: str):
        return self._data[key]

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    @property
    def choices(self) -> List[dict]:
        return self._data.get("choices", [])

    @property
    def usage(self) -> dict:
        return self._data.get("usage", {})

    @property
    def model(self) -> str:
        return self._data.get("model", "")

    @property
    def id(self) -> str:
        return self._data.get("id", "")

    def get_output_text(self) -> str:
        """Extract output text from response."""
        texts = []
        for choice in self.choices:
            message = choice.get("message", {})
            content = message.get("content", "")
            if content:
                texts.append(content)
        return "\n".join(texts)

    def to_dict(self) -> dict:
        """Return the raw response data."""
        return self._data

    def __repr__(self) -> str:
        parts = [f"IRPResponse(model={self.model!r})"]
        if self.irp_receipt:
            parts.append(f"tokens={self.irp_receipt.total_tokens}")
        if self.irp_verification:
            parts.append(f"status={self.irp_verification.status}")
        return f"<{', '.join(parts)}>"


def _parse_optional_int(value: Optional[str]) -> Optional[int]:
    """Parse an optional header value as int, returning None if missing or empty."""
    if value is None or value == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None
