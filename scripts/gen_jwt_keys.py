#!/usr/bin/env python3
"""
Generate Ed25519 JWT signing keys for AgentForge.

Outputs:
  - jwt_private.pem  (KEEP SECRET — goes in .env as JWT_PRIVATE_KEY_PEM)
  - jwt_public.pem   (can be distributed for token verification)

Usage:
  python scripts/gen_jwt_keys.py
"""

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding, PrivateFormat, PublicFormat, NoEncryption
)
import os

private_key = Ed25519PrivateKey.generate()
public_key = private_key.public_key()

private_pem = private_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
public_pem = public_key.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)

# Write files
with open("jwt_private.pem", "wb") as f:
    f.write(private_pem)

with open("jwt_public.pem", "wb") as f:
    f.write(public_pem)

print("✓ Generated jwt_private.pem and jwt_public.pem")
print()
print("Add to .env:")
print(f"JWT_PRIVATE_KEY_PEM={repr(private_pem.decode())}")
print(f"JWT_PUBLIC_KEY_PEM={repr(public_pem.decode())}")
print()
print("⚠️  Keep jwt_private.pem secret. Add to .gitignore (already done).")
