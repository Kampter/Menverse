"""Tests for IRP service discovery."""

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from irp.discovery import CapabilityAdvertisement, IRPDiscovery


def _minimal_advertisement_dict() -> dict:
    """Return a minimal valid advertisement payload."""
    return {
        "issuer": "https://provider.example.com",
        "irp_versions_supported": ["0.1"],
        "capabilities": ["chat.completions", "receipts.v1"],
        "endpoints": {
            "chat_completions": "https://provider.example.com/v1/chat/completions",
        },
        "public_keys": [
            {"kid": "key-2026-01", "alg": "ed25519", "key_b64": "AAAA"},
        ],
    }


class TestCapabilityAdvertisement:
    """Test the CapabilityAdvertisement dataclass."""

    def test_capability_advertisement_from_dict_minimal(self):
        data = _minimal_advertisement_dict()
        ad = CapabilityAdvertisement.from_dict(data)

        assert ad.issuer == "https://provider.example.com"
        assert ad.irp_versions_supported == ["0.1"]
        assert "chat.completions" in ad.capabilities
        assert ad.endpoints["chat_completions"].endswith("/v1/chat/completions")
        assert ad.public_keys[0]["kid"] == "key-2026-01"
        assert ad.qos_classes_supported == []
        assert ad.pricing_url is None
        assert ad.model_card_urls == {}
        assert ad.raw == data

    def test_capability_advertisement_from_dict_full(self):
        data = _minimal_advertisement_dict()
        data["qos_classes_supported"] = ["standard", "priority"]
        data["pricing_url"] = "https://provider.example.com/pricing"
        data["model_card_urls"] = {"gpt-4": "https://provider.example.com/models/gpt-4"}

        ad = CapabilityAdvertisement.from_dict(data)
        assert ad.qos_classes_supported == ["standard", "priority"]
        assert ad.pricing_url == "https://provider.example.com/pricing"
        assert ad.model_card_urls["gpt-4"].endswith("/models/gpt-4")

    @pytest.mark.parametrize(
        "missing_field",
        [
            "issuer",
            "irp_versions_supported",
            "capabilities",
            "endpoints",
            "public_keys",
        ],
    )
    def test_capability_advertisement_from_dict_missing_required_raises(
        self, missing_field
    ):
        data = _minimal_advertisement_dict()
        del data[missing_field]

        with pytest.raises(ValueError, match=missing_field):
            CapabilityAdvertisement.from_dict(data)

    def test_capability_advertisement_from_dict_non_dict_raises(self):
        with pytest.raises(ValueError):
            CapabilityAdvertisement.from_dict([])  # type: ignore[arg-type]

    def test_capability_advertisement_supports(self):
        ad = CapabilityAdvertisement.from_dict(_minimal_advertisement_dict())
        assert ad.supports("chat.completions") is True
        assert ad.supports("receipts.v1") is True
        assert ad.supports("nonexistent.capability") is False

    def test_capability_advertisement_public_key_by_kid(self):
        data = _minimal_advertisement_dict()
        data["public_keys"].append(
            {"kid": "key-2026-02", "alg": "ed25519", "key_b64": "BBBB"}
        )
        ad = CapabilityAdvertisement.from_dict(data)

        found = ad.public_key_by_kid("key-2026-01")
        assert found is not None
        assert found["key_b64"] == "AAAA"

        found2 = ad.public_key_by_kid("key-2026-02")
        assert found2 is not None
        assert found2["key_b64"] == "BBBB"

        assert ad.public_key_by_kid("missing") is None


class TestIRPDiscovery:
    """Test the IRPDiscovery client."""

    def _make_response(
        self,
        status_code: int = 200,
        json_data: dict | None = None,
        invalid_json: bool = False,
    ) -> MagicMock:
        """Build a mock httpx.Response."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = status_code

        if invalid_json:
            response.json.side_effect = json.JSONDecodeError("expecting value", "x", 0)
        else:
            response.json.return_value = json_data or {}

        if status_code >= 400:
            response.raise_for_status.side_effect = httpx.HTTPStatusError(
                f"{status_code} error",
                request=MagicMock(spec=httpx.Request),
                response=response,
            )
        else:
            response.raise_for_status.return_value = None
        return response

    def test_discovery_url_construction(self):
        d = IRPDiscovery("https://provider.example.com/")
        assert d._url() == "https://provider.example.com/.well-known/irp-configuration"

        d2 = IRPDiscovery("https://provider.example.com")
        assert d2._url() == "https://provider.example.com/.well-known/irp-configuration"

    def test_discovery_fetch(self):
        data = _minimal_advertisement_dict()
        mock_response = self._make_response(200, data)

        with patch("irp.discovery.httpx.get", return_value=mock_response) as mock_get:
            d = IRPDiscovery("https://provider.example.com")
            ad = d.fetch()

        mock_get.assert_called_once_with(
            "https://provider.example.com/.well-known/irp-configuration",
            timeout=10.0,
        )
        assert isinstance(ad, CapabilityAdvertisement)
        assert ad.issuer == "https://provider.example.com"
        assert ad.supports("chat.completions")

    def test_discovery_fetch_dict(self):
        data = _minimal_advertisement_dict()
        mock_response = self._make_response(200, data)

        with patch("irp.discovery.httpx.get", return_value=mock_response):
            d = IRPDiscovery("https://provider.example.com")
            result = d.fetch_dict()

        assert result == data

    def test_discovery_fetch_invalid_json(self):
        mock_response = self._make_response(200, invalid_json=True)

        with patch("irp.discovery.httpx.get", return_value=mock_response):
            d = IRPDiscovery("https://provider.example.com")
            with pytest.raises(json.JSONDecodeError):
                d.fetch()

    def test_discovery_fetch_non_dict_json_raises(self):
        mock_response = self._make_response(200, json_data=None)
        mock_response.json.return_value = ["not", "an", "object"]

        with patch("irp.discovery.httpx.get", return_value=mock_response):
            d = IRPDiscovery("https://provider.example.com")
            with pytest.raises(ValueError):
                d.fetch()

    def test_discovery_fetch_http_error(self):
        mock_response = self._make_response(404)

        with patch("irp.discovery.httpx.get", return_value=mock_response):
            d = IRPDiscovery("https://provider.example.com")
            with pytest.raises(httpx.HTTPStatusError):
                d.fetch()

    def test_discovery_fetch_missing_required_field_raises(self):
        data = _minimal_advertisement_dict()
        del data["issuer"]
        mock_response = self._make_response(200, data)

        with patch("irp.discovery.httpx.get", return_value=mock_response):
            d = IRPDiscovery("https://provider.example.com")
            with pytest.raises(ValueError, match="issuer"):
                d.fetch()

    def test_discovery_custom_timeout(self):
        data = _minimal_advertisement_dict()
        mock_response = self._make_response(200, data)

        with patch("irp.discovery.httpx.get", return_value=mock_response) as mock_get:
            d = IRPDiscovery("https://provider.example.com", timeout=2.5)
            d.fetch()

        mock_get.assert_called_once()
        _, kwargs = mock_get.call_args
        assert kwargs["timeout"] == 2.5
