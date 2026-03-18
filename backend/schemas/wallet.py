import uuid
from datetime import datetime
from pydantic import BaseModel


class WalletCreate(BaseModel):
    passphrase: str


class WalletOut(BaseModel):
    model_config = {"from_attributes": True}
    wallet_id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime


class WalletKeyOut(BaseModel):
    model_config = {"from_attributes": True}
    key_id: uuid.UUID
    agent_id: uuid.UUID
    key_version: int
    created_at: datetime
    revoked_at: datetime | None = None


class StoreKeyRequest(BaseModel):
    agent_id: uuid.UUID
    private_key_hex: str   # 32 bytes hex (from birth)
    passphrase: str


class RetrieveKeyRequest(BaseModel):
    agent_id: uuid.UUID
    passphrase: str


class RetrieveKeyResponse(BaseModel):
    agent_id: uuid.UUID
    private_key_hex: str
    key_version: int
    warning: str = "Keep this key secure. Do not share."


class RotateKeyRequest(BaseModel):
    agent_id: uuid.UUID
    passphrase: str


class RotateKeyResponse(BaseModel):
    agent_id: uuid.UUID
    new_private_key_hex: str
    key_version: int
    new_fingerprint: str
    warning: str = "New private key generated. Store securely. Old key revoked."


class ExportRequest(BaseModel):
    passphrase: str
    export_passphrase: str


class ImportRequest(BaseModel):
    encrypted_blob_hex: str
    export_passphrase: str
    new_passphrase: str
