# IRP Metering & Audit Log

**Document**: IRP Metering & Audit Log Specification
**Status**: Draft
**Version**: 0.1.0
**Companion to**: [IRP Core Protocol](./irp-core.md), [IRP Auth & Discovery](./irp-auth.md), [IRP Conformance](./irp-conformance.md)

---

## 1. Abstract

This document defines normative rules for **metering, receipt issuance, signing,
and audit-log integrity** in the Inference Receipt Protocol (IRP). It specifies
how Large Language Model (LLM) providers MUST report per-request usage in a
**signed receipt**, how receipts are **canonically serialized** for signing, and
how clients MUST verify receipts to detect tampering, replay, and over-counting
("ghost tokens"). It also specifies an OPTIONAL **append-only Merkle audit log**
that providers SHOULD operate to enable third-party inclusion proofs and
ecosystem-wide auditability.

The goal is to make AI inference billing **client-verifiable**: a receipt that
cannot be silently modified, that cannot be replayed, and whose token counts can
be checked locally by the customer with a deterministic tokenizer.

This document is a companion to the [IRP Core Protocol](./irp-core.md) and
applies the canonical signing rules across the entire receipt-bearing surface of
the protocol.

---

## 2. Status & Conventions

This is a **Draft** specification. It is intended for implementation review and
feedback. Future revisions may introduce backward-incompatible changes prior to
v1.0.

