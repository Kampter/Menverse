# IRP - Inference Receipt Protocol v0.1

**Client-side verifiable AI inference billing.**

[![Tests](https://github.com/Kampter/Menverse/actions/workflows/tests.yml/badge.svg)](https://github.com/Kampter/Menverse/actions)
[![Docs](https://img.shields.io/badge/docs-irp.dev-blue)](https://kampter.github.io/Menverse/)

IRP is an open protocol that allows users to independently verify the accuracy of AI inference receipts, including token counts, costs, and digital signatures.

## Problem

Current AI inference APIs are black boxes:

- **Token counts cannot be verified** - You pay what the server says you used
- **No digital signatures** - Receipts can be silently modified
- **No audit trail** - No way to detect systematic overcharging
- **No standard format** - Each provider uses different metrics
- **No QoS guarantees** - No standardized latency or quality commitments

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

## Quick Start

### Installation

```bash
pip install irp
```

### Basic Usage

```python
from irp import IRPClient

# Create client with provider's public key for signature verification
client = IRPClient(
    base_url="https://api.together.ai",
    api_key="your-api-key",
    provider_public_key="base64-encoded-public-key",
)

# Make inference request - IRP verification is automatic
response = client.chat.completions.create(
    model="meta-llama/Llama-3-8B",
    messages=[{"role": "user", "content": "Hello, world!"}],
)

# Check receipt
print(f"Tokens: {response.irp_receipt.total_tokens}")
print(f"Cost: ${response.irp_receipt.cost_total}")

# Check verification
if response.irp_verification:
    print(f"Status: {response.irp_verification.status}")
    print(f"Input diff: {response.irp_verification.input_diff_percent:.1f}%")
    print(f"Signature valid: {response.irp_verification.signature_valid}")
```

### Service Discovery

```python
from irp import IRPDiscovery

# Discover provider capabilities
discovery = IRPDiscovery(base_url="https://api.example.com")
advert = discovery.fetch()

print(f"Issuer: {advert.issuer}")
print(f"Supported versions: {advert.irp_versions_supported}")
print(f"Capabilities: {advert.capabilities}")
print(f"QoS classes: {advert.qos_classes_supported}")
```

### QoS Selection

```python
from irp import QoSClass, QOS_PARAMETERS, select_qos

# Check QoS parameters for a class
params = QOS_PARAMETERS[QoSClass.INTERACTIVE]
print(f"Target TTFT: {params.target_ttft_ms}ms")
print(f"Billing multiplier: {params.billing_multiplier}x")

# Negotiate QoS with server
chosen, reason = select_qos(
    desired=QoSClass.REAL_TIME,
    server_supported=[QoSClass.STANDARD, QoSClass.INTERACTIVE],
)
print(f"Chosen: {chosen.value}")  # interactive (downgraded from real-time)
```

### Manual Verification

```python
from irp import Receipt, ReceiptValidator

# Create a receipt from provider response
receipt = Receipt(
    request_id="req-123",
    timestamp="2026-01-01T00:00:00Z",
    provider="together-ai",
    model="meta-llama/Llama-3-8B",
    input_tokens=10,
    output_tokens=5,
    total_tokens=15,
    signature="base64-signature",
    public_key="base64-public-key",
)

# Verify with your own token counting
validator = ReceiptValidator(threshold_percent=5.0)
result = validator.verify(
    receipt=receipt,
    local_input_text="Hello, world!",
    local_output_text="Hi there!",
)

print(f"Status: {result.status}")
print(f"Errors: {result.errors}")
```

### Signed Receipts

```python
from irp import Receipt, ReceiptValidator
from irp.signer import ReceiptSigner

# Provider side: generate keypair and sign
signer = ReceiptSigner()
public_key = signer.public_key

receipt = Receipt(
    request_id="req-456",
    timestamp="2026-01-01T00:00:00Z",
    provider="my-provider",
    model="gpt-4",
    input_tokens=100,
    output_tokens=50,
    total_tokens=150,
)

signature = signer.sign(receipt)
receipt.signature = signature
receipt.public_key = public_key

# Client side: verify
validator = ReceiptValidator(provider_public_key=public_key)
result = validator.verify(receipt=receipt)
print(f"Signature valid: {result.signature_valid}")
```

### Frame Encoding

```python
from irp import (
    FrameType, FrameHeader, IRPRequestFrame,
    encode_frame_to_bytes, decode_frame_from_bytes,
)

# Build a request frame
frame = IRPRequestFrame(
    header=FrameHeader(version="0.1", frame_type=FrameType.REQUEST, stream_id=1),
    method="chat.completions",
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello"}],
    qos_class="interactive",
)

# Encode to wire format (length-prefixed JSON)
wire = encode_frame_to_bytes(frame)

# Decode back
decoded = decode_frame_from_bytes(wire, IRPRequestFrame)
```

### Merkle Audit Log

```python
from irp.audit import MerkleAuditLog
from irp.signer import build_canonical_dict

# Build an append-only audit log
log = MerkleAuditLog()

# Append receipts
for receipt in receipts:
    canonical = build_canonical_dict(receipt)
    idx = log.append(canonical.encode("utf-8"))

# Get current root hash
root = log.root_hash()

# Generate inclusion proof for a specific receipt
proof = log.proof(leaf_index=0)

# Verify proof against root
assert MerkleAuditLog.verify_proof(proof, root)
```

### Audit Report

```python
# After many requests, generate an audit report
report = validator.generate_report()
print(report)
```

Output:

```
============================================================
IRP Audit Report
============================================================

Total receipts verified: 150
  Valid:   142 (94.7%)
  Warning: 5
  Error:   3

Average input token diff:  1.23%
Average output token diff: 0.87%

Details:
  [WARNING] request_id=req-99, input_diff=8.5%
    - Input token count differs by 8.5% (threshold: 5.0%)
  [ERROR] request_id=req-101, signature_valid=False
    - Signature verification failed

============================================================
```

## Specification Documents

IRP is specified through a family of companion documents:

| Document | Scope | Status |
|----------|-------|--------|
| [IRP Core Protocol](https://kampter.github.io/Menverse/spec/irp-core/) | Message formats, frame types, procedures, error codes, versioning | Draft |
| [IRP Auth & Discovery](https://kampter.github.io/Menverse/spec/irp-auth/) | Authentication, service discovery, capability advertisement | Draft |
| [IRP Metering & Audit](https://kampter.github.io/Menverse/spec/irp-metering/) | Receipt schema, Merkle audit log, billing semantics | Draft |
| [IRP QoS Profile](https://kampter.github.io/Menverse/spec/irp-qos/) | 5-level QoS classes with normative SLA parameters | Draft |
| [IRP Conformance](https://kampter.github.io/Menverse/spec/irp-conformance/) | Conformance profiles and test vectors | Draft |
| [IRP Extensions](https://kampter.github.io/Menverse/spec/irp-extensions/) | Extension registry and lifecycle | Draft |

## Architecture

### Components

| Component | Module | Purpose |
|-----------|--------|---------|
| `Receipt` | `models.py` | Data model for inference receipts |
| `ReceiptSigner` | `signer.py` | Ed25519 signing for providers |
| `ReceiptValidator` | `receipt.py` | Full validation: tokens + signature + threshold |
| `TokenCounter` | `tokenizer.py` | Client-side token counting (tiktoken + fallback) |
| `IRPClient` | `client.py` | HTTP client wrapper with automatic verification |
| `IRPDiscovery` | `discovery.py` | `.well-known/irp-configuration` service discovery |
| `HandshakeRequest/Response` | `handshake.py` | Capability negotiation handshake |
| `QoSClass/QoSParameters` | `qos.py` | 5-level QoS with normative SLA table |
| `IRPError/IRPErrorCode` | `errors.py` | Structured error codes with HTTP mapping |
| `ProtocolVersion` | `version.py` | Protocol version registry and negotiation |
| `IRPRequestFrame/IRPResponseFrame` | `frame.py` | Length-prefixed JSON wire format |
| `MerkleAuditLog` | `audit.py` | RFC 6962 Merkle tree for tamper-evident logs |
| `ReferenceServer` | `server_ref/` | stdlib reference server skeleton |

### Receipt Format

An IRP receipt contains:

```
request_id          - Unique request identifier
timestamp           - ISO 8601 timestamp
provider            - Provider name
model               - Model identifier
model_version       - Model version (optional)
input_tokens        - Input token count
output_tokens       - Output token count
total_tokens        - Total tokens used
reasoning_tokens    - Reasoning/thinking tokens (optional)
cached_tokens       - Cached prompt tokens (optional)
latency             - Queue/TTFT/TPOT/Total latency
cost_*              - Pricing information (input/output/total)
signature           - Ed25519 signature of receipt data
public_key          - Provider's signing public key
input_hash          - SHA-256 of input content
output_hash         - SHA-256 of output content
nonce               - Replay-protection nonce
version             - IRP protocol version
policy_id           - Billing policy reference (optional)
```

### HTTP Headers

Providers supporting IRP return these headers:

```
X-IRP-Request-Id: req-123
X-IRP-Timestamp: 2026-01-01T00:00:00Z
X-IRP-Provider: together-ai
X-IRP-Model: meta-llama/Llama-3-8B
X-IRP-Model-Version: 1.0
X-IRP-Input-Tokens: 10
X-IRP-Output-Tokens: 5
X-IRP-Total-Tokens: 15
X-IRP-Reasoning-Tokens: 3
X-IRP-Cached-Tokens: 2
X-IRP-Latency-Total: 150.5
X-IRP-Latency-TTFT: 45.2
X-IRP-Cost-Total: 0.0002
X-IRP-Cost-Currency: USD
X-IRP-Signature: base64signature
X-IRP-Public-Key: base64publickey
X-IRP-Nonce: abc123
X-IRP-Version: 0.1.0
```

## Verification Logic

IRP performs three checks on every receipt:

1. **Token Count Verification**
   - Count tokens locally using the same tokenizer
   - Compare with server-reported count
   - Flag if difference exceeds threshold (default 5%)

2. **Digital Signature Verification**
   - Verify Ed25519 signature of receipt data
   - Ensures receipt was not tampered with
   - Uses provider's public key
   - Backwards-compatible with legacy 7-field canonical

3. **Audit Logging**
   - Record all verification results
   - Chain receipts into Merkle tree for tamper evidence
   - Generate summary statistics
   - Export audit reports

## Token Counting

IRP uses a dual strategy for token counting:

1. **Exact counting** with tiktoken (when available and encoding known)
2. **Approximate counting** as fallback:
   - CJK characters: ~1.5 tokens/char
   - English words: ~1.3 tokens/word
   - Code/special chars: ~0.5 tokens/char

## Reference Server

A stdlib-only reference server is included for testing and protocol validation:

```bash
cd irp
python -m irp.server_ref.app --port 8765
```

Endpoints:
- `GET /.well-known/irp-configuration` - Capability advertisement
- `POST /v1/chat/completions` - Chat completion with IRP receipts
- `GET /v1/irp/log/root` - Current Merkle root hash
- `GET /v1/irp/log/proof?id=<request_id>` - Inclusion proof

## Roadmap

### MVP v0.1 (Completed)

- [x] Core receipt data model
- [x] Ed25519 signing/verification
- [x] Client-side token counting
- [x] Receipt validation with thresholds
- [x] Audit logging and reports
- [x] HTTP client wrapper
- [x] Service discovery (`.well-known/irp-configuration`)
- [x] Capability negotiation handshake
- [x] 5-level QoS classes
- [x] Structured error codes
- [x] Protocol version management
- [x] Wire-format frame schemas
- [x] RFC 6962 Merkle audit log
- [x] Reference server skeleton
- [x] 6 specification documents
- [x] 156 unit tests

### Future

- [ ] TEE (Trusted Execution Environment) attestation
- [ ] Blockchain anchoring for audit logs
- [ ] Multi-provider receipt aggregation
- [ ] Web dashboard for audit visualization
- [ ] Provider SDK for easy IRP adoption
- [ ] Full OAuth 2.0 flow implementation
- [ ] HTTP/3 specific optimizations

## License

MIT License - See [LICENSE](../LICENSE) for details.

## Contributing

IRP is an open protocol. Contributions are welcome:

1. Open an issue to discuss changes
2. Fork and implement
3. Submit a pull request

## References

- [Research Report](../research/SUMMARY_REPORT.md) - Deep research on AI inference protocol standardization
- [IRP Core Spec](https://kampter.github.io/Menverse/spec/irp-core/) - Core protocol specification
