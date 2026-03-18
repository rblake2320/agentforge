"""
Tamper detection endpoints.

POST /api/v1/tamper/sessions/start             — Start tracked session
POST /api/v1/tamper/sessions/{id}/end          — End session + final Merkle root
POST /api/v1/tamper/sign                       — Sign a message (chain entry)
GET  /api/v1/tamper/{agent_id}/chain/{session} — Get full chain
POST /api/v1/tamper/{agent_id}/verify-chain/{session} — Verify chain integrity
POST /api/v1/tamper/heartbeat/{agent_id}       — Issue server challenge
POST /api/v1/tamper/heartbeat/respond          — Submit challenge response
POST /api/v1/tamper/kill-switch/{agent_id}     — Trigger kill switch
GET  /api/v1/tamper/{agent_id}/status          — Heartbeat + tamper status
"""

import uuid
from fastapi import APIRouter, HTTPException, status
from ..deps import CurrentUser, DbDep
from ..schemas.tamper import (
    SignMessageRequest, SignMessageResponse, VerifyMessageRequest,
    ChainVerifyResult, HeartbeatChallengeResponse, HeartbeatSubmitRequest,
    HeartbeatSubmitResponse, KillSwitchRequest, KillSwitchResponse,
    StartSessionResponse,
)
from ..services.identity import get_agent
from ..services.tamper import (
    start_session, end_session, sign_message_entry, verify_message_entry,
    get_session_chain, verify_full_chain, issue_challenge,
    submit_challenge_response, trigger_kill_switch, get_heartbeat_status,
)
from ..models.agent_identity import AgentSession
from ..models.tamper import Heartbeat

router = APIRouter(prefix="/api/v1/tamper", tags=["tamper"])


@router.post("/sessions/start", response_model=StartSessionResponse, status_code=201)
def start_tracked_session(agent_id: uuid.UUID, current_user: CurrentUser, db: DbDep):
    agent = get_agent(db, agent_id, current_user)
    if not agent:
        raise HTTPException(404, "Agent not found")
    session = start_session(db, agent)
    return StartSessionResponse(
        session_id=session.session_id,
        agent_id=agent.agent_id,
        started_at=session.started_at,
    )


@router.post("/sessions/{session_id}/end")
def end_tracked_session(session_id: uuid.UUID, current_user: CurrentUser, db: DbDep) -> dict:
    session = db.get(AgentSession, session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    agent = get_agent(db, session.agent_id, current_user)
    if not agent:
        raise HTTPException(403, "Not authorized")
    session = end_session(db, session)
    return {
        "session_id": str(session.session_id),
        "interaction_count": session.interaction_count,
        "merkle_root": session.merkle_root,
        "ended_at": session.ended_at.isoformat() if session.ended_at else None,
    }


@router.post("/sign", response_model=SignMessageResponse)
def sign_msg(body: SignMessageRequest, current_user: CurrentUser, db: DbDep):
    session = db.get(AgentSession, body.session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    agent = get_agent(db, session.agent_id, current_user)
    if not agent:
        raise HTTPException(403, "Not authorized")
    try:
        private_seed = bytes.fromhex(body.private_key_hex)
        if len(private_seed) != 32:
            raise ValueError()
    except (ValueError, AttributeError):
        raise HTTPException(422, "private_key_hex must be 64 hex characters (32 bytes)")
    message_bytes = body.message.encode()
    entry = sign_message_entry(db, agent, session, message_bytes, private_seed)
    return SignMessageResponse(
        sig_id=entry.sig_id,
        message_hash=entry.message_hash,
        signature=entry.signature.hex(),
        sequence_num=entry.sequence_num,
        prev_hash=entry.prev_hash,
    )


@router.get("/{agent_id}/chain/{session_id}", response_model=list[dict])
def get_chain(agent_id: uuid.UUID, session_id: uuid.UUID, current_user: CurrentUser, db: DbDep):
    agent = get_agent(db, agent_id, current_user)
    if not agent:
        raise HTTPException(404, "Agent not found")
    return get_session_chain(db, agent_id, session_id)


@router.post("/{agent_id}/verify-chain/{session_id}", response_model=ChainVerifyResult)
def verify_chain(agent_id: uuid.UUID, session_id: uuid.UUID, current_user: CurrentUser, db: DbDep):
    agent = get_agent(db, agent_id, current_user)
    if not agent:
        raise HTTPException(404, "Agent not found")
    return ChainVerifyResult(**verify_full_chain(db, agent, session_id))


@router.post("/heartbeat/{agent_id}", response_model=HeartbeatChallengeResponse)
def issue_heartbeat_challenge(agent_id: uuid.UUID, current_user: CurrentUser, db: DbDep):
    """Server issues a random challenge. Agent must sign it and submit back."""
    agent = get_agent(db, agent_id, current_user)
    if not agent or not agent.is_active:
        raise HTTPException(404, "Agent not found or inactive")
    hb = issue_challenge(db, agent)
    return HeartbeatChallengeResponse(
        heartbeat_id=hb.heartbeat_id,
        agent_id=hb.agent_id,
        challenge=hb.challenge,
        created_at=hb.created_at,
    )


@router.post("/heartbeat/respond", response_model=HeartbeatSubmitResponse)
def respond_to_heartbeat(body: HeartbeatSubmitRequest, current_user: CurrentUser, db: DbDep):
    """Agent submits its signature of the server challenge."""
    hb = db.get(Heartbeat, body.heartbeat_id)
    if not hb:
        raise HTTPException(404, "Heartbeat not found")
    agent = get_agent(db, hb.agent_id, current_user)
    if not agent:
        raise HTTPException(403, "Not authorized")
    verified = submit_challenge_response(db, hb, agent, body.response_signature)
    return HeartbeatSubmitResponse(
        heartbeat_id=hb.heartbeat_id,
        verified=verified,
        status=hb.status.value,
    )


@router.post("/kill-switch/{agent_id}", response_model=KillSwitchResponse)
def kill_agent(agent_id: uuid.UUID, body: KillSwitchRequest, current_user: CurrentUser, db: DbDep):
    agent = get_agent(db, agent_id, current_user)
    if not agent:
        raise HTTPException(404, "Agent not found")
    event = trigger_kill_switch(db, agent, current_user, body.reason)
    return KillSwitchResponse(
        event_id=event.event_id,
        agent_id=event.agent_id,
        reason=event.reason,
        executed_at=event.executed_at,
    )


@router.get("/{agent_id}/status")
def agent_tamper_status(agent_id: uuid.UUID, current_user: CurrentUser, db: DbDep) -> dict:
    agent = get_agent(db, agent_id, current_user)
    if not agent:
        raise HTTPException(404, "Agent not found")
    hb_status = get_heartbeat_status(db, agent_id)
    return {
        "agent_id": str(agent_id),
        "is_active": agent.is_active,
        "heartbeat": hb_status,
        "key_fingerprint": agent.key_fingerprint,
    }
