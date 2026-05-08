"""
Inference Receipt Protocol (IRP) v0.1

A protocol for verifiable AI inference billing.

Provides client-side verification of inference receipts including:
- Token count validation
- Digital signature verification
- Latency metrics
- Audit logging
"""

from .models import Receipt, VerificationResult, LatencyMetrics
from .receipt import ReceiptVerifier
from .client import IRPClient

__version__ = "0.1.0"
__all__ = [
    "Receipt",
    "VerificationResult",
    "LatencyMetrics",
    "ReceiptVerifier",
    "IRPClient",
]
