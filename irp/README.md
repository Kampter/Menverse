# IRP - Inference Receipt Protocol v0.1

**Client-side verifiable AI inference billing.**

IRP is an open protocol that allows users to independently verify the accuracy of AI inference receipts, including token counts, costs, and digital signatures.

## Problem

Current AI inference APIs are black boxes:
- **Token counts cannot be verified** - You pay what the server says you used
- **No digital signatures** - Receipts can be silently modified
- **No audit trail** - No way to detect systematic overcharging
- **No standard format** - Each provider uses different metrics

## Solution

IRP adds a thin verification layer to any OpenAI-compatible API:

```
Your App -> IRP Client -> Provider API
               |
               v
         [Local Verification]
         - Count tokens independently
         - Verify digital signatures
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

## Architecture

### Components

| Component | Purpose |
|-----------|---------|
| `Receipt` | Data model for inference receipts |
| `ReceiptSigner` | Ed25519 signing for providers |
| `ReceiptVerifier` | Signature verification for clients |
| `TokenCounter` | Client-side token counting (tiktoken + fallback) |
| `ReceiptValidator` | Full validation: tokens + signature + threshold |
| `IRPClient` | HTTP client wrapper with automatic verification |

### Receipt Format

An IRP receipt contains:

```
request_id          - Unique request identifier
timestamp           - ISO 8601 timestamp
provider            - Provider name
model               - Model identifier
input_tokens        - Input token count
output_tokens       - Output token count
total_tokens        - Total tokens used
latency             - Queue/TTFT/TPOT/Total latency
cost_*              - Pricing information
signature           - Ed25519 signature of receipt data
public_key          - Provider's signing public key
```

### HTTP Headers

Providers supporting IRP return these headers:

```
X-IRP-Request-Id: req-123
X-IRP-Timestamp: 2026-01-01T00:00:00Z
X-IRP-Provider: together-ai
X-IRP-Model: meta-llama/Llama-3-8B
X-IRP-Input-Tokens: 10
X-IRP-Output-Tokens: 5
X-IRP-Total-Tokens: 15
X-IRP-Latency-Total: 150.5
X-IRP-Latency-TTFT: 45.2
X-IRP-Cost-Total: 0.0002
X-IRP-Signature: base64signature
X-IRP-Public-Key: base64publickey
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

3. **Audit Logging**
   - Record all verification results
   - Generate summary statistics
   - Export audit reports

## Token Counting

IRP uses a dual strategy for token counting:

1. **Exact counting** with tiktoken (when available and encoding known)
2. **Approximate counting** as fallback:
   - CJK characters: ~1.5 tokens/char
   - English words: ~1.3 tokens/word
   - Code/special chars: ~0.5 tokens/char

## Roadmap

- [x] Core receipt data model
- [x] Ed25519 signing/verification
- [x] Client-side token counting
- [x] Receipt validation with thresholds
- [x] Audit logging and reports
- [x] HTTP client wrapper
- [ ] TEE (Trusted Execution Environment) attestation
- [ ] Merkle tree audit log anchoring
- [ ] Multi-provider receipt aggregation
- [ ] Web dashboard for audit visualization
- [ ] Provider SDK for easy IRP adoption

## License

MIT License - See [LICENSE](LICENSE) for details.

## Contributing

IRP is an open protocol. Contributions are welcome:

1. Open an issue to discuss changes
2. Fork and implement
3. Submit a pull request

## References

This project was inspired by the need for transparent AI inference billing, as discussed in the AI inference protocol standardization research:

- [Research Report](../research/SUMMARY_REPORT.md)
