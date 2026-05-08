#!/usr/bin/env python3
"""Example: Provider signs a receipt, client verifies the signature."""

from irp.signer import ReceiptSigner
from irp import Receipt, ReceiptValidator


def main():
    # Provider side: generate keypair and sign receipt
    print("=== Provider Side ===")
    provider_signer = ReceiptSigner()
    public_key = provider_signer.public_key
    print(f"Provider public key: {public_key[:40]}...")

    # Provider creates receipt data
    receipt_data = {
        "request_id": "req-456",
        "timestamp": "2026-01-01T00:00:00Z",
        "provider": "my-provider",
        "model": "gpt-4",
        "input_tokens": 100,
        "output_tokens": 50,
        "total_tokens": 150,
    }

    # Provider signs the receipt
    signature = provider_signer.sign_receipt(receipt_data)
    print(f"Signature: {signature[:40]}...")
    print()

    # Client side: verify the receipt
    print("=== Client Side ===")
    receipt = Receipt(
        request_id="req-456",
        timestamp="2026-01-01T00:00:00Z",
        provider="my-provider",
        model="gpt-4",
        input_tokens=100,
        output_tokens=50,
        total_tokens=150,
        signature=signature,
        public_key=public_key,
    )

    # Client verifies with provider's public key
    validator = ReceiptValidator(
        provider_public_key=public_key,
        threshold_percent=10.0,
    )

    result = validator.verify(receipt=receipt)

    print(f"Signature valid: {result.signature_valid}")
    print(f"Status: {result.status}")

    # Tamper with receipt and re-verify
    print()
    print("=== Tamper Attack ===")
    receipt_tampered = Receipt(
        request_id="req-456",
        timestamp="2026-01-01T00:00:00Z",
        provider="my-provider",
        model="gpt-4",
        input_tokens=200,  # Tampered!
        output_tokens=50,
        total_tokens=250,
        signature=signature,  # Original signature
        public_key=public_key,
    )

    result_tampered = validator.verify(receipt=receipt_tampered)
    print(f"Signature valid: {result_tampered.signature_valid}")
    print(f"Signature error: {result_tampered.signature_error}")
    print(f"Status: {result_tampered.status}")


if __name__ == "__main__":
    main()
