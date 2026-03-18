"""
Wallet endpoints — encrypted key storage and management.

POST /api/v1/wallet/                   — Create/get wallet
GET  /api/v1/wallet/                   — Wallet info + agent list
POST /api/v1/wallet/keys/store         — Store agent private key (after birth)
POST /api/v1/wallet/keys/retrieve      — Decrypt and return private key
POST /api/v1/wallet/keys/rotate/{id}   — Rotate agent keypair
POST /api/v1/wallet/export             — Encrypted export
POST /api/v1/wallet/import             — Import from encrypted blob
"""

import uuid
from fastapi import APIRouter, HTTPException, status
from ..deps import CurrentUser, DbDep
from ..schemas.wallet import (
    WalletCreate, WalletOut, StoreKeyRequest, RetrieveKeyRequest,
    RetrieveKeyResponse, RotateKeyRequest, RotateKeyResponse,
    ExportRequest, ImportRequest, WalletKeyOut
)
from ..services.wallet import (
    get_or_create_wallet, store_agent_key, retrieve_agent_key,
    rotate_agent_key, export_wallet, import_wallet
)
from ..services.identity import get_agent
from ..models.wallet import WalletKey

router = APIRouter(prefix="/api/v1/wallet", tags=["wallet"])


@router.post("/", response_model=WalletOut, status_code=status.HTTP_201_CREATED)
def create_wallet(body: WalletCreate, current_user: CurrentUser, db: DbDep):
    wallet = get_or_create_wallet(db, current_user, body.passphrase)
    return WalletOut.model_validate(wallet)


@router.get("/", response_model=dict)
def get_wallet(current_user: CurrentUser, db: DbDep) -> dict:
    from ..models.wallet import Wallet
    wallet = db.query(Wallet).filter_by(owner_id=current_user.id).first()
    if not wallet:
        raise HTTPException(status_code=404, detail="No wallet found. POST /api/v1/wallet/ to create.")
    keys = db.query(WalletKey).filter_by(wallet_id=wallet.wallet_id).all()
    return {
        "wallet_id": str(wallet.wallet_id),
        "owner_id": str(wallet.owner_id),
        "created_at": wallet.created_at.isoformat(),
        "key_count": len([k for k in keys if k.revoked_at is None]),
        "revoked_key_count": len([k for k in keys if k.revoked_at is not None]),
        "keys": [
            {
                "key_id": str(k.key_id),
                "agent_id": str(k.agent_id),
                "key_version": k.key_version,
                "created_at": k.created_at.isoformat(),
                "revoked_at": k.revoked_at.isoformat() if k.revoked_at else None,
            }
            for k in keys
        ],
    }


@router.post("/keys/store", response_model=WalletKeyOut, status_code=status.HTTP_201_CREATED)
def store_key(body: StoreKeyRequest, current_user: CurrentUser, db: DbDep):
    from ..models.wallet import Wallet
    wallet = db.query(Wallet).filter_by(owner_id=current_user.id).first()
    if not wallet:
        raise HTTPException(status_code=404, detail="Create wallet first")
    agent = get_agent(db, body.agent_id, current_user)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    try:
        private_seed = bytes.fromhex(body.private_key_hex)
        if len(private_seed) != 32:
            raise ValueError("Private key must be 32 bytes (64 hex chars)")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    wk = store_agent_key(db, wallet, agent, private_seed, body.passphrase)
    return WalletKeyOut.model_validate(wk)


@router.post("/keys/retrieve", response_model=RetrieveKeyResponse)
def retrieve_key(body: RetrieveKeyRequest, current_user: CurrentUser, db: DbDep):
    from ..models.wallet import Wallet
    wallet = db.query(Wallet).filter_by(owner_id=current_user.id).first()
    if not wallet:
        raise HTTPException(status_code=404, detail="No wallet found")
    try:
        private_seed = retrieve_agent_key(db, wallet, body.agent_id, body.passphrase)
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

    # Get version
    wk = (
        db.query(WalletKey)
        .filter_by(wallet_id=wallet.wallet_id, agent_id=body.agent_id)
        .order_by(WalletKey.key_version.desc())
        .first()
    )
    return RetrieveKeyResponse(
        agent_id=body.agent_id,
        private_key_hex=private_seed.hex(),
        key_version=wk.key_version if wk else 1,
    )


@router.post("/keys/rotate/{agent_id}", response_model=RotateKeyResponse)
def rotate_key(agent_id: uuid.UUID, body: RotateKeyRequest, current_user: CurrentUser, db: DbDep):
    from ..models.wallet import Wallet
    from ..crypto.ed25519 import fingerprint as fp_fn
    wallet = db.query(Wallet).filter_by(owner_id=current_user.id).first()
    if not wallet:
        raise HTTPException(status_code=404, detail="No wallet found")
    agent = get_agent(db, agent_id, current_user)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    new_seed, new_wk = rotate_agent_key(db, wallet, agent, body.passphrase)
    return RotateKeyResponse(
        agent_id=agent_id,
        new_private_key_hex=new_seed.hex(),
        key_version=new_wk.key_version,
        new_fingerprint=fp_fn(agent.public_key),
    )


@router.post("/export")
def export_wallet_endpoint(body: ExportRequest, current_user: CurrentUser, db: DbDep) -> dict:
    from ..models.wallet import Wallet
    wallet = db.query(Wallet).filter_by(owner_id=current_user.id).first()
    if not wallet:
        raise HTTPException(status_code=404, detail="No wallet found")
    blob = export_wallet(db, wallet, current_user, body.passphrase, body.export_passphrase)
    return {"encrypted_blob_hex": blob.hex()}


@router.post("/import", response_model=WalletOut)
def import_wallet_endpoint(body: ImportRequest, current_user: CurrentUser, db: DbDep):
    try:
        blob = bytes.fromhex(body.encrypted_blob_hex)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid hex blob")
    try:
        wallet = import_wallet(db, current_user, blob, body.export_passphrase, body.new_passphrase)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Import failed: {e}")
    return WalletOut.model_validate(wallet)
