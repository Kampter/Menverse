# IRP QoS Profile

**Document**: irp-qos
**Version**: 0.1 (Draft)
**Status**: Companion specification to [IRP Core Protocol](./irp-core.md)
**Date**: 2026-05-08

---

## 1. Abstract

This document defines the **Quality of Service (QoS) Profile** for the
Inference Receipt Protocol (IRP). It specifies five normative QoS classes
(`real-time`, `interactive`, `standard`, `batch`, `background`) along with
their service-level semantics: latency budgets, retry behaviour, scheduling
priority, default billing multipliers, and intended use cases.

The purpose of the QoS Profile is to give clients and providers a small,
shared vocabulary for negotiating the trade-off between **latency**,
**reliability**, and **cost** on a per-request basis, while keeping the
billing model auditable through IRP receipts. It complements the wire
format defined in [IRP Core Protocol](./irp-core.md) by adding the
header fields, error codes, and downgrade semantics that govern
QoS negotiation.

This document is **normative**. Implementations claiming "QoS Profile
compliant" status MUST conform to the conformance rules in
[Section 7](#7-conformance) and be cross-listed in
[Conformance Profile](./irp-conformance.md).

---

## 2. Status & Conventions

This is a draft companion specification to the IRP Core Protocol v0.1.
It is intended to be stabilised together with IRP Core v1.0.

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT",
"SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this
document are to be interpreted as described in [BCP 14] [RFC 2119]
[RFC 8174] when, and only when, they appear in all capitals, as
shown here.

In this document:

- **Client** means the entity issuing an inference request.
- **Provider** means the entity executing the inference and emitting
  the receipt.
- **Frame** has the meaning given in [IRP Core Protocol](./irp-core.md).
- **Receipt** has the meaning given in [IRP Core Protocol](./irp-core.md).
- **TTFT** stands for *time to first token* (server clock).
- **SLA** stands for *service level agreement*.

All time values are integer milliseconds unless otherwise stated.

---

## 3. Introduction

### 3.1 Why QoS classes at all?

Inference workloads span at least four orders of magnitude in latency
sensitivity, from sub-100 ms voice agents to overnight batch jobs.
A single SLA cannot serve all of them: setting it to "real-time"
forces the provider to over-provision for cold workloads, while
setting it to "best effort" makes interactive products unusable.

Today, providers paper over this by exposing **N** ad-hoc tiers
("priority", "fast", "scale", "flex", "batch", ...), each with its
own naming, billing, and retry rules. The result is that clients
cannot:

1. Compare offers across providers without bespoke integration.
2. Carry SLA expectations across an aggregator (e.g. OpenRouter,
   LiteLLM) without information loss.
3. Audit whether a provider has silently degraded service to reduce
   cost.

### 3.2 Why exactly five?

This profile defines **five** classes — not one and not many. Five is
the smallest set that distinguishes the four scheduling regimes that
appear in common LLM deployments (interactive chat, IDE-assist,
document/agent generation, batch) plus a fifth "background" tier for
telemetry and offline analytics where any non-trivial cost reduction
is preferable to speed.

The five classes map to the use cases described informally in the
[research summary](../../research/SUMMARY_REPORT.md), section "MVP
草案" item 4 (实时 / 交互 / 标准 / 批量 / 后台).

| Class           | Identifier             | Tier | Typical use case            |
|-----------------|------------------------|:----:|------------------------------|
| Real-time       | `irp.qos.real-time`    | 0    | Live voice / video agents    |
| Interactive     | `irp.qos.interactive`  | 1    | Chat UI, IDE assistant       |
| Standard        | `irp.qos.standard`     | 2    | Document generation, RAG     |
| Batch           | `irp.qos.batch`        | 3    | Async bulk jobs, evaluations |
| Background      | `irp.qos.background`   | 4    | Telemetry, offline analytics |

The five-class model is deliberately fixed in this version; future
versions MAY register additional classes (see
[Section 9](#9-iana-considerations)) but MUST NOT renumber or rename
the five base classes.

### 3.3 Relationship to IRP Core

The QoS Profile is **purely advisory at the wire level**. It does not
change the structure of frames or receipts defined in
[IRP Core Protocol](./irp-core.md). It only:

- Defines additional request/response headers
  ([Section 6](#6-header-fields)).
- Reserves error code `5000 SLA_VIOLATED` in the IRP error registry
  ([Section 5.3](#53-sla-violation)).
- Adds an OPTIONAL `qos` field to the receipt for downstream audit
  ([Section 5.4](#54-receipt-fields)).

A provider that does not implement this profile MUST simply ignore
the headers; clients MUST be prepared for that case.

---

## 4. QoS Class Definitions

This section defines, for each of the five classes:

- **Identifier**: the fully qualified string used in IANA registration
  and on the wire.
- **Short name**: the value used in the `X-IRP-QoS` header.
- **Numeric tier**: a small integer (0 = strictest, 4 = loosest)
  used for ordering and scheduling.
- **Latency budget**: target TTFT and target total latency.
- **Retry semantics**: at-most-once / at-least-once / exactly-once.
- **Scheduling priority**: behaviour under provider contention.
- **Billing tier**: NORMATIVE default cost multiplier relative
  to `standard` (= 1.0).
- **Use cases**: 3-5 representative examples.

### 4.1 SLA-parameter matrix (summary)

The following table summarises the normative defaults. Detailed
prose for each class follows in Sections 4.2 - 4.6.

| Param \ Class           | real-time | interactive | standard | batch  | background |
|-------------------------|:---------:|:-----------:|:--------:|:------:|:----------:|
| Identifier suffix       | `real-time` | `interactive` | `standard` | `batch` | `background` |
| Numeric tier            | 0         | 1           | 2        | 3      | 4          |
| Target TTFT (ms)        | 200       | 800         | 2 000    | 30 000 | none       |
| Target total (ms)       | 1 500     | 5 000       | 30 000   | 3 600 000 | none    |
| Retry semantics         | at-most-once | at-most-once | at-least-once | at-least-once | at-least-once |
| Scheduling priority     | preempts 1-4 | preempts 2-4 | preempts 3-4 | preempts 4 | best-effort |
| Default billing × | 2.0       | 1.5         | 1.0      | 0.5    | 0.3        |
| Idempotency-Key required| MAY       | MAY         | SHOULD   | MUST   | MUST       |
| Streaming               | REQUIRED  | RECOMMENDED | OPTIONAL | OPTIONAL | OPTIONAL  |
| Queue admission         | reject if full | reject if full | queue | queue | queue / drop |

The "Default billing ×" column gives the multiplier on the
provider's `standard` per-token price. Providers MAY override
these values but MUST advertise the override in their service
descriptor (see [Section 5.5](#55-advertising-overrides)).

### 4.2 `real-time`

- **Identifier**: `irp.qos.real-time`
- **Short name**: `real-time`
- **Numeric tier**: `0`
- **Target TTFT**: 200 ms (server-measured, p95).
- **Target total latency**: 1 500 ms (p95) for short responses
  (≤ 256 output tokens).
- **Retry semantics**: **at-most-once**. The provider MUST NOT
  internally retry the upstream model call; partial output already
  emitted to the client MUST NOT be replayed. Clients MUST NOT
  automatically retry on transient errors at this tier.
- **Scheduling priority**: `real-time` requests preempt all lower
  tiers. Under sustained overload, the provider SHOULD reject new
  `real-time` requests rather than degrade service for in-flight
  ones (see [Section 5.2](#52-downgrade)).
- **Default billing multiplier**: **2.0×** the provider's
  `standard` rate.
- **Streaming**: REQUIRED. The provider MUST stream tokens as soon
  as they are produced; buffering whole responses is forbidden.
- **Use cases**:
  1. Live voice agents (full-duplex speech-to-speech).
  2. Real-time translation overlays.
  3. Conversational avatars in games or VR.
  4. Latency-critical embedded assistants (in-vehicle, robotics).
  5. Live closed-captioning.

### 4.3 `interactive`

- **Identifier**: `irp.qos.interactive`
- **Short name**: `interactive`
- **Numeric tier**: `1`
- **Target TTFT**: 800 ms (p95).
- **Target total latency**: 5 000 ms (p95) for typical chat-length
  responses (≤ 1 024 output tokens).
- **Retry semantics**: **at-most-once**. As with `real-time`, the
  provider MUST NOT replay partial output. Clients MAY retry on
  transport-level failures provided no tokens were observed.
- **Scheduling priority**: preempts `standard`, `batch`,
  `background`. Yields to `real-time`.
- **Default billing multiplier**: **1.5×**.
- **Streaming**: RECOMMENDED.
- **Use cases**:
  1. Conversational chat UIs.
  2. IDE / code-completion assistants (line-level).
  3. Search-result answer boxes.
  4. Form auto-fill suggestions.
  5. Customer-support agent first-line.

### 4.4 `standard`

- **Identifier**: `irp.qos.standard`
- **Short name**: `standard`
- **Numeric tier**: `2`
- **Target TTFT**: 2 000 ms (p95).
- **Target total latency**: 30 000 ms (p95).
- **Retry semantics**: **at-least-once**. The provider MAY retry
  internally on transient upstream errors. Clients SHOULD send an
  `Idempotency-Key` (see [IRP Core Protocol](./irp-core.md)) so
  duplicates can be suppressed.
- **Scheduling priority**: preempts `batch`, `background`.
  Yields to `real-time`, `interactive`.
- **Default billing multiplier**: **1.0×** (this is the reference
  rate).
- **Streaming**: OPTIONAL.
- **Use cases**:
  1. Document or e-mail drafting.
  2. Retrieval-augmented generation (RAG) endpoints.
  3. Single-step agent tool calls.
  4. Synchronous report generation.
  5. Form-based "summarise this" features.

### 4.5 `batch`

- **Identifier**: `irp.qos.batch`
- **Short name**: `batch`
- **Numeric tier**: `3`
- **Target TTFT**: 30 000 ms.
- **Target total latency**: 1 hour (3 600 000 ms) per request.
- **Retry semantics**: **at-least-once**. The provider SHOULD
  retry internally on transient errors. Clients MUST send an
  `Idempotency-Key`; receipts for retried requests MUST share
  the same `request_id`.
- **Scheduling priority**: preempts `background`. Yields to all
  higher tiers.
- **Default billing multiplier**: **0.5×**.
- **Streaming**: OPTIONAL. Many batch back-ends return only the
  final response.
- **Use cases**:
  1. Overnight evaluation runs (eval harnesses).
  2. Bulk dataset labelling.
  3. Periodic content moderation sweeps.
  4. Embedding generation for large corpora.
  5. Offline fine-tune data preparation.

### 4.6 `background`

- **Identifier**: `irp.qos.background`
- **Short name**: `background`
- **Numeric tier**: `4`
- **Target TTFT**: not specified.
- **Target total latency**: not specified. Best effort, may be
  delayed indefinitely.
- **Retry semantics**: **at-least-once**. The provider MAY drop
  requests entirely if the queue is full; clients MUST treat
  any non-2xx response as a hint to retry later.
- **Scheduling priority**: lowest. May be paused or shed during
  any contention.
- **Default billing multiplier**: **0.3×**.
- **Streaming**: OPTIONAL.
- **Use cases**:
  1. Telemetry enrichment (e.g. log summarisation).
  2. Background re-ranking of cached results.
  3. Optional content tagging.
  4. Offline analytics pipelines.
  5. Pre-warming caches with speculative completions.

---

## 5. QoS Negotiation

### 5.1 Request flow

The negotiation flow is a single round-trip:

```
   Client                                Provider
     |                                       |
     |  Request frame                        |
     |    X-IRP-QoS: <desired>               |
     |    X-IRP-Latency-Budget-Ms: <opt>     |
     |-------------------------------------->|
     |                                       |
     |                                Schedule
     |                                       |
     |  Response frame                       |
     |    X-IRP-QoS-Accepted: <class>        |
     |    X-IRP-QoS-Downgrade-Reason: <opt>  |
     |<--------------------------------------|
     |                                       |
```

Procedurally:

1. The client SHOULD set `X-IRP-QoS` in the request frame to one of
   the five short names. If absent, the provider MUST treat the
   request as `standard`.
2. The client MAY set `X-IRP-Latency-Budget-Ms` to a stricter
   total-latency target than the class default. The value MUST be
   a positive integer ≤ the class default for the requested class.
   A value greater than the class default MUST be ignored by the
   provider (and MAY trigger a warning log).
3. The provider MUST set `X-IRP-QoS-Accepted` in the response frame
   to the class actually scheduled. This MAY differ from the
   requested class only by **downgrade**, never by upgrade.
4. If `X-IRP-QoS-Accepted` differs from `X-IRP-QoS`, the provider
   MUST set `X-IRP-QoS-Downgrade-Reason` to a registered reason
   code (see [Section 5.2](#52-downgrade)).
5. The accepted class is the one used for billing and for SLA
   evaluation.

### 5.2 Downgrade

A provider MAY downgrade a request to a lower-tier class (i.e.
strictly higher numeric tier) when it cannot meet the requested
SLA. Upgrade (offering a stricter class than requested) is
NOT permitted, because the client did not consent to the higher
billing rate.

The provider MUST set `X-IRP-QoS-Downgrade-Reason` to one of the
following reason tokens:

| Token              | Meaning                                              |
|--------------------|------------------------------------------------------|
| `capacity`         | The requested tier has no available capacity.        |
| `not-supported`    | The provider does not implement the requested tier.  |
| `policy`           | A provider policy disallows the requested tier for this caller. |
| `quota-exceeded`   | The caller has exhausted their quota at the requested tier. |
| `model-incompatible` | The selected model cannot meet the requested SLA.   |

Additional reason tokens MAY be registered per
[Section 9](#9-iana-considerations).

When a downgrade occurs, the provider:

- MUST bill at the multiplier of the **accepted** class, not the
  requested class.
- MUST record both the requested and accepted class in the receipt
  (see [Section 5.4](#54-receipt-fields)).
- SHOULD emit a structured log event so the client can audit
  downgrade rates.

### 5.3 SLA violation

If the provider accepts a request at class `C` but fails to meet
the latency budget of `C` (TTFT or total), the provider MUST
emit an `ERROR` frame with code `5000 SLA_VIOLATED` after
the response completes (or in lieu of a successful response, if
the violation occurs mid-stream and the provider chooses to
terminate).

The error code `5000 SLA_VIOLATED` is **defined in this document**
and **registered in the IRP Core error registry** (see
[IRP Core Protocol](./irp-core.md), section "Error Codes").

The `ERROR` frame for `5000` MUST include the following structured
fields:

```
{
  "code": 5000,
  "name": "SLA_VIOLATED",
  "qos_accepted": "interactive",
  "metric": "ttft",          // "ttft" | "total"
  "budget_ms": 800,
  "observed_ms": 1342,
  "request_id": "req-..."
}
```

Behaviour after a violation:

- The provider SHOULD NOT charge for a request that violates SLA.
  If it does charge, it MUST set `cost_total` to a value reduced
  by at least the violation severity (e.g. proportional to
  `observed_ms - budget_ms`); the precise reduction is provider
  policy but MUST be advertised.
- The client MAY treat a `5000` violation as a failure for the
  purposes of retry (subject to the class's retry semantics).

### 5.4 Receipt fields

When the QoS Profile is in use, the receipt defined in
[IRP Core Protocol](./irp-core.md) is extended with an OPTIONAL
`qos` object:

```
qos: {
  requested:  "interactive",
  accepted:   "standard",
  downgrade_reason: "capacity",
  budget_ms:  800,            // budget for the accepted class
  observed_ttft_ms: 612,
  observed_total_ms: 4123,
  sla_violated: false
}
```

A receipt MUST include the `qos` object whenever a non-default
class was negotiated, a downgrade occurred, or an SLA violation
was reported. Receipts for plain `standard` requests with no
budget override MAY omit the object.

The `qos` object is part of the receipt's signed payload, so
clients can independently audit downgrade and violation rates.

### 5.5 Advertising overrides

If a provider chooses to deviate from the default billing
multipliers in [Section 4.1](#41-sla-parameter-matrix-summary),
it MUST publish the overrides in its service descriptor
(the IRP discovery document; see future irp-discovery spec).
At minimum, an override MUST include:

- The class identifier.
- The override multiplier or absolute price.
- The effective date.

A provider that has not advertised an override MUST charge at
the normative default multiplier for the accepted class.

---

## 6. Header Fields

This profile defines four headers. They appear in IRP frames as
defined by [IRP Core Protocol](./irp-core.md). When IRP is carried
over HTTP, they appear as HTTP headers; when carried over other
transports, they appear in the transport's metadata channel.

### 6.1 `X-IRP-QoS` (request)

```
X-IRP-QoS = real-time / interactive / standard / batch / background
```

- **Direction**: client → provider.
- **Cardinality**: at most one occurrence per request.
- **ABNF**: see [Section 6.5](#65-abnf).
- **Default if absent**: `standard`.
- **Case**: tokens are case-sensitive and MUST be lowercase.

### 6.2 `X-IRP-QoS-Accepted` (response)

```
X-IRP-QoS-Accepted = real-time / interactive / standard / batch / background
```

- **Direction**: provider → client.
- **Cardinality**: at most one occurrence per response.
- **Required**: MUST be present if the provider implements this
  profile, even if the value equals the requested value.

### 6.3 `X-IRP-QoS-Downgrade-Reason` (response, OPTIONAL)

```
X-IRP-QoS-Downgrade-Reason = capacity
                           / not-supported
                           / policy
                           / quota-exceeded
                           / model-incompatible
                           / extension-token        ; registered
```

- **Direction**: provider → client.
- **Cardinality**: at most one occurrence per response.
- **Presence rule**: MUST be present iff `X-IRP-QoS-Accepted`
  differs from the requested class. MUST NOT be present otherwise.

### 6.4 `X-IRP-Latency-Budget-Ms` (request, OPTIONAL)

```
X-IRP-Latency-Budget-Ms = 1*DIGIT     ; positive integer milliseconds
```

- **Direction**: client → provider.
- **Cardinality**: at most one occurrence per request.
- **Semantics**: caller-supplied stricter total-latency budget.
  MUST be a positive integer; MUST NOT exceed the class default
  for `X-IRP-QoS`. If the value is malformed, the provider MUST
  ignore the header and SHOULD log a warning.

### 6.5 ABNF

The header values use the following ABNF (per [RFC 5234]):

```
qos-class       = "real-time" / "interactive" / "standard"
                / "batch" / "background"

reason-token    = "capacity" / "not-supported" / "policy"
                / "quota-exceeded" / "model-incompatible"
                / extension-reason

extension-reason = 1*( ALPHA / DIGIT / "-" )       ; registered

millis          = 1*DIGIT                          ; positive integer
```

---

## 7. Conformance

An implementation that wishes to claim **"IRP QoS Profile compliant"**
MUST satisfy all of the following:

1. It MUST implement at least **3 of the 5 classes**.
2. The set of implemented classes MUST include **`standard`**.
3. For each unimplemented class, the implementation MUST downgrade
   the request to its nearest implemented class (≤ tier 2) and set
   `X-IRP-QoS-Downgrade-Reason: not-supported`.
4. It MUST never silently treat a request at class `C` as if it
   were a different class without setting `X-IRP-QoS-Accepted`
   accordingly.
5. It MUST honour the normative default billing multipliers for
   any class it implements, unless overrides have been advertised
   per [Section 5.5](#55-advertising-overrides).
6. It MUST emit `5000 SLA_VIOLATED` for any in-budget acceptance
   it fails to honour.
7. It MUST include a `qos` object in receipts whenever a non-
   default negotiation occurred (see
   [Section 5.4](#54-receipt-fields)).

Conformance levels and the broader compliance test suite are
defined in [Conformance Profile](./irp-conformance.md). An
implementation listed there MUST cross-reference this document.

Clients MUST be tolerant of providers that do not implement the
profile: the absence of `X-IRP-QoS-Accepted` in a response
indicates a non-participating provider, and clients MUST NOT
treat that as a `5000` violation.

---

## 8. Security Considerations

### 8.1 Covert tier discrimination

The QoS Profile gives providers a low-friction way to silently
shift load across tiers. Without discipline, a provider could
secretly downgrade paying users (e.g. to free up `real-time`
capacity for a more profitable customer) and bill them at the
contracted rate. Such behaviour would defeat the auditability
goal of IRP.

Therefore:

- Providers **MUST NOT** use the QoS class as a covert channel
  for tier-based discrimination among callers paying at the same
  advertised rate.
- Whenever an accepted class differs from the requested class,
  the downgrade **MUST** be reflected in the receipt
  (`qos.requested`, `qos.accepted`, `qos.downgrade_reason`).
- Providers **SHOULD** publish aggregate downgrade statistics
  (e.g. monthly per-class downgrade rate) so clients can
  cross-check their own observations.
- Clients **SHOULD** monitor the rate of downgrades they observe
  and treat anomalous spikes as a signal to seek alternative
  providers.

### 8.2 Latency as a side channel

Latency budgets create a narrow timing side channel: an attacker
controlling client traffic could in principle observe whether
co-tenant requests are exceeding budget. The risk is small but
real. Providers SHOULD jitter `observed_*_ms` values reported in
receipts by a small (≤ 5 %) random factor before signing, where
operationally acceptable.

### 8.3 Resource exhaustion at the highest tier

Because `real-time` preempts all lower tiers, an attacker who
can submit requests at `real-time` can degrade service for other
classes. Providers MUST gate access to `real-time` (and SHOULD
gate `interactive`) by authenticated quota; an unauthenticated
caller MUST default to `standard` regardless of the
`X-IRP-QoS` header.

### 8.4 Replay and idempotency

`at-least-once` retry semantics in `standard`, `batch`, and
`background` mean a provider may execute the upstream model
call multiple times. Clients MUST send an `Idempotency-Key`
where required (see [Section 4](#4-qos-class-definitions)) and
SHOULD treat duplicate receipts that share `request_id` as a
single billable event.

### 8.5 Logging downgrades to receipts

Receipts are the load-bearing audit artefact in IRP. Providers
**SHOULD** log every downgrade and every SLA violation to the
receipt's `qos` object. Out-of-band logs (HTTP access logs,
internal traces) are insufficient because they cannot be
independently verified by the client.

---

## 9. IANA Considerations

This document requests three new registries under the IRP namespace
(to be created jointly with [IRP Core Protocol](./irp-core.md)),
plus one error code registration:

### 9.1 IRP QoS Class registry

Initial entries:

| Identifier            | Short name    | Tier | Reference     |
|-----------------------|---------------|:----:|---------------|
| `irp.qos.real-time`   | `real-time`   | 0    | This document |
| `irp.qos.interactive` | `interactive` | 1    | This document |
| `irp.qos.standard`    | `standard`    | 2    | This document |
| `irp.qos.batch`       | `batch`       | 3    | This document |
| `irp.qos.background`  | `background`  | 4    | This document |

Registration policy: **Specification Required** ([RFC 8126]).
New entries MUST:

- Use the prefix `irp.qos.`.
- Specify a numeric tier ≥ 5 (the tiers 0 - 4 are permanently
  reserved for the base classes).
- Provide a complete SLA-parameter row matching the columns of
  [Section 4.1](#41-sla-parameter-matrix-summary).

### 9.2 IRP QoS Header registry

Initial entries:

| Header                          | Direction          | Reference     |
|---------------------------------|--------------------|---------------|
| `X-IRP-QoS`                     | request            | This document |
| `X-IRP-QoS-Accepted`            | response           | This document |
| `X-IRP-QoS-Downgrade-Reason`    | response           | This document |
| `X-IRP-Latency-Budget-Ms`       | request            | This document |

Registration policy: **Specification Required**. Headers added
to this registry MUST begin with `X-IRP-QoS-` or `X-IRP-Latency-`.

### 9.3 IRP QoS Downgrade Reason registry

Initial entries: `capacity`, `not-supported`, `policy`,
`quota-exceeded`, `model-incompatible` (see
[Section 5.2](#52-downgrade)).

Registration policy: **First Come First Served** ([RFC 8126]).
Tokens MUST match `1*( ALPHA / DIGIT / "-" )` and MUST be
lowercase.

### 9.4 IRP Error code 5000

This document registers the error code `5000 SLA_VIOLATED` in
the IRP Core error registry (see [IRP Core Protocol](./irp-core.md),
section "Error Codes"). The reference is this document.

---

## 10. References

### 10.1 Normative

- [IRP Core Protocol](./irp-core.md) — frame format, receipt
  format, error registry.
- [RFC 2119] Bradner, S., "Key words for use in RFCs to Indicate
  Requirement Levels", BCP 14, RFC 2119, March 1997.
- [RFC 8174] Leiba, B., "Ambiguity of Uppercase vs Lowercase in
  RFC 2119 Key Words", BCP 14, RFC 8174, May 2017.
- [RFC 5234] Crocker, D., Ed., and P. Overell, "Augmented BNF for
  Syntax Specifications: ABNF", STD 68, RFC 5234, January 2008.
- [RFC 8126] Cotton, M., Leiba, B., and T. Narten, "Guidelines for
  Writing an IANA Considerations Section in RFCs", BCP 26,
  RFC 8126, June 2017.

### 10.2 Informative

- [Conformance Profile](./irp-conformance.md) — compliance test
  suite and conformance levels.
- [Research Summary Report](../../research/SUMMARY_REPORT.md) —
  background on the five-class motivation (section "MVP 草案").
- [IRP README](../../README.md) — protocol overview.

---

*End of irp-qos.md*