The key words "**MUST**", "**MUST NOT**", "**REQUIRED**", "**SHALL**", "**SHALL
NOT**", "**SHOULD**", "**SHOULD NOT**", "**RECOMMENDED**", "**MAY**", and
"**OPTIONAL**" in this document are to be interpreted as described in
[RFC 2119](https://www.rfc-editor.org/rfc/rfc2119) and
[RFC 8174](https://www.rfc-editor.org/rfc/rfc8174) when, and only when, they
appear in all capitals, as shown here.

Throughout this document:

- **"Provider"** refers to an entity that issues receipts (typically an LLM API
  operator).
- **"Client"** refers to an entity that consumes receipts (typically the
  customer or its billing-audit agent).
- **"Receipt"** refers to a single signed JSON object as defined in Section 4.
- **"Canonical bytes"** refers to the deterministic UTF-8 byte serialization
  defined in Section 5.

All times are in UTC unless otherwise specified. All hashes are SHA-256 unless
otherwise specified. All signatures are Ed25519 ([RFC 8032](https://www.rfc-editor.org/rfc/rfc8032))
unless otherwise specified.

---

## 3. Introduction

### 3.1 Background

LLM inference is billed by token count. However, **token counting is not
standardized**: the same input passed to different providers can yield token
counts that differ by up to 9× (notably with Gemini models compared to OpenAI),
and providers have been observed to report token counts inconsistent with
locally-computed counts using the documented tokenizer ("ghost tokens").
Receipts are typically returned as plain JSON, allowing **silent modification**
in transit or after-the-fact, and there is no widely-deployed mechanism for
**replay protection** or for third parties to audit a provider's billing
ledger.

### 3.2 Threat Model

This specification addresses the following adversaries and failure modes:

| # | Threat | Description |
|---|--------|-------------|
| T1 | **Malicious over-counting** | Provider inflates `input_tokens`, `output_tokens`, or `total_tokens` beyond what a deterministic tokenizer would produce on the same bytes. |
| T2 | **Receipt tampering** | A man-in-the-middle, a compromised proxy, or a malicious provider modifies receipt fields (e.g. `cost`, `total_tokens`) after issuance. |
| T3 | **Replay** | An attacker (or buggy provider) re-uses a previously-issued receipt for a new request, causing double-billing or stale-data acceptance. |
| T4 | **Ghost tokens** | Provider charges for tokens that do not appear in the canonicalized input or output (e.g. invisible system prompts, padding, hidden reasoning) without disclosing them in `reasoning_tokens` or equivalent. |
| T5 | **Audit-log forgery** | Provider claims a receipt was "logged" but is unable to produce an inclusion proof against a previously-published Merkle root. |
| T6 | **Key confusion** | Attacker substitutes a public key under their control to forge receipts. |

### 3.3 Goals

- **Verifiability**: a client with the provider's public key MUST be able to
  detect any modification of a receipt.
- **Replay resistance**: each receipt MUST carry a fresh nonce and a timestamp
  that the client can use to bound acceptance.
- **Local re-counting**: input and output bytes are hashed and bound to the
  receipt so the client MAY recount tokens locally.
- **Auditability**: receipts MAY be logged in an append-only Merkle structure
  with periodically-published roots, enabling third-party verification.

### 3.4 Non-Goals

- This document does **not** specify the wire protocol (HTTP routes, headers,
  status codes). See [IRP Core Protocol](./irp-core.md).
- This document does **not** specify how providers price tokens. The `cost`
  block is descriptive, not prescriptive.
- This document does **not** specify confidentiality of receipts. Receipts MAY
  contain sensitive metadata; transport-layer protection (TLS) is REQUIRED, but
  receipt content is not encrypted by IRP itself.

---

## 4. Receipt Schema

### 4.1 Top-level structure

A receipt is a JSON object. Implementations MUST emit each field at the top
level of the object (no nesting under a wrapper). The following table lists all
fields, their types, and whether they are REQUIRED or OPTIONAL.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `request_id` | string (UUID v4) | REQUIRED | Globally unique identifier for the inference request. MUST be a UUID v4 per [RFC 4122](https://www.rfc-editor.org/rfc/rfc4122). |
| `timestamp` | string (RFC 3339) | REQUIRED | UTC timestamp when the receipt was issued. MUST conform to [RFC 3339](https://www.rfc-editor.org/rfc/rfc3339) `date-time` with `Z` suffix or `+00:00`. |
| `nonce` | string (base64) | REQUIRED | At least 128 bits of cryptographically random data, base64-encoded (RFC 4648 §4, padded). |
| `version` | string (semver) | REQUIRED | IRP receipt schema version. This document defines `0.1.0`. |
| `provider` | string | REQUIRED | Provider identifier (e.g. `"openai"`, `"anthropic"`). MUST match the issuer in the provider directory. |
| `model` | string | REQUIRED | Model name as advertised by the provider (e.g. `"gpt-4o"`). |
| `model_version` | string | OPTIONAL | Specific model version or revision (e.g. `"gpt-4o-2024-11-20"`). |
| `policy_id` | string | OPTIONAL | Identifier for the pricing/quota policy applied to this request. |
| `input_tokens` | integer | REQUIRED | Number of tokens in the request input as reported by the provider. MUST be ≥ 0. |
| `output_tokens` | integer | REQUIRED | Number of tokens in the response output as reported by the provider. MUST be ≥ 0. |
| `reasoning_tokens` | integer | OPTIONAL | Tokens consumed by hidden chain-of-thought / reasoning, if any. MUST be ≥ 0 when present. |
| `cached_tokens` | integer | OPTIONAL | Tokens served from prompt cache, if applicable. MUST be ≥ 0 when present. |
| `total_tokens` | integer | REQUIRED | Sum charged for billing. MUST equal `input_tokens + output_tokens + (reasoning_tokens \|\| 0)` minus any provider-defined cache discount; clients MUST be able to reproduce the relation from `policy_id`. |
| `input_hash` | string (hex) | REQUIRED | SHA-256 of the canonical input bytes (Section 9), lowercase hex. 64 characters. |
| `output_hash` | string (hex) | REQUIRED | SHA-256 of the canonical output bytes (Section 9), lowercase hex. 64 characters. |
| `latency` | object | REQUIRED | Latency breakdown; see Section 4.2. |
| `cost` | object | REQUIRED | Monetary cost breakdown; see Section 4.3. |
| `signature` | string (base64) | REQUIRED | Ed25519 signature over canonical bytes (Section 5), base64-encoded. |
| `public_key` | string (base64) | REQUIRED | Ed25519 public key of the signing entity, base64-encoded (32 bytes raw). |
| `signature_alg` | string | REQUIRED | Signature algorithm identifier. MUST be `"ed25519"` for this version. |

### 4.2 `latency` object

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `queue_ms` | integer | REQUIRED | Time spent in provider's queue before processing began, in milliseconds. MUST be ≥ 0. |
| `ttft_ms` | integer | REQUIRED | Time from request acceptance to first output token, in milliseconds. MUST be ≥ 0. |
| `tpot_ms` | integer | REQUIRED | Average time per output token across the full generation, in milliseconds. MUST be ≥ 0. |
| `total_ms` | integer | REQUIRED | Total wall-clock duration from request acceptance to last output token, in milliseconds. MUST be ≥ 0 and ≥ `queue_ms + ttft_ms`. |

All values MUST be integers (millisecond resolution). Sub-millisecond timings
MUST be rounded to nearest integer.

### 4.3 `cost` object

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `currency` | string (ISO 4217) | REQUIRED | Three-letter currency code (e.g. `"USD"`, `"EUR"`). |
| `input` | string (decimal) | REQUIRED | Input cost as a string-encoded decimal (e.g. `"0.000123"`). String form avoids float rounding. |
| `output` | string (decimal) | REQUIRED | Output cost. |
| `total` | string (decimal) | REQUIRED | Sum of `input + output` plus any other line items, in `currency`. |

Decimal strings MUST match the regex `^-?(0|[1-9][0-9]*)(\.[0-9]+)?$` (no
leading zeros, no exponent notation, no trailing zeros required but permitted
within the fractional part).

### 4.4 Example receipt (pretty-printed)

```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2026-05-08T14:23:01Z",
  "nonce": "Qk1MMn8gw3xMtX2yZ4vP9w==",
  "version": "0.1.0",
  "provider": "openai",
  "model": "gpt-4o",
  "model_version": "gpt-4o-2024-11-20",
  "policy_id": "tier-standard-2026-q2",
  "input_tokens": 42,
  "output_tokens": 128,
  "reasoning_tokens": 0,
  "cached_tokens": 0,
  "total_tokens": 170,
  "input_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "output_hash": "2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae",
  "latency": {
    "queue_ms": 12,
    "ttft_ms": 340,
    "tpot_ms": 18,
    "total_ms": 2604
  },
  "cost": {
    "currency": "USD",
    "input": "0.000105",
    "output": "0.001280",
    "total": "0.001385"
  },
  "signature": "MEUCIQDw8x...base64...==",
  "public_key": "MCowBQYDK2VwAyEA8j6V0a7p...==",
  "signature_alg": "ed25519"
}
```

> The pretty-printed form is illustrative. Signing operates over **canonical
> bytes** (Section 5), not the pretty-printed text.

### 4.5 Forward-compatibility

Implementations MUST tolerate unknown top-level fields on receive (forward
compatibility). They MUST NOT include unknown fields when signing, and they MUST
include any unknown received fields in the canonical bytes when re-verifying a
foreign receipt. This means: **the canonical message is whatever fields are
present, except `signature` and `public_key`** (Section 5).

---

## 5. Canonical Serialization for Signing

The signature is computed over the **canonical bytes** of the receipt. The
canonical bytes are produced by the following deterministic procedure.

### 5.1 Procedure

Given a receipt object `R`:

1. Construct `R'` = `R` with the fields `signature` and `public_key` **removed**.
   All other fields (including `signature_alg`) MUST remain.
2. Recursively sort the keys of every JSON object in `R'` in **lexicographic
   order by Unicode code point** (UTF-16 code unit order, equivalent to byte
   order for ASCII). Arrays MUST preserve their order; only object keys are
   sorted.
3. Serialize `R'` to JSON with:
   - **No insignificant whitespace.** No spaces or newlines between tokens.
   - Separators `,` between elements and `:` between key and value.
   - Strings encoded per [RFC 8259](https://www.rfc-editor.org/rfc/rfc8259) with
     the minimal-escape rules of Section 5.2.
   - Numbers encoded per Section 5.3.
   - Booleans as the literals `true` / `false`. Null as `null`.
4. The resulting Unicode text is encoded as **UTF-8** with no byte-order mark.
5. The UTF-8 bytes are the **canonical bytes**. They are the message input to
   the Ed25519 signing primitive.

### 5.2 String encoding

- Solidus (`/`) MUST NOT be escaped.
- Forward-slash MUST NOT be escaped.
- Non-ASCII characters MUST be emitted as raw UTF-8 (NOT `\uXXXX`-escaped),
  except for control characters U+0000–U+001F and U+007F which MUST be
  `\u`-escaped in lowercase hex form (e.g. `	` for tab).
- Quotation mark (`"`) MUST be escaped as `\"`.
- Reverse solidus (`\`) MUST be escaped as `\\`.

### 5.3 Number encoding

- **Integers** MUST be emitted as bare integer literals with no leading zeros
  (e.g. `0`, `42`, `-7`). The literal `-0` MUST NOT be emitted; emit `0`.
- **Decimal strings** in the `cost` block are emitted as JSON **strings**, not
  JSON numbers. This avoids floating-point ambiguity. Producers and consumers
  MUST treat `cost.input`, `cost.output`, `cost.total` as opaque decimal
  strings.
- Implementations MUST NOT emit floating-point numbers in any receipt field.
  Latency values are integer milliseconds; token counts are integers; cost is a
  string.

### 5.4 Worked example

Suppose the receipt (after step 1, with `signature` and `public_key` removed)
is:

```json
{
  "version": "0.1.0",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2026-05-08T14:23:01Z",
  "nonce": "Qk1MMn8gw3xMtX2yZ4vP9w==",
  "provider": "openai",
  "model": "gpt-4o",
  "input_tokens": 42,
  "output_tokens": 128,
  "total_tokens": 170,
  "input_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "output_hash": "2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae",
  "latency": {"total_ms": 2604, "queue_ms": 12, "ttft_ms": 340, "tpot_ms": 18},
  "cost": {"currency": "USD", "total": "0.001385", "input": "0.000105", "output": "0.001280"},
  "signature_alg": "ed25519"
}
```

After step 2 (lexicographically sorted keys, recursively) and step 3 (no
whitespace), the canonical text is:

```
{"cost":{"currency":"USD","input":"0.000105","output":"0.001280","total":"0.001385"},"input_hash":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855","input_tokens":42,"latency":{"queue_ms":12,"total_ms":2604,"tpot_ms":18,"ttft_ms":340},"model":"gpt-4o","nonce":"Qk1MMn8gw3xMtX2yZ4vP9w==","output_hash":"2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae","output_tokens":128,"provider":"openai","request_id":"550e8400-e29b-41d4-a716-446655440000","signature_alg":"ed25519","timestamp":"2026-05-08T14:23:01Z","total_tokens":170,"version":"0.1.0"}
```

The UTF-8 bytes of that text are the input to Ed25519. The signature, base64-
encoded, is then placed in the `signature` field of the full receipt, and the
provider's public key is placed in `public_key`.

### 5.5 Determinism requirement

For the same input receipt object, **all conformant implementations MUST
produce byte-identical canonical bytes**. This is verified by the Conformance
test suite (see [IRP Conformance](./irp-conformance.md)). A producer that emits
non-deterministic canonical bytes is non-conformant even if its signatures
verify.

---

## 6. Anti-Replay

A signed receipt is **necessary but not sufficient**. Without replay protection,
an attacker (or a careless provider) can re-present a previously-valid receipt
to inflate billing or to satisfy a stale audit query. This section specifies the
mandatory anti-replay mechanism.

### 6.1 Nonce

Every receipt MUST carry a `nonce` of at least 128 bits of cryptographically-
random data, base64-encoded.

- Producers MUST generate the nonce from a cryptographically-secure source
  (e.g. `/dev/urandom`, `getrandom(2)`, or platform CSPRNG).
- Producers MUST NOT reuse a nonce across receipts. The probability of accidental
  collision at 128 bits is negligible.
- Producers SHOULD use 192 or 256 bits of entropy if their volume warrants it.

### 6.2 Timestamp window

Clients MUST reject any receipt whose `timestamp` differs from the client's
trusted clock by more than **±60 seconds**.

- Clients SHOULD use NTP-disciplined time. If the client's clock is known to be
  unreliable, the client MAY relax the window, but MUST NOT exceed ±5 minutes
  without an explicit operator decision.
- Providers MUST issue receipts with timestamps reflecting the actual issuance
  time, not the client's request time, not a rounded value.

### 6.3 Nonce-cache retention

Clients MUST maintain a local store of `(nonce, timestamp)` tuples for at least
the duration of the timestamp window plus a safety margin. **A retention period
of 10 minutes is RECOMMENDED.** During that window:

- If a receipt is received whose `nonce` already appears in the store, the
  client MUST reject it as a replay.
- After the window elapses, entries MAY be evicted; the timestamp window
  guarantees that a receipt outside the window would already be rejected on
  timestamp grounds.

### 6.4 Server-side nonce uniqueness

Providers MUST also ensure nonce uniqueness within their own issuance pipeline:
two distinct receipts MUST NOT share a nonce. This prevents accidental
duplicate issuance.

### 6.5 Why signature is insufficient

A signature attests to authenticity of bytes, not freshness. An attacker who
captures `(receipt, signature)` once can replay them indefinitely against any
client that does not check the timestamp **and** the nonce. Both checks are
REQUIRED.

---

## 7. Client Verification Flow

A conformant client MUST perform the following steps **in order** when
processing a received receipt. Failure at any step MUST result in the receipt
being **flagged with the specific reason**; the client MUST NOT silently accept
a partially-valid receipt.

### 7.1 Procedure

1. **Schema check.** Parse the receipt as JSON. Verify that all REQUIRED fields
   (Section 4) are present and well-typed. If any REQUIRED field is missing or
   malformed, FLAG `schema_invalid` and stop.

2. **Timestamp window.** Compute `|now - receipt.timestamp|`. If the difference
   exceeds ±60 seconds, FLAG `timestamp_skew` and stop.

3. **Nonce uniqueness.** Look up `receipt.nonce` in the local nonce store
   (Section 6.3). If present, FLAG `replay_detected` and stop. Otherwise, insert
   `(nonce, timestamp)` into the store.

4. **Input hash.** Compute `SHA-256` of the canonical input bytes (Section 9.1)
   that the client sent. Compare to `receipt.input_hash`. If they differ, FLAG
   `input_hash_mismatch` and stop.

5. **Output hash.** Compute `SHA-256` of the canonical output bytes (Section
   9.2) that the client received. Compare to `receipt.output_hash`. If they
   differ, FLAG `output_hash_mismatch` and stop.

6. **Local token recount.** Run a deterministic tokenizer (e.g. `tiktoken` for
   OpenAI-family models) over the canonical input and output bytes to obtain
   `local_input_tokens` and `local_output_tokens`. Compare to the
   provider-reported counts:

   - `input_diff_pct = |receipt.input_tokens - local_input_tokens| / max(local_input_tokens, 1)`
   - `output_diff_pct = |receipt.output_tokens - local_output_tokens| / max(local_output_tokens, 1)`

   If either exceeds the configured threshold (**default 5%**, configurable per
   policy), FLAG `token_count_mismatch` with both diffs in the flag detail. The
   client MAY continue verification (e.g. to still check the signature) but
   MUST surface the mismatch in the verification result.

7. **Signature verification.** Build the canonical bytes (Section 5) of the
   receipt with `signature` and `public_key` removed. Look up the provider's
   trusted public key (out-of-band; see Section 10) and verify it equals
   `receipt.public_key`. If keys do not match, FLAG `key_mismatch` and stop.
   Verify the Ed25519 signature over the canonical bytes using the public key.
   If verification fails, FLAG `signature_invalid` and stop.

8. **Acceptance.** If all preceding steps pass without flag, return
   `status = valid`. Otherwise, return `status = warning` (token-count
   mismatch only) or `status = error` (any other flag).

### 7.2 Pseudocode

```
function verify(receipt, sent_input_bytes, received_output_bytes,
                trusted_keys, nonce_store, now):
    if not schema_ok(receipt):
        return flag("schema_invalid")

    if abs(now - receipt.timestamp) > 60:
        return flag("timestamp_skew")

    if receipt.nonce in nonce_store:
        return flag("replay_detected")
    nonce_store.add(receipt.nonce, receipt.timestamp)

    if sha256(sent_input_bytes) != receipt.input_hash:
        return flag("input_hash_mismatch")

    if sha256(received_output_bytes) != receipt.output_hash:
        return flag("output_hash_mismatch")

    local_in  = tokenize(sent_input_bytes,     receipt.model)
    local_out = tokenize(received_output_bytes, receipt.model)
    in_diff  = abs(receipt.input_tokens  - local_in ) / max(local_in,  1)
    out_diff = abs(receipt.output_tokens - local_out) / max(local_out, 1)
    token_warn = (in_diff > 0.05) or (out_diff > 0.05)

    if receipt.public_key != trusted_keys[receipt.provider]:
        return flag("key_mismatch")
    if not ed25519_verify(canonical_bytes(receipt),
                          receipt.signature,
                          receipt.public_key):
        return flag("signature_invalid")

    return ok(token_warn=token_warn)
```

### 7.3 Threshold rationale

The default 5% threshold is empirically chosen: deterministic tokenizers for
the same model on the same bytes typically diverge by less than 1% across
implementations (the 9× discrepancies cited in Section 3.1 are between
*different* tokenizer families). The threshold is configurable so that
conservative deployments MAY set it tighter (1%) and tolerant deployments MAY
set it looser (10%). Setting it above 25% defeats the purpose and is NOT
RECOMMENDED.

---

## 8. Audit Log Integrity (Merkle)

Providers SHOULD maintain an **append-only Merkle audit log** of all issued
receipts. This enables:

- **Inclusion proofs**: a client can ask the provider to prove that a specific
  `request_id` was logged under a previously-published root.
- **Consistency proofs**: third parties (auditors, regulators) can verify that
  the log is append-only by comparing roots over time.
- **Tamper detection**: a provider that wishes to retroactively modify a
  receipt cannot do so without producing an inconsistent root, which is
  detectable.

The structure is modeled on [RFC 6962](https://www.rfc-editor.org/rfc/rfc6962)
(Certificate Transparency).

### 8.1 Tree structure

The log is a binary Merkle tree over the SHA-256 hashes of canonical receipt
bytes.

- **Leaf**: for receipt `R`, the leaf hash is
  `LH(R) = SHA-256(0x00 || canonical_bytes(R))`.
- **Internal node**: for left and right child hashes `L` and `R`, the internal
  hash is `IH(L, R) = SHA-256(0x01 || L || R)`.
- The single-byte domain separators `0x00` and `0x01` are mandatory and follow
  RFC 6962. They prevent second-preimage attacks via leaf/internal confusion.

The leaf hash is computed over the **same canonical bytes** used for signing
(Section 5), with `signature` and `public_key` excluded. The signature itself
is **not** part of the leaf hash, so a leaf is uniquely determined by receipt
content.

### 8.2 Append-only semantics

Once a receipt is appended to the log, it MUST NOT be removed or modified.
Tree size grows monotonically. The tree shape at size `n` is fully determined
by the leaves and follows RFC 6962's binary-decomposition rule.

### 8.3 Root publication

Providers SHOULD publish a **signed root** at regular intervals. A suggested
cadence is **once per hour**, with the root signed by the provider's IRP
issuance key (or a dedicated log-signing key documented in the provider
directory).

A root publication is a JSON object:

```json
{
  "tree_size": 1234567,
  "root_hash": "9b5e...hex...64chars",
  "timestamp": "2026-05-08T15:00:00Z",
  "signature": "base64==",
  "public_key": "base64==",
  "signature_alg": "ed25519"
}
```

The signature is computed over the canonical bytes of the same object with
`signature` and `public_key` removed (same rules as Section 5).

### 8.4 Endpoints

Providers that operate an audit log SHOULD expose the following HTTP endpoints
under their IRP API base path (see [IRP Core Protocol](./irp-core.md)):

#### 8.4.1 `GET /v1/irp/log/root`

Returns the current signed root.

**Request**: no parameters.

**Response (200)**: a JSON object as defined in Section 8.3.

**Caching**: the response MAY be served from a CDN-side cache for up to the
publication interval (e.g. 1 hour).

#### 8.4.2 `GET /v1/irp/log/proof`

Returns an inclusion proof for a given `request_id`.

**Query parameters**:

| Name | Required | Description |
|------|----------|-------------|
| `request_id` | REQUIRED | UUID of the receipt to prove. |
| `tree_size` | OPTIONAL | Tree size at which to anchor the proof. Defaults to current tree size. |

**Response (200)**:

```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "tree_size": 1234567,
  "leaf_index": 998001,
  "leaf_hash": "hex...64chars",
  "audit_path": [
    "hex...64chars",
    "hex...64chars",
    "..."
  ],
  "root_hash": "hex...64chars"
}
```

The `audit_path` is the list of sibling hashes from the leaf up to (but not
including) the root, in leaf-to-root order, exactly as defined in RFC 6962
§2.1.1.

**Response (404)**: if `request_id` is not in the log at the requested
`tree_size`.

#### 8.4.3 Verifying an inclusion proof (client-side)

```
function verify_inclusion(leaf_hash, leaf_index, tree_size, audit_path, root_hash):
    h = leaf_hash
    idx = leaf_index
    last = tree_size - 1
    for sibling in audit_path:
        if idx == last and idx % 2 == 0:
            # right edge: no sibling to combine, just promote
            pass  # (audit_path entry skipped per RFC 6962)
        elif idx % 2 == 0:
            h = SHA-256(0x01 || h || sibling)
        else:
            h = SHA-256(0x01 || sibling || h)
        idx //= 2
        last //= 2
    return h == root_hash
```

Implementations SHOULD follow the precise RFC 6962 algorithm for edge cases
(odd tree sizes, single-leaf trees).

### 8.5 Consistency proofs (OPTIONAL)

Providers MAY also expose a consistency-proof endpoint
`GET /v1/irp/log/consistency?old=<size1>&new=<size2>` that returns a path
proving the log of size `size1` is a prefix of the log of size `size2`. This is
RECOMMENDED for providers that publish historical roots, as it allows third
parties to detect retroactive log forks.

### 8.6 Privacy considerations

Receipts MAY contain sensitive metadata (`policy_id`, model, latency) and the
input/output hashes link a leaf to specific request bytes. Providers MUST NOT
expose receipt **content** through proof endpoints (only hashes and proof
paths). The leaf hash alone reveals nothing about the input/output bytes
without preimage knowledge.

---

## 9. Hash Computation Rules

This section specifies the exact byte sequences that go into `input_hash` and
`output_hash`.

### 9.1 Input hash

The input is hashed as follows, in priority order:

1. **OpenAI-style messages array.** If the request payload contains a `messages`
   array (the dominant convention as of 2026), the input bytes are the
   canonical JSON serialization of that array, using the same canonicalization
   rules as Section 5 (lex-sorted keys, no whitespace, UTF-8). Tools, system
   prompts, and any non-message parameters that affect billing MUST be included
   in the canonicalization (e.g. wrap as `{"messages": [...], "tools": [...], "system": "..."}`).

2. **Raw text fallback.** If the request is a raw-text completion (legacy
   completions API), the input bytes are the UTF-8 encoding of the prompt
   string with no additional framing.

3. **Provider-specific fallback.** If neither applies (e.g. multimodal requests
   with binary attachments), the provider MUST document its canonicalization in
   the provider directory and clients MUST follow that documented rule. The
   binary attachment hashes MUST be inlined as part of the canonical input.

`input_hash` is then `SHA-256(input_bytes)`, lowercase hex.

### 9.2 Output hash

The output is hashed over the **concatenation of assistant message contents**
in the order they appear in the response.

- For non-streaming responses, this is the `content` field (or equivalent) of
  each assistant message, concatenated as UTF-8 bytes with no separator.
- For tool-call responses, the canonical JSON of each tool call (lex-sorted
  keys, no whitespace) is appended after the text content of the message in the
  order produced.
- For streaming responses, the client MUST reassemble the full output (all
  tokens, all tool calls) and hash the **same bytes** that a non-streaming
  response would produce. The hash MUST NOT depend on chunk boundaries.

`output_hash` is then `SHA-256(output_bytes)`, lowercase hex.

### 9.3 Determinism

The hash MUST be byte-deterministic given the same logical input/output. Two
clients computing the hash from the same conversation transcript MUST obtain
the same hex string.

### 9.4 Empty bodies

For zero-byte input or output (rare but legal — e.g. empty system prompt),
the hash is the SHA-256 of the empty string:
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

---

## 10. Security Considerations

### 10.1 Public key distribution

The trust anchor of IRP is the provider's public key. Clients MUST obtain it
**out-of-band** from a trusted source. Acceptable sources include:

- The provider's well-known endpoint as defined in
  [IRP Auth & Discovery](./irp-auth.md), served over TLS with a publicly-trusted
  certificate, e.g. `https://api.example.com/.well-known/irp/keys`.
- A signed provider directory operated by a federation or registry.
- A direct exchange via an authenticated channel (vendor onboarding).

Clients MUST NOT trust a `public_key` field in a receipt without cross-checking
it against an out-of-band trusted source. Including the key in the receipt is
for transparency and auditability, not for trust establishment.

### 10.2 Key rotation

Providers SHOULD rotate signing keys at least annually. Rotation procedure:

1. Publish the new public key alongside the existing one in the well-known
   endpoint, with non-overlapping `valid_from` / `valid_until` timestamps and a
   transition window of at least 24 hours.
2. During the transition window, sign new receipts with the new key. Receipts
   issued before `new.valid_from` MUST verify with the old key.
3. After the transition window, retire the old key. Retain it (and its
   provenance) for audit purposes for the receipt-retention period (typically
   1–7 years per regulatory regime).

Clients MUST be able to maintain multiple trusted keys per provider and select
the correct one based on `receipt.public_key`.

### 10.3 Signing-key compromise

If a signing key is suspected of compromise:

1. The provider MUST immediately revoke the key by publishing a `revoked: true`
   flag on the well-known endpoint with a `revoked_at` timestamp.
2. The provider MUST sign all subsequent receipts with a fresh key.
3. Receipts with the compromised key and `timestamp >= revoked_at` MUST be
   rejected by clients.
4. Receipts with the compromised key and `timestamp < revoked_at` MAY be
   accepted, but clients SHOULD downgrade them to `warning` and require an
   inclusion proof against a published root that pre-dates `revoked_at`.

### 10.4 Tokenizer trust

The client-side tokenizer used in step 6 of the verification flow (Section 7)
must be trusted by the client. The client SHOULD use the same tokenizer
implementation that the provider documents (e.g. `tiktoken` with a specific
encoding name for OpenAI-family models). If the provider does not publish a
deterministic tokenizer, the client SHOULD treat token counts as advisory and
weight other checks (hashes, signature) more heavily.

### 10.5 Side channels

Receipts include latency metrics. In high-security deployments, latency may be
a side channel for inference content (e.g. variable-length output revealing
prompt class). IRP does not mitigate this; deployments concerned with side
channels SHOULD round latency values to coarse buckets, document the rounding
in `policy_id`, and accept the loss of fine-grained billing transparency.

### 10.6 Replay across clients

The nonce-store mechanism in Section 6 protects against replay against a
**single** client. An attacker who obtains a valid receipt MAY replay it
against a *different* client that has not previously seen it. This is mitigated
by the fact that the input/output hash binding makes the receipt useful only in
the context of the specific request/response pair; replaying against a client
who did not perform that exact request will fail step 4 (input hash mismatch).

### 10.7 Audit log forks

A malicious provider could maintain two divergent logs and serve different
roots to different clients. This attack is detectable if and only if clients
**share root observations** out-of-band (e.g. via a third-party auditor or a
gossip protocol). Operators of high-stakes deployments SHOULD subscribe to a
log-monitoring service or operate their own, independent log-witness.

---

## 11. IANA Considerations

This document requests IANA establish a registry titled **"IRP Signature
Algorithms"** under a new "Inference Receipt Protocol Parameters" group. The
registry is governed by the **Specification Required** policy
([RFC 8126](https://www.rfc-editor.org/rfc/rfc8126) §4.6).

### 11.1 Initial contents

| Identifier | Description | Reference | Status |
|------------|-------------|-----------|--------|
| `ed25519` | Ed25519 signature scheme over SHA-512 | [RFC 8032](https://www.rfc-editor.org/rfc/rfc8032) | MANDATORY |

### 11.2 Reserved (future)

The following identifiers are **reserved** for future allocation but not yet
specified by this document:

| Identifier | Intended algorithm |
|------------|--------------------|
| `ecdsa-p256` | ECDSA over NIST P-256 with SHA-256 |
| `ecdsa-p384` | ECDSA over NIST P-384 with SHA-384 |
| `ed448` | Ed448 signature scheme |
| `ml-dsa-44` | ML-DSA (FIPS 204) at security level 1 (post-quantum) |
| `ml-dsa-65` | ML-DSA at security level 3 (post-quantum) |

Future registrations MUST include: identifier string, full algorithm
specification, key encoding, signature encoding, and a stable normative
reference.

### 11.3 Audit-log domain separators

The bytes `0x00` (leaf domain) and `0x01` (internal-node domain) defined in
Section 8.1 are reserved by this specification and MUST NOT be reassigned for
other uses in the IRP audit-log hash.

---

## 12. References

### 12.1 Normative

- [RFC 2119] Bradner, S., "Key words for use in RFCs to Indicate Requirement
  Levels", BCP 14, RFC 2119, March 1997.
- [RFC 3339] Klyne, G. and C. Newman, "Date and Time on the Internet:
  Timestamps", RFC 3339, July 2002.
- [RFC 4122] Leach, P., Mealling, M., and R. Salz, "A Universally Unique
  IDentifier (UUID) URN Namespace", RFC 4122, July 2005.
- [RFC 4648] Josefsson, S., "The Base16, Base32, and Base64 Data Encodings",
  RFC 4648, October 2006.
- [RFC 6962] Laurie, B., Langley, A., and E. Kasper, "Certificate
  Transparency", RFC 6962, June 2013.
- [RFC 8032] Josefsson, S. and I. Liusvaara, "Edwards-Curve Digital Signature
  Algorithm (EdDSA)", RFC 8032, January 2017.
- [RFC 8126] Cotton, M., Leiba, B., and T. Narten, "Guidelines for Writing an
  IANA Considerations Section in RFCs", BCP 26, RFC 8126, June 2017.
- [RFC 8174] Leiba, B., "Ambiguity of Uppercase vs Lowercase in RFC 2119 Key
  Words", BCP 14, RFC 8174, May 2017.
- [RFC 8259] Bray, T., Ed., "The JavaScript Object Notation (JSON) Data
  Interchange Format", STD 90, RFC 8259, December 2017.

### 12.2 Companion documents

- [IRP Core Protocol](./irp-core.md) — wire format, HTTP endpoints, error
  codes.
- [IRP Auth & Discovery](./irp-auth.md) — authentication, well-known endpoints,
  provider directory.
- [IRP Conformance](./irp-conformance.md) — test vectors and conformance test
  suite.

### 12.3 Informative

- [FIPS 204] National Institute of Standards and Technology, "Module-Lattice-
  Based Digital Signature Standard", FIPS PUB 204, August 2024.
- [tiktoken] OpenAI, "tiktoken: a fast BPE tokeniser for use with OpenAI's
  models", https://github.com/openai/tiktoken.

---

## Appendix A. Field summary table

| Field | Type | Required | Hashed | Signed | Notes |
|-------|------|----------|--------|--------|-------|
| `request_id` | UUID | yes | no | yes | UUID v4 |
| `timestamp` | RFC 3339 | yes | no | yes | UTC |
| `nonce` | base64 | yes | no | yes | ≥128 bits |
| `version` | semver | yes | no | yes | `0.1.0` |
| `provider` | string | yes | no | yes |  |
| `model` | string | yes | no | yes |  |
| `model_version` | string | no | no | yes |  |
| `policy_id` | string | no | no | yes |  |
| `input_tokens` | integer | yes | no | yes |  |
| `output_tokens` | integer | yes | no | yes |  |
| `reasoning_tokens` | integer | no | no | yes |  |
| `cached_tokens` | integer | no | no | yes |  |
| `total_tokens` | integer | yes | no | yes |  |
| `input_hash` | hex | yes | binds input | yes | SHA-256 |
| `output_hash` | hex | yes | binds output | yes | SHA-256 |
| `latency.queue_ms` | integer | yes | no | yes |  |
| `latency.ttft_ms` | integer | yes | no | yes |  |
| `latency.tpot_ms` | integer | yes | no | yes |  |
| `latency.total_ms` | integer | yes | no | yes |  |
| `cost.currency` | ISO 4217 | yes | no | yes |  |
| `cost.input` | decimal string | yes | no | yes |  |
| `cost.output` | decimal string | yes | no | yes |  |
| `cost.total` | decimal string | yes | no | yes |  |
| `signature` | base64 | yes | no | **no** | Ed25519, excluded from canonical |
| `public_key` | base64 | yes | no | **no** | Excluded from canonical |
| `signature_alg` | string | yes | no | yes | `ed25519` for v0.1.0 |

---

## Appendix B. Error codes for verification flags

The following flag identifiers are RECOMMENDED for cross-implementation
consistency. Clients MAY emit additional codes; these MUST be unambiguous
suffixes prefixed with the implementation name.

| Code | Severity | Step | Meaning |
|------|----------|------|---------|
| `schema_invalid` | error | 1 | Required field missing or malformed. |
| `timestamp_skew` | error | 2 | `timestamp` outside ±60s window. |
| `replay_detected` | error | 3 | `nonce` already seen within retention window. |
| `input_hash_mismatch` | error | 4 | Computed input hash differs from receipt. |
| `output_hash_mismatch` | error | 5 | Computed output hash differs from receipt. |
| `token_count_mismatch` | warning | 6 | Local recount differs by more than threshold. |
| `key_mismatch` | error | 7 | `public_key` does not match trusted key for provider. |
| `signature_invalid` | error | 7 | Ed25519 verification failed. |

---

## Appendix C. Change log

| Version | Date | Notes |
|---------|------|-------|
| 0.1.0 | 2026-05-08 | Initial draft. |
