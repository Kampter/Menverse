"""Tests for IRP QoS levels (irp.qos)."""

from __future__ import annotations

import pytest

from irp.qos import (
    QOS_PARAMETERS,
    QoSClass,
    QoSParameters,
    parse_qos_class,
    select_qos,
)


# Canonical ordering from highest to lowest priority.
_ORDER = [
    QoSClass.REAL_TIME,
    QoSClass.INTERACTIVE,
    QoSClass.STANDARD,
    QoSClass.BATCH,
    QoSClass.BACKGROUND,
]


def test_qos_class_values() -> None:
    """String values must match the spec exactly."""
    assert QoSClass.REAL_TIME.value == "real-time"
    assert QoSClass.INTERACTIVE.value == "interactive"
    assert QoSClass.STANDARD.value == "standard"
    assert QoSClass.BATCH.value == "batch"
    assert QoSClass.BACKGROUND.value == "background"


def test_qos_parameters_complete() -> None:
    """All 5 classes present and tiers 0..4 unique."""
    assert set(QOS_PARAMETERS.keys()) == set(QoSClass)
    assert len(QOS_PARAMETERS) == 5

    tiers = [QOS_PARAMETERS[c].tier for c in QoSClass]
    assert sorted(tiers) == [0, 1, 2, 3, 4]
    assert len(set(tiers)) == 5

    for c, params in QOS_PARAMETERS.items():
        assert isinstance(params, QoSParameters)
        assert params.qos_class is c


def test_qos_parameters_billing_monotonic() -> None:
    """billing_multiplier must descend across the canonical ordering."""
    multipliers = [QOS_PARAMETERS[c].billing_multiplier for c in _ORDER]
    for a, b in zip(multipliers, multipliers[1:]):
        assert a > b, f"expected {a} > {b} in {multipliers}"
    # STANDARD is the reference == 1.0.
    assert QOS_PARAMETERS[QoSClass.STANDARD].billing_multiplier == 1.0


def test_qos_parameters_latency_monotonic() -> None:
    """target_ttft_ms must ascend across the canonical ordering."""
    ttfts = [QOS_PARAMETERS[c].target_ttft_ms for c in _ORDER]
    for a, b in zip(ttfts, ttfts[1:]):
        assert a < b, f"expected {a} < {b} in {ttfts}"


def test_select_qos_supported_returns_desired() -> None:
    """If desired is supported, return it with no downgrade reason."""
    chosen, reason = select_qos(
        QoSClass.INTERACTIVE,
        [QoSClass.REAL_TIME, QoSClass.INTERACTIVE, QoSClass.STANDARD],
    )
    assert chosen is QoSClass.INTERACTIVE
    assert reason is None


def test_select_qos_unsupported_downgrades() -> None:
    """Unsupported desired downgrades to nearest lower-priority supported."""
    chosen, reason = select_qos(
        QoSClass.REAL_TIME,
        [QoSClass.STANDARD, QoSClass.BATCH],
    )
    assert chosen is QoSClass.STANDARD
    assert reason is not None
    assert "real-time" in reason
    assert "standard" in reason


def test_select_qos_no_supported_raises() -> None:
    """An empty server_supported list must raise ValueError."""
    with pytest.raises(ValueError):
        select_qos(QoSClass.STANDARD, [])


def test_parse_qos_class_valid() -> None:
    """Valid spec strings parse to the corresponding enum value."""
    assert parse_qos_class("real-time") is QoSClass.REAL_TIME
    assert parse_qos_class("interactive") is QoSClass.INTERACTIVE
    assert parse_qos_class("standard") is QoSClass.STANDARD
    assert parse_qos_class("batch") is QoSClass.BATCH
    assert parse_qos_class("background") is QoSClass.BACKGROUND


def test_parse_qos_class_invalid() -> None:
    """Unknown strings raise ValueError."""
    with pytest.raises(ValueError):
        parse_qos_class("fast")
