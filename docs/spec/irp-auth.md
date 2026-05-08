# IRP Auth & Discovery Profile (v0.1)

**Status**: Draft
**Document type**: Companion profile to [Core Protocol](./irp-core.md)
**Audience**: Implementers of IRP providers and clients

---

## 1. Abstract

The Inference Receipt Protocol (IRP) is an open protocol for client-side
verifiable AI inference billing. This document defines the **Auth & Discovery
Profile**: how clients discover IRP-capable providers and how clients
authenticate to those providers.

The profile is intentionally minimal and reuses existing, widely-deployed
building blocks:

- **OAuth 2.0 Bearer tokens** (RFC 6749 / RFC 6750) as the default
  authentication mode. Existing API-key-based providers fit this mode by
  treating the API key as an opaque bearer token.
- **DPoP** (RFC 9449) as an OPTIONAL proof-of-possession binding for
  replay-protected sessions and stronger receipt provenance.
- **mTLS** (RFC 8705) as an OPTIONAL channel-binding mode for enterprise
  deployments.
- **`.well-known/irp-configuration`** (RFC 8615) as a JSON discovery
  document that advertises supported versions, capabilities, endpoints,
  and provider signing keys. The pattern follows OpenID Connect Discovery.

The profile separates **client authentication** (proves who is calling)
from **receipt signing** (proves what was billed). The provider's signing
keys are distributed via the discovery document and are independent of any
client credential.

---

## 2. Status & Conventions

This document is a **Draft** profile published alongside IRP v0.1. It is
expected to evolve before being submitted as an Internet-Draft.

