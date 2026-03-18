import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel, field_validator


class AgentCreate(BaseModel):
    display_name: str
    agent_type: str = "assistant"
    model_version: str = ""
    purpose: str = ""
    capabilities: list[str] = []
    preferred_runtime: str = "nim"
    is_public: bool = False

    @field_validator("display_name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("display_name cannot be empty")
        if len(v) > 255:
            raise ValueError("display_name too long (max 255 chars)")
        return v

    @field_validator("agent_type")
    @classmethod
    def valid_type(cls, v: str) -> str:
        allowed = {"assistant", "worker", "researcher", "analyst", "coder", "custom"}
        if v not in allowed:
            raise ValueError(f"agent_type must be one of {allowed}")
        return v


class AgentOut(BaseModel):
    model_config = {"from_attributes": True}

    agent_id: uuid.UUID
    owner_id: uuid.UUID
    did_uri: str
    display_name: str
    agent_type: str
    model_version: str
    purpose: str
    capabilities: list[Any]
    key_fingerprint: str
    key_algorithm: str
    is_active: bool
    is_public: bool
    preferred_runtime: str
    created_at: datetime


class AgentDetail(AgentOut):
    did_document: dict
    verifiable_credential: dict
    behavioral_signature: dict
    routing_config: dict


class VerifyRequest(BaseModel):
    challenge: str   # hex-encoded bytes to sign


class VerifyResponse(BaseModel):
    agent_id: uuid.UUID
    did_uri: str
    challenge: str
    signature: str    # hex-encoded signature
    public_key: str   # hex-encoded public key
    verified: bool
