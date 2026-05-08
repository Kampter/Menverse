"""Tests for the RFC 6962-style Merkle audit log."""

from __future__ import annotations

import hashlib

import pytest

from irp.audit import MerkleAuditLog, MerkleProof


LEAF_PREFIX = b"\x00"
NODE_PREFIX = b"\x01"


def _leaf(data: bytes) -> bytes:
    return hashlib.sha256(LEAF_PREFIX + data).digest()


def _node(left: bytes, right: bytes) -> bytes:
    return hashlib.sha256(NODE_PREFIX + left + right).digest()


def test_empty_log_root_is_sha256_empty() -> None:
    log = MerkleAuditLog()
    assert log.root_hash() == hashlib.sha256(b"").digest()
    assert len(log) == 0


def test_single_leaf_root() -> None:
    log = MerkleAuditLog()
    log.append(b"a")
    assert log.root_hash() == _leaf(b"a")


def test_two_leaf_root() -> None:
    log = MerkleAuditLog()
    log.append(b"a")
    log.append(b"b")
    expected = _node(_leaf(b"a"), _leaf(b"b"))
    assert log.root_hash() == expected


def test_three_leaf_root() -> None:
    # n=3 -> k=2 (largest power of 2 < 3): split into [a,b] and [c].
    log = MerkleAuditLog()
    log.append(b"a")
    log.append(b"b")
    log.append(b"c")
    left = _node(_leaf(b"a"), _leaf(b"b"))
    right = _leaf(b"c")
    expected = _node(left, right)
    assert log.root_hash() == expected


def test_four_leaf_root_matches_reference_vector() -> None:
    # Reference vector from the unit description.
    log = MerkleAuditLog()
    for d in (b"a", b"b", b"c", b"d"):
        log.append(d)
    expected = _node(
        _node(_leaf(b"a"), _leaf(b"b")),
        _node(_leaf(b"c"), _leaf(b"d")),
    )
    assert log.root_hash() == expected


def test_append_returns_index() -> None:
    log = MerkleAuditLog()
    assert log.append(b"first") == 0
    assert log.append(b"second") == 1
    assert log.append(b"third") == 2


def test_log_size_grows() -> None:
    log = MerkleAuditLog()
    for i in range(5):
        log.append(f"receipt-{i}".encode())
    assert len(log) == 5


@pytest.mark.parametrize("size", [1, 2, 3, 4, 5, 6, 7, 8, 16])
def test_proof_round_trip(size: int) -> None:
    log = MerkleAuditLog()
    for i in range(size):
        log.append(f"receipt-{i}".encode())
    root = log.root_hash()
    for i in range(size):
        proof = log.proof(i)
        assert proof.leaf_index == i
        assert proof.tree_size == size
        assert proof.leaf_hash == _leaf(f"receipt-{i}".encode())
        assert MerkleAuditLog.verify_proof(proof, root) is True


def test_proof_round_trip_size_seven() -> None:
    # The unit explicitly calls out tree size 7 (non-trivial unbalanced shape).
    log = MerkleAuditLog()
    for i in range(7):
        log.append(f"r{i}".encode())
    root = log.root_hash()
    for i in range(7):
        proof = log.proof(i)
        assert MerkleAuditLog.verify_proof(proof, root) is True


def test_proof_invalid_root_fails_verify() -> None:
    log = MerkleAuditLog()
    for i in range(7):
        log.append(f"r{i}".encode())
    proof = log.proof(3)
    bad_root = bytes(32)  # all-zero root, definitely not real
    assert MerkleAuditLog.verify_proof(proof, bad_root) is False


def test_proof_invalid_path_fails_verify() -> None:
    log = MerkleAuditLog()
    for i in range(7):
        log.append(f"r{i}".encode())
    root = log.root_hash()
    proof = log.proof(3)
    assert proof.audit_path, "expected non-empty audit path for size-7 tree"

    # Flip a single bit in the first sibling.
    tampered_first = bytes([proof.audit_path[0][0] ^ 0x01]) + proof.audit_path[0][1:]
    tampered_path = [tampered_first, *proof.audit_path[1:]]
    tampered = MerkleProof(
        leaf_index=proof.leaf_index,
        leaf_hash=proof.leaf_hash,
        audit_path=tampered_path,
        tree_size=proof.tree_size,
    )
    assert MerkleAuditLog.verify_proof(tampered, root) is False


