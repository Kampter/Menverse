"""Data models for IRP (Inference Receipt Protocol)."""

import base64
import secrets
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


def generate_nonce() -> str:
    """Generate a 128-bit random nonce, base64-encoded (22 chars, no padding)."""
    return base64.b64encode(secrets.token_bytes(16)).decode("ascii").rstrip("=")


@dataclass
class LatencyMetrics:
    """Latency breakdown for an inference request."""

    queue_ms: float = 0.0
    time_to_first_token_ms: float = 0.0
    time_per_output_token_ms: float = 0.0
    total_ms: float = 0.0

    def __repr__(self) -> str:
        return (
            f"Latency(queue={self.queue_ms:.1f}ms, "
            f"ttft={self.time_to_first_token_ms:.1f}ms, "
            f"tput={self.time_per_output_token_ms:.1f}ms, "
            f"total={self.total_ms:.1f}ms)"
        )


@dataclass
class Receipt:
    """An inference receipt returned by the provider."""

    request_id: str
    timestamp: str
    provider: str
    model: str
    model_version: Optional[str] = None

    # Token counts as reported by the provider
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: Optional[int] = None
    cached_tokens: Optional[int] = None
    total_tokens: int = 0

    # Latency metrics
    latency: LatencyMetrics = field(default_factory=LatencyMetrics)

    # Cost information
    cost_currency: str = "USD"
    cost_input: float = 0.0
    cost_output: float = 0.0
    cost_total: float = 0.0

    # Cryptographic proof
    signature: str = ""
    public_key: str = ""

    # Raw content hashes for verification
    input_hash: Optional[str] = None
    output_hash: Optional[str] = None

    # IRP protocol metadata
    nonce: str = ""
    version: str = "0.1.0"
    policy_id: Optional[str] = None

    def __post_init__(self):
        if self.total_tokens == 0:
            self.total_tokens = self.input_tokens + self.output_tokens


@dataclass
class VerificationResult:
    """Result of client-side verification of a receipt."""

    request_id: str
    is_valid: bool = False

    # Token count verification
    server_input_tokens: int = 0
    local_input_tokens: int = 0
    input_diff: int = 0
    input_diff_percent: float = 0.0

    server_output_tokens: int = 0
    local_output_tokens: int = 0
    output_diff: int = 0
    output_diff_percent: float = 0.0

    # Signature verification
    signature_valid: bool = False
    signature_error: Optional[str] = None

    # Threshold check
    within_threshold: bool = False
    threshold_percent: float = 5.0

    # Overall status
    status: str = "unknown"  # "valid", "warning", "error"
    errors: list = field(default_factory=list)

    def __repr__(self) -> str:
        return (
            f"VerificationResult(request_id={self.request_id[:8]}..., "
            f"status={self.status}, "
            f"input_diff={self.input_diff_percent:.1f}%, "
            f"output_diff={self.output_diff_percent:.1f}%, "
            f"signature_valid={self.signature_valid})"
        )
