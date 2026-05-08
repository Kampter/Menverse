"""RFC 6962-style append-only Merkle audit log for receipt integrity.

A single Ed25519 signature on each receipt is not enough: a provider could
silently drop or mutate receipts in their archive after the fact. By chaining
receipts into an append-only Merkle tree and publishing the root, the log
becomes tamper-evident — any modification to a past receipt changes the root.

Hashing follows RFC 6962 (Certificate Transparency):
    leaf:  SHA256(0x00 || data)
    node:  SHA256(0x01 || left || right)
    empty: SHA256(b"")
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class MerkleProof:
    """Inclusion proof for a leaf at a given index."""

    leaf_index: int
    leaf_hash: bytes  # 32 bytes
    audit_path: list[bytes]  # sibling hashes from leaf to root
    tree_size: int  # tree size at the time of proof


class MerkleAuditLog:
    """Append-only Merkle log of receipt canonical bytes."""

    LEAF_PREFIX = b"\x00"
    NODE_PREFIX = b"\x01"

    def __init__(self) -> None:
        # Stored as the 32-byte leaf hashes; the internal tree is recomputed
        # on demand. For an MVP this is fine — append is O(1) and root/proof
        # are O(n). A production log would maintain incremental tree state.
        self._leaves: list[bytes] = []

    def __len__(self) -> int:
        return len(self._leaves)

    @classmethod
    def _hash_leaf(cls, data: bytes) -> bytes:
        return hashlib.sha256(cls.LEAF_PREFIX + data).digest()

    @classmethod
    def _hash_node(cls, left: bytes, right: bytes) -> bytes:
        return hashlib.sha256(cls.NODE_PREFIX + left + right).digest()

    @staticmethod
    def _largest_power_of_two_less_than(n: int) -> int:
        """Largest k = 2^a such that k < n (RFC 6962 split point for n >= 2)."""
        if n < 2:
            raise ValueError("n must be >= 2")
        # e.g. n=2 (10) -> bit_length=2 -> 1 << 0 = 1
        # e.g. n=5 (101) -> bit_length=3 -> 1 << 1 = 2 ... wait that's wrong too.
        # We need the highest power of 2 strictly less than n.
        # For n=2: k=1, n=3: k=2, n=4: k=2, n=5: k=4
        # 1 << (n.bit_length() - 1) gives: n=2->2, n=3->2, n=4->4, n=5->4
        # That's >= n when n is power of 2. So we need to shift one more when n is power of 2.
        # Actually simpler: 1 << (n.bit_length() - 1) is the largest power of 2 <= n.
        # We want strictly less, so: if n is power of 2, divide by 2.
        k = 1 << (n.bit_length() - 1)
        if k == n:
            k >>= 1
        return k

    @classmethod
    def _merkle_tree_hash(cls, leaves: list[bytes]) -> bytes:
        """RFC 6962 MTH over an already-hashed list of leaves."""
        n = len(leaves)
        if n == 0:
            return hashlib.sha256(b"").digest()
        if n == 1:
            return leaves[0]
        k = cls._largest_power_of_two_less_than(n)
        left = cls._merkle_tree_hash(leaves[:k])
        right = cls._merkle_tree_hash(leaves[k:])
        return cls._hash_node(left, right)

    def append(self, canonical_bytes: bytes) -> int:
        """Hash canonical_bytes as a leaf and append. Returns the leaf index."""
        index = len(self._leaves)
        self._leaves.append(self._hash_leaf(canonical_bytes))
        return index

    def root_hash(self) -> bytes:
        """Compute current Merkle root. Returns 32 bytes. Empty tree -> SHA256(b"")."""
        return self._merkle_tree_hash(self._leaves)

    @classmethod
    def _path(cls, leaves: list[bytes], index: int) -> list[bytes]:
        """RFC 6962 PATH(m, D[n]): audit path for leaf at index m within D[0:n]."""
        n = len(leaves)
        if n <= 1:
            return []
        k = cls._largest_power_of_two_less_than(n)
        if index < k:
            # Sibling is the MTH of the right subtree.
            return cls._path(leaves[:k], index) + [cls._merkle_tree_hash(leaves[k:])]
        # Sibling is the MTH of the left subtree.
        return cls._path(leaves[k:], index - k) + [cls._merkle_tree_hash(leaves[:k])]

    def proof(self, leaf_index: int) -> MerkleProof:
        """Generate inclusion proof for leaf at given index.

        Raises IndexError if leaf_index is out of bounds.
        """
        n = len(self._leaves)
        if leaf_index < 0 or leaf_index >= n:
            raise IndexError(
                f"leaf_index {leaf_index} out of range for tree of size {n}"
            )
        return MerkleProof(
            leaf_index=leaf_index,
            leaf_hash=self._leaves[leaf_index],
            audit_path=self._path(self._leaves, leaf_index),
            tree_size=n,
        )

    @classmethod
    def _verify(cls, leaf_hash: bytes, index: int, size: int, path: list[bytes], path_idx: int) -> tuple[bytes | None, int]:
        """RFC 6962 proof verification — recursive mirror of _path().

        Returns (reconstructed_root_hash, next_path_idx) or (None, _) on failure.
        """
        if size <= 1:
            return leaf_hash, path_idx
        k = cls._largest_power_of_two_less_than(size)
        if index < k:
            # Leaf is in the left subtree; sibling is the MTH of the right subtree.
            left, path_idx = cls._verify(leaf_hash, index, k, path, path_idx)
            if left is None:
                return None, path_idx
            if path_idx >= len(path):
                return None, path_idx
            sibling = path[path_idx]
            path_idx += 1
            return cls._hash_node(left, sibling), path_idx
        # Leaf is in the right subtree; sibling is the MTH of the left subtree.
        right, path_idx = cls._verify(leaf_hash, index - k, size - k, path, path_idx)
        if right is None:
            return None, path_idx
        if path_idx >= len(path):
            return None, path_idx
        sibling = path[path_idx]
        path_idx += 1
        return cls._hash_node(sibling, right), path_idx

    @staticmethod
    def verify_proof(proof: MerkleProof, root_hash: bytes) -> bool:
        """Reconstruct root from proof and compare with given root_hash."""
        if proof.tree_size <= 0:
            return False
        if proof.leaf_index < 0 or proof.leaf_index >= proof.tree_size:
            return False

        computed, path_idx = MerkleAuditLog._verify(
            proof.leaf_hash, proof.leaf_index, proof.tree_size, proof.audit_path, 0
        )
        if computed is None:
            return False

        # Reject proofs with extra path entries.
        if path_idx != len(proof.audit_path):
            return False

        return computed == root_hash
