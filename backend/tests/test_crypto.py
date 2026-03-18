"""
Crypto module tests — Ed25519, Vault (XChaCha20-Poly1305 + Argon2id), Merkle tree.
"""

import pytest
import nacl.exceptions
from backend.crypto.ed25519 import (
    generate_keypair, sign_message, verify_signature, fingerprint, public_key_to_base64url, public_key_from_base64url
)
from backend.crypto.vault import encrypt_key, decrypt_key, derive_key, generate_salt
from backend.crypto.merkle import MerkleTree, hash_leaf


class TestEd25519:
    def test_keypair_generation(self):
        kp = generate_keypair()
        assert len(kp.private_key) == 32
        assert len(kp.public_key) == 32

    def test_two_keypairs_are_unique(self):
        kp1 = generate_keypair()
        kp2 = generate_keypair()
        assert kp1.private_key != kp2.private_key
        assert kp1.public_key != kp2.public_key

    def test_sign_verify_roundtrip(self):
        kp = generate_keypair()
        message = b"hello agentforge"
        sig = sign_message(kp.private_key, message)
        assert len(sig) == 64
        assert verify_signature(kp.public_key, message, sig)

    def test_wrong_message_fails(self):
        kp = generate_keypair()
        sig = sign_message(kp.private_key, b"original")
        assert not verify_signature(kp.public_key, b"tampered", sig)

    def test_wrong_key_fails(self):
        kp1 = generate_keypair()
        kp2 = generate_keypair()
        sig = sign_message(kp1.private_key, b"message")
        assert not verify_signature(kp2.public_key, b"message", sig)

    def test_tampered_signature_fails(self):
        kp = generate_keypair()
        msg = b"important message"
        sig = bytearray(sign_message(kp.private_key, msg))
        sig[0] ^= 0xFF  # flip first byte
        assert not verify_signature(kp.public_key, msg, bytes(sig))

    def test_fingerprint_is_64_hex(self):
        kp = generate_keypair()
        fp = fingerprint(kp.public_key)
        assert len(fp) == 64
        assert all(c in "0123456789abcdef" for c in fp)

    def test_fingerprint_deterministic(self):
        kp = generate_keypair()
        assert fingerprint(kp.public_key) == fingerprint(kp.public_key)

    def test_base64url_roundtrip(self):
        kp = generate_keypair()
        encoded = public_key_to_base64url(kp.public_key)
        decoded = public_key_from_base64url(encoded)
        assert decoded == kp.public_key


class TestVault:
    def test_encrypt_decrypt_roundtrip(self):
        kp = generate_keypair()
        ciphertext, salt = encrypt_key(kp.private_key, "test-passphrase")
        recovered = decrypt_key(ciphertext, salt, "test-passphrase")
        assert recovered == kp.private_key

    def test_wrong_passphrase_fails(self):
        kp = generate_keypair()
        ciphertext, salt = encrypt_key(kp.private_key, "correct-passphrase")
        with pytest.raises(Exception):
            decrypt_key(ciphertext, salt, "wrong-passphrase")

    def test_tampered_ciphertext_fails(self):
        kp = generate_keypair()
        ciphertext, salt = encrypt_key(kp.private_key, "passphrase")
        tampered = bytearray(ciphertext)
        tampered[-1] ^= 0xFF
        with pytest.raises(Exception):
            decrypt_key(bytes(tampered), salt, "passphrase")

    def test_different_salts_produce_different_ciphertexts(self):
        kp = generate_keypair()
        ct1, s1 = encrypt_key(kp.private_key, "passphrase")
        ct2, s2 = encrypt_key(kp.private_key, "passphrase")
        # Salts should differ (random)
        assert s1 != s2
        # Ciphertexts should differ (random nonce)
        assert ct1 != ct2

    def test_argon2id_key_derivation(self):
        salt = generate_salt()
        key1 = derive_key("passphrase", salt)
        key2 = derive_key("passphrase", salt)
        assert key1 == key2  # deterministic
        assert len(key1) == 32

    def test_different_salts_produce_different_keys(self):
        s1, s2 = generate_salt(), generate_salt()
        k1 = derive_key("same", s1)
        k2 = derive_key("same", s2)
        assert k1 != k2


class TestMerkle:
    def test_empty_tree_root_is_none(self):
        tree = MerkleTree()
        assert tree.root is None

    def test_single_leaf_root_equals_leaf(self):
        tree = MerkleTree()
        tree.add_leaf(b"msg1")
        assert tree.root == hash_leaf(b"msg1")

    def test_root_changes_when_leaf_added(self):
        tree = MerkleTree()
        tree.add_leaf(b"msg1")
        r1 = tree.root
        tree.add_leaf(b"msg2")
        r2 = tree.root
        assert r1 != r2

    def test_inclusion_proof_single_leaf(self):
        tree = MerkleTree()
        tree.add_leaf(b"msg")
        proof = tree.get_proof(0)
        assert tree.verify_proof(b"msg", 0, proof, tree.root)

    def test_inclusion_proof_multiple_leaves(self):
        tree = MerkleTree()
        messages = [b"msg1", b"msg2", b"msg3", b"msg4"]
        for m in messages:
            tree.add_leaf(m)
        root = tree.root
        for i, m in enumerate(messages):
            proof = tree.get_proof(i)
            assert tree.verify_proof(m, i, proof, root), f"Proof failed for leaf {i}"

    def test_tampered_message_fails_proof(self):
        tree = MerkleTree()
        tree.add_leaf(b"original")
        tree.add_leaf(b"other")
        proof = tree.get_proof(0)
        assert not tree.verify_proof(b"tampered", 0, proof, tree.root)

    def test_odd_number_of_leaves(self):
        tree = MerkleTree()
        for i in range(5):
            tree.add_leaf(f"msg{i}".encode())
        root = tree.root
        assert root is not None
        # Verify all 5 proofs
        for i in range(5):
            proof = tree.get_proof(i)
            assert tree.verify_proof(f"msg{i}".encode(), i, proof, root)

    def test_to_dict(self):
        tree = MerkleTree()
        tree.add_leaf(b"m1")
        d = tree.to_dict()
        assert d["leaf_count"] == 1
        assert d["root"] is not None
        assert d["key_algorithm"] == "sha256"
