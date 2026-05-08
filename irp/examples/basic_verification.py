#!/usr/bin/env python3
"""Basic example: Verify an inference receipt manually."""

from irp import Receipt, ReceiptValidator


def main():
    # Step 1: Create a receipt (normally this comes from the provider's API response)
    receipt = Receipt(
        request_id="req-123",
        timestamp="2026-01-01T00:00:00Z",
        provider="together-ai",
        model="meta-llama/Llama-3-8B",
        input_tokens=10,
        output_tokens=5,
        total_tokens=15,
        cost_total=0.0002,
    )

    print(f"Receipt: {receipt.request_id}")
    print(f"  Model: {receipt.model}")
    print(f"  Server tokens: {receipt.total_tokens}")
    print()

    # Step 2: Verify with local token counting
    validator = ReceiptValidator(threshold_percent=5.0)

    result = validator.verify(
        receipt=receipt,
        local_input_text="Hello, world!",
        local_output_text="Hi there!",
    )

    print(f"Verification Result:")
    print(f"  Status: {result.status}")
    print(f"  Local input tokens: {result.local_input_tokens}")
    print(f"  Local output tokens: {result.local_output_tokens}")
    print(f"  Input diff: {result.input_diff_percent:.1f}%")
    print(f"  Output diff: {result.output_diff_percent:.1f}%")
    print(f"  Within threshold: {result.within_threshold}")

    if result.errors:
        print(f"  Errors: {result.errors}")

    # Step 3: Generate audit report
    print()
    report = validator.generate_report()
    print(report)


if __name__ == "__main__":
    main()
