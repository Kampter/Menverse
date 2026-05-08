"""Tests for IRP handshake (capability negotiation)."""

import pytest

from irp.handshake import (
    HandshakeRequest,
    HandshakeResponse,
    _version_tuple,
    decode_handshake_headers,
    encode_handshake_headers,
    negotiate,
)


class TestNegotiate:
    """Negotiation between client and provider."""

    def test_negotiate_compatible_versions(self):
        """Server picks the highest version both parties support."""
        request = HandshakeRequest(
            client_irp_version="0.1.0",
            client_supported_versions=["0.1.0", "0.2.0", "1.0.0"],
            desired_capabilities=["irp.metering.token-count.v1"],
        )

        response = negotiate(
            request=request,
            server_supported_versions=["0.1.0", "0.2.0"],
            server_capabilities=["irp.metering.token-count.v1"],
            server_public_key_kid="kid-1",
        )

        assert response.error is None
        assert response.server_irp_version == "0.2.0"
        assert response.public_key_kid == "kid-1"
        assert response.accepted_capabilities == ["irp.metering.token-count.v1"]
        assert response.rejected_capabilities == []

    def test_negotiate_no_common_version(self):
        """When no overlap, response carries the documented error sentinel."""
        request = HandshakeRequest(
            client_irp_version="2.0.0",
            client_supported_versions=["2.0.0"],
            desired_capabilities=["irp.metering.token-count.v1"],
        )

        response = negotiate(
            request=request,
            server_supported_versions=["0.1.0", "0.2.0"],
            server_capabilities=["irp.metering.token-count.v1"],
            server_public_key_kid="kid-1",
        )

        assert response.error == "no compatible version"
        assert response.server_irp_version == ""
        assert response.accepted_capabilities == []

    def test_negotiate_capabilities_intersection(self):
        """Accepted = intersection; rejected = client-asked but server-unsupported."""
        request = HandshakeRequest(
            client_irp_version="0.1.0",
            client_supported_versions=["0.1.0"],
            desired_capabilities=[
                "irp.metering.token-count.v1",
                "irp.audit.merkle.v1",
                "irp.experimental.zk.v1",
            ],
        )

        response = negotiate(
            request=request,
            server_supported_versions=["0.1.0"],
            server_capabilities=[
                "irp.metering.token-count.v1",
                "irp.audit.merkle.v1",
                "irp.something.else.v1",
            ],
            server_public_key_kid="kid-2",
        )

        assert response.error is None
        assert response.accepted_capabilities == [
            "irp.metering.token-count.v1",
            "irp.audit.merkle.v1",
        ]
        assert response.rejected_capabilities == ["irp.experimental.zk.v1"]

    def test_negotiate_empty_desired_capabilities(self):
        """A client with no desired capabilities gets empty accepted/rejected lists."""
        request = HandshakeRequest(
            client_irp_version="0.1.0",
            client_supported_versions=["0.1.0"],
            desired_capabilities=[],
        )

        response = negotiate(
            request=request,
            server_supported_versions=["0.1.0"],
            server_capabilities=["irp.metering.token-count.v1"],
            server_public_key_kid="kid-3",
        )

        assert response.error is None
        assert response.server_irp_version == "0.1.0"
        assert response.accepted_capabilities == []
        assert response.rejected_capabilities == []


class TestHandshakeHeaders:
    """HTTP header (de)serialization."""

    def test_encode_decode_handshake_headers_roundtrip(self):
        """encode then decode reproduces the original request."""
        original = HandshakeRequest(
            client_irp_version="0.1.0",
            client_supported_versions=["0.1.0", "0.2.0"],
            desired_capabilities=[
                "irp.metering.token-count.v1",
                "irp.audit.merkle.v1",
            ],
            client_id="client-abc",
        )

        headers = encode_handshake_headers(original)
        decoded = decode_handshake_headers(headers)

        assert decoded == original

    def test_encode_omits_client_id_when_none(self):
        """X-IRP-Client-Id is absent when client_id is not set."""
        request = HandshakeRequest(
            client_irp_version="0.1.0",
            client_supported_versions=["0.1.0"],
            desired_capabilities=["irp.metering.token-count.v1"],
            client_id=None,
        )

        headers = encode_handshake_headers(request)

        assert "X-IRP-Client-Id" not in headers
        assert headers["X-IRP-Version"] == "0.1.0"
        assert headers["X-IRP-Versions-Supported"] == "0.1.0"
        assert headers["X-IRP-Capabilities"] == "irp.metering.token-count.v1"

    def test_decode_handshake_headers_missing_required(self):
        """A missing required header raises ValueError."""
        # Missing X-IRP-Version
        with pytest.raises(ValueError):
            decode_handshake_headers(
                {
                    "X-IRP-Versions-Supported": "0.1.0",
                    "X-IRP-Capabilities": "irp.metering.token-count.v1",
                }
            )

        # Missing X-IRP-Versions-Supported
        with pytest.raises(ValueError):
            decode_handshake_headers(
                {
                    "X-IRP-Version": "0.1.0",
                    "X-IRP-Capabilities": "irp.metering.token-count.v1",
                }
            )

        # Missing X-IRP-Capabilities
        with pytest.raises(ValueError):
            decode_handshake_headers(
                {
                    "X-IRP-Version": "0.1.0",
                    "X-IRP-Versions-Supported": "0.1.0",
                }
            )


class TestVersionTupleHelper:
    """The internal _version_tuple semver helper."""

    def test_version_tuple_helper(self):
        assert _version_tuple("1.2.3") == (1, 2, 3)
        assert _version_tuple("0.1.0") == (0, 1, 0)
        assert _version_tuple("10.20.30") == (10, 20, 30)

        # Reject incomplete versions.
        with pytest.raises(ValueError):
            _version_tuple("1.2")

        # Reject non-numeric components.
        with pytest.raises(ValueError):
            _version_tuple("1.2.x")

        # Reject empty input.
        with pytest.raises(ValueError):
            _version_tuple("")
