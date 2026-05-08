"""Core receipt verification logic for IRP."""

import json
from typing import Optional, List

from .models import Receipt, VerificationResult, LatencyMetrics
from .signer import ReceiptVerifier
from .tokenizer import create_counter_for_model


class ReceiptValidator:
    """Validates inference receipts client-side."""

    def __init__(
        self,
        provider_public_key: Optional[str] = None,
        threshold_percent: float = 5.0,
    ):
        self.threshold_percent = threshold_percent
        self._signature_verifier = ReceiptVerifier(provider_public_key)
        self._audit_log: List[VerificationResult] = []

    def set_public_key(self, public_key_b64: str) -> None:
        """Set or update the provider's public key for signature verification."""
        self._signature_verifier.set_public_key(public_key_b64)

    def verify(
        self,
        receipt: Receipt,
        local_input_text: Optional[str] = None,
        local_output_text: Optional[str] = None,
        local_messages: Optional[list] = None,
    ) -> VerificationResult:
        """
        Verify a receipt against client-side computations.

        Args:
            receipt: The receipt from the provider.
            local_input_text: The input text sent (for token counting).
            local_output_text: The output text received.
            local_messages: OpenAI-format messages (alternative to input_text).

        Returns:
            VerificationResult with detailed comparison.
        """
        result = VerificationResult(
            request_id=receipt.request_id,
            threshold_percent=self.threshold_percent,
        )

        # Record server token counts
        result.server_input_tokens = receipt.input_tokens
        result.server_output_tokens = receipt.output_tokens

        # Count tokens locally
        counter = create_counter_for_model(receipt.model)

        if local_messages:
            result.local_input_tokens = counter.count_messages(local_messages)
        elif local_input_text:
            result.local_input_tokens = counter.count(local_input_text)

        if local_output_text:
            result.local_output_tokens = counter.count(local_output_text)

        # Calculate differences
        if receipt.input_tokens > 0:
            result.input_diff = abs(receipt.input_tokens - result.local_input_tokens)
            result.input_diff_percent = (
                result.input_diff / receipt.input_tokens
            ) * 100

        if receipt.output_tokens > 0:
            result.output_diff = abs(
                receipt.output_tokens - result.local_output_tokens
            )
            result.output_diff_percent = (
                result.output_diff / receipt.output_tokens
            ) * 100

        # Check threshold
        max_diff = max(result.input_diff_percent, result.output_diff_percent)
        result.within_threshold = max_diff <= self.threshold_percent

        # Verify signature if present
        if receipt.signature and receipt.public_key:
            # Build canonical receipt data for signing
            receipt_data = {
                "request_id": receipt.request_id,
                "timestamp": receipt.timestamp,
                "provider": receipt.provider,
                "model": receipt.model,
                "input_tokens": receipt.input_tokens,
                "output_tokens": receipt.output_tokens,
                "total_tokens": receipt.total_tokens,
            }
            if receipt.input_hash:
                receipt_data["input_hash"] = receipt.input_hash
            if receipt.output_hash:
                receipt_data["output_hash"] = receipt.output_hash

            sig_valid, sig_error = self._signature_verifier.verify(
                receipt_data, receipt.signature
            )
            result.signature_valid = sig_valid
            if sig_error:
                result.signature_error = sig_error

        # Determine overall status
        if not result.signature_valid and receipt.signature:
            result.status = "error"
            result.errors.append("Signature verification failed")
        elif not result.within_threshold:
            result.status = "warning"
            if result.input_diff_percent > self.threshold_percent:
                result.errors.append(
                    f"Input token count differs by {result.input_diff_percent:.1f}% "
                    f"(threshold: {self.threshold_percent}%)"
                )
            if result.output_diff_percent > self.threshold_percent:
                result.errors.append(
                    f"Output token count differs by {result.output_diff_percent:.1f}% "
                    f"(threshold: {self.threshold_percent}%)"
                )
        else:
            result.status = "valid"

        result.is_valid = result.status == "valid"

        # Log
        self._audit_log.append(result)

        return result

    def get_audit_log(self) -> List[VerificationResult]:
        """Get all verification results for audit."""
        return self._audit_log.copy()

    def get_summary(self) -> dict:
        """Get summary statistics of all verifications."""
        if not self._audit_log:
            return {"total": 0}

        total = len(self._audit_log)
        valid = sum(1 for r in self._audit_log if r.status == "valid")
        warnings = sum(1 for r in self._audit_log if r.status == "warning")
        errors = sum(1 for r in self._audit_log if r.status == "error")

        avg_input_diff = sum(r.input_diff_percent for r in self._audit_log) / total
        avg_output_diff = sum(r.output_diff_percent for r in self._audit_log) / total

        return {
            "total": total,
            "valid": valid,
            "warnings": warnings,
            "errors": errors,
            "valid_rate": valid / total * 100,
            "avg_input_diff_percent": avg_input_diff,
            "avg_output_diff_percent": avg_output_diff,
        }

    def generate_report(self) -> str:
        """Generate a human-readable audit report."""
        summary = self.get_summary()
        lines = [
            "=" * 60,
            "IRP Audit Report",
            "=" * 60,
            f"",
            f"Total receipts verified: {summary['total']}",
            f"  Valid:   {summary['valid']} ({summary['valid_rate']:.1f}%)",
            f"  Warning: {summary['warnings']}",
            f"  Error:   {summary['errors']}",
            f"",
            f"Average input token diff:  {summary['avg_input_diff_percent']:.2f}%",
            f"Average output token diff: {summary['avg_output_diff_percent']:.2f}%",
            f"",
        ]

        if summary["warnings"] > 0 or summary["errors"] > 0:
            lines.append("Details:")
            for result in self._audit_log:
                if result.status != "valid":
                    lines.append(f"  [{result.status.upper()}] {result}")
                    for error in result.errors:
                        lines.append(f"    - {error}")

        lines.append("=" * 60)
        return "\n".join(lines)
