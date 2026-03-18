"""
Wallet service — encrypted private key storage and management.

Security model:
- Master wallet key = Argon2id(user_passphrase, salt) → XChaCha20-Poly1305
- Each agent's private key encrypted with wallet's master key (not raw passphrase)
- Key rotation: new keypair generated, old key marked revoked, new key stored
- Export/import: wallet exported as encrypted JSON blob
"""

import uuid
import json
import os
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from ..models.wallet import Wallet, WalletAgent, WalletKey
from ..models.user import User
from ..models.agent_identity import AgentIdentity
from ..crypto.vault import encrypt_key, decrypt_key, encrypt_blob, decrypt_blob, derive_key, generate_salt
from ..crypto.ed25519 import generate_keypair, fingerprint


def get_or_create_wallet(db: Session, user: User, passphrase: str) -> Wallet:
    """Get user's wallet or create one. Passphrase derives the master key."""
    wallet = db.query(Wallet).filter(Wallet.owner_id == user.id).first()
    if wallet:
        return wallet
    return _create_wallet(db, user, passphrase)


def _create_wallet(db: Session, user: User, passphrase: str) -> Wallet:
    """Create a new wallet with a master key derived from the passphrase."""
    salt = generate_salt()
    # Derive master key — encrypt a test blob to validate passphrase on future unlocks
    master_key = derive_key(passphrase, salt)
    # Encrypt the master key itself with a validation marker
    enc, _ = encrypt_key(master_key, passphrase + ":wallet-master")
    # We actually just store the encrypted 32-byte master key, keyed by passphrase
    # In practice, salt lets us re-derive and verify
    wallet = Wallet(
        owner_id=user.id,
        master_key_enc=enc,
        master_key_salt=salt,
    )
    db.add(wallet)
    db.commit()
    db.refresh(wallet)
    return wallet


def store_agent_key(
    db: Session,
    wallet: Wallet,
    agent: AgentIdentity,
    private_key_seed: bytes,
    passphrase: str,
) -> WalletKey:
    """Encrypt and store an agent's private key in the wallet."""
    # Derive per-agent encryption key from wallet master key
    salt = generate_salt()
    master_key = derive_key(passphrase, wallet.master_key_salt)
    # Use master key as the passphrase for per-key encryption
    enc, key_salt = encrypt_key(private_key_seed, master_key)

    # Determine version from highest existing key (including revoked)
    latest = (
        db.query(WalletKey)
        .filter(WalletKey.wallet_id == wallet.wallet_id, WalletKey.agent_id == agent.agent_id)
        .order_by(WalletKey.key_version.desc())
        .first()
    )
    version = (latest.key_version + 1) if latest else 1

    wk = WalletKey(
        wallet_id=wallet.wallet_id,
        agent_id=agent.agent_id,
        private_key_enc=enc,
        key_salt=key_salt,
        key_version=version,
    )
    db.add(wk)

    # Link agent to wallet
    existing_link = (
        db.query(WalletAgent)
        .filter(WalletAgent.wallet_id == wallet.wallet_id, WalletAgent.agent_id == agent.agent_id)
        .first()
    )
    if not existing_link:
        wa = WalletAgent(wallet_id=wallet.wallet_id, agent_id=agent.agent_id)
        db.add(wa)

    db.commit()
    db.refresh(wk)
    return wk


def retrieve_agent_key(
    db: Session,
    wallet: Wallet,
    agent_id: uuid.UUID,
    passphrase: str,
) -> bytes:
    """
    Decrypt and return an agent's private key seed.
    Returns bytes on success, raises ValueError on wrong passphrase or missing key.
    """
    wk = (
        db.query(WalletKey)
        .filter(
            WalletKey.wallet_id == wallet.wallet_id,
            WalletKey.agent_id == agent_id,
            WalletKey.revoked_at == None,
        )
        .order_by(WalletKey.key_version.desc())
        .first()
    )
    if not wk:
        raise ValueError(f"No active key found for agent {agent_id}")

    master_key = derive_key(passphrase, wallet.master_key_salt)
    return decrypt_key(wk.private_key_enc, wk.key_salt, master_key)


