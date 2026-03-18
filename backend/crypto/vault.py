"""
Secure key storage using XChaCha20-Poly1305 (PyNaCl SecretBox) +
Argon2id for key derivation.

Security properties:
- XChaCha20-Poly1305: 256-bit key, 192-bit nonces (safe for random generation),
  authenticated encryption — no separate HMAC needed.
- Argon2id: GPU/ASIC resistant (128 MiB memory, 3 iterations, 4 parallelism).
  An RTX 5090 can crack PBKDF2/bcrypt but NOT Argon2id at these parameters.
- Each encryption uses a fresh random nonce (SecretBox.encrypt auto-generates).
- Salt is stored alongside ciphertext — fresh salt per key.
"""

import nacl.secret
import nacl.utils
from argon2.low_level import hash_secret_raw, Type
import os


# Argon2id parameters (OWASP 2024 recommendation)
ARGON2_MEMORY_COST = 131072   # 128 MiB in KiB
ARGON2_TIME_COST = 3
ARGON2_PARALLELISM = 4
ARGON2_HASH_LEN = 32          # 256-bit output key
ARGON2_SALT_LEN = 16          # 128-bit salt


def derive_key(passphrase: str | bytes, salt: bytes) -> bytes:
    """
    Derive a 256-bit symmetric key from a passphrase using Argon2id.

    Args:
        passphrase: User password or master secret (str or bytes)
        salt: 16-byte random salt (stored alongside ciphertext)

    Returns:
        32-byte derived key for use with SecretBox
    """
    if isinstance(passphrase, str):
        passphrase = passphrase.encode("utf-8")
    return hash_secret_raw(
        secret=passphrase,
        salt=salt,
        time_cost=ARGON2_TIME_COST,
        memory_cost=ARGON2_MEMORY_COST,
        parallelism=ARGON2_PARALLELISM,
        hash_len=ARGON2_HASH_LEN,
        type=Type.ID,
    )


def generate_salt() -> bytes:
    """Generate a cryptographically secure random 16-byte salt."""
    return nacl.utils.random(ARGON2_SALT_LEN)


def encrypt_key(private_key_seed: bytes, passphrase: str | bytes) -> tuple[bytes, bytes]:
    """
    Encrypt a private key seed using XChaCha20-Poly1305.

    Args:
        private_key_seed: 32-byte Ed25519 private key seed
        passphrase: Encryption passphrase (user password or server secret)

    Returns:
        (ciphertext_with_nonce, salt) — both must be stored; salt needed for decryption
    """
    salt = generate_salt()
    key = derive_key(passphrase, salt)
    box = nacl.secret.SecretBox(key)
    # SecretBox.encrypt() prepends a 24-byte random nonce automatically
    ciphertext = box.encrypt(private_key_seed)
    return bytes(ciphertext), salt


def decrypt_key(ciphertext: bytes, salt: bytes, passphrase: str | bytes) -> bytes:
    """
    Decrypt a private key seed.

    Args:
        ciphertext: Output from encrypt_key (includes nonce)
        salt: Salt used during encryption
        passphrase: Same passphrase used for encryption

    Returns:
        32-byte private key seed

    Raises:
        nacl.exceptions.CryptoError: If decryption fails (wrong passphrase or tampered)
    """
    key = derive_key(passphrase, salt)
    box = nacl.secret.SecretBox(key)
    return bytes(box.decrypt(ciphertext))


def encrypt_blob(data: bytes, key_32: bytes) -> bytes:
    """
    Encrypt arbitrary data with a pre-derived 32-byte key (XChaCha20-Poly1305).
    Used for memory blobs, session state, etc.
    """
    box = nacl.secret.SecretBox(key_32)
    return bytes(box.encrypt(data))


def decrypt_blob(ciphertext: bytes, key_32: bytes) -> bytes:
    """Decrypt data encrypted with encrypt_blob."""
    box = nacl.secret.SecretBox(key_32)
    return bytes(box.decrypt(ciphertext))
