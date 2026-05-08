"""
Inference Receipt Protocol (IRP) v0.1

A protocol for verifiable AI inference billing.

Provides client-side verification of inference receipts including:
- Token count validation
- Digital signature verification
- Latency metrics
- Audit logging
- QoS class negotiation
"""

from .models import Receipt, VerificationResult, LatencyMetrics
from .receipt import ReceiptValidator
from .client import IRPClient
from .qos import QoSClass, QoSParameters, QOS_PARAMETERS, select_qos, parse_qos_class

__version__ = "0.1.0"
__all__ = [
    "Receipt",
    "VerificationResult",
    "LatencyMetrics",
    "ReceiptValidator",
    "IRPClient",
    "QoSClass",
    "QoSParameters",
    "QOS_PARAMETERS",
    "select_qos",
    "parse_qos_class",
]
