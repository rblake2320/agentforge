"""
Agent identity endpoints.

POST /api/v1/agents/           — Birth a new agent
GET  /api/v1/agents/           — List user's agents
GET  /api/v1/agents/{id}       — Agent detail (includes DID doc + VC)
GET  /api/v1/agents/{id}/certificate  — Public birth certificate (VC)
POST /api/v1/agents/{id}/verify       — Challenge-response verification
DELETE /api/v1/agents/{id}     — Deactivate agent
"""

import os
import uuid
from fastapi import APIRouter, HTTPException, status
from sqlalchemy.orm import Session

from ..deps import CurrentUser, DbDep
from ..schemas.agent import AgentCreate, AgentOut, AgentDetail, VerifyRequest, VerifyResponse
from ..services.identity import birth_agent, get_agent, list_agents, verify_agent_challenge, deactivate_agent

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])


@router.post("/", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_agent(body: AgentCreate, current_user: CurrentUser, db: DbDep) -> dict:
    """
    Birth a new agent. Returns agent info + private key (ONE TIME ONLY).
    The private key is not stored server-side — the client must encrypt + save it.
    """
    agent, private_key_seed = birth_agent(db, current_user, body)
    return {
        "agent": AgentOut.model_validate(agent).model_dump(),
        "private_key_hex": private_key_seed.hex(),
        "warning": "Store this private key securely. It will never be shown again.",
    }


@router.get("/", response_model=list[AgentOut])
def get_agents(current_user: CurrentUser, db: DbDep) -> list:
    return list_agents(db, current_user)


@router.get("/{agent_id}", response_model=AgentDetail)
def get_agent_detail(agent_id: uuid.UUID, current_user: CurrentUser, db: DbDep):
    agent = get_agent(db, agent_id, current_user)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return AgentDetail.model_validate(agent)


@router.get("/{agent_id}/certificate", response_model=dict)
def get_certificate(agent_id: uuid.UUID, current_user: CurrentUser, db: DbDep) -> dict:
    """Return the W3C Verifiable Credential (birth certificate) for an agent."""
    agent = get_agent(db, agent_id, current_user)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return agent.verifiable_credential


@router.post("/{agent_id}/verify", response_model=VerifyResponse)
def verify_agent(agent_id: uuid.UUID, body: VerifyRequest, current_user: CurrentUser, db: DbDep) -> dict:
    """
    Challenge-response identity verification.
    Client signs the challenge with the agent's private key and submits the signature.
    Server verifies with the stored public key.

    In a real flow: server issues a random challenge, client signs it.
    Here the client provides both challenge and signature for simplicity.
    """
    agent = get_agent(db, agent_id, current_user)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    # For Phase 1, client provides pre-signed challenge
    # Phase 2 will implement server-issued challenge nonces
    # We need both challenge + signature; use a simple JSON body extension
    # challenge is hex-encoded data to sign, but we need the signature too
    # For now, generate a server-side challenge and return it for the client to sign
    challenge_bytes = os.urandom(32)
    challenge_hex = challenge_bytes.hex()

    return {
        "agent_id": agent.agent_id,
        "did_uri": agent.did_uri,
        "challenge": challenge_hex,
        "signature": "",  # Client must sign this challenge and POST back
        "public_key": agent.public_key.hex(),
        "verified": False,  # Full verify flow in Phase 2
    }


@router.post("/{agent_id}/verify/submit", response_model=VerifyResponse)
def submit_verification(
    agent_id: uuid.UUID,
    body: VerifyRequest,
    current_user: CurrentUser,
    db: DbDep,
) -> dict:
    """Submit a signed challenge for verification."""
    from ..schemas.agent import VerifyResponse

    agent = get_agent(db, agent_id, current_user)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    # body.challenge should be the hex challenge issued by /verify
    # We need the signature too — extend VerifyRequest in Phase 2
    # For now, return structure
    verified = False
    signature_hex = ""

    return {
        "agent_id": agent.agent_id,
        "did_uri": agent.did_uri,
        "challenge": body.challenge,
        "signature": signature_hex,
        "public_key": agent.public_key.hex(),
        "verified": verified,
    }


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_agent(agent_id: uuid.UUID, current_user: CurrentUser, db: DbDep) -> None:
    agent = get_agent(db, agent_id, current_user)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    deactivate_agent(db, agent)
