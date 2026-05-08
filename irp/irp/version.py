"""IRP protocol versioning.

Provides semantic-versioned protocol identifiers, a registry of known
versions with lifecycle status, and a negotiation helper used by clients
and servers to agree on a mutually supported version.

Background: research/07 showed that protocols which break compatibility
without a clear evolution policy (e.g. WiMAX) tend to die, while ones
that version cleanly (e.g. LTE) survive. IRP therefore makes versioning
first-class from day one.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class LifecycleStatus(str, Enum):
    """Status of an IRP version per the deprecation policy."""

    EXPERIMENTAL = "experimental"
    STABLE = "stable"
    DEPRECATED = "deprecated"
    REMOVED = "removed"


@dataclass(frozen=True, order=True)
class ProtocolVersion:
    """Semantic-versioned IRP protocol version.

    Ordering is lexicographic over (major, minor, patch), which gives
    standard semver comparison for free via ``order=True``.
    """

    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, s: str) -> "ProtocolVersion":
        """Parse ``"0.1.0"`` into ``ProtocolVersion(0, 1, 0)``.

        Raises:
            ValueError: if ``s`` is not exactly three dot-separated
                non-negative integers.
        """
        if not isinstance(s, str) or not s:
            raise ValueError(f"invalid protocol version: {s!r}")
        parts = s.split(".")
        if len(parts) != 3:
            raise ValueError(
                f"invalid protocol version {s!r}: expected 'MAJOR.MINOR.PATCH'"
            )
        try:
            major, minor, patch = (int(p) for p in parts)
        except ValueError as e:
            raise ValueError(
                f"invalid protocol version {s!r}: components must be integers"
            ) from e
        if major < 0 or minor < 0 or patch < 0:
            raise ValueError(
                f"invalid protocol version {s!r}: components must be non-negative"
            )
        return cls(major, minor, patch)

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    def is_compatible_with(self, other: "ProtocolVersion") -> bool:
        """Return True if ``self`` and ``other`` share the same major version.

        This follows the standard semver rule: within a major version,
        changes are backward-compatible.
        """
        return self.major == other.major


@dataclass(frozen=True)
class VersionEntry:
    """Registry entry for a known IRP version."""

    version: ProtocolVersion
    status: LifecycleStatus
    released: str  # ISO 8601 date
    deprecated_after: str | None = None  # ISO 8601, set when DEPRECATED
    notes: str = ""


# Known versions. Update as protocol evolves.
KNOWN_VERSIONS: list[VersionEntry] = [
    VersionEntry(
        version=ProtocolVersion(0, 1, 0),
        status=LifecycleStatus.EXPERIMENTAL,
        released="2026-01-01",
        notes="Initial draft.",
    ),
]


_ACTIVE_STATUSES = frozenset(
    {
        LifecycleStatus.EXPERIMENTAL,
        LifecycleStatus.STABLE,
        LifecycleStatus.DEPRECATED,
    }
)


def supported_versions() -> list[ProtocolVersion]:
    """Return all versions whose status is EXPERIMENTAL, STABLE, or DEPRECATED.

    REMOVED versions are excluded.
    """
    return [e.version for e in KNOWN_VERSIONS if e.status in _ACTIVE_STATUSES]


def is_removed(version: ProtocolVersion) -> bool:
    """Return True iff ``version`` is in the registry with status REMOVED."""
    for entry in KNOWN_VERSIONS:
        if entry.version == version:
            return entry.status is LifecycleStatus.REMOVED
    return False


def negotiate(
    client_supported: list[ProtocolVersion],
    server_supported: list[ProtocolVersion],
) -> ProtocolVersion | None:
    """Pick the highest mutually supported version.

    Args:
        client_supported: versions the client can speak.
        server_supported: versions the server can speak.

    Returns:
        The highest version present in both lists, or ``None`` if there
        is no overlap.
    """
    overlap = set(client_supported) & set(server_supported)
    if not overlap:
        return None
    return max(overlap)