The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**,
**SHALL NOT**, **SHOULD**, **SHOULD NOT**, **RECOMMENDED**, **MAY**, and
**OPTIONAL** in this document are to be interpreted as described in
[RFC 2119](https://www.rfc-editor.org/rfc/rfc2119) and
[RFC 8174](https://www.rfc-editor.org/rfc/rfc8174) when, and only when,
they appear in all capitals, as shown here.

JSON examples follow [RFC 8259](https://www.rfc-editor.org/rfc/rfc8259).
HTTP examples follow [RFC 9110](https://www.rfc-editor.org/rfc/rfc9110).
Base64 encoding refers to base64url without padding unless stated otherwise.

---

## 3. Introduction

### 3.1 Goals

The Auth & Discovery profile has three goals:

1. **Low friction onboarding.** A client that already speaks
   "OpenAI-style" Bearer authentication MUST be able to talk to an IRP
   provider with no new credentials, only a new endpoint. Existing API
   keys are treated as opaque bearer tokens.
2. **Optional stronger guarantees.** Deployments that need replay
   protection, proof-of-origin in receipts, or enterprise channel binding
   can layer on DPoP or mTLS without changing the rest of IRP.
3. **Federation-friendly discovery.** A client SHOULD be able to learn
   everything it needs about a provider (versions, capabilities,
   endpoints, signing keys) from a single well-known URL, just like
   OpenID Connect.

### 3.2 Non-goals

- IRP does not define a new authorization framework. It binds to OAuth 2.0
  and reuses existing token issuance flows.
- IRP does not mandate user identity. A bearer token MAY represent a
  service account, an API key, or an end user; the protocol does not
  care.
- IRP does not couple authentication to receipt signing. A leaked client
  credential does **not** allow forging receipts; receipts are signed by
  the provider.

### 3.3 Design choices

| Choice | Rationale |
|--------|-----------|
| Default to Bearer | Matches existing AI provider API conventions (OpenAI, Anthropic, Together, Fireworks). Zero migration cost. |
| DPoP optional | Replay protection is valuable but not free; deployments with TLS-terminating proxies often cannot inspect application headers. |
| `.well-known` JSON | Proven pattern (OIDC, OAuth 2.0 Authorization Server Metadata). Cacheable, statically servable. |
| Provider keys in discovery | One fetch yields everything a client needs to verify receipts. Avoids a separate JWKS round-trip for the MVP. |
| Capabilities as strings | Forward-compatible with the [Extension Registry](./irp-extensions.md); clients filter by capability without parsing version semantics. |

---

## 4. Service Discovery

### 4.1 Location

A provider that supports IRP **MUST** publish a JSON document at:

```
https://<provider-host>/.well-known/irp-configuration
```

The path is registered with IANA per [Section 12](#12-iana-considerations).

The document **MUST** be served over HTTPS. Providers **SHOULD** allow
unauthenticated `GET` on this URL — discovery is a public capability
advertisement, analogous to OIDC discovery.

### 4.2 Required fields

A conforming `.well-known/irp-configuration` JSON object **MUST** include
the following fields:

| Field | Type | Description |
|-------|------|-------------|
| `issuer` | string (URL) | Stable identifier of the provider. Receipts signed by this provider MUST carry this `issuer` value. |
| `irp_versions_supported` | array of strings | List of IRP core protocol versions the provider speaks (e.g. `["0.1.0"]`). |
| `capabilities` | array of strings | Capability identifiers the provider advertises (see [Section 5](#5-capability-advertisement)). |
| `endpoints` | object | Map of endpoint name -> absolute HTTPS URL. See [Section 4.4](#44-endpoints-object). |
| `public_keys` | array of objects | Provider signing keys. Each entry MUST contain `kid`, `alg`, and `key_b64`. See [Section 8](#8-public-key-distribution). |

### 4.3 Optional fields

| Field | Type | Description |
|-------|------|-------------|
| `qos_classes_supported` | array of strings | QoS classes the provider can serve (see [QoS Profile](./irp-qos.md)). Example: `["realtime", "interactive", "standard", "batch", "background"]`. |
| `pricing_url` | string (URL) | Human-readable pricing page. |
| `model_card_urls` | object | Map from model identifier to a URL that returns a model card. |
| `auth_modes_supported` | array of strings | Subset of `["bearer", "dpop", "mtls"]`. If absent, clients MUST assume `["bearer"]`. |
| `dpop_signing_alg_values_supported` | array of strings | JWS algorithms accepted in DPoP proofs (e.g. `["ES256", "EdDSA"]`). REQUIRED if `dpop` is in `auth_modes_supported`. |
| `service_documentation` | string (URL) | Link to provider's IRP-specific docs. |

### 4.4 Endpoints object

The `endpoints` object **MUST** include the following keys when the
corresponding feature is supported:

| Key | Required when | Description |
|-----|---------------|-------------|
| `chat_completions` | Always | URL of the IRP-conformant chat completions endpoint. |
| `log_root` | Provider supports audit log per [Metering & Audit](./irp-metering-audit.md) | URL that returns the current Merkle root of the receipt log. |
| `log_proof` | Provider supports audit log | URL template for fetching inclusion proofs; clients append `?receipt_id=<id>`. |
| `models` | RECOMMENDED | URL that lists models and their per-model capabilities. |
| `usage` | OPTIONAL | URL for aggregated billing usage queries. |

Additional endpoint keys MAY be present and **MUST** be ignored by clients
that do not understand them.

### 4.5 Cacheability

Providers **SHOULD** include a `Cache-Control: max-age=<seconds>` response
header on `.well-known/irp-configuration`. A `max-age` of one hour
(`3600`) is RECOMMENDED for normal operation; values up to 86400 (one
day) are acceptable when keys are not actively rotating.

Clients **SHOULD** refresh the discovery document at least once per day,
even if the cache is still valid, to pick up new keys before activation.
Clients **MUST** refetch the document if signature verification of a
receipt fails with `unknown_kid`.

### 4.6 Example document

```json
{
  "issuer": "https://api.example-ai.com",
  "irp_versions_supported": ["0.1.0"],
  "capabilities": [
    "irp.core.chat",
    "irp.core.receipts",
    "irp.qos.standard",
    "irp.qos.batch",
    "irp.audit.merkle",
    "irp.tokenizer.tiktoken"
  ],
  "auth_modes_supported": ["bearer", "dpop"],
  "dpop_signing_alg_values_supported": ["ES256", "EdDSA"],
  "endpoints": {
    "chat_completions": "https://api.example-ai.com/v1/chat/completions",
    "log_root": "https://api.example-ai.com/v1/irp/log/root",
    "log_proof": "https://api.example-ai.com/v1/irp/log/proof",
    "models": "https://api.example-ai.com/v1/models"
  },
  "public_keys": [
    {
      "kid": "2026-05-key-1",
      "alg": "Ed25519",
      "key_b64": "MCowBQYDK2VwAyEAGb9ECWmEzf6FQbrBZ9w7lshQhqowtrbLDFw4rXAxZuE",
      "use": "receipt-sign",
      "not_before": "2026-05-01T00:00:00Z",
      "not_after": "2026-08-01T00:00:00Z"
    }
  ],
  "qos_classes_supported": ["realtime", "interactive", "standard", "batch"],
  "pricing_url": "https://example-ai.com/pricing",
  "service_documentation": "https://example-ai.com/docs/irp"
}
```

### 4.7 Schema (informal)

The following JSON-schema-like fragment is informative; the normative
text above takes precedence.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["issuer", "irp_versions_supported", "capabilities", "endpoints", "public_keys"],
  "properties": {
    "issuer": { "type": "string", "format": "uri" },
    "irp_versions_supported": {
      "type": "array",
      "minItems": 1,
      "items": { "type": "string" }
    },
    "capabilities": {
      "type": "array",
      "items": { "type": "string", "pattern": "^irp\\.[a-z0-9_-]+\\.[a-z0-9_.-]+$" }
    },
    "auth_modes_supported": {
      "type": "array",
      "items": { "enum": ["bearer", "dpop", "mtls"] }
    },
    "dpop_signing_alg_values_supported": {
      "type": "array",
      "items": { "type": "string" }
    },
    "endpoints": {
      "type": "object",
      "required": ["chat_completions"],
      "properties": {
        "chat_completions": { "type": "string", "format": "uri" },
        "log_root":         { "type": "string", "format": "uri" },
        "log_proof":        { "type": "string", "format": "uri" },
        "models":           { "type": "string", "format": "uri" },
        "usage":            { "type": "string", "format": "uri" }
      },
      "additionalProperties": { "type": "string", "format": "uri" }
    },
    "public_keys": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "required": ["kid", "alg", "key_b64"],
        "properties": {
          "kid":        { "type": "string" },
          "alg":        { "type": "string" },
          "key_b64":    { "type": "string" },
          "use":        { "type": "string" },
          "not_before": { "type": "string", "format": "date-time" },
          "not_after":  { "type": "string", "format": "date-time" }
        }
      }
    },
    "qos_classes_supported": {
      "type": "array",
      "items": { "type": "string" }
    },
    "pricing_url":           { "type": "string", "format": "uri" },
    "model_card_urls":       { "type": "object", "additionalProperties": { "type": "string", "format": "uri" } },
    "service_documentation": { "type": "string", "format": "uri" }
  }
}
```

---

## 5. Capability Advertisement

### 5.1 Identifier syntax

A **capability identifier** is a dot-separated lowercase string of the
form:

```
irp.<category>.<name>
```

- `<category>` is one of the registered categories (e.g. `core`, `qos`,
  `audit`, `tokenizer`, `attestation`).
- `<name>` is the specific feature within the category.
- Implementations **MUST NOT** invent identifiers outside the
  `irp.<category>.<name>` namespace; experimental capabilities use the
  `x-` prefix as defined in the [Extension Registry](./irp-extensions.md).

### 5.2 Example identifiers

| Identifier | Meaning |
|------------|---------|
| `irp.core.chat` | Provider implements the Core chat endpoint. |
| `irp.core.receipts` | Provider returns IRP receipts on every billed response. |
| `irp.qos.standard` | Provider supports the `standard` QoS class. |
| `irp.audit.merkle` | Provider exposes a Merkle-tree audit log. |
| `irp.tokenizer.tiktoken` | Provider's token counts use a tiktoken-compatible algorithm. |
| `irp.attestation.tee` | Provider can attest the TEE that ran the inference. |

### 5.3 Discovery semantics

- Clients **SHOULD** filter providers by required capability set when
  routing across multiple IRP-capable backends.
- A client that does not recognize a capability identifier **MUST**
  ignore it. Unknown identifiers are not errors; they are forward
  compatibility.
- Capability presence is necessary but not sufficient: a provider that
  advertises `irp.audit.merkle` **MUST** also expose `endpoints.log_root`
  and `endpoints.log_proof`. A client SHOULD treat missing endpoints as
  the capability not actually being available.

Registration of new capabilities is governed by the
[Extension Registry](./irp-extensions.md).

---

## 6. Authentication Modes

IRP defines three authentication modes. Mode A is mandatory; Modes B and
C are optional.

A provider's `auth_modes_supported` array signals which modes it accepts.
A client **MUST** select an authentication mode that appears in that
array (or fall back to `bearer` if the field is absent).

### 6.1 Mode A: Bearer Token (REQUIRED)

This is the default and minimum-conformance mode.

The client **MUST** include an `Authorization` header:

```
Authorization: Bearer <token>
```

The `<token>` value is opaque to IRP and **MAY** be:

- A long-lived API key issued out-of-band by the provider (this is the
  common case today).
- An OAuth 2.0 access token obtained via any OAuth 2.0 grant type per
  RFC 6749. IRP does not constrain which grants are used; the provider
  publishes its authorization server in `service_documentation` if
  applicable.

There is no additional binding between the token and the request payload
in Mode A. Token confidentiality relies on TLS.

A provider **MUST** reject a request with an invalid, expired, or revoked
token using HTTP `401 Unauthorized` and a `WWW-Authenticate: Bearer`
header per RFC 6750:

```
HTTP/1.1 401 Unauthorized
WWW-Authenticate: Bearer realm="irp", error="invalid_token",
                  error_description="The access token expired"
```

### 6.2 Mode B: DPoP-Bound Bearer (OPTIONAL)

Mode B layers [DPoP](https://www.rfc-editor.org/rfc/rfc9449) on top of a
bearer token. It binds each request to a client-held key, providing
replay protection and proof-of-origin that can be referenced from the
issued receipt.

**Client behavior**:

1. Generate an ephemeral asymmetric keypair (`ES256` or `EdDSA`
   RECOMMENDED). Keep it for the lifetime of the session.
2. For every request, build a DPoP proof JWT per RFC 9449 §4 with claims:
   - `htm`: the HTTP method (e.g. `POST`)
   - `htu`: the request URL (without query/fragment)
   - `iat`: issued-at timestamp
   - `jti`: unique nonce
   - `ath`: base64url SHA-256 of the access token (REQUIRED when used
     with a bearer token, per RFC 9449 §4.3)
3. Include both headers:

```
Authorization: DPoP <token>
DPoP: <signed-jwt>
```

Note the `Authorization` scheme is `DPoP`, not `Bearer`, when DPoP is in
use. The `<token>` itself is the same bearer token from Mode A.

**Provider behavior**:

- Verify the DPoP proof signature against the public key in the JWT
  header (`jwk` field).
- Verify `htm`, `htu`, `iat` (within a short clock-skew window), and
  `ath` (SHA-256 of token).
- Track `jti` values for replay detection within a configured window.
- On failure, respond with `401` and `WWW-Authenticate: DPoP error="..."`.

A provider **MAY** include a DPoP nonce (`DPoP-Nonce` response header) to
require the client to incorporate it into subsequent proofs, per
RFC 9449 §8.

When DPoP is used, the provider **SHOULD** include the JWK thumbprint
(`jkt`) of the client's DPoP key in the receipt's `client_binding` field,
so that downstream verifiers can confirm the receipt was issued for a
request from that key.

The `client_binding` field is defined by this profile as an extension to
the Core Receipt schema. It is an object with two fields:

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | Binding type: `dpop_jkt` for DPoP, `mtls_thumbprint` for mTLS. |
| `value` | string | The binding value (JWK thumbprint or certificate thumbprint). |

If the client does not recognize `client_binding`, it **MUST** ignore it.

### 6.3 Mode C: mTLS (OPTIONAL)

Mode C uses mutual TLS per [RFC 8705](https://www.rfc-editor.org/rfc/rfc8705).
The client presents a TLS client certificate during the handshake; the
provider binds the subscriber identity to the certificate's
`Subject` / SAN.

This mode is RECOMMENDED for enterprise deployments where:

- Client identity is rooted in a corporate PKI.
- The deployment terminates TLS at a controlled gateway that can pin
  certificates.
- Bearer-token leakage is a higher concern than operational complexity.

When Mode C is used, the `Authorization` header is OPTIONAL. If a bearer
token is also present, both **MUST** validate (mTLS for channel,
bearer for resource scope).

The provider **SHOULD** include the certificate's SHA-256 thumbprint
in the receipt's `client_binding` field, with `type: "mtls_thumbprint"`.

### 6.4 Auth and receipt signing are independent

A common misunderstanding is that the client's auth credential signs
receipts. It does not.

- **Client auth credential** (bearer token, DPoP key, mTLS cert) proves
  *who is calling*. It is held by the client.
- **Provider signing key** (in `public_keys`) proves *what was billed*.
  It is held by the provider.

A receipt is signed exclusively with the provider's signing key. A
compromised client credential does not allow an attacker to forge
receipts; it only allows the attacker to issue requests as that client.
The two trust roots are deliberately separated so that:

- Receipt verification is a pure offline operation against the
  discovery document.
- Client credentials can be rotated without invalidating historic
  receipts.
- Auditors who do not hold any client credential can still verify
  receipts.

---

## 7. Authentication Flow

### 7.1 Sequence (text diagram)

```
Client                                Provider
  |                                       |
  | 1. GET /.well-known/irp-configuration |
  |-------------------------------------->|
  |                                       |
  |     200 OK + JSON discovery doc       |
  |<--------------------------------------|
  |                                       |
  | (Client picks IRP version + auth mode |
  |  it understands and the provider      |
  |  supports.)                           |
  |                                       |
  | 2. POST /v1/chat/completions          |
  |    Authorization: Bearer <token>      |
  |    [DPoP: <jwt>]      (Mode B only)   |
  |    X-IRP-Client-Id: my-app/1.4.0      |
  |    Body: ChatCompletionRequest        |
  |-------------------------------------->|
  |                                       |
  | (Provider validates auth, runs        |
  |  inference, signs receipt with        |
  |  provider key.)                       |
  |                                       |
  | 3. 200 OK                             |
  |    X-IRP-Auth-Mode: dpop              |
  |    Body: ChatCompletionResponse       |
  |          + receipt (signed)           |
  |<--------------------------------------|
  |                                       |
  | 4. Verify receipt signature against   |
  |    public_keys from step 1.           |
  |                                       |
```

### 7.2 Steps in detail

1. **Discovery.** The client GETs the well-known URL. It caches the
   document per `Cache-Control` and refreshes at least daily.
2. **Negotiation (local).** From the document the client selects:
   - The highest IRP version it implements that also appears in
     `irp_versions_supported`.
   - The strongest auth mode it can perform that appears in
     `auth_modes_supported`.
   - The set of capabilities it requires, verifying each is present.
   If any required item is missing, the client MUST NOT continue against
   this provider and SHOULD emit a structured error.
3. **Request.** The client sends the inference request to the
   `chat_completions` endpoint with auth headers as specified by the
   chosen mode.
4. **Provider validation.** The provider validates the credential. For
   Mode B it also verifies the DPoP proof. For Mode C it verifies the
   client certificate during the TLS handshake.
5. **Inference and receipt.** The provider performs inference and returns
   the response together with an IRP receipt. The receipt is signed by a
   key whose `kid` is listed in `public_keys`.
6. **Receipt verification.** The client verifies the receipt signature
   using the public key from the cached discovery document. If the
   `kid` is unknown, the client refetches the document once before
   failing.

### 7.3 Error handling

| Condition | Status | `WWW-Authenticate` value |
|-----------|--------|---------------------------|
| Missing credential | 401 | `Bearer realm="irp"` |
| Invalid / expired bearer | 401 | `Bearer error="invalid_token"` |
| DPoP proof missing when DPoP required | 401 | `DPoP error="invalid_dpop_proof"` |
| DPoP proof signature invalid | 401 | `DPoP error="invalid_dpop_proof"` |
| DPoP `jti` replay | 401 | `DPoP error="invalid_dpop_proof"` |
| mTLS cert missing or untrusted | TLS handshake fails | n/a |
| Unsupported IRP version | 400 | n/a (use `irp_error: unsupported_version`) |
| Capability not supported | 400 | n/a (use `irp_error: unsupported_capability`) |

---

## 8. Public Key Distribution

### 8.1 Key entries in discovery

Each entry in `public_keys` describes one provider signing key:

| Field | Required | Description |
|-------|----------|-------------|
| `kid` | yes | Stable, unique identifier. Receipts reference this value. |
| `alg` | yes | Signing algorithm name. RECOMMENDED: `Ed25519` or `ES256`. |
| `key_b64` | yes | Public key, base64-encoded. For `Ed25519`, RAW 32-byte key OR SubjectPublicKeyInfo (SPKI); the chosen encoding MUST be consistent for the provider and SHOULD match SPKI. |
| `use` | no | Key usage. RECOMMENDED value: `receipt-sign`. |
| `not_before` | no | RFC 3339 timestamp before which the key MUST NOT be used to sign. |
| `not_after` | no | RFC 3339 timestamp after which the key MUST NOT be used to sign. |

Multiple keys MAY be present at the same time to support overlap during
rotation.

### 8.2 Rotation procedure

To minimize disruption, providers **MUST** follow this rotation procedure:

1. **Pre-publish.** At least **24 hours** before activating a new key,
   the provider adds the new key to `public_keys` with a future
   `not_before`. Clients refreshing the document daily will see the new
   key before they ever encounter a receipt signed with it.
2. **Activate.** At the planned `not_before`, the provider begins signing
   with the new key. The old key remains in the document.
3. **Retire.** When the provider stops signing with the old key, it
   sets `not_after` on the old key entry. The old key entry **MUST**
   remain in the document for at least **30 days** so that clients
   verifying historic receipts still find the key.
4. **Remove.** After 30 days, the provider MAY delete the old key entry.
   Clients that need to verify older receipts SHOULD pin the relevant
   key locally.

### 8.3 Compromise procedure

If a signing key is suspected of compromise:

1. The provider **MUST** stop signing with the key immediately and
   publish an updated discovery document with the key entry annotated
   (e.g. `not_after` set to the present, plus an out-of-band advisory
   in `service_documentation`).
2. Clients **SHOULD** treat receipts signed with a revoked key after the
   announced `not_after` as invalid, regardless of receipt timestamp.
3. The provider **SHOULD** publish a list of receipt IDs known to have
   been issued with the compromised key during the unauthorized window
   so that auditors can quarantine them.

There is no online revocation mechanism in v0.1; revocation is
communicated by updating the discovery document. This is a deliberate
simplicity tradeoff and may be revisited in a later profile.

---

## 9. Headers

The following HTTP headers are defined or used by this profile.

### 9.1 Request headers

| Header | Required | Mode | Purpose |
|--------|----------|------|---------|
| `Authorization` | yes (Mode A, B); optional (Mode C) | A: `Bearer`, B: `DPoP` | Carries the bearer token. |
| `DPoP` | yes for Mode B | B | Carries the DPoP proof JWT. |
| `X-IRP-Client-Id` | no | any | Free-form string identifying the client implementation, e.g. `my-app/1.4.0 irp-py/0.1`. Servers MUST treat this as opaque debug metadata; it is not authentication. |
| `X-IRP-Version` | OPTIONAL | any | Client's chosen IRP core version. Provider may use it to select response formatting; absent value means "highest supported". |

### 9.2 Response headers

| Header | When | Purpose |
|--------|------|---------|
| `WWW-Authenticate` | On `401` | Per RFC 6750 / RFC 9449. Indicates the auth scheme expected. |
| `X-IRP-Auth-Mode` | OPTIONAL on success | Informational. Echoes the mode the provider validated: `bearer`, `dpop`, or `mtls`. |
| `Cache-Control` | On discovery doc | Governs client caching. |
| `DPoP-Nonce` | When provider requires nonces | Forces client to include the nonce in subsequent DPoP proofs. |

`X-IRP-*` headers are non-standard and use the `X-` prefix only because
they are project-specific debug metadata, not protocol semantics. They
**MUST NOT** be relied upon for security decisions.

---

## 10. Conformance

This profile defines three levels of auth & discovery conformance.

| Level | Required | Notes |
|-------|----------|-------|
| **AD-Min** | Mode A; `.well-known/irp-configuration` with required fields. | This is the minimum any IRP-conformant provider MUST satisfy. |
| **AD-DPoP** | AD-Min + Mode B + `dpop_signing_alg_values_supported`. | RECOMMENDED for any provider whose receipts are intended to demonstrate origin in a forensic context. |
| **AD-mTLS** | AD-Min + Mode C. | RECOMMENDED for enterprise-only deployments. |

A provider MAY satisfy multiple levels simultaneously by listing all
modes in `auth_modes_supported`.

A client conforms to this profile if it:

- Can fetch and parse `.well-known/irp-configuration`.
- Can perform Mode A.
- Refreshes the discovery document at least daily, or on `unknown_kid`.

See the overall [Conformance Profile](./irp-conformance.md) for how this
profile composes with Core, QoS, and Metering & Audit.

---

## 11. Security Considerations

### 11.1 Token leakage

Bearer tokens are vulnerable to leakage. Implementations:

- **MUST** transport requests over TLS 1.2 or higher with secure ciphers.
- **MUST NOT** log full tokens. If logging is necessary, redact to a
  prefix of at most 8 characters plus a SHA-256 hash.
- **SHOULD** scope tokens narrowly: per-environment, per-application,
  per-purpose. Long-lived all-powerful "master keys" are
  NOT RECOMMENDED.
- **SHOULD** offer DPoP (Mode B) for clients that need stronger binding.

### 11.2 Replay

Mode A provides no replay protection beyond TLS. An attacker on the wire
cannot replay (TLS prevents that) but a copy of the token leaked
elsewhere can be used freely until expiry.

Mode B mitigates replay by binding each request to a fresh DPoP proof
with a unique `jti`. Providers SHOULD enforce a `jti` cache for at least
the configured proof lifetime. A `DPoP-Nonce` further hardens against
replay across re-issued tokens.

### 11.3 Discovery enumeration

The `.well-known/irp-configuration` URL is intentionally discoverable.
This is the same model as OIDC and is considered acceptable: the
document advertises only public capability metadata and public keys.

Providers **MUST NOT** include any secret in this document. In
particular, they **MUST NOT** include private keys, customer-specific
configuration, or pricing data that is not already public.

Operators concerned about scraping can rate-limit the well-known URL
without breaking the protocol; clients refresh at most once per day in
steady state.

### 11.4 Key compromise

See [Section 8.3](#83-compromise-procedure). The lack of an online
revocation mechanism in v0.1 means clients cannot reject a receipt at
verification time purely because a key was later revoked; they must
fetch fresh discovery state. Clients that maintain long-lived caches
**MUST** refresh the discovery document on any verification failure
before treating the failure as final.

### 11.5 Discovery integrity

The discovery document is itself unsigned in v0.1. Its integrity rests
entirely on TLS to the provider's host. Operators **SHOULD**:

- Pin the well-known origin to the same TLS certificate / CA as the
  rest of the provider's API.
- Use HSTS and CAA records to reduce the attack surface against MITM.
- Consider future profiles that add a JWS-signed discovery document.

### 11.6 Privacy

Discovery is a public capability advertisement and reveals no
client-specific information. The `X-IRP-Client-Id` header is
client-controlled and SHOULD NOT include personal data. Providers
SHOULD limit retention of access logs containing tokens or DPoP `jti`
values to what is needed for replay protection and abuse handling.

### 11.7 Cross-protocol concerns

Bearer tokens used for IRP **SHOULD NOT** be reused for non-IRP APIs on
unrelated origins, to avoid scope confusion. When a single token
authorizes both an IRP endpoint and an OAuth-protected non-IRP endpoint
on the same provider, the provider is responsible for ensuring that
both surfaces enforce the same scope semantics.

---

## 12. IANA Considerations

This document requests registration of the following well-known URI per
[RFC 8615](https://www.rfc-editor.org/rfc/rfc8615):

| URI suffix | Change controller | Specification |
|------------|-------------------|---------------|
| `irp-configuration` | IRP working group | This document |

The shorter suffix `irp` is also reserved at the discretion of the IRP
working group as an alias for future profiles; v0.1 clients **MUST**
use `irp-configuration`.

This document does not request any new HTTP header field registrations
beyond those already defined by RFC 6750 and RFC 9449. The `X-IRP-*`
headers are local extensions and are not registered.

---

## 13. References

### 13.1 Normative

- [RFC 2119] Bradner, S., "Key words for use in RFCs to Indicate
  Requirement Levels", BCP 14, RFC 2119, March 1997.
- [RFC 6749] Hardt, D., Ed., "The OAuth 2.0 Authorization Framework",
  RFC 6749, October 2012.
- [RFC 6750] Jones, M. and D. Hardt, "The OAuth 2.0 Authorization
  Framework: Bearer Token Usage", RFC 6750, October 2012.
- [RFC 8174] Leiba, B., "Ambiguity of Uppercase vs Lowercase in RFC 2119
  Key Words", RFC 8174, May 2017.
- [RFC 8259] Bray, T., Ed., "The JavaScript Object Notation (JSON) Data
  Interchange Format", RFC 8259, December 2017.
- [RFC 8615] Nottingham, M., "Well-Known Uniform Resource Identifiers
  (URIs)", RFC 8615, May 2019.
- [RFC 8705] Campbell, B. et al., "OAuth 2.0 Mutual-TLS Client
  Authentication and Certificate-Bound Access Tokens", RFC 8705,
  February 2020.
- [RFC 9110] Fielding, R. et al., "HTTP Semantics", RFC 9110, June 2022.
- [RFC 9449] Fett, D., Campbell, B., Bradley, J., Lodderstedt, T.,
  Jones, M., and D. Waite, "OAuth 2.0 Demonstrating Proof of Possession
  (DPoP)", RFC 9449, September 2023.

### 13.2 Informative

- [OIDC-Discovery] Sakimura, N. et al., "OpenID Connect Discovery 1.0".
- [Core Protocol](./irp-core.md) — IRP core request, response, and
  receipt format.
- [QoS Profile](./irp-qos.md) — QoS class definitions.
- [Metering & Audit Profile](./irp-metering-audit.md) — Merkle audit
  log and inclusion proofs.
- [Conformance Profile](./irp-conformance.md) — Overall conformance
  matrix.
- [Extension Registry](./irp-extensions.md) — Capability identifier
  registration policy.

---

## Appendix A. Worked example: client onboarding

The following shows a complete first-contact session. All values are
illustrative.

### A.1 Discovery

Request:

```
GET /.well-known/irp-configuration HTTP/1.1
Host: api.example-ai.com
Accept: application/json
```

Response:

```
HTTP/1.1 200 OK
Content-Type: application/json
Cache-Control: max-age=3600

{
  "issuer": "https://api.example-ai.com",
  "irp_versions_supported": ["0.1.0"],
  "capabilities": [
    "irp.core.chat", "irp.core.receipts",
    "irp.qos.standard", "irp.audit.merkle"
  ],
  "auth_modes_supported": ["bearer", "dpop"],
  "dpop_signing_alg_values_supported": ["ES256", "EdDSA"],
  "endpoints": {
    "chat_completions": "https://api.example-ai.com/v1/chat/completions",
    "log_root": "https://api.example-ai.com/v1/irp/log/root",
    "log_proof": "https://api.example-ai.com/v1/irp/log/proof"
  },
  "public_keys": [
    {
      "kid": "k1",
      "alg": "Ed25519",
      "key_b64": "MCowBQYDK2VwAyEAGb9ECWmEzf6FQbrBZ9w7lshQhqowtrbLDFw4rXAxZuE",
      "use": "receipt-sign",
      "not_before": "2026-05-01T00:00:00Z",
      "not_after": "2026-08-01T00:00:00Z"
    }
  ]
}
```

### A.2 Mode A request (bearer)

```
POST /v1/chat/completions HTTP/1.1
Host: api.example-ai.com
Authorization: Bearer sk_live_abcd1234...
Content-Type: application/json
X-IRP-Client-Id: example-cli/0.2.1 irp-py/0.1

{ "model": "ex-llm-7b",
  "messages": [{ "role": "user", "content": "hello" }] }
```

### A.3 Mode B request (DPoP)

The DPoP JWT header and payload (illustrative; signature omitted):

```
{
  "typ": "dpop+jwt",
  "alg": "EdDSA",
  "jwk": { "kty": "OKP", "crv": "Ed25519",
           "x": "11qYAYKxCrfVS_7TyWQHOg7hcvPapiMlrwIaaPcHURo" }
}
.
{
  "htm": "POST",
  "htu": "https://api.example-ai.com/v1/chat/completions",
  "iat": 1746662400,
  "jti": "0d8a5f21c0fe4a30b0c5a8f2",
  "ath": "fUHyO2r2Z3DZ53EsNrWBb0xWXoaNy59IiKCAqksmQEo"
}
```

Request:

```
POST /v1/chat/completions HTTP/1.1
Host: api.example-ai.com
Authorization: DPoP sk_live_abcd1234...
DPoP: eyJ0eXAiOiJkcG9wK2p3dCIsImFsZyI6IkVkRFNBIiwi...
Content-Type: application/json

{ "model": "ex-llm-7b",
  "messages": [{ "role": "user", "content": "hello" }] }
```

Response:

```
HTTP/1.1 200 OK
Content-Type: application/json
X-IRP-Auth-Mode: dpop

{
  "id": "chatcmpl-...",
  "choices": [...],
  "irp_receipt": {
    "issuer": "https://api.example-ai.com",
    "kid": "k1",
    "alg": "Ed25519",
    "client_binding": {
      "type": "dpop_jkt",
      "value": "0ZcOCORZNYy-DWpqq30jZyJGHTN0d2HglBV3uiguA4I"
    },
    "...": "...",
    "signature": "..."
  }
}
```

The client verifies `irp_receipt.signature` using the `k1` public key
from the discovery document and confirms `client_binding.value` matches
the JWK thumbprint of its own DPoP key.

---

## Appendix B. Migration notes for existing API-key providers

A provider that today serves an OpenAI-compatible JSON API over
`Authorization: Bearer <api-key>` can become AD-Min conformant by:

1. Publishing `https://<host>/.well-known/irp-configuration` with the
   minimum required fields. The same long-lived API keys continue to
   work — they fit Mode A as opaque bearer tokens.
2. Generating an Ed25519 keypair and listing the public half in
   `public_keys`. The private half is used by the inference path to
   sign IRP receipts.
3. Returning IRP receipts on chat completion responses per
   [Core Protocol](./irp-core.md).

No changes to client credentials or token issuance flows are required
to reach AD-Min. DPoP and mTLS can be adopted incrementally without
breaking AD-Min clients.
