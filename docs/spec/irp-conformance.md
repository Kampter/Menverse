# IRP Conformance Profile

**Document**: `irp-conformance.md`
**Version**: v0.1
**Status**: Draft (MVP)
**Editors**: IRP Working Group

---

## 1. Abstract

This document defines the **conformance profiles** for the Inference Receipt
Protocol (IRP). It specifies two compliance levels — **IRP Core** and **IRP
Extended** — and supplies the **golden test vectors** by which an
implementation's claim of compliance is to be objectively validated.

A provider or client implementation MAY publicly claim conformance to a
profile **only if** every mandatory item in the corresponding checklist
passes the test vectors defined in §8. Conformance is the **single source of
truth** for the question "is this implementation IRP-compliant?". Marketing
language, internal documentation, and feature lists are NOT substitutes for
passing the vectors.

This conformance authority is the keystone that prevents the protocol from
fragmenting into mutually incompatible dialects. Lessons from prior
standardization efforts (see [research/07_telecom_standards_history.md] and
[research/09_cloud_standardization_failures.md]) show that protocols which
ship test suites and golden samples win, while those that delegate validation
to "implementer interpretation" fragment and die.

---

## 2. Status & Conventions

This document is a **draft specification** intended to mature alongside the
IRP MVP. It is published under the [IRP](./irp-core.md) umbrella.

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT",
"SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this
document are to be interpreted as described in
[RFC 2119](https://www.rfc-editor.org/rfc/rfc2119) and
[RFC 8174](https://www.rfc-editor.org/rfc/rfc8174) when, and only when,
they appear in all capitals.

All byte-level examples are presented as either lower-case hexadecimal
(`hex:`) or standard Base64 (`b64:`), as labelled. JSON examples are
presented in the **canonical form** mandated by §9 of
[Core Protocol](./irp-core.md): UTF-8, sorted keys, no insignificant
whitespace, and the `(",", ":")` separator pair (i.e. equivalent to
Python's `json.dumps(obj, sort_keys=True, separators=(",", ":"))`).

---

## 3. Introduction

### 3.1 Why Conformance Matters

Standards without conformance tests are aspirations. The history of the
Internet, telecommunications, and cloud APIs is a graveyard of "open"
specifications that everyone implemented slightly differently and that
ultimately fragmented into vendor lock-in. A protocol survives in the wild
when:

1. The mandatory baseline is small enough that any reasonable provider
   can implement it.
2. Optional capabilities are explicitly named so providers don't smuggle
   them into the baseline.
3. A neutral, published test suite produces a binary pass/fail answer.
4. Reference vectors are reproducible from a fixed seed so any party can
   regenerate them and verify byte-for-byte equality.

This document delivers (1)–(4) for IRP v0.1.

### 3.2 The Two Profiles

| Profile          | Status              | Required for       | Items   |
| ---------------- | ------------------- | ------------------ | ------- |
| **IRP Core**     | Mandatory baseline  | Any compliance     | C1–C9   |
| **IRP Extended** | Optional capability | Per-feature claim  | E1–E6   |

A provider that wants to call itself "IRP-compliant" MUST satisfy every
item in IRP Core (§4). A provider MAY additionally claim any subset of
IRP Extended (§5), and MUST enumerate which subset (e.g.
`"IRP Core v0.1; IRP Extended (E1, E3)"`).

Clients have their own conformance profile (§7) because verifying
receipts is asymmetric work — the verifier MUST do enough that simply
trusting the provider does not constitute "compliance".

### 3.3 Anti-Patterns Explicitly Forbidden

Implementers are reminded that the following do NOT constitute conformance:

- Implementing a *superset* of IRP Core that nonetheless skips a Core
  item (e.g. signing receipts but omitting nonces).
- Adding undocumented "extensions" inside Core fields and claiming the
  implementation is "Core-plus" rather than passing E-vectors.
- Self-certification by the provider without making test artefacts
  publicly reproducible from this document's seeds.

---

## 4. IRP Core Profile

A provider MUST implement every item in this table to claim
"IRP Core compliant v0.1". Each row links to the normative section in the
relevant specification and to the golden test vector that exercises it.

| ID  | Mandatory item                              | Acceptance criterion                                                                                                                                                              | Spec reference                                                       | Test vector              |
| --- | ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------- | ------------------------ |
| C1  | Frame format                                | Server emits receipt frames whose canonical JSON form matches the schema in Core §9 byte-for-byte; no extra top-level keys are present in the signed canonical.                  | [Core Protocol §9](./irp-core.md)                                    | TV1                      |
| C2  | Discovery                                   | `GET /.well-known/irp-configuration` returns 200 with the document fields enumerated in Auth & Discovery §4 and is fetchable over HTTPS.                                         | [Auth & Discovery §4](./irp-auth.md)                                 | Procedural (§9.1)        |
| C3  | Bearer Token authentication                 | Provider accepts `Authorization: Bearer <token>` (Mode A) and rejects malformed / missing tokens with `INVALID_AUTH`.                                                            | [Auth & Discovery §6 Mode A](./irp-auth.md)                          | Procedural (§9.1)        |
| C4  | Token-count metering                        | Receipts contain integer `input_tokens` and `output_tokens`; reported counts agree with a reference tokenizer for the model within 5%.                                            | [Metering §4](./irp-metering.md)                                     | TV1, TV2                 |
| C5  | Ed25519 signed receipts                     | Receipts include a base64 Ed25519 signature over the canonical signed payload defined in Metering §5.                                                                            | [Metering §5](./irp-metering.md)                                     | TV1                      |
| C6  | Anti-replay (nonce + timestamp)             | Each receipt has a unique `request_id`, a separate cryptographically-random `nonce` (≥128 bits, base64), and an RFC 3339 `timestamp`; client rejects duplicates within retention window. | [Metering §6](./irp-metering.md)                                     | TV4, TV5                 |
| C7  | At least QoS class `standard`               | Provider advertises `standard` in the `qos` array of its discovery document and accepts requests asking for it.                                                                 | [QoS Profile §4](./irp-qos.md)                                       | Procedural (§9.1)        |
| C8  | Standard error codes                        | Errors use the codes enumerated in Core §7 and Metering Appendix B. Core numeric codes: `AUTH_FAILED` (2000), `RATE_LIMITED` (3001), `SIGNATURE_INVALID` (4001), `TOKEN_COUNT_MISMATCH` (4005), `INTERNAL_ERROR` (5000). Conformance string aliases: `INVALID_AUTH`, `RATE_LIMITED`, `SIG_INVALID`, `TOKEN_DIFF`, `REPLAY_DETECTED`, `SKEW_EXCEEDED`, `MODEL_NOT_FOUND`, `INTERNAL`. See §4.2 for the mapping. | [Core §7](./irp-core.md), [Metering Appendix B](./irp-metering.md) | Procedural (§9.1)        |
| C9  | Public-key publication                      | Discovery document advertises a stable public-key URI returning the provider's current Ed25519 verify key in the published JWK or raw-base64 format.                              | [Auth & Discovery §8](./irp-auth.md)                                 | TV1 (decode + verify)    |

### 4.1 One-line acceptance summary

> **IRP Core v0.1 = HTTPS endpoint that publishes a discovery document,
> authenticates Bearer tokens, returns receipts whose canonical form has
> integer `input_tokens` / `output_tokens` and a verifiable Ed25519
> signature over a unique nonce + timestamp, and uses standard error codes.**

If a provider's implementation cannot be summarised in one sentence
matching the above, it is not IRP Core compliant.

### 4.2 Error code mapping

The conformance profile uses string error codes for readability. The
following table maps each conformance string to the normative numeric
code defined in [IRP Core Protocol §7](./irp-core.md) and to the
verification flag defined in [Metering Appendix B](./irp-metering.md).

| Conformance string | Core numeric code | Core code name         | Metering flag        | Used in |
| ------------------ | ----------------- | ---------------------- | -------------------- | ------- |
| `INVALID_AUTH`     | 2000              | `AUTH_FAILED`          | —                    | C3      |
| `RATE_LIMITED`     | 3001              | `RATE_LIMITED`         | —                    | C3      |
| `TOKEN_DIFF`       | 4005              | `TOKEN_COUNT_MISMATCH` | `token_count_mismatch` | C4, V3  |
| `SIG_INVALID`      | 4001              | `SIGNATURE_INVALID`    | `signature_invalid`    | C5, V1  |
| `REPLAY_DETECTED`  | —                 | —                      | `replay_detected`      | C6, V5  |
| `SKEW_EXCEEDED`    | —                 | —                      | `timestamp_skew`       | C6, V2  |
| `MODEL_NOT_FOUND`  | 3007              | `MODEL_UNAVAILABLE`    | —                    | C8      |
| `INTERNAL`         | 5000              | `INTERNAL_ERROR`       | —                    | C8      |

> **Note:** `REPLAY_DETECTED` and `SKEW_EXCEEDED` are client-side
> verification outcomes rather than provider error codes. They correspond
> to the `replay_detected` and `timestamp_skew` flags in Metering
> Appendix B and are surfaced as string errors in the conformance test
> procedure for clarity.

---

## 5. IRP Extended Profile

A provider MAY additionally claim any subset of the following, each of
which has its own self-contained acceptance test. Claims MUST be itemised
(`"IRP Extended (E1, E3, E4)"`); the bare claim "IRP Extended" without a
list is not valid.

| ID  | Optional capability             | Acceptance criterion                                                                                                                                                                 | Spec reference                                            | Test vector |
| --- | ------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------- | ----------- |
| E1  | Merkle audit log                | Provider exposes `GET /v1/irp/log/root` and `GET /v1/irp/log/proof?leaf=<hash>` returning Ed25519-signed roots and inclusion proofs that verify per [Metering §8](./irp-metering.md). | [Metering §8](./irp-metering.md)                          | TV6, TV7    |
| E2  | Content hashes in receipt       | Receipts contain `input_hash` and `output_hash` (SHA-256, lowercase hex of UTF-8 bytes) over the request and response payloads.                                                       | [Metering §5.4](./irp-metering.md)                        | Procedural  |
| E3  | Multiple QoS classes            | Provider advertises ≥3 of the 5 QoS classes (`realtime`, `interactive`, `standard`, `batch`, `background`) and applies their SLOs as defined in [QoS §4](./irp-qos.md).                | [QoS Profile §4](./irp-qos.md)                            | Procedural  |
| E4  | DPoP-bound auth                 | Provider supports DPoP-bound bearer tokens per [Auth §6 Mode B](./irp-auth.md) and rejects replayed `jti`s.                                                                            | [Auth & Discovery §6 Mode B](./irp-auth.md)               | Procedural  |
| E5  | mTLS auth                       | Provider supports mutual-TLS authentication per [Auth §6 Mode C](./irp-auth.md).                                                                                                      | [Auth & Discovery §6 Mode C](./irp-auth.md)               | Procedural  |
| E6  | Streaming receipts              | Provider emits per-chunk receipts during a streamed response; final receipt aggregates and is signed. (Normative spec TBD in a future extension document; see [Extension Registry §5.6](./irp-extensions.md) for the placeholder identifier.) | [Extension Registry §5.6](./irp-extensions.md) (placeholder) | Procedural  |

### 5.1 Combining extensions

Extensions are independent. A provider claiming `E1` MUST NOT assume any
client also implements `E1`; the discovery document is the only signal a
client may rely on for available extensions. Clients MUST tolerate
encountering only the Core profile from any given provider.

---

## 6. (Reserved)

Section number reserved for symmetry with related specifications. No
normative content.

---

## 7. Client Conformance

A client implementation MAY claim "IRP Core verifier v0.1" only if it
performs every check in this table.

| ID  | Mandatory verification step                  | Acceptance criterion                                                                                                                                                                                | Test vector  |
| --- | -------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------ |
| V1  | Verify Ed25519 signature                     | Client recomputes canonical JSON over the signed-fields set, decodes the base64 signature, calls Ed25519-verify with the provider's published public key, and refuses receipts whose check fails. | TV1, TV3     |
| V2  | Validate timestamp ±60s skew                 | Client rejects any receipt whose `timestamp` differs from the verifier's monotonic-NTP-aligned clock by more than 60 s.                                                                            | TV5          |
| V3  | Compare reported tokens with locally counted | Client recomputes input/output token counts using a tokenizer matching `model`, and raises `TOKEN_DIFF` when either count exceeds a configurable threshold (default 5 %).                          | TV2          |
| V4  | Maintain audit log of all verifications      | Client persists every `VerificationResult` with at least `request_id`, `timestamp`, status, and signature outcome; the log MUST be append-only.                                                    | Procedural   |
| V5  | Reject receipts with replayed nonces         | Client maintains a nonce cache keyed on `request_id`, retains entries at least for the configured replay window (default 24 h), and rejects any duplicate.                                         | TV4          |

### 7.1 Client conformance summary

> **An IRP-conformant client recomputes the canonical signed bytes,
> verifies Ed25519 against the published key, checks the timestamp
> against its own clock, recomputes token counts within threshold,
> remembers nonces it has seen, and writes everything to an
> append-only log.**

A "client" that merely accepts the provider's word for the receipt
contents is **not** an IRP-conformant client and MUST NOT claim
verification.

---

## 8. Test Vectors

This section defines the **golden vectors** by which compliance is
measured. Every vector is reproducible: feed the documented test seed
into the canonical Python implementation at `irp/irp/` (the reference
generator) and the byte-for-byte outputs MUST equal those listed here.

### 8.1 Stable test keypair

All signing in §8 uses Ed25519 with the deterministic seed below. This
is a **test seed only**; production providers MUST use a CSPRNG-derived
seed and MUST NOT publish their private key.

| Field              | Value                                                                            |
| ------------------ | -------------------------------------------------------------------------------- |
| Seed (32 bytes)    | `hex:0000000000000000000000000000000000000000000000000000000000000000`           |
| Public key (raw)   | `hex:3b6a27bcceb6a42d62a3a8d02a6f0d73653215771de243a63ac048a18b59da29`           |
| Public key (b64)   | `b64:O2onvM62pC1io6jQKm8Nc2UyFXcd4kOmOsBIoYtZ2ik=`                               |

Reference generator:

```bash
cd irp && uv run python -c '
from nacl.signing import SigningKey
sk = SigningKey(bytes(32))
print(sk.verify_key.encode().hex())
'
# expected: 3b6a27bcceb6a42d62a3a8d02a6f0d73653215771de243a63ac048a18b59da29
```

### 8.2 Canonicalisation rule

Throughout §8, "canonical JSON" means the bytes produced by:

```python
json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
```

The signed canonical for a receipt covers the following fields:
`request_id`, `timestamp`, `provider`, `model`, `input_tokens`,
`output_tokens`, `total_tokens`, `nonce`, `version`, `signature_alg`,
plus the two optional fields `input_hash`, `output_hash` when, and only
when, they are present.

This is the **minimal signed subset** used by the conformance test
vectors (TV1–TV5). Full receipts per [Metering §4](./irp-metering.md)
also include `latency`, `cost`, `model_version`, `policy_id`,
`reasoning_tokens`, and `cached_tokens`; all of these are part of the
signed canonical per Metering §5.1. An implementation that passes the
test vectors MUST also handle the full schema to be interoperable.

Fields outside the set present in a receipt (e.g. provider-specific
extensions) are **unsigned data** and MUST be ignored by signature
verification.

---

### 8.3 TV1 — Valid receipt → PASS

**Input — canonical signed bytes (UTF-8):**

```json
{"input_tokens":100,"model":"gpt-test-1","output_tokens":200,"provider":"example.ai","request_id":"req_tv1_0000000000000001","timestamp":"2026-01-15T12:00:00Z","total_tokens":300}
```

**Hex of those exact bytes (whitespace-free):**

```
hex:7b22696e7075745f746f6b656e73223a3130302c226d6f64656c223a226770742d746573742d31222c226f75747075745f746f6b656e73223a3230302c2270726f7669646572223a226578616d706c652e6169222c22726571756573745f6964223a227265715f7476315f30303030303030303030303030303031222c2274696d657374616d70223a22323032362d30312d31355431323a30303a30305a222c22746f74616c5f746f6b656e73223a3330307d
```

**Expected SHA-256 of canonical bytes:**

```
hex:4a28f6e3ec314ed5728229ba00bd7009d2b533947682e06542a13ed173999bfb
```

**Expected Ed25519 signature (with the §8.1 keypair):**

```
b64:MrQIhD25ukFutdEQgSR8g4p/+o1VNTHCUSAtV4z+gJbs8YBR43SQI1fNi1QkmQpRYWXEfyzr4Tm+Cfl3jO4QCg==
hex:32b408843db9ba416eb5d11081247c838a7ffa8d553531c251202d578cfe8096ecf18051e374902357cd8b5424990a516165c47f2cebe139be09f9778cee100a
```

**Expected outcome:** verifier returns `PASS` (signature valid,
timestamp within skew when verifier clock is set to
`2026-01-15T12:00:00Z`, no replay, and a tokenizer simulating 100 input
+ 200 output tokens stays inside the 5 % threshold).

---

### 8.4 TV2 — Tampered tokens → FAIL `TOKEN_DIFF`

A receipt is presented whose **outer** JSON differs from the signed
canonical: the provider's wire payload claims 250 output tokens (and
350 total) but the signed body is the TV1 body declaring 200/300.

**Outer (claimed) JSON:**

```json
{"input_tokens":100,"model":"gpt-test-1","output_tokens":250,"provider":"example.ai","request_id":"req_tv1_0000000000000001","timestamp":"2026-01-15T12:00:00Z","total_tokens":350}
```

**SHA-256 of outer JSON:**

```
hex:0b814f041e3753926fa54ba9473a5620ab8fd22bf404484118bac94a9164a0bd
```

**Signature attached** is TV1's signature
(`b64:MrQIhD25ukFutdEQgSR8g4p/+o1VNTHCUSAtV4z+gJbs8YBR43SQI1fNi1QkmQpRYWXEfyzr4Tm+Cfl3jO4QCg==`),
which was produced over the TV1 canonical body where output_tokens=200.

**Locally counted tokens (provided to verifier):** 100 input, 200 output.

**Expected outcome:** verifier returns `FAIL` with error code
`TOKEN_DIFF`. Even when a verifier accepts a receipt's signature over
*its* declared canonical, the comparison `|reported - locally_counted|
/ reported = 50 / 250 = 20.0 %` exceeds the default 5 % threshold.

This vector specifically exercises **C4** (token-count metering) and
**V3** (reported vs locally counted check).

---

### 8.5 TV3 — Tampered field outside signed canonical → FAIL `SIG_INVALID`

A receipt is presented in which a field included in the signed set
(`model`) has been changed after signing. The signature attached is
TV1's signature, but the canonical body the verifier reconstructs no
longer matches.

**Receipt canonical (after tamper):**

```json
{"input_tokens":100,"model":"gpt-test-1-pro","output_tokens":200,"provider":"example.ai","request_id":"req_tv1_0000000000000001","timestamp":"2026-01-15T12:00:00Z","total_tokens":300}
```

**SHA-256 of this canonical:**

```
hex:227c56de744f18f552395685b7b64af8b50ccde4ab9a15188348b66f89aed089
```

**Signature attached:** TV1 signature
(`b64:MrQIhD25ukFutdEQgSR8g4p/+o1VNTHCUSAtV4z+gJbs8YBR43SQI1fNi1QkmQpRYWXEfyzr4Tm+Cfl3jO4QCg==`).

**Expected outcome:** verifier returns `FAIL` with error code
`SIG_INVALID`. The Ed25519 verification step fails because the
attacker's tamper changed a field included in the signed canonical.

This vector exercises **C5 / V1**.

---

### 8.6 TV4 — Replayed nonce → FAIL `REPLAY_DETECTED`

The verifier is fed TV1 once, accepts it, then the same TV1 receipt is
presented a second time within the replay-retention window (default
24 h).

**Inputs:** TV1 (bytes, signature, public key) — twice.

**Expected outcome:** first verification PASSes; second verification
FAILs with error code `REPLAY_DETECTED`. Implementations MUST NOT
accept the same `(provider, request_id)` pair twice within their
configured window.

This vector exercises **C6 / V5**.

---

### 8.7 TV5 — Stale timestamp (90 s old) → FAIL `SKEW_EXCEEDED`

A receipt is signed with a timestamp 90 seconds older than the
verifier's clock. The default skew tolerance is ±60 s, so this MUST
be rejected.

**Verifier clock fixed at:** `2026-01-15T12:00:00Z`

**Canonical signed bytes:**

```json
{"input_tokens":100,"model":"gpt-test-1","output_tokens":200,"provider":"example.ai","request_id":"req_tv5_0000000000000001","timestamp":"2026-01-15T11:58:30Z","total_tokens":300}
```

**SHA-256 of canonical bytes:**

```
hex:b4c448a090d90aaeed92de386ff5201bffff4828ae0e8cd7298b4ce6a55d1f5e
```

**Expected Ed25519 signature (§8.1 keypair):**

```
b64:sQ2K6B+PP4e0ZfneiPp2Oz4MR5/Uiy0BQHI/lMiKJh0OufTSQJP47Svdm9SHFXv3XKa810OpuOa2/La5uAXSAg==
```

**Expected outcome:** signature is cryptographically valid, but the
verifier MUST return `FAIL` with error code `SKEW_EXCEEDED` because
`|now − timestamp| = 90 s > 60 s`.

This vector exercises **C6 / V2**.

---

### 8.8 TV6 — Valid Merkle inclusion proof → PASS (Extension E1)

A 4-leaf SHA-256 Merkle tree is constructed deterministically:

| Position | Hash (hex)                                                         |
| -------- | ------------------------------------------------------------------ |
| L0       | `d2dbf006f96dd05044a8f63d8f118f23925ba4cc5750f8b6c8e287fd506c8188` |
| L1       | `4140bf0e8569ed03ec838871ff2f190e9b3ea86bc083d7e9901049f75f00e855` |
| L2       | `649837ddcb7e1967086d7d35aaef7b975c513815d96fc6e70015e93a2bfe0f9a` |
| L3       | `9fde56c376760bd399b82eb8569229a2dff19219411ac71154dfeab2cf502454` |
| N01      | `8b0f563106070048a1057926820c7118dec20b8a73715544f4528487c16dc0d7` |
| N23      | `e14ca3b6f61e59b3412e24e7661ee39b0d3ef34fa3aff8497ae8c2897fd8f2d5` |
| ROOT     | `476c4a255bbaa3fa397182c77cb1bc85be71aa10349349f67e5c2bdd0453bfa0` |

(Construction: `Lᵢ = SHA-256("leaf-{i}")`, internal nodes are
`SHA-256(left ‖ right)`.)

**Inclusion proof for L2:**

| Step | Sibling hash (hex)                                                  | Position |
| ---- | ------------------------------------------------------------------- | -------- |
| 1    | `9fde56c376760bd399b82eb8569229a2dff19219411ac71154dfeab2cf502454` | right    |
| 2    | `8b0f563106070048a1057926820c7118dec20b8a73715544f4528487c16dc0d7` | left     |

**Verification:**

```
step1 = SHA-256( L2 ‖ siblings[0] )
      = SHA-256( 6498…0f9a ‖ 9fde…2454 )
      = e14ca3b6f61e59b3412e24e7661ee39b0d3ef34fa3aff8497ae8c2897fd8f2d5 (= N23)
step2 = SHA-256( siblings[1] ‖ step1 )
      = SHA-256( 8b0f…c0d7 ‖ e14c…f2d5 )
      = 476c4a255bbaa3fa397182c77cb1bc85be71aa10349349f67e5c2bdd0453bfa0 (= ROOT)
```

**Expected outcome:** `PASS`; the recomputed root equals the published
root.

---

### 8.9 TV7 — Invalid Merkle inclusion proof → FAIL (Extension E1)

Identical to TV6 except sibling 1 is replaced with an unrelated hash:

```
bad_sibling = SHA-256("bogus-sibling")
            = ec70d9e3abe06769 ... (any hash other than the correct L3)
```

The verifier recomputes step 1 with this bad sibling, then step 2,
and observes the final hash differs from `ROOT`.

**Expected outcome:** `FAIL`; the verifier MUST refuse the inclusion
proof and refuse to accept the receipt as having been admitted to the
log at the claimed time.

---

### 8.10 Vector index

| ID  | Tests                                         | Expected outcome                       |
| --- | --------------------------------------------- | -------------------------------------- |
| TV1 | C1, C5, V1                                    | PASS                                   |
| TV2 | C4, V3                                        | FAIL `TOKEN_DIFF`                      |
| TV3 | C5, V1                                        | FAIL `SIG_INVALID`                     |
| TV4 | C6, V5                                        | FAIL `REPLAY_DETECTED`                 |
| TV5 | C6, V2                                        | FAIL `SKEW_EXCEEDED`                   |
| TV6 | E1                                            | PASS                                   |
| TV7 | E1                                            | FAIL (proof invalid)                   |

> **Reproducibility note.** The reference generator producing every
> byte in §8 is the Python implementation at `irp/irp/`
> (`irp.signer.ReceiptSigner`, `irp.receipt.ReceiptValidator`). Feed
> the seed from §8.1 and the canonicalisation rule from §8.2 and the
> outputs MUST be byte-identical to those listed. Any divergence is a
> bug in the implementation, not in this document.

---

## 9. Test Procedure

### 9.1 Provider self-test

A provider verifies its own conformance by running the following
sequence and confirming all checks pass.

1. **Discovery liveness.** Issue
   `GET https://<provider>/.well-known/irp-configuration`. Expect HTTP
   200 with at least `issuer`, `signing_keys_uri`, `qos`, and
   `extensions` fields. (C2)
2. **Public-key fetch.** Issue `GET <signing_keys_uri>`. Expect a JWK
   set or raw-base64 key matching the provider's published key. (C9)
3. **Auth handshake.** Issue an inference request with a missing
   `Authorization` header. Expect HTTP 401 + body `{"error":"INVALID_AUTH"}`.
   Then retry with a valid Bearer token; expect 200. (C3, C8)
4. **Receipt round-trip.** Submit `N ≥ 100` requests with varied
   prompt sizes covering at least three orders of magnitude
   (10 / 1 000 / 10 000 input tokens). For each receipt:
   - Recompute the canonical signed bytes per §8.2 and SHA-256.
   - Verify the Ed25519 signature using the provider's published
     public key. (C5)
   - Recount input/output tokens and assert the difference is
     ≤ 5 %. (C4)
   - Assert `request_id` is unique. (C6)
   - Assert `timestamp` is within ±60 s of NTP-aligned clock. (C6)
5. **QoS exposure.** Confirm `standard` is present in the discovery
   document's `qos` array, and that a request with
   `"qos":"standard"` is accepted. (C7)
6. **Negative tests.** Reproduce TV2, TV3, TV4, TV5 against the
   provider's verification endpoint or its reference client; assert
   the documented failure modes occur.
7. **Optional E-tests.** For any `Eₙ` claimed in marketing, run the
   §5 acceptance test for that capability (e.g. fetch
   `/v1/irp/log/root` and verify a TV6 inclusion proof for E1).

A provider passes IRP Core conformance iff steps 1–6 produce no
failures. Steps 7 are required only for the corresponding extension
claims.

### 9.2 Client self-test

A client verifies its own conformance by feeding the §8 vectors into
its `verify()` API and confirming the outcomes match the §8.10 index.

```python
# Pseudo-code; see irp/tests/ for runnable form.
client = IrpClient(threshold_percent=5.0, replay_window_s=86400)
client.set_public_key("O2onvM62pC1io6jQKm8Nc2UyFXcd4kOmOsBIoYtZ2ik=")

# TV1 must PASS
assert client.verify(tv1_receipt, local_input_tokens=100,
                     local_output_tokens=200, now=tv1_ts).status == "valid"
# TV2 must FAIL with TOKEN_DIFF
assert "TOKEN_DIFF" in client.verify(tv2_receipt, local_input_tokens=100,
                                     local_output_tokens=200, now=tv1_ts).errors
# TV3 must FAIL with SIG_INVALID
assert "SIG_INVALID" in client.verify(tv3_receipt, local_input_tokens=100,
                                      local_output_tokens=200, now=tv1_ts).errors
# TV4: replay
client.verify(tv1_receipt, ...)  # PASS
assert "REPLAY_DETECTED" in client.verify(tv1_receipt, ...).errors
# TV5: skew
assert "SKEW_EXCEEDED" in client.verify(tv5_receipt,
                                        local_input_tokens=100,
                                        local_output_tokens=200,
                                        now="2026-01-15T12:00:00Z").errors
# TV6/TV7 only required if E1 is claimed.
```

### 9.3 Suggested CI workflow

Implementers SHOULD wire the conformance suite into continuous
integration so regressions are caught at merge time. The minimal GitHub
Actions snippet below illustrates the shape; adapt to your CI of
choice.

```yaml
name: irp-conformance
on: [push, pull_request]
jobs:
  conformance:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install reference IRP package
        run: |
          pip install uv
          uv venv && source .venv/bin/activate
          uv pip install -e ./irp
      - name: Run provider self-test
        run: ./scripts/irp-provider-conformance.sh
      - name: Run client self-test against golden vectors
        run: uv run pytest irp/tests/test_conformance.py -v
      - name: Re-derive test vectors from seed and diff
        run: |
          uv run python irp/scripts/regen_vectors.py > /tmp/vectors.txt
          diff /tmp/vectors.txt docs/spec/test-vectors.golden.txt
```

The last step — re-deriving every byte in §8 from the §8.1 seed and
diffing — is the closest thing to a tamper-evidence guarantee that the
spec and reference code remain in sync. Implementers SHOULD run it on
every commit.

---

## 10. Compliance Claim

A provider that has passed §9.1 MAY publicly state, in marketing copy,
documentation, or contractual material, the phrase:

> **"IRP Core compliant v0.1"**

Providers that have additionally passed any subset of §5 acceptance
tests MAY append an itemised extension list, e.g.:

> **"IRP Core compliant v0.1; IRP Extended (E1, E3, E4)"**

Providers MUST NOT:

- Claim "IRP-compliant" without specifying `Core` and the version.
- Claim "IRP Extended" without itemising the specific `Eₙ` indices.
- Claim a future profile (`v0.2`, `v1.0`, etc.) before its
  conformance document is published.
- Re-use the IRP name to market features that fail any C-item.

A claim is **falsifiable**. Any third party MAY rerun §9.1 against the
provider's public endpoint and publish the results. False claims are
misleading-advertising violations in most jurisdictions and may further
constitute trademark misuse if and when "IRP" is registered.

A client passing §9.2 MAY state:

> **"IRP Core verifier v0.1"**

The same itemisation rules apply.

### 10.1 Self-attestation template

Providers SHOULD publish a machine-readable attestation at a stable URL
(e.g. `/.well-known/irp-conformance.json`) of the form:

```json
{
  "spec_version": "v0.1",
  "core": "compliant",
  "extensions": ["E1", "E3", "E4"],
  "tested_at": "2026-04-30T08:00:00Z",
  "report_uri": "https://example.ai/conformance/2026-04-30.html",
  "signing_keys_uri": "https://example.ai/.well-known/jwks.json"
}
```

Clients MAY use this document to filter providers by capability.

---

## 11. References

Normative:

- [`irp-core.md`](./irp-core.md) — IRP Core Protocol
- [`irp-qos.md`](./irp-qos.md) — IRP QoS Profile
- [`irp-metering.md`](./irp-metering.md) — IRP Metering & Receipts
- [`irp-auth.md`](./irp-auth.md) — IRP Authentication & Discovery
- [`irp-extensions.md`](./irp-extensions.md) — IRP Optional Extensions

Informative:

- [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119) — Key words for
  use in RFCs to indicate requirement levels
- [RFC 8174](https://www.rfc-editor.org/rfc/rfc8174) — Ambiguity of
  uppercase vs lowercase in RFC 2119 keywords
- [RFC 8032](https://www.rfc-editor.org/rfc/rfc8032) — Edwards-Curve
  Digital Signature Algorithm (EdDSA / Ed25519)
- [RFC 9162](https://www.rfc-editor.org/rfc/rfc9162) — Certificate
  Transparency Version 2.0 (Merkle tree construction reference)
- `research/SUMMARY_REPORT.md` — IRP design rationale and standards
  history
- `research/07_telecom_standards_history.md` — WiFi Alliance success
  via certification
- `research/09_cloud_standardization_failures.md` — failures to ship
  test vectors

---

*End of `irp-conformance.md`.*