def test_proof_out_of_bounds_raises() -> None:
    log = MerkleAuditLog()
    for i in range(3):
        log.append(f"r{i}".encode())
    with pytest.raises(IndexError):
        log.proof(99)
    with pytest.raises(IndexError):
        log.proof(-1)


def test_proof_on_empty_log_raises() -> None:
    log = MerkleAuditLog()
    with pytest.raises(IndexError):
        log.proof(0)


def test_tampered_leaf_hash_fails_verify() -> None:
    log = MerkleAuditLog()
    for i in range(4):
        log.append(f"r{i}".encode())
    root = log.root_hash()
    proof = log.proof(2)
    tampered = MerkleProof(
        leaf_index=proof.leaf_index,
        leaf_hash=_leaf(b"not-the-original"),
        audit_path=proof.audit_path,
        tree_size=proof.tree_size,
    )
    assert MerkleAuditLog.verify_proof(tampered, root) is False


def test_root_changes_after_append() -> None:
    # Append-only integrity: adding a new receipt must change the root.
    log = MerkleAuditLog()
    log.append(b"a")
    log.append(b"b")
    root_before = log.root_hash()
    log.append(b"c")
    assert log.root_hash() != root_before


def test_verify_proof_tree_size_zero_returns_false() -> None:
    proof = MerkleProof(
        leaf_index=0,
        leaf_hash=_leaf(b"x"),
        audit_path=[],
        tree_size=0,
    )
    assert MerkleAuditLog.verify_proof(proof, _leaf(b"x")) is False


def test_verify_proof_negative_leaf_index_returns_false() -> None:
    proof = MerkleProof(
        leaf_index=-1,
        leaf_hash=_leaf(b"x"),
        audit_path=[],
        tree_size=1,
    )
    assert MerkleAuditLog.verify_proof(proof, _leaf(b"x")) is False


def test_verify_proof_leaf_index_out_of_range_returns_false() -> None:
    proof = MerkleProof(
        leaf_index=1,
        leaf_hash=_leaf(b"x"),
        audit_path=[],
        tree_size=1,
    )
    assert MerkleAuditLog.verify_proof(proof, _leaf(b"x")) is False


def test_verify_proof_extra_path_entries_returns_false() -> None:
    log = MerkleAuditLog()
    log.append(b"a")
    root = log.root_hash()
    proof = log.proof(0)
    # Audit path for a single-leaf tree is empty; add a bogus entry.
    tampered = MerkleProof(
        leaf_index=proof.leaf_index,
        leaf_hash=proof.leaf_hash,
        audit_path=[bytes(32)],
        tree_size=proof.tree_size,
    )
    assert MerkleAuditLog.verify_proof(tampered, root) is False


def test_verify_proof_too_few_path_entries_returns_false() -> None:
    log = MerkleAuditLog()
    log.append(b"a")
    log.append(b"b")
    root = log.root_hash()
    proof = log.proof(0)
    # Audit path for a 2-leaf tree has 1 entry; strip it.
    tampered = MerkleProof(
        leaf_index=proof.leaf_index,
        leaf_hash=proof.leaf_hash,
        audit_path=[],
        tree_size=proof.tree_size,
    )
    assert MerkleAuditLog.verify_proof(tampered, root) is False


def test_verify_proof_single_leaf_tree() -> None:
    log = MerkleAuditLog()
    log.append(b"solo")
    root = log.root_hash()
    proof = log.proof(0)
    assert proof.tree_size == 1
    assert proof.audit_path == []
    assert MerkleAuditLog.verify_proof(proof, root) is True


def test_audit_path_length_is_correct() -> None:
    # Audit path length should be ceil(log2(tree_size)) for power-of-2 sizes,
    # and similarly bounded for non-power-of-2 sizes.
    log = MerkleAuditLog()
    for i in range(16):
        log.append(f"r{i}".encode())
    for i in range(16):
        proof = log.proof(i)
        # Max path length for size n is ceil(log2(n)) when n is power of 2,
        # but for RFC 6962 it can be up to floor(log2(n)) + 1 for non-power-of-2.
        # For size 16, max path length is 4.
        assert len(proof.audit_path) <= 4, f"path too long for leaf {i}"