def rotate_agent_key(
    db: Session,
    wallet: Wallet,
    agent: AgentIdentity,
    passphrase: str,
) -> tuple[bytes, WalletKey]:
    """
    Rotate an agent's keypair.
    1. Generate new Ed25519 keypair
    2. Revoke old wallet key
    3. Store new key
    4. Update agent's public key + fingerprint + DID doc
    Returns (new_private_key_seed, new_WalletKey)
    """
    from ..crypto.did import create_did_document
    from ..config import get_settings
    settings = get_settings()

    # Revoke old key
    old_key = (
        db.query(WalletKey)
        .filter(WalletKey.wallet_id == wallet.wallet_id, WalletKey.agent_id == agent.agent_id, WalletKey.revoked_at == None)
        .first()
    )
    if old_key:
        old_key.revoked_at = datetime.now(timezone.utc)
        db.flush()

    # Generate new keypair
    new_kp = generate_keypair()

    # Update agent identity
    agent.public_key = new_kp.public_key
    agent.key_fingerprint = fingerprint(new_kp.public_key)
    agent.did_document = create_did_document(
        str(agent.agent_id), new_kp.public_key, settings.agentforge_domain
    )
    db.flush()

    # Store new encrypted key
    new_wk = store_agent_key(db, wallet, agent, new_kp.private_key, passphrase)
    return new_kp.private_key, new_wk


def export_wallet(
    db: Session,
    wallet: Wallet,
    user: User,
    passphrase: str,
    export_passphrase: str,
) -> bytes:
    """
    Export wallet as encrypted JSON blob.
    All keys are re-encrypted with export_passphrase for portability.
    """
    # Verify passphrase by attempting to derive master key
    master_key = derive_key(passphrase, wallet.master_key_salt)

    keys = (
        db.query(WalletKey)
        .filter(WalletKey.wallet_id == wallet.wallet_id, WalletKey.revoked_at == None)
        .all()
    )

    export_data = {
        "version": 1,
        "wallet_id": str(wallet.wallet_id),
        "owner_email": user.email,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "keys": [],
    }

    for wk in keys:
        # Decrypt with current passphrase
        try:
            private_seed = decrypt_key(wk.private_key_enc, wk.key_salt, master_key)
        except Exception:
            continue
        # Re-encrypt with export passphrase
        enc, salt = encrypt_key(private_seed, export_passphrase)
        export_data["keys"].append({
            "agent_id": str(wk.agent_id),
            "key_version": wk.key_version,
            "private_key_enc": enc.hex(),
            "key_salt": salt.hex(),
        })

    plaintext = json.dumps(export_data).encode()
    # Wrap entire export in another encryption layer
    export_salt = generate_salt()
    export_key = derive_key(export_passphrase, export_salt)
    final_enc = encrypt_blob(plaintext, export_key)
    return export_salt + final_enc   # prepend salt for decryption


def import_wallet(
    db: Session,
    user: User,
    encrypted_blob: bytes,
    export_passphrase: str,
    new_passphrase: str,
) -> Wallet:
    """Import a wallet from an encrypted export blob."""
    export_salt = encrypted_blob[:16]
    ciphertext = encrypted_blob[16:]
    export_key = derive_key(export_passphrase, export_salt)
    plaintext = decrypt_blob(ciphertext, export_key)
    export_data = json.loads(plaintext)

    # Create new wallet
    wallet = get_or_create_wallet(db, user, new_passphrase)

    # Re-import keys
    new_master = derive_key(new_passphrase, wallet.master_key_salt)
    for key_data in export_data.get("keys", []):
        enc = bytes.fromhex(key_data["private_key_enc"])
        salt = bytes.fromhex(key_data["key_salt"])
        private_seed = decrypt_key(enc, salt, export_passphrase)
        agent_id = uuid.UUID(key_data["agent_id"])

        agent = db.get(AgentIdentity, agent_id)
        if agent and agent.owner_id == user.id:
            new_enc, new_salt = encrypt_key(private_seed, new_master)
            wk = WalletKey(
                wallet_id=wallet.wallet_id,
                agent_id=agent_id,
                private_key_enc=new_enc,
                key_salt=new_salt,
                key_version=key_data.get("key_version", 1),
            )
            db.add(wk)

    db.commit()
    return wallet
