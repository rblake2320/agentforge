import uuid
from datetime import datetime
from pydantic import BaseModel


class SignMessageRequest(BaseModel):
    session_id: uuid.UUID
    message: str           # base64 or plaintext message to sign
    private_key_hex: str   # agent's private key (client-held)


class SignMessageResponse(BaseModel):
    sig_id: uuid.UUID
    message_hash: str
    signature: str
    sequence_num: int
    prev_hash: str | None


class VerifyMessageRequest(BaseModel):
    sig_id: uuid.UUID


class ChainEntry(BaseModel):
    sig_id: str
    sequence_num: int
    message_hash: str
    prev_hash: str | None
    signature: str
    created_at: str


class ChainVerifyResult(BaseModel):
    all_valid: bool
    entry_count: int
    entries: list[dict]


class HeartbeatChallengeResponse(BaseModel):
    heartbeat_id: uuid.UUID
    agent_id: uuid.UUID
    challenge: str    # hex bytes for agent to sign
    created_at: datetime


class HeartbeatSubmitRequest(BaseModel):
    heartbeat_id: uuid.UUID
    response_signature: str   # hex signature of challenge


class HeartbeatSubmitResponse(BaseModel):
    heartbeat_id: uuid.UUID
    verified: bool
    status: str


class KillSwitchRequest(BaseModel):
    reason: str


class KillSwitchResponse(BaseModel):
    event_id: uuid.UUID
    agent_id: uuid.UUID
    reason: str
    executed_at: datetime


class StartSessionResponse(BaseModel):
    session_id: uuid.UUID
    agent_id: uuid.UUID
    started_at: datetime
