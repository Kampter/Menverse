"""QoS (Quality of Service) levels for IRP.

Defines the 5-level QoS class enum, normative SLA parameter table, and
helpers for selecting / parsing QoS classes.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class QoSClass(str, Enum):
    """IRP QoS classes (5 levels)."""

    REAL_TIME = "real-time"
    INTERACTIVE = "interactive"
    STANDARD = "standard"
    BATCH = "batch"
    BACKGROUND = "background"


@dataclass(frozen=True)
class QoSParameters:
    """Normative SLA parameters per QoS class."""

    qos_class: QoSClass
    tier: int                   # 0=highest priority, 4=lowest
    target_ttft_ms: int         # time-to-first-token target
    target_total_ms: int        # total request budget
    retry_semantics: str        # "at-most-once" | "at-least-once" | "exactly-once"
    billing_multiplier: float   # cost multiplier vs standard (=1.0)
    use_cases: list[str]        # short labels


# The normative table — 5 entries.
QOS_PARAMETERS: dict[QoSClass, QoSParameters] = {
    QoSClass.REAL_TIME: QoSParameters(
        qos_class=QoSClass.REAL_TIME, tier=0,
        target_ttft_ms=200, target_total_ms=2_000,
        retry_semantics="at-most-once", billing_multiplier=2.0,
        use_cases=["live-voice", "trading-signal", "live-translate"],
    ),
    QoSClass.INTERACTIVE: QoSParameters(
        qos_class=QoSClass.INTERACTIVE, tier=1,
        target_ttft_ms=800, target_total_ms=5_000,
        retry_semantics="at-most-once", billing_multiplier=1.5,
        use_cases=["chat-ui", "ide-assist", "search-rerank"],
    ),
    QoSClass.STANDARD: QoSParameters(
        qos_class=QoSClass.STANDARD, tier=2,
        target_ttft_ms=2_000, target_total_ms=60_000,
        retry_semantics="at-least-once", billing_multiplier=1.0,
        use_cases=["doc-gen", "summarize", "classify"],
    ),
    QoSClass.BATCH: QoSParameters(
        qos_class=QoSClass.BATCH, tier=3,
        target_ttft_ms=30_000, target_total_ms=3_600_000,
        retry_semantics="at-least-once", billing_multiplier=0.5,
        use_cases=["bulk-data-process", "embedding-build", "label-sweep"],
    ),
    QoSClass.BACKGROUND: QoSParameters(
        qos_class=QoSClass.BACKGROUND, tier=4,
        target_ttft_ms=60_000, target_total_ms=86_400_000,  # up to 24h
        retry_semantics="at-least-once", billing_multiplier=0.3,
        use_cases=["nightly-eval", "cold-storage-tag", "telemetry-aggregate"],
    ),
}


def select_qos(
    desired: QoSClass,
    server_supported: list[QoSClass],
) -> tuple[QoSClass, str | None]:
    """Select the effective QoS class for a request.

    If ``desired`` is in ``server_supported``, returns ``(desired, None)``.
    Otherwise downgrades to the nearest lower-priority supported class
    (i.e. the supported class with the smallest ``tier`` strictly greater
    than ``desired.tier``). If no such class exists, falls back to the
    supported class with the lowest tier (highest priority among supported).

    Raises:
        ValueError: if ``server_supported`` is empty.
    """
    if not server_supported:
        raise ValueError("server_supported must contain at least one QoSClass")

    if desired in server_supported:
        return desired, None

    desired_tier = QOS_PARAMETERS[desired].tier

    # Sort supported classes by tier ascending (highest priority first).
    sorted_supported = sorted(
        server_supported, key=lambda c: QOS_PARAMETERS[c].tier
    )

    # Prefer the nearest lower-priority class (smallest tier > desired_tier).
    lower_priority = [
        c for c in sorted_supported if QOS_PARAMETERS[c].tier > desired_tier
    ]
    if lower_priority:
        chosen = lower_priority[0]
        reason = (
            f"desired QoS {desired.value!r} not supported by server; "
            f"downgraded to {chosen.value!r}"
        )
        return chosen, reason

    # No lower-priority class available — fall back to the highest-priority
    # supported class (smallest tier).
    chosen = sorted_supported[0]
    reason = (
        f"desired QoS {desired.value!r} not supported by server; "
        f"no lower-priority class available, using {chosen.value!r}"
    )
    return chosen, reason


def parse_qos_class(value: str) -> QoSClass:
    """Parse a string like ``"real-time"`` or ``"standard"`` into a ``QoSClass``.

    Raises:
        ValueError: if ``value`` does not match any known QoS class.
    """
    try:
        return QoSClass(value)
    except ValueError as exc:
        valid = ", ".join(c.value for c in QoSClass)
        raise ValueError(
            f"unknown QoS class {value!r}; expected one of: {valid}"
        ) from exc
