"""Tests for irp.version — protocol versioning primitives."""

import pytest

from irp.version import (
    KNOWN_VERSIONS,
    LifecycleStatus,
    ProtocolVersion,
    VersionEntry,
    is_removed,
    negotiate,
    supported_versions,
)


class TestParse:
    def test_parse_valid(self):
        assert ProtocolVersion.parse("0.1.0") == ProtocolVersion(0, 1, 0)

    def test_parse_invalid_format(self):
        with pytest.raises(ValueError):
            ProtocolVersion.parse("0.1")
        with pytest.raises(ValueError):
            ProtocolVersion.parse("abc.def.ghi")
        with pytest.raises(ValueError):
            ProtocolVersion.parse("")

    def test_parse_too_many_parts(self):
        with pytest.raises(ValueError):
            ProtocolVersion.parse("1.2.3.4")

    def test_parse_leading_zeros(self):
        with pytest.raises(ValueError, match="leading zeros"):
            ProtocolVersion.parse("01.02.03")
        with pytest.raises(ValueError, match="leading zeros"):
            ProtocolVersion.parse("00.1.0")

    def test_parse_zero_is_allowed(self):
        assert ProtocolVersion.parse("0.0.0") == ProtocolVersion(0, 0, 0)

    def test_str_roundtrip(self):
        assert str(ProtocolVersion.parse("1.2.3")) == "1.2.3"


class TestOrdering:
    def test_ordering(self):
        assert ProtocolVersion(1, 0, 0) > ProtocolVersion(0, 9, 9)
        assert ProtocolVersion(0, 1, 0) < ProtocolVersion(0, 2, 0)
        assert ProtocolVersion(0, 1, 5) < ProtocolVersion(0, 2, 0)

    def test_patch_ordering(self):
        assert ProtocolVersion(0, 1, 0) < ProtocolVersion(0, 1, 1)
        assert ProtocolVersion(1, 2, 3) < ProtocolVersion(1, 2, 4)


class TestCompatibility:
    def test_is_compatible_with_same_major_stable(self):
        assert ProtocolVersion(1, 2, 0).is_compatible_with(ProtocolVersion(1, 5, 3))

    def test_is_compatible_with_different_major(self):
        assert not ProtocolVersion(0, 1, 0).is_compatible_with(ProtocolVersion(1, 0, 0))

    def test_is_compatible_with_major_zero_same_minor(self):
        assert ProtocolVersion(0, 1, 0).is_compatible_with(ProtocolVersion(0, 1, 5))

    def test_is_compatible_with_major_zero_different_minor(self):
        assert not ProtocolVersion(0, 1, 0).is_compatible_with(ProtocolVersion(0, 2, 0))


class TestRegistry:
    def test_supported_versions_includes_experimental(self):
        versions = supported_versions()
        assert ProtocolVersion(0, 1, 0) in versions

    def test_is_removed_known(self):
        # No removed versions in the initial registry
        assert not is_removed(ProtocolVersion(0, 1, 0))

    def test_is_removed_unknown(self):
        # Unknown versions are treated as "not removed"
        assert not is_removed(ProtocolVersion(9, 9, 9))


class TestNegotiate:
    def test_negotiate_overlap_picks_highest(self):
        client = [ProtocolVersion(0, 1, 0), ProtocolVersion(0, 2, 0)]
        server = [ProtocolVersion(0, 1, 0)]
        result = negotiate(client, server)
        assert result == ProtocolVersion(0, 1, 0)

    def test_negotiate_no_overlap(self):
        client = [ProtocolVersion(0, 1, 0)]
        server = [ProtocolVersion(0, 2, 0)]
        assert negotiate(client, server) is None

    def test_negotiate_empty_lists(self):
        assert negotiate([], []) is None

    def test_negotiate_empty_client(self):
        assert negotiate([], [ProtocolVersion(0, 1, 0)]) is None

    def test_negotiate_empty_server(self):
        assert negotiate([ProtocolVersion(0, 1, 0)], []) is None

    def test_negotiate_picks_absolute_highest(self):
        common = [
            ProtocolVersion(0, 1, 0),
            ProtocolVersion(0, 2, 0),
            ProtocolVersion(0, 3, 0),
        ]
        assert negotiate(common, common) == ProtocolVersion(0, 3, 0)
