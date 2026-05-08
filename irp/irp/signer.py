"""Ed25519 digital signatures for receipt verification."""

import base64
import hashlib
import json
from typing import Optional, Tuple, Union

from nacl.signing import SigningKey, VerifyKey
from nacl.exceptions import BadSignatureError


def _canonical_json(data: dict) -> bytes:
    """Deterministic JSON serialization for signing."""
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _build_legacy_canonical_dict(receipt) -> dict:
    """Build the legacy 7-field canonical dict for backwards compatibility."""
    data = {
        "request_id": receipt.request_id,
        "timestamp": receipt.timestamp,
        "provider": receipt.provider,
        "model": receipt.model,
        "input_tokens": receipt.input_tokens,
        "output_tokens": receipt.output_tokens,
        "total_tokens": receipt.total_tokens,
    }
    if receipt.input_hash is not None:
        data["input_hash"] = receipt.input_hash
    if receipt.output_hash is not None:
        data["output_hash"] = receipt.output_hash
    return data


def build_canonical_dict(receipt) -> dict:
    """Build the canonical dict from a Receipt — excludes signature & public_key."""
    data = {
        "request_id": receipt.request_id,
        "timestamp": receipt.timestamp,
        "version": receipt.version,
        "provider": receipt.provider,
        "model": receipt.model,
        "input_tokens": receipt.input_tokens,
        "output_tokens": receipt.output_tokens,
        "total_tokens": receipt.total_tokens,
        "cost_currency": receipt.cost_currency,
        "cost_input": receipt.cost_input,
        "cost_output": receipt.cost_output,
        "cost_total": receipt.cost_total,
        "latency": {
            "queue_ms": receipt.latency.queue_ms,
            "time_to_first_token_ms": receipt.latency.time_to_first_token_ms,
            "time_per_output_token_ms": receipt.latency.time_per_output_token_ms,
            "total_ms": receipt.latency.total_ms,
        },
    }

    if receipt.nonce:
        data["nonce"] = receipt.nonce
    if receipt.model_version is not None:
        data["model_version"] = receipt.model_version
    if receipt.policy_id is not None:
        data["policy_id"] = receipt.policy_id
    if receipt.reasoning_tokens is not None:
        data["reasoning_tokens"] = receipt.reasoning_tokens
    if receipt.cached_tokens is not None:
        data["cached_tokens"] = receipt.cached_tokens
    if receipt.input_hash is not None:
        data["input_hash"] = receipt.input_hash
    if receipt.output_hash is not None:
        data["output_hash"] = receipt.output_hash

    return data


class ReceiptSigner:
    """Signs inference receipts with Ed25519."""

    def __init__(self, private_key: Optional[bytes] = None):
        if private_key:
            self._signing_key = SigningKey(private_key)
        else:
            self._signing_key = SigningKey.generate()
        self._verify_key = self._signing_key.verify_key

    @property
    def public_key(self) -> str:
        """Return base64-encoded public key."""
        return base64.b64encode(self._verify_key.encode()).decode("ascii")

    @property
    def private_key(self) -> str:
        """Return base64-encoded private key (for storage)."""
        return base64.b64encode(self._signing_key.encode()).decode("ascii")

    def sign(self, receipt) -> str:
        """Sign a Receipt object and return base64-encoded signature."""
        canonical_dict = build_canonical_dict(receipt)
        return self.sign_receipt(canonical_dict)

    def sign_receipt(self, receipt_data: Union[dict, "Receipt"]) -> str:
        """Sign receipt data and return base64-encoded signature.

        Accepts either a dict (legacy) or a Receipt object (new).
        """
        if hasattr(receipt_data, "request_id"):
            # It's a Receipt object
            receipt_data = build_canonical_dict(receipt_data)

        message = _canonical_json(receipt_data)
        signed = self._signing_key.sign(message)
        return base64.b64encode(signed.signature).decode("ascii")

    def verify(self, receipt_data: Union[dict, "Receipt"], signature_b64: str) -> bool:
        """Verify a signature against receipt data.

        Accepts either a dict (legacy) or a Receipt object (new).
        For Receipt objects, tries the new full canonical first, then
        falls back to the legacy 7-field canonical for backwards compatibility.
        """
        candidates = []
        if hasattr(receipt_data, "request_id"):
            candidates.append(build_canonical_dict(receipt_data))
            candidates.append(_build_legacy_canonical_dict(receipt_data))
        else:
            candidates.append(receipt_data)

        signature = base64.b64decode(signature_b64)
        for data in candidates:
            try:
                self._verify_key.verify(_canonical_json(data), signature)
                return True
            except (BadSignatureError, ValueError):
                pass
        return False


class ReceiptVerifier:
    """Verifies signatures using a provider's public key."""

    def __init__(self, public_key_b64: Optional[str] = None):
        self._verify_key: Optional[VerifyKey] = None
        if public_key_b64:
            self.set_public_key(public_key_b64)

    def set_public_key(self, public_key_b64: str) -> None:
        """Set the public key for verification."""
        key_bytes = base64.b64decode(public_key_b64)
        self._verify_key = VerifyKey(key_bytes)

    def verify(
        self,
        receipt_data: Union[dict, "Receipt"],
        signature_b64: str,
    ) -> Tuple[bool, Optional[str]]:
        """
        Verify a signature against receipt data.

        Accepts either a dict (legacy) or a Receipt object (new).
        For Receipt objects, tries the new full canonical first, then
        falls back to the legacy 7-field canonical for backwards compatibility.

        Returns (is_valid, error_message).
        """
        if self._verify_key is None:
            return False, "No public key configured"

        candidates = []
        if hasattr(receipt_data, "request_id"):
            # It's a Receipt — try new canonical first, then legacy
            candidates.append(build_canonical_dict(receipt_data))
            candidates.append(_build_legacy_canonical_dict(receipt_data))
        else:
            # It's a raw dict — use as-is (legacy call site)
            candidates.append(receipt_data)

        last_error = None
        signature = base64.b64decode(signature_b64)
        for data in candidates:
            try:
                self._verify_key.verify(_canonical_json(data), signature)
                return True, None
            except BadSignatureError:
                last_error = "Invalid signature: receipt data may have been tampered with"
            except ValueError as e:
                last_error = f"Signature decoding error: {e}"

        return False, last_error


def hash_content(content: str) -> str:
    """Hash content for integrity verification."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
