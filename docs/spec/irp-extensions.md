# IRP Extension Registry

**Status**: Draft
**Version**: 0.1
**Document Identifier**: `irp-extensions`
**Last Updated**: 2026-05-08

---

## Abstract

This document defines the **Extension Registry** for the Inference Receipt
Protocol (IRP). It specifies:

1. The capability identifier format used to name IRP extensions.
2. The lifecycle states an extension passes through (Experimental, Proposed,
   Stable, Deprecated, Removed).
3. The proposal, review, and acceptance process for new extensions.
4. The initial registry of capability identifiers shipped with IRP v0.1.
5. The rules for vendor-prefixed (proprietary) extensions versus
   community-registered extensions.

The Extension Registry is the single source of truth for which capability
identifiers are recognized by conforming IRP implementations and what each one
means. Implementations advertise supported capabilities during connection
negotiation (see [Core Protocol](./irp-core.md)); the values they exchange
MUST come from this registry or follow the vendor-prefix rule below.

The registry is intentionally small at v0.1. The lessons of CDMI, OCCI, and
similar over-extended cloud standards (research/09) are clear: every optional
field a standard ships becomes a compatibility hazard that nobody implements
the same way. IRP keeps its Core small (see [Conformance](./irp-conformance.md))
and routes everything else through this registry with explicit lifecycle labels
and a public review process, modeled on how MCP separated its core from
governed extensions.

---

## 1. Status & Conventions

This document is part of the IRP v0.1 specification suite. It is **normative**
for the rules it states and **informative** for the discussion that surrounds
them.

The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**,
**SHOULD**, **SHOULD NOT**, **RECOMMENDED**, **MAY**, and **OPTIONAL** are
to be interpreted as described in [RFC 2119][rfc2119] and [RFC 8174][rfc8174]
when, and only when, they appear in all capitals.

[rfc2119]: https://www.rfc-editor.org/rfc/rfc2119
[rfc8174]: https://www.rfc-editor.org/rfc/rfc8174

