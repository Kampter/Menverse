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
from .receipt import ReceiptValidator
from .client import IRPClient
from .errors import IRPError, IRPErrorCode, ERROR_HTTP_STATUS, code_from_int

__version__ = "0.1.0"
__all__ = [
    "Receipt",
    "VerificationResult",
    "LatencyMetrics",
    "ReceiptValidator",
    "IRPClient",
    "IRPError",
    "IRPErrorCode",
    "ERROR_HTTP_STATUS",
    "code_from_int",
]
