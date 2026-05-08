"""Ed25519 digital signatures for receipt verification."""

import base64
import hashlib
import json
from typing import Optional, Tuple

from nacl.signing import SigningKey, VerifyKey
from nacl.exceptions import BadSignatureError


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

    def sign_receipt(self, receipt_data: dict) -> str:
        """Sign receipt data and return base64-encoded signature."""
        # Normalize: sort keys for deterministic serialization
        canonical = json.dumps(receipt_data, sort_keys=True, separators=(",", ":"))
        message = canonical.encode("utf-8")
        signed = self._signing_key.sign(message)
        return base64.b64encode(signed.signature).decode("ascii")

    def verify(self, receipt_data: dict, signature_b64: str) -> bool:
        """Verify a signature against receipt data."""
        try:
            canonical = json.dumps(receipt_data, sort_keys=True, separators=(",", ":"))
            message = canonical.encode("utf-8")
            signature = base64.b64decode(signature_b64)
            self._verify_key.verify(message, signature)
            return True
        except (BadSignatureError, ValueError):
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

    def verify(self, receipt_data: dict, signature_b64: str) -> Tuple[bool, Optional[str]]:
        """
        Verify a signature against receipt data.

        Returns (is_valid, error_message).
        """
        if self._verify_key is None:
            return False, "No public key configured"

        try:
            canonical = json.dumps(receipt_data, sort_keys=True, separators=(",", ":"))
            message = canonical.encode("utf-8")
            signature = base64.b64decode(signature_b64)
            self._verify_key.verify(message, signature)
            return True, None
        except BadSignatureError:
            return False, "Invalid signature: receipt data may have been tampered with"
        except ValueError as e:
            return False, f"Signature decoding error: {e}"


def hash_content(content: str) -> str:
    """Hash content for integrity verification."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
