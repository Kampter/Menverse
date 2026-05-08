"""Tests for IRP (Inference Receipt Protocol)."""

import pytest

from irp.models import Receipt, VerificationResult, LatencyMetrics
from irp.signer import ReceiptSigner, ReceiptVerifier, hash_content
from irp.tokenizer import TokenCounter, create_counter_for_model
from irp.receipt import ReceiptValidator


class TestReceiptSigner:
    """Test digital signature functionality."""

    def test_generate_keypair(self):
        signer = ReceiptSigner()
        assert signer.public_key
        assert signer.private_key
        assert len(signer.public_key) > 0

    def test_sign_and_verify(self):
        signer = ReceiptSigner()
        receipt_data = {
            "request_id": "test-123",
            "timestamp": "2026-01-01T00:00:00Z",
            "provider": "test-provider",
            "model": "gpt-4",
            "input_tokens": 100,
            "output_tokens": 50,
            "total_tokens": 150,
        }

        signature = signer.sign_receipt(receipt_data)
        assert signature
        assert len(signature) > 0

        # Self-verify
        assert signer.verify(receipt_data, signature) is True

    def test_tampered_data_fails(self):
        signer = ReceiptSigner()
        receipt_data = {
            "request_id": "test-123",
            "input_tokens": 100,
        }

        signature = signer.sign_receipt(receipt_data)

        # Tamper with data
        receipt_data["input_tokens"] = 200
        assert signer.verify(receipt_data, signature) is False

    def test_cross_verifier(self):
        signer = ReceiptSigner()
        receipt_data = {"request_id": "test", "input_tokens": 100}
        signature = signer.sign_receipt(receipt_data)

        verifier = ReceiptVerifier(signer.public_key)
        valid, error = verifier.verify(receipt_data, signature)
        assert valid is True
        assert error is None

    def test_verify_with_wrong_key(self):
        signer = ReceiptSigner()
        wrong_signer = ReceiptSigner()
        receipt_data = {"request_id": "test", "input_tokens": 100}
        signature = signer.sign_receipt(receipt_data)

        verifier = ReceiptVerifier(wrong_signer.public_key)
        valid, error = verifier.verify(receipt_data, signature)
        assert valid is False
        assert error is not None

    def test_hash_content(self):
        h1 = hash_content("hello world")
        h2 = hash_content("hello world")
        h3 = hash_content("different text")

        assert h1 == h2
        assert h1 != h3
        assert len(h1) == 64  # SHA-256 hex


class TestTokenCounter:
    """Test token counting functionality."""

    def test_count_empty(self):
        counter = TokenCounter()
        assert counter.count("") == 0

    def test_count_english(self):
        counter = TokenCounter()
        count = counter.count("Hello world")
        assert count > 0

    def test_count_chinese(self):
        counter = TokenCounter()
        count = counter.count("你好世界")
        assert count > 0

    def test_count_messages(self):
        counter = TokenCounter()
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello!"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        count = counter.count_messages(messages)
        assert count > 0

    def test_approximate_fallback(self):
        """Test that approximate counting works when tiktoken unavailable."""
        # Create a counter with a fake encoding that will fail
        counter = TokenCounter("nonexistent_encoding_12345")
        assert not counter.is_exact

        count = counter.count("Hello world this is a test")
        assert count > 0

        # Approximate should be in reasonable range
        assert 5 <= count <= 30

    def test_create_counter_for_model(self):
        gpt4 = create_counter_for_model("gpt-4")
        assert gpt4.encoding_name == "cl100k_base"

        gpt4o = create_counter_for_model("gpt-4o")
        assert gpt4o.encoding_name == "o200k_base"

        claude = create_counter_for_model("claude-3-sonnet")
        assert claude.encoding_name == "cl100k_base"  # Fallback


