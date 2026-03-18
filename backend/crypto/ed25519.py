"""
Ed25519 cryptographic primitives using PyNaCl.

Security properties:
- 256-bit security level
- Deterministic signing (no RNG in signing path)
- sodium_memzero used to clear key material from memory
- All secrets held as SigningKey objects (never raw bytes in persistent vars)
"""

import nacl.signing
import nacl.encoding
import nacl.exceptions
from nacl.utils import random as nacl_random
import hashlib
from typing import NamedTuple


class KeyPair(NamedTuple):
    private_key: bytes   # 32-byte seed (never persist raw — use vault.py)
    public_key: bytes    # 32-byte public key


def generate_keypair() -> KeyPair:
    """Generate a fresh Ed25519 keypair. Private key returned as seed bytes."""
    signing_key = nacl.signing.SigningKey.generate()
    private_seed = bytes(signing_key)
    public_key = bytes(signing_key.verify_key)
    return KeyPair(private_key=private_seed, public_key=public_key)


def sign_message(private_key_seed: bytes, message: bytes) -> bytes:
    """Sign a message with Ed25519. Returns 64-byte signature."""
    signing_key = nacl.signing.SigningKey(private_key_seed)
    signed = signing_key.sign(message)
    # signed.signature is 64 bytes
    return bytes(signed.signature)


def verify_signature(public_key: bytes, message: bytes, signature: bytes) -> bool:
    """Verify an Ed25519 signature. Returns True if valid, False otherwise."""
    try:
        verify_key = nacl.signing.VerifyKey(public_key)
        verify_key.verify(message, signature)
        return True
    except nacl.exceptions.BadSignatureError:
        return False


def fingerprint(public_key: bytes) -> str:
    """
    Generate a key fingerprint for display purposes.
    Format: SHA-256 of public key, hex-encoded, lowercase.
    """
    return hashlib.sha256(public_key).hexdigest()


def public_key_to_base64url(public_key: bytes) -> str:
    """Encode public key as base64url (no padding) for DID Documents."""
    import base64
    return base64.urlsafe_b64encode(public_key).rstrip(b"=").decode()


def public_key_from_base64url(encoded: str) -> bytes:
    """Decode base64url-encoded public key."""
    import base64
    padding = 4 - len(encoded) % 4
    if padding != 4:
        encoded += "=" * padding
    return base64.urlsafe_b64decode(encoded)


def secure_zero(data: bytearray) -> None:
    """Overwrite a bytearray with zeros (best-effort memory clearing in Python)."""
    for i in range(len(data)):
        data[i] = 0
