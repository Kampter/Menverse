"""
Inference Receipt Protocol (IRP) v0.1

A protocol for verifiable AI inference billing.

Provides client-side verification of inference receipts including:
- Token count validation
- Digital signature verification
- Latency metrics
- Audit logging
"""

from .models import Receipt, VerificationResult, LatencyMetrics, generate_nonce
from .receipt import ReceiptValidator
from .signer import build_canonical_dict
from .client import IRPClient

__version__ = "0.1.1"
__all__ = [
    "Receipt",
    "VerificationResult",
    "LatencyMetrics",
    "ReceiptValidator",
    "IRPClient",
    "generate_nonce",
    "build_canonical_dict",
]
