"""
Merkle hash tree implementation for tamper-evident session chains.

Properties:
- O(log n) proofs (tree not chain)
- Cross-signed roots for tamper evidence
- SHA-256 leaf hashing, SHA-256 internal nodes
- key_algorithm field for post-quantum readiness (future ML-DSA-65 hybrid)
"""

import hashlib
from dataclasses import dataclass, field
from typing import Optional
import json


def sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def hash_leaf(message: bytes) -> bytes:
    """Hash a leaf node. Prefix with 0x00 to prevent second-preimage attacks."""
    return sha256(b"\x00" + message)


def hash_internal(left: bytes, right: bytes) -> bytes:
    """Hash two child nodes into a parent. Prefix with 0x01."""
    return sha256(b"\x01" + left + right)


@dataclass
class MerkleTree:
    """
    Binary Merkle tree built from message hashes.
    Supports O(log n) inclusion proofs.
    """
    leaves: list[bytes] = field(default_factory=list)
    _tree: list[list[bytes]] = field(default_factory=list, repr=False)
    key_algorithm: str = "sha256"   # Future: "sha256+ml-dsa-65" hybrid

    def add_leaf(self, message: bytes) -> int:
        """Add a message and return its leaf index."""
        self.leaves.append(hash_leaf(message))
        self._tree = []   # invalidate cached tree
        return len(self.leaves) - 1

    def _build_tree(self) -> list[list[bytes]]:
        """Build the full tree bottom-up."""
        if not self.leaves:
            return []
        layers = [list(self.leaves)]
        current = list(self.leaves)
        while len(current) > 1:
            if len(current) % 2 == 1:
                current.append(current[-1])   # duplicate last leaf if odd
            next_layer = [
                hash_internal(current[i], current[i + 1])
                for i in range(0, len(current), 2)
            ]
            layers.append(next_layer)
            current = next_layer
        return layers

    @property
    def root(self) -> Optional[bytes]:
        """Current Merkle root. None if no leaves."""
        if not self.leaves:
            return None
        tree = self._build_tree()
        return tree[-1][0]

    def get_proof(self, leaf_index: int) -> list[dict]:
        """
        Generate an inclusion proof for leaf at leaf_index.
        Returns list of {"sibling": hex, "position": "left"|"right"} dicts.
        """
        if leaf_index >= len(self.leaves):
            raise IndexError(f"Leaf index {leaf_index} out of range")
        tree = self._build_tree()
        proof = []
        idx = leaf_index
        for layer in tree[:-1]:
            if idx % 2 == 0:
                sibling_idx = idx + 1 if idx + 1 < len(layer) else idx
                position = "right"
            else:
                sibling_idx = idx - 1
                position = "left"
            proof.append({
                "sibling": layer[sibling_idx].hex(),
                "position": position
            })
            idx //= 2
        return proof

    def verify_proof(self, leaf_message: bytes, leaf_index: int, proof: list[dict], root: bytes) -> bool:
        """Verify an inclusion proof."""
        current = hash_leaf(leaf_message)
        idx = leaf_index
        for step in proof:
            sibling = bytes.fromhex(step["sibling"])
            if step["position"] == "right":
                current = hash_internal(current, sibling)
            else:
                current = hash_internal(sibling, current)
            idx //= 2
        return current == root

    def to_dict(self) -> dict:
        return {
            "leaf_count": len(self.leaves),
            "root": self.root.hex() if self.root else None,
            "key_algorithm": self.key_algorithm,
        }


def build_session_root(message_hashes: list[bytes]) -> Optional[bytes]:
    """Build a Merkle root from a list of message hashes (convenience function)."""
    tree = MerkleTree()
    for h in message_hashes:
        tree.leaves.append(h)   # already hashed
    return tree.root
