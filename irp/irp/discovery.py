"""Client-side IRP service discovery via .well-known/irp-configuration."""

from dataclasses import dataclass, field
from typing import Optional

import httpx


_REQUIRED_FIELDS = (
    "issuer",
    "irp_versions_supported",
    "capabilities",
    "endpoints",
    "public_keys",
)


@dataclass
class CapabilityAdvertisement:
    """Parsed IRP capability advertisement from a provider."""

    issuer: str
    irp_versions_supported: list[str]
    capabilities: list[str]
    endpoints: dict[str, str]
    public_keys: list[dict]
    qos_classes_supported: list[str] = field(default_factory=list)
    pricing_url: Optional[str] = None
    model_card_urls: dict[str, str] = field(default_factory=dict)
    raw: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> "CapabilityAdvertisement":
        """Parse advertisement dict and validate required fields."""
        if not isinstance(data, dict):
            raise ValueError("Advertisement must be a JSON object")

        for key in _REQUIRED_FIELDS:
            if key not in data:
                raise ValueError(f"Missing required field: {key!r}")

        return cls(
            issuer=data["issuer"],
            irp_versions_supported=list(data["irp_versions_supported"]),
            capabilities=list(data["capabilities"]),
            endpoints=dict(data["endpoints"]),
            public_keys=list(data["public_keys"]),
            qos_classes_supported=list(data.get("qos_classes_supported", [])),
            pricing_url=data.get("pricing_url"),
            model_card_urls=dict(data.get("model_card_urls", {})),
            raw=data,
        )

    def supports(self, capability_id: str) -> bool:
        """Return True if capability_id is advertised."""
        return capability_id in self.capabilities

    def public_key_by_kid(self, kid: str) -> Optional[dict]:
        """Return the public key entry matching kid, or None."""
        for entry in self.public_keys:
            if isinstance(entry, dict) and entry.get("kid") == kid:
                return entry
        return None


class IRPDiscovery:
    """Fetches and parses .well-known/irp-configuration from a provider."""

    WELL_KNOWN_PATH = "/.well-known/irp-configuration"

    def __init__(self, base_url: str, timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self) -> str:
        """Build the full well-known URL."""
        return f"{self.base_url}{self.WELL_KNOWN_PATH}"

    def fetch_dict(self) -> dict:
        """Return raw JSON dict from the well-known endpoint."""
        response = httpx.get(self._url(), timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError("Advertisement response must be a JSON object")
        return data

    def fetch(self) -> CapabilityAdvertisement:
        """HTTP GET <base_url>/.well-known/irp-configuration."""
        return CapabilityAdvertisement.from_dict(self.fetch_dict())