class TestReceiptValidator:
    """Test receipt validation logic."""

    def test_valid_receipt(self):
        validator = ReceiptValidator(threshold_percent=10.0)

        receipt = Receipt(
            request_id="test-123",
            timestamp="2026-01-01T00:00:00Z",
            provider="test",
            model="gpt-4",
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
        )

        result = validator.verify(
            receipt=receipt,
            local_input_text="Hello world",
            local_output_text="Hi!",
        )

        assert result.request_id == "test-123"
        assert result.status in ["valid", "warning"]
        assert result.server_input_tokens == 10
        assert result.server_output_tokens == 5

    def test_receipt_with_signature(self):
        signer = ReceiptSigner()
        validator = ReceiptValidator(
            provider_public_key=signer.public_key,
            threshold_percent=100.0,  # Very lenient for this test
        )

        receipt_data = {
            "request_id": "test-123",
            "timestamp": "2026-01-01T00:00:00Z",
            "provider": "test",
            "model": "gpt-4",
            "input_tokens": 10,
            "output_tokens": 5,
            "total_tokens": 15,
        }
        signature = signer.sign_receipt(receipt_data)

        receipt = Receipt(
            request_id="test-123",
            timestamp="2026-01-01T00:00:00Z",
            provider="test",
            model="gpt-4",
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
            signature=signature,
            public_key=signer.public_key,
        )

        result = validator.verify(receipt=receipt)
        assert result.signature_valid is True

    def test_invalid_signature(self):
        validator = ReceiptValidator(threshold_percent=100.0)

        receipt = Receipt(
            request_id="test-123",
            timestamp="2026-01-01T00:00:00Z",
            provider="test",
            model="gpt-4",
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
            signature="invalid_signature",
            public_key="",
        )

        result = validator.verify(receipt=receipt)
        assert result.signature_valid is False
        assert result.status == "error"

    def test_token_diff_exceeds_threshold(self):
        validator = ReceiptValidator(threshold_percent=1.0)

        receipt = Receipt(
            request_id="test-123",
            timestamp="2026-01-01T00:00:00Z",
            provider="test",
            model="gpt-4",
            input_tokens=1000,
            output_tokens=500,
            total_tokens=1500,
        )

        result = validator.verify(
            receipt=receipt,
            local_input_text="Short text",
            local_output_text="Short reply",
        )

        assert result.status == "warning"
        assert len(result.errors) > 0

    def test_audit_log(self):
        validator = ReceiptValidator(threshold_percent=100.0)

        for i in range(3):
            receipt = Receipt(
                request_id=f"test-{i}",
                timestamp="2026-01-01T00:00:00Z",
                provider="test",
                model="gpt-4",
                input_tokens=10,
                output_tokens=5,
                total_tokens=15,
            )
            validator.verify(receipt=receipt)

        log = validator.get_audit_log()
        assert len(log) == 3

        summary = validator.get_summary()
        assert summary["total"] == 3

    def test_report_generation(self):
        validator = ReceiptValidator(threshold_percent=100.0)

        receipt = Receipt(
            request_id="test-123",
            timestamp="2026-01-01T00:00:00Z",
            provider="test",
            model="gpt-4",
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
        )
        validator.verify(receipt=receipt)

        report = validator.generate_report()
        assert "IRP Audit Report" in report
        assert "test-123" in report or "Total receipts" in report


class TestModels:
    """Test data models."""

    def test_receipt_defaults(self):
        receipt = Receipt(
            request_id="test",
            timestamp="2026-01-01T00:00:00Z",
            provider="test",
            model="gpt-4",
        )
        assert receipt.input_tokens == 0
        assert receipt.output_tokens == 0
        assert receipt.total_tokens == 0

    def test_receipt_total_computed(self):
        receipt = Receipt(
            request_id="test",
            timestamp="2026-01-01T00:00:00Z",
            provider="test",
            model="gpt-4",
            input_tokens=10,
            output_tokens=5,
        )
        assert receipt.total_tokens == 15

    def test_latency_repr(self):
        latency = LatencyMetrics(
            queue_ms=10.0,
            time_to_first_token_ms=100.0,
            time_per_output_token_ms=20.0,
            total_ms=200.0,
        )
        repr_str = repr(latency)
        assert "queue=10.0ms" in repr_str
        assert "ttft=100.0ms" in repr_str

    def test_verification_result_repr(self):
        result = VerificationResult(
            request_id="abc123def456",
            status="valid",
            signature_valid=True,
            input_diff_percent=2.0,
            output_diff_percent=1.0,
        )
        repr_str = repr(result)
        assert "valid" in repr_str
        assert "signature_valid=True" in repr_str