The terms "Core", "Conformance Profile", "receipt", "metering", "QoS class",
and "audit" have the meanings given in their respective sister specifications;
see [References](#11-references).

Code spans such as `irp.transport.http2` denote capability identifiers
exchanged on the wire. Identifiers are case-sensitive ASCII strings.

---

## 2. Introduction

### 2.1 Why a Registry?

IRP is designed as a **small core plus governed extensions**. The Core
([Core Protocol](./irp-core.md), [Conformance](./irp-conformance.md)) defines
the minimum every conforming implementation MUST support: HTTP/2 transport,
the receipt envelope, the five-class QoS scheme, bearer authentication, and
deterministic token-count metering with input/output hashing.

Everything else — alternative transports, additional metering schemes,
TEE/ZK audit modes, alternative auth methods, observability hooks — is an
**extension**. Extensions are negotiated at connection time using
**capability identifiers**.

The registry exists so that implementations can recognize the same
identifiers without bilateral coordination, and so vendors can ship
proprietary extensions without blocking on a standards process while
the community ratifies common features via review.

### 2.2 Design Philosophy

Three principles, drawn from the lessons in
`research/09_cloud_standardization_failures.md` and
`research/01_internet_standards_history.md`:

1. **Small Core.** A standard that makes everything optional makes nothing
   interoperable. CDMI shipped 60+ optional capabilities; no two
   implementations agreed on which to support. IRP keeps the Core minimal
   and refuses to absorb features unless they are universally implemented.

2. **Explicit Lifecycle.** Every identifier is in one of five states
   (§4). The Model Context Protocol demonstrated that explicit
   `Active` / `Deprecated` / `Removed` labels keep an extensible standard
   honest; we adopt the same pattern.

3. **Running Code Before Stability.** No identifier moves to **Stable**
   without a working reference implementation and at least two maintainer
   approvals. This is the rule that worked for HTTP/2 (SPDY ran in
   production before standardization) and QUIC (gQUIC ran in Chrome
   before becoming RFC 9000).

### 2.3 Two Tracks

- **Community track.** Extensions for general interoperability. Use a
  non-vendor category prefix (e.g., `irp.metering.*`) and MUST go through
  the review process (§7–§8).

- **Vendor track.** Proprietary extensions. Use the
  `irp.vendor.<vendor-id>.*` prefix (§9) and MAY ship without review.
  Clients MUST be able to ignore unrecognized vendor extensions safely.

---

## 3. Capability Identifier Format

### 3.1 General Format

A capability identifier is an ASCII string of the form:

```
irp.<category>.<name>[.<version>]
```

Where:

| Component   | Definition                                                                                          |
| ----------- | --------------------------------------------------------------------------------------------------- |
| `irp`       | Fixed literal prefix. MUST be lowercase.                                                            |
| `<category>`| One of the categories in §3.2. MUST be lowercase.                                                   |
| `<name>`    | Short feature name. MUST match `[a-z0-9]([a-z0-9-]*[a-z0-9])?`. Hyphens allowed; underscores not.   |
| `<version>` | Optional. MUST match `v[0-9]+`. Used only for breaking changes within the same `<name>` (see §10). |

The full identifier MUST match:

```
^irp\.[a-z]+\.[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9-]+)?(\.v[0-9]+)?$
```

(The third optional segment exists only for vendor-prefixed identifiers; see
§3.4.) Identifiers are case-sensitive; implementations MUST NOT canonicalize
or fold case.

The total length of a capability identifier MUST NOT exceed **128
characters**. Implementations MAY reject longer values.

### 3.2 Categories

| Category          | Purpose                                                                              |
| ----------------- | ------------------------------------------------------------------------------------ |
| `transport`       | Wire transports (HTTP/2, HTTP/3, future QUIC profiles).                              |
| `metering`        | Schemes for counting work and binding it to receipts (token counts, input hashes).   |
| `audit`           | Audit-trail mechanisms (Merkle trees, TEE attestation, ZK proofs).                   |
| `qos`             | Quality-of-service class systems.                                                    |
| `auth`            | Authentication and proof-of-possession schemes.                                      |
| `observability`   | Streaming receipts, metrics, traces, debug hooks.                                    |
| `experimental`    | Research-grade or unstable identifiers. SHOULD use this category instead of others when state is `Experimental`. |
| `vendor`          | Proprietary, vendor-prefixed identifiers (see §3.4).                                 |

New categories MUST NOT be introduced except by an extension proposal that
amends this document.

### 3.3 Community Identifiers

A **community identifier** uses any non-`vendor` category. Community
identifiers MUST be reviewed (§8) before they may appear in a registry row
with state `Stable` or `Deprecated`. Implementations MAY emit Experimental or
Proposed community identifiers, but receivers are not required to understand
them.

### 3.4 Vendor-Prefixed Identifiers

A **vendor identifier** uses the `vendor` category and a vendor-id segment:

```
irp.vendor.<vendor-id>.<name>
```

Where `<vendor-id>` is a short, stable, lowercase string registered by the
vendor with the IRP maintainers (typically the vendor's primary domain,
shortened — e.g., `acme`, `examplelabs`, `northstar`). A vendor-id MUST
match `[a-z]([a-z0-9-]*[a-z0-9])?` and SHOULD be ≤ 24 characters.

Vendor identifiers do **not** require review. The vendor is solely
responsible for their semantics. A vendor-id is reserved on a first-come,
first-served basis to prevent collisions; the maintainers MAY refuse a
vendor-id that is misleading, abusive, or attempts to impersonate another
party.

Receivers MUST NOT fail a connection or receipt solely because a vendor
identifier is unrecognized; see the skip-on-unknown rule in §8.3.

### 3.5 Examples

| Identifier                              | Valid? | Notes                                                       |
| --------------------------------------- | ------ | ----------------------------------------------------------- |
| `irp.transport.http2`                   | Yes    | Stable Core transport.                                      |
| `irp.metering.token-count.v1`           | Yes    | Versioned community identifier.                             |
| `irp.audit.merkle.v1`                   | Yes    | Versioned community identifier.                             |
| `irp.vendor.acme.realtime-burst`        | Yes    | Vendor identifier, no review required.                      |
| `irp.experimental.cohort-receipt`       | Yes    | Experimental community identifier.                          |
| `IRP.transport.http2`                   | No     | Uppercase prefix.                                           |
| `irp.transport.HTTP2`                   | No     | Uppercase name.                                             |
| `irp.transport.http_2`                  | No     | Underscore not allowed.                                     |
| `irp.foo.bar`                           | No     | `foo` is not a recognized category.                         |
| `irp.metering.token-count.v1.beta`      | No     | Version segment must match `v[0-9]+` exactly.               |

---

## 4. Lifecycle States

Every registered identifier is in exactly one of the following states. The
state is the registry's contract with implementations.

### 4.1 State Definitions

| State          | Stability                                                                 | Notice Period | Receiver MUST                                    |
| -------------- | ------------------------------------------------------------------------- | ------------- | ------------------------------------------------ |
| Experimental   | Opt-in, MAY change without notice. Identifier SHOULD use `irp.experimental.*` prefix. | None          | Treat as unrecognized if not explicitly enabled. |
| Proposed       | Submitted via §7 process; under review. Maximum 90 days in this state.    | None          | Be prepared for renaming or rejection.           |
| Stable         | Accepted by maintainers; semantics frozen. Backwards-compatible changes only. | N/A           | Implement per spec; reject malformed values.     |
| Deprecated     | Marked for removal. Continues to function.                                | ≥ 6 months    | Emit a deprecation warning if used (§4.3).       |
| Removed        | No longer registered. Identifier MUST NOT be reused for 24 months.        | N/A           | Treat as unrecognized; SHOULD log if observed.   |

### 4.2 State Transitions

The permitted transitions are:

```
Experimental ──► Proposed ──► Stable ──► Deprecated ──► Removed
     │              │
     └──► (abandoned, no longer listed)
                    │
                    └──► (rejected, not listed)
```

- An Experimental identifier MAY be promoted directly to Proposed when a
  full proposal (§7) is submitted.
- A Proposed identifier MUST become Stable, be returned to Experimental,
  or be rejected within **90 days**. Maintainers MAY extend the review
  window once, by at most 30 days, with public notice.
- A Stable identifier MAY only become Deprecated. It MUST NOT skip
  directly to Removed.
- A Deprecated identifier MUST remain in the registry for at least
  **6 months** after the deprecation announcement before it MAY be moved
  to Removed.
- A Removed identifier MUST NOT be reissued (i.e., re-registered with the
  same string) for at least **24 months** after removal, regardless of
  whether the new semantics differ.

### 4.3 Deprecation Warnings

When an implementation uses a Deprecated identifier — for example,
advertising it during capability negotiation or emitting it in a receipt —
the receiving party SHOULD log a deprecation warning that includes:

- The deprecated identifier.
- The date it was deprecated.
- The earliest date it MAY be removed.
- The recommended replacement, if any.

Servers MAY also emit a `Warning` HTTP header (per RFC 7234 §5.5, code
299) on responses that depend on a Deprecated identifier. Clients MUST
NOT fail solely because such a warning is present.

### 4.4 Backwards-Compatible Changes to Stable Identifiers

While Stable, the wire-level semantics of an identifier are frozen. The
following changes are considered **backwards-compatible** and MAY be made
without changing state or version:

- Clarifying ambiguous prose in the referenced specification.
- Adding new optional fields to a payload.
- Adding new permitted values to an extensible enumeration, where unknown
  values were already required to be ignored.
- Tightening a SHOULD into a MUST when no compliant implementation
  relied on the looser behavior.

The following are **breaking changes** and MUST be made via a new versioned
identifier (§10), not by mutating the existing one:

- Removing or renaming a required field.
- Changing the type, encoding, or unit of a field.
- Changing the meaning of an existing enumerated value.
- Loosening a MUST into a SHOULD or MAY.

---

## 5. Initial Registry

The following identifiers are registered as of IRP v0.1. The
`Since` column gives the IRP version in which the identifier first
appeared in this registry.

### 5.1 Transport

| Identifier              | State        | Since | Removed After | Reference                              |
| ----------------------- | ------------ | ----- | ------------- | -------------------------------------- |
| `irp.transport.http2`   | Stable       | 0.1   | —             | [Core Protocol](./irp-core.md)         |
| `irp.transport.http3`   | Experimental | 0.1   | —             | [Core Protocol](./irp-core.md) §future |

### 5.2 Metering

| Identifier                       | State  | Since | Removed After | Reference                       |
| -------------------------------- | ------ | ----- | ------------- | ------------------------------- |
| `irp.metering.token-count.v1`    | Stable | 0.1   | —             | [Metering](./irp-metering.md)   |
| `irp.metering.input-hash`        | Stable | 0.1   | —             | [Metering](./irp-metering.md)   |
| `irp.metering.output-hash`       | Stable | 0.1   | —             | [Metering](./irp-metering.md)   |

### 5.3 Audit

| Identifier                     | State        | Since | Removed After | Reference                       |
| ------------------------------ | ------------ | ----- | ------------- | ------------------------------- |
| `irp.audit.merkle.v1`          | Stable       | 0.1   | —             | [Metering](./irp-metering.md)   |
| `irp.audit.tee-attestation`    | Experimental | 0.1   | —             | Deferred to a future profile.   |
| `irp.audit.zk-proof`           | Experimental | 0.1   | —             | Deferred to a future profile.   |

### 5.4 QoS

| Identifier              | State  | Since | Removed After | Reference            |
| ----------------------- | ------ | ----- | ------------- | -------------------- |
| `irp.qos.5class.v1`     | Stable | 0.1   | —             | [QoS](./irp-qos.md)  |

### 5.5 Auth

| Identifier         | State    | Since | Removed After | Reference              |
| ------------------ | -------- | ----- | ------------- | ---------------------- |
| `irp.auth.bearer`  | Stable   | 0.1   | —             | [Auth](./irp-auth.md)  |
| `irp.auth.dpop`    | Optional | 0.1   | —             | [Auth](./irp-auth.md)  |
| `irp.auth.mtls`    | Optional | 0.1   | —             | [Auth](./irp-auth.md)  |

> **Note on `Optional`**: Auth identifiers labeled `Optional` are Stable in
> their definition but are not required by the Core Conformance Profile.
> A conforming implementation MAY support them; if it does, it MUST follow
> the referenced spec exactly. They are listed here as Optional rather than
> Stable to make their non-mandatory status visible at a glance. For
> lifecycle purposes (§4) they behave identically to Stable.

### 5.6 Observability

| Identifier                             | State        | Since | Removed After | Reference                                  |
| -------------------------------------- | ------------ | ----- | ------------- | ------------------------------------------ |
| `irp.observability.streaming-receipt`  | Experimental | 0.1   | —             | TBD; see §7 for proposing a stable spec.   |

### 5.7 Reading the Registry

- **State** is the lifecycle state from §4.
- **Since** is the IRP version in which the row was added to the registry.
  Never decreases.
- **Removed After** is populated only when an identifier is moved to
  `Deprecated` (set to the earliest date it MAY be removed) or `Removed`
  (set to the actual removal date).
- **Reference** is the normative document that defines the identifier's
  semantics. For Experimental identifiers without a finalized reference,
  this column points to the proposal or notes "Deferred". An Experimental
  row without a reference is a placeholder reservation; it confers no
  interoperability guarantee.

---

## 6. Extension Proposal Template

Every proposal for a new community identifier — or for a state change
(e.g., Experimental → Proposed → Stable) — MUST be filed using the
template below. Vendor-prefixed extensions (§9) do NOT use this template.

A proposal MUST include the following sections in order. Each section is
required unless explicitly marked optional.

### 6.1 Required Sections

1. **Identifier (preliminary).**
   The proposed capability identifier, conforming to §3.1. Mark as
   "preliminary" until accepted.

2. **Motivation.**
   At least one concrete use case with a real, named pain point.
   Hypothetical use cases are not sufficient. State who is blocked
   today, what they are doing as a workaround, and why a registered
   identifier is the right solution.

3. **Specification.**
   Normative prose using RFC 2119 keywords. Cover:
   - Pre-conditions for advertising the capability.
   - Wire format (request, response, receipt fields).
   - Processing rules.
   - Error handling.
   - Interaction with the Core.

4. **Wire format / header changes.**
   Exact byte- or field-level definition of any new headers, JSON
   fields, or framing. If the extension only re-uses existing wire
   shapes, say so explicitly.

5. **Security considerations.**
   Threat model, attacker capabilities assumed, and mitigations. At
   minimum: confidentiality, integrity, replay protection, denial of
   service, downgrade attacks. State explicitly if the extension
   weakens any Core security property.

6. **Compatibility analysis.**
   Answer both questions:
   - Does the extension **break** the Core in any way? (If yes, the
     proposal MUST be rejected unless it is a Core revision.)
   - Does the extension **extend** the Core, and how? Specifically, what
     does an implementation that does NOT implement this extension see
     when it interacts with one that does?

7. **Reference implementation.**
   A link to running code that implements the proposal. Per the lessons
   in `research/05_ecosystem_analysis.md` ("running code beats running
   prose"), a proposal without a reference implementation MUST NOT
   reach the Stable state. The reference implementation MUST be open
   source under an OSI-approved license.

### 6.2 Optional Sections

- **Alternatives considered.** What other designs were evaluated and why
  this one was chosen.
- **Future work.** What follow-up extensions might build on this one.
- **Test vectors.** Concrete request/response pairs that conforming
  implementations MUST handle.

### 6.3 Style

Proposals SHOULD be 5–30 pages. Shorter proposals are typically
under-specified; longer ones typically combine several extensions and
SHOULD be split.

---

## 7. Submission and Review Process

### 7.1 Submission

A proposal is submitted by:

1. Opening an issue **and** a pull request on
   [github.com/Kampter/Menverse](https://github.com/Kampter/Menverse).
   - The issue serves as the public discussion thread.
   - The pull request adds a row to the registry in §5 and includes the
     full proposal text under `docs/spec/proposals/<identifier>.md`.
2. Tagging the issue with the `irp-extension` label.
3. Cross-posting a notice to the IRP mailing list / discussions board
   (channel TBD; until established, a comment on the canonical
   tracking issue is sufficient).

### 7.2 Maintainer Triage

Maintainers MUST respond to a new proposal within **30 days** with one of:

- **Accept for review** — assign to the public comment period (§7.3).
- **Request changes** — list specific blockers; clock pauses while the
  author iterates.
- **Decline** — close with a written explanation. The proposer MAY
  appeal once by re-opening with new evidence.

Silence after 30 days is not consent. Proposers SHOULD escalate by
pinging the maintainers list.

### 7.3 Public Comment Period

Once accepted for review, the proposal enters a **30-day public comment
period**. During this period:

- Anyone MAY comment on the issue.
- The proposer SHOULD respond to substantive comments and revise as
  needed.
- The state of the proposed identifier in the registry is `Proposed`.
- The total elapsed time from `Proposed` to either `Stable` or back to
  `Experimental` MUST NOT exceed 90 days from initial submission.

### 7.4 Acceptance Criteria

A proposal MAY transition to `Stable` only when **all** of the following
are true:

1. A reference implementation exists (per §6.1.7) and has been verified
   to interoperate with at least one independent implementation.
2. **At least two maintainers** have publicly approved (consensus model;
   no single maintainer can block, but no single maintainer can ratify).
3. No unresolved blocking objections from the public comment period.
4. The Compatibility Analysis (§6.1.6) demonstrates the proposal does
   not break the Core.

If all criteria are met, a maintainer merges the registry PR and updates
the row's state to `Stable`.

### 7.5 Marking as Stable Requires Production Use

An identifier moves to `Stable` only after **at least one production
deployment** has operated successfully for ≥ 30 consecutive days.
If review completes without production evidence, the identifier stays
in `Proposed` (or returns to `Experimental`) until evidence
accumulates.

"Production deployment" means a deployment that serves real
(non-test) traffic, is operated by a party other than the proposer (or
is independently verified), and has run for ≥ 30 consecutive days
without rolling back the extension.

### 7.6 Rejection and Appeal

If a proposal is rejected, the closing maintainer MUST provide a written
rationale. The proposer MAY appeal once by reopening with additional
evidence. A second rejection is final for that revision; a substantially
revised proposal with a different identifier MAY be filed.

### 7.7 Out-of-Band Channels

The process above is the **only** path to a registered community
identifier. Private agreements produce vendor-prefixed extensions (§9),
not registered identifiers.

---

## 8. Vendor-Prefixed Extensions

### 8.1 Purpose

Vendor-prefixed extensions exist so that providers can ship features at
their own pace without being bottlenecked by the registry process. They
also serve as a **proving ground**: a feature that succeeds across
multiple deployments under different vendor IDs is a strong candidate
for promotion to a community identifier.

### 8.2 Rules

- Vendor identifiers MUST use the form
  `irp.vendor.<vendor-id>.<name>` (§3.4).
- Vendor identifiers MAY be added, changed, or removed at the vendor's
  discretion. The vendor SHOULD publish a stability policy for their
  own identifiers, but the IRP registry does not enforce one.
- Vendors MUST NOT use a vendor-id they have not registered.
- Vendors MUST NOT impersonate another vendor's vendor-id.

### 8.3 Skip-on-Unknown Rule

When a client encounters a vendor identifier it does not recognize, it:

- **MUST** parse the surrounding wire structure as if the unknown
  capability were absent.
- **MUST NOT** terminate the connection, fail the receipt, or surface
  an error to the user solely because of the unknown identifier.
- **SHOULD** log the unknown identifier at debug level for operator
  visibility.
- **MAY** include the unknown identifier verbatim in any audit trail
  it emits.

This rule applies symmetrically to servers receiving unknown vendor
identifiers from clients. The skip-on-unknown rule is what makes vendor
extensions safe at the ecosystem level: a client built against one
provider's vendor extensions does not break when it talks to another
provider that does not implement them.

### 8.4 Promotion to Community

A vendor-prefixed extension MAY be promoted to a community identifier by
filing a proposal (§6) under a non-vendor category. The proposal SHOULD
cite the vendor extension(s) that demonstrate production use, but the
community identifier MUST have its own normative specification — the
vendor's documentation alone is not sufficient.

If a vendor extension is promoted, the original vendor identifier
typically remains usable for backwards compatibility, but the vendor
SHOULD encourage clients to migrate to the community identifier. The
two identifiers refer to the same wire feature; receivers SHOULD treat
them as equivalent during the transition.

---

## 9. Versioning Within Identifier

When a Stable identifier needs a breaking change (per §4.4), a new
identifier is registered with a `.v<N+1>` suffix:

- `irp.metering.token-count.v1` defines the v1 wire format.
- `irp.metering.token-count.v2` (hypothetical) would define a
  backwards-incompatible v2.

Rules:

- A new version MUST go through the full proposal process (§6–§7),
  including a fresh reference implementation.
- The previous version is **automatically Deprecated** on the day the
  new version reaches Stable, with the standard 6-month notice.
- Implementations MAY support both versions simultaneously; if they do,
  they MUST advertise both during capability negotiation and let the
  peer choose.
- Identifiers that have never had a breaking change MAY omit the
  version segment entirely (e.g., `irp.metering.input-hash`). When the
  first breaking change is needed, the proposer MUST register
  `…input-hash.v2` and treat the unversioned form as v1 for
  deprecation purposes.

The version segment is the **only** sanctioned mechanism for breaking
change within a single name. Implementations MUST NOT mutate the
semantics of an unversioned or `.v1` identifier in incompatible ways.

---

## 10. Implementation Notes

This section is **informative**.

### 10.1 Negotiating Capabilities

Implementations advertise the capability identifiers they support at
connection time (see [Core Protocol](./irp-core.md) for the exact wire
shape). A typical exchange:

```
client.capabilities = [
  "irp.transport.http2",
  "irp.metering.token-count.v1",
  "irp.metering.input-hash",
  "irp.metering.output-hash",
  "irp.audit.merkle.v1",
  "irp.qos.5class.v1",
  "irp.auth.bearer",
]

server.capabilities = client.capabilities + [
  "irp.observability.streaming-receipt",
  "irp.vendor.acme.realtime-burst",
]
```

The intersection determines which features are active for the session.
Identifiers the client does not recognize on the server side (here,
`irp.observability.streaming-receipt` and the vendor identifier) are
silently dropped per §3.4 / §8.3.

### 10.2 Handling Deprecated Identifiers

A receiver that sees a Deprecated identifier in a peer's capability
list:

1. SHOULD continue to interoperate using the Deprecated identifier.
2. SHOULD log a deprecation warning naming the replacement.
3. SHOULD prefer the replacement identifier when both are advertised.

A sender that advertises a Deprecated identifier:

1. SHOULD also advertise the replacement, if one exists, so peers can
   prefer it.
2. SHOULD migrate before the removal date listed in the registry.

---

## 11. References

### 11.1 Normative

- **[RFC 2119][rfc2119]** — Key words for use in RFCs to Indicate
  Requirement Levels.
- **[RFC 8174][rfc8174]** — Ambiguity of Uppercase vs Lowercase in
  RFC 2119 Key Words.
- **[Core Protocol](./irp-core.md)** — `irp-core.md`, IRP Core Protocol
  v0.1.
- **[Conformance](./irp-conformance.md)** — `irp-conformance.md`, IRP
  Conformance Profile v0.1.
- **[QoS](./irp-qos.md)** — `irp-qos.md`, IRP QoS Class System v0.1.
- **[Metering](./irp-metering.md)** — `irp-metering.md`, IRP Metering
  Specification v0.1.
- **[Auth](./irp-auth.md)** — `irp-auth.md`, IRP Authentication
  Schemes v0.1.

### 11.2 Informative

- `research/01_internet_standards_history.md` — historical lessons on
  HTTP/2, QUIC, and "running code".
- `research/05_ecosystem_analysis.md` — vendor incentives and the case
  for vendor-prefixed extensions.
- `research/09_cloud_standardization_failures.md` — CDMI, OCCI, and the
  cost of "everything optional".
- Model Context Protocol (MCP) — extension lifecycle pattern adapted
  here.

---

## Appendix A. Change Log

| Version | Date       | Notes                                |
| ------- | ---------- | ------------------------------------ |
| 0.1     | 2026-05-08 | Initial publication of the registry. |

## Appendix B. Open Questions

Deferred to future revisions:

1. **Capability bundles.** Named bundles (e.g., "Audit-EU-2026") that
   pin a set of identifiers for regulatory profiles.
2. **Per-identifier deprecation grace.** Configurable notice periods,
   e.g., shorter for security-driven removals.
3. **Trust anchor for vendor-id registration.** A lighter-weight
   process than maintainer-mediated first-come-first-served.
4. **Identifier translation.** Bidirectional mapping to neighboring
   standards (OpenTelemetry, MCP).
