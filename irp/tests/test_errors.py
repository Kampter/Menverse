"""Tests for IRP error code registry and exception type."""

import pytest

from irp.errors import (
    ERROR_HTTP_STATUS,
    IRPError,
    IRPErrorCode,
    code_from_int,
)


def test_error_code_ranges():
    """Spot-check that codes have the expected stable wire values."""
    assert IRPErrorCode.INVALID_FRAME == 1000
    assert IRPErrorCode.AUTH_FAILED == 2001
    assert IRPErrorCode.QUOTA_EXCEEDED == 3000
    assert IRPErrorCode.RECEIPT_SIGNATURE_INVALID == 4001
    assert IRPErrorCode.SLA_VIOLATED == 5000
    assert IRPErrorCode.INTERNAL_ERROR == 9999


def test_error_code_no_collisions():
    """All error code values must be unique."""
    values = [c.value for c in IRPErrorCode]
    assert len(values) == len(set(values))


def test_error_http_status_complete():
    """Every IRPErrorCode must have an entry in ERROR_HTTP_STATUS."""
    for code in IRPErrorCode:
        assert code in ERROR_HTTP_STATUS, f"missing HTTP mapping for {code.name}"
        status = ERROR_HTTP_STATUS[code]
        assert isinstance(status, int)
        assert 100 <= status <= 599


def test_irp_error_str():
    """str(IRPError) contains both the code name and its integer value."""
    err = IRPError(IRPErrorCode.AUTH_FAILED, "bad token")
    s = str(err)
    assert "AUTH_FAILED" in s
    assert "2001" in s
    assert "bad token" in s


def test_irp_error_to_dict_without_request_id():
    """to_dict includes code, name, detail; omits request_id when unset."""
    err = IRPError(IRPErrorCode.RECEIPT_INVALID, "missing signature")
    d = err.to_dict()
    assert d["code"] == 4000
    assert d["name"] == "RECEIPT_INVALID"
    assert d["detail"] == "missing signature"
    assert "request_id" not in d


def test_irp_error_to_dict_with_request_id():
    """to_dict includes request_id when provided."""
    err = IRPError(
        IRPErrorCode.RECEIPT_INVALID,
        "missing signature",
        request_id="req-123",
    )
    d = err.to_dict()
    assert d["code"] == 4000
    assert d["name"] == "RECEIPT_INVALID"
    assert d["detail"] == "missing signature"
    assert d["request_id"] == "req-123"


def test_irp_error_to_dict_with_empty_request_id():
    """to_dict includes request_id even when it is an empty string."""
    err = IRPError(
        IRPErrorCode.RECEIPT_INVALID,
        "missing signature",
        request_id="",
    )
    d = err.to_dict()
    assert "request_id" in d
    assert d["request_id"] == ""


def test_irp_error_default_detail():
    """IRPError with default detail produces a sensible message."""
    err = IRPError(IRPErrorCode.AUTH_FAILED)
    assert err.detail == ""
    assert "AUTH_FAILED" in str(err)
    d = err.to_dict()
    assert d["detail"] == ""


def test_irp_error_http_status():
    """The http_status property surfaces the mapped status code."""
    assert IRPError(IRPErrorCode.QUOTA_EXCEEDED).http_status == 429
    assert IRPError(IRPErrorCode.AUTH_REQUIRED).http_status == 401
    assert IRPError(IRPErrorCode.INTERNAL_ERROR).http_status == 500


def test_code_from_int_known():
    """Known integer values resolve to the matching IRPErrorCode."""
    assert code_from_int(2001) == IRPErrorCode.AUTH_FAILED
    assert code_from_int(1000) == IRPErrorCode.INVALID_FRAME
    assert code_from_int(9999) == IRPErrorCode.INTERNAL_ERROR


def test_code_from_int_unknown():
    """Unknown integer values raise ValueError."""
    with pytest.raises(ValueError):
        code_from_int(99999)
    with pytest.raises(ValueError):
        code_from_int(0)
