"""Tests for IRP Schema Extensions (Unit #15)."""

import pytest

from irp.models import Receipt, LatencyMetrics, generate_nonce
from irp.signer import ReceiptSigner, ReceiptVerifier, build_canonical_dict
from irp.receipt import ReceiptValidator


class TestReceiptNewFields:
    def test_receipt_new_fields_default(self):
        receipt = Receipt(
            request_id="test",
            timestamp="2026-01-01T00:00:00Z",
            provider="test",
            model="gpt-4",
        )
        assert receipt.nonce == ""
        assert receipt.version == "0.1.0"
        assert receipt.policy_id is None


class TestGenerateNonce:
    def test_generate_nonce_uniqueness(self):
        nonces = {generate_nonce() for _ in range(100)}
        assert len(nonces) == 100

    def test_generate_nonce_length(self):
        nonce = generate_nonce()
        assert len(nonce) == 22


class TestBuildCanonicalDict:
    def test_build_canonical_dict_includes_billing(self):
        receipt = Receipt(
            request_id="r1",
            timestamp="2026-01-01T00:00:00Z",
            provider="p",
            model="m",
            cost_total=1.23,
            latency=LatencyMetrics(total_ms=500.0),
        )
        d = build_canonical_dict(receipt)
        assert d["cost_total"] == 1.23
        assert d["latency"]["total_ms"] == 500.0

    def test_build_canonical_dict_excludes_signature(self):
        receipt = Receipt(
            request_id="r1",
            timestamp="2026-01-01T00:00:00Z",
            provider="p",
            model="m",
            signature="sig",
            public_key="pk",
        )
        d = build_canonical_dict(receipt)
        assert "signature" not in d
        assert "public_key" not in d

    def test_build_canonical_dict_omits_none_optional(self):
        receipt = Receipt(
            request_id="r1",
            timestamp="2026-01-01T00:00:00Z",
            provider="p",
            model="m",
            model_version=None,
            policy_id=None,
        )
        d = build_canonical_dict(receipt)
        assert "model_version" not in d
        assert "policy_id" not in d

    def test_build_canonical_dict_includes_set_optional(self):
        receipt = Receipt(
            request_id="r1",
            timestamp="2026-01-01T00:00:00Z",
            provider="p",
            model="m",
            model_version="v1",
            policy_id="premium-2026-q1",
            nonce="abc123",
            reasoning_tokens=10,
            cached_tokens=5,
            input_hash="ihash",
            output_hash="ohash",
        )
        d = build_canonical_dict(receipt)
        assert d["model_version"] == "v1"
        assert d["policy_id"] == "premium-2026-q1"
        assert d["nonce"] == "abc123"
        assert d["reasoning_tokens"] == 10
        assert d["cached_tokens"] == 5
        assert d["input_hash"] == "ihash"
        assert d["output_hash"] == "ohash"


class TestSignatureCoverage:
    def test_signature_covers_cost_field(self):
        signer = ReceiptSigner()
        receipt = Receipt(
            request_id="r1",
            timestamp="2026-01-01T00:00:00Z",
            provider="p",
            model="m",
            cost_total=1.0,
        )
        receipt.signature = signer.sign(receipt)
        receipt.public_key = signer.public_key

        # Mutate cost
        receipt.cost_total = 2.0
        verifier = ReceiptVerifier(signer.public_key)
        valid, _ = verifier.verify(receipt, receipt.signature)
        assert valid is False

    def test_signature_covers_latency_field(self):
        signer = ReceiptSigner()
        receipt = Receipt(
            request_id="r1",
            timestamp="2026-01-01T00:00:00Z",
            provider="p",
            model="m",
            latency=LatencyMetrics(total_ms=100.0),
        )
        receipt.signature = signer.sign(receipt)
        receipt.public_key = signer.public_key

        # Mutate latency
        receipt.latency.total_ms = 200.0
        verifier = ReceiptVerifier(signer.public_key)
        valid, _ = verifier.verify(receipt, receipt.signature)
        assert valid is False


class TestSignerAccepts:
    def test_signer_accepts_dict_legacy(self):
        signer = ReceiptSigner()
        receipt_data = {
            "request_id": "test-123",
            "timestamp": "2026-01-01T00:00:00Z",
            "provider": "test",
            "model": "gpt-4",
            "input_tokens": 100,
            "output_tokens": 50,
            "total_tokens": 150,
        }
        signature = signer.sign_receipt(receipt_data)
        assert signature
        assert signer.verify(receipt_data, signature) is True

    def test_signer_accepts_receipt(self):
        signer = ReceiptSigner()
        receipt = Receipt(
            request_id="test-123",
            timestamp="2026-01-01T00:00:00Z",
            provider="test",
            model="gpt-4",
            input_tokens=100,
            output_tokens=50,
        )
        signature = signer.sign_receipt(receipt)
        assert signature
        assert signer.verify(receipt, signature) is True


class TestValidatorCanonical:
    def test_validator_canonical_uses_build_canonical_dict(self):
        signer = ReceiptSigner()
        validator = ReceiptValidator(provider_public_key=signer.public_key)

        receipt = Receipt(
            request_id="r1",
            timestamp="2026-01-01T00:00:00Z",
            provider="p",
            model="m",
            nonce="n1",
            version="0.1.1",
            policy_id="policy-1",
            cost_total=1.5,
            latency=LatencyMetrics(total_ms=300.0, queue_ms=10.0),
        )
        receipt.signature = signer.sign(receipt)
        receipt.public_key = signer.public_key

        result = validator.verify(receipt=receipt)
        assert result.signature_valid is True
