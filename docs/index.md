# Inference Receipt Protocol (IRP)

**An open protocol for client-side verifiable AI inference billing.**

---

## What is IRP?

IRP addresses a fundamental asymmetry in the AI inference market: providers unilaterally report token counts and costs, leaving clients with no mechanism to independently verify charges.

IRP introduces a **signed Receipt** data structure that accompanies every inference response, containing cryptographically attested token counts, latency metrics, and cost breakdowns. Clients verify Receipts independently using local token counters and Ed25519 signature validation.

## Problem

Current AI inference APIs are black boxes:

- **Token counts cannot be verified** — You pay what the server says you used
- **No digital signatures** — Receipts can be silently modified
- **No audit trail** — No way to detect systematic overcharging
- **No standard format** — Each provider uses different metrics
- **No QoS guarantees** — No standardized latency or quality commitments

## Solution

IRP adds a thin verification layer to any OpenAI-compatible API:

```
Your App -> IRP Client -> Provider API
               |
               v
         [Local Verification]
         - Count tokens independently
         - Verify digital signatures
         - Check QoS commitments
         - Generate audit reports
```

## Key Features

| Feature | Description |
|---------|-------------|
| **Signed Receipts** | Every inference response carries an Ed25519-signed receipt |
| **Token Verification** | Client-side token counting with configurable threshold |
| **Merkle Audit Log** | RFC 6962-style append-only log for tamper evidence |
| **QoS Classes** | 5 levels (real-time / interactive / standard / batch / background) |
| **Service Discovery** | `.well-known/irp-configuration` for capability advertisement |
| **Version Negotiation** | Protocol version handshake for backwards compatibility |
| **Frame Format** | Length-prefixed JSON over any transport |

## Quick Start

```bash
pip install irp
```

```python
from irp import IRPClient

client = IRPClient(
    base_url="https://api.together.ai",
    api_key="your-key",
    provider_public_key="base64-key",
)

response = client.chat.completions.create(
    model="meta-llama/Llama-3-8B",
    messages=[{"role": "user", "content": "Hello!"}],
)

print(f"Tokens: {response.irp_receipt.total_tokens}")
print(f"Verified: {response.irp_verification.status}")
```

## Specifications

IRP is specified through a family of companion documents:

| Document | Scope |
|----------|-------|
| [IRP Core Protocol](spec/irp-core.md) | Message formats, frame types, procedures, error codes, versioning |
| [IRP Auth & Discovery](spec/irp-auth.md) | Authentication, service discovery, capability advertisement |
| [IRP Metering & Audit](spec/irp-metering.md) | Receipt schema, Merkle audit log, billing semantics |
| [IRP QoS Profile](spec/irp-qos.md) | 5-level QoS classes with normative SLA parameters |
| [IRP Conformance](spec/irp-conformance.md) | Conformance profiles and test vectors |
| [IRP Extensions](spec/irp-extensions.md) | Extension registry and lifecycle |

## Project Status

**MVP v0.1 — Complete**

- 6 specification documents
- 14 Python modules
- 156 unit tests
- Reference server skeleton
- All core MVP features implemented

See the [GitHub repository](https://github.com/Kampter/Menverse) for source code and issues.

## License

MIT License
