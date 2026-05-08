"""IRP capability negotiation handshake.

Defines the request/response shape exchanged between an IRP-capable client and
provider when establishing a session, plus helpers to negotiate a compatible
protocol version and capability set, and to encode/decode the request as HTTP
headers (X-IRP-*).
"""

from dataclasses import dataclass, field
from typing import Optional


# Header names used to transport handshake fields over HTTP.
_HDR_VERSION = "X-IRP-Version"
_HDR_VERSIONS = "X-IRP-Versions-Supported"
_HDR_CAPABILITIES = "X-IRP-Capabilities"
_HDR_CLIENT_ID = "X-IRP-Client-Id"


@dataclass
class HandshakeRequest:
    """Initial client capability assertion in a request."""

    client_irp_version: str
    client_supported_versions: list[str]
    desired_capabilities: list[str]
    client_id: Optional[str] = None


@dataclass
class HandshakeResponse:
    """Provider's negotiated response."""

    server_irp_version: str
    accepted_capabilities: list[str] = field(default_factory=list)
    rejected_capabilities: list[str] = field(default_factory=list)
    public_key_kid: str = ""
    error: Optional[str] = None


def _version_tuple(version: str) -> tuple[int, ...]:
    """Convert a dotted semver-ish string to a tuple of ints.

    Requires exactly three numeric components (MAJOR.MINOR.PATCH). Raises
    ValueError on any other shape so callers can rely on a stable comparison
    key without pulling a semver dependency.
    """
    if not isinstance(version, str) or not version:
        raise ValueError(f"invalid version: {version!r}")

    parts = version.split(".")
    if len(parts) != 3:
        raise ValueError(
            f"invalid version {version!r}: expected MAJOR.MINOR.PATCH"
        )

    try:
        return tuple(int(p) for p in parts)
    except ValueError as exc:
        raise ValueError(f"invalid version {version!r}: non-integer component") from exc


def negotiate(
    request: HandshakeRequest,
    server_supported_versions: list[str],
    server_capabilities: list[str],
    server_public_key_kid: str,
) -> HandshakeResponse:
    """Compute the negotiated handshake response.

    - Selects highest mutually supported version (semver compare).
    - Capabilities = intersection(client.desired_capabilities, server_capabilities),
      preserving the client's requested order.
    - Returns ``HandshakeResponse`` with ``error="no compatible version"`` and
      ``server_irp_version=""`` if no version is shared.
    """
    common_versions = [
        v for v in server_supported_versions if v in request.client_supported_versions
    ]

    if not common_versions:
        return HandshakeResponse(
            server_irp_version="",
            accepted_capabilities=[],
            rejected_capabilities=list(request.desired_capabilities),
            public_key_kid=server_public_key_kid,
            error="no compatible version",
        )

    selected_version = max(common_versions, key=_version_tuple)

    server_cap_set = set(server_capabilities)
    accepted: list[str] = []
    rejected: list[str] = []
    for cap in request.desired_capabilities:
        if cap in server_cap_set:
            accepted.append(cap)
        else:
            rejected.append(cap)

    return HandshakeResponse(
        server_irp_version=selected_version,
        accepted_capabilities=accepted,
        rejected_capabilities=rejected,
        public_key_kid=server_public_key_kid,
        error=None,
    )


def encode_handshake_headers(req: HandshakeRequest) -> dict[str, str]:
    """Encode a handshake request as HTTP headers.

    Produces ``X-IRP-Version``, ``X-IRP-Versions-Supported`` (CSV),
    ``X-IRP-Capabilities`` (CSV), and optionally ``X-IRP-Client-Id``.
    """
    headers: dict[str, str] = {
        _HDR_VERSION: req.client_irp_version,
        _HDR_VERSIONS: ",".join(req.client_supported_versions),
        _HDR_CAPABILITIES: ",".join(req.desired_capabilities),
    }
    if req.client_id is not None:
        headers[_HDR_CLIENT_ID] = req.client_id
    return headers


def decode_handshake_headers(headers: dict[str, str]) -> HandshakeRequest:
    """Inverse of ``encode_handshake_headers``.

    Raises ``ValueError`` if a required header is missing.
    """
    missing = [h for h in (_HDR_VERSION, _HDR_VERSIONS, _HDR_CAPABILITIES) if h not in headers]
    if missing:
        raise ValueError(f"missing required handshake headers: {missing}")

    version = headers[_HDR_VERSION]
    supported = _split_csv(headers[_HDR_VERSIONS])
    capabilities = _split_csv(headers[_HDR_CAPABILITIES])
    client_id = headers.get(_HDR_CLIENT_ID)

    return HandshakeRequest(
        client_irp_version=version,
        client_supported_versions=supported,
        desired_capabilities=capabilities,
        client_id=client_id,
    )


def _split_csv(value: str) -> list[str]:
    """Split a CSV header value, trimming whitespace and dropping empty entries."""
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]
