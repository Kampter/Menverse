"""
Inference Receipt Protocol (IRP) v0.1

A protocol for verifiable AI inference billing.

Provides client-side verification of inference receipts including:
- Token count validation
- Digital signature verification
- Latency metrics
- Audit logging
- Wire-format frame schemas
"""

from .models import Receipt, VerificationResult, LatencyMetrics, generate_nonce
from .receipt import ReceiptValidator
from .client import IRPClient
from .discovery import CapabilityAdvertisement, IRPDiscovery
from .qos import QoSClass, QoSParameters, QOS_PARAMETERS, select_qos, parse_qos_class
from .errors import IRPError, IRPErrorCode, ERROR_HTTP_STATUS, code_from_int
from .version import (
    LifecycleStatus,
    ProtocolVersion,
    VersionEntry,
    is_removed,
    negotiate,
    supported_versions,
)
from .frame import (
    IRP_VERSION,
    FrameType,
    FrameHeader,
    IRPRequestFrame,
    IRPResponseFrame,
    encode_frame_to_bytes,
    decode_frame_from_bytes,
    request_frame_to_http_headers,
    response_frame_to_http_headers,
)
from .signer import build_canonical_dict

__version__ = "0.1.1"
__all__ = [
    "Receipt",
    "VerificationResult",
    "LatencyMetrics",
    "ReceiptValidator",
    "IRPClient",
    "CapabilityAdvertisement",
    "IRPDiscovery",
    "QoSClass",
    "QoSParameters",
    "QOS_PARAMETERS",
    "select_qos",
    "parse_qos_class",
    "IRPError",
    "IRPErrorCode",
    "ERROR_HTTP_STATUS",
    "code_from_int",
    "LifecycleStatus",
    "ProtocolVersion",
    "VersionEntry",
    "is_removed",
    "negotiate",
    "supported_versions",
    "IRP_VERSION",
    "FrameType",
    "FrameHeader",
    "IRPRequestFrame",
    "IRPResponseFrame",
    "encode_frame_to_bytes",
    "decode_frame_from_bytes",
    "request_frame_to_http_headers",
    "response_frame_to_http_headers",
    "generate_nonce",
    "build_canonical_dict",
]
