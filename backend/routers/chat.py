"""
Agent chat endpoints — multi-runtime with identity injection and tamper signing.

POST /api/v1/chat/{agent_id}   — Chat with agent (auto-routes to optimal runtime)
GET  /api/v1/chat/{agent_id}/history/{session_id} — Session history
"""

import uuid
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from ..deps import CurrentUser, DbDep
from ..services.identity import get_agent
from ..services.tamper import start_session, sign_message_entry
from ..services.runtime_manager import chat
from ..models.agent_identity import AgentSession

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


class ChatRequest(BaseModel):
    messages: list[dict]        # [{"role": "user", "content": "..."}]
    session_id: uuid.UUID | None = None
    system_prompt: str | None = None
    runtime: str | None = None  # "nim" | "ollama" | None (auto)
    private_key_hex: str | None = None   # For tamper signing (optional)


class ChatResponseOut(BaseModel):
    content: str
    model: str
    runtime: str
    session_id: uuid.UUID
    sig_id: uuid.UUID | None = None
    latency_ms: float


@router.post("/{agent_id}", response_model=ChatResponseOut)
async def chat_with_agent(agent_id: uuid.UUID, body: ChatRequest, current_user: CurrentUser, db: DbDep):
    agent = get_agent(db, agent_id, current_user)
    if not agent or not agent.is_active:
        raise HTTPException(404, "Agent not found or inactive")

    # Get or create session
    if body.session_id:
        session = db.get(AgentSession, body.session_id)
        if not session or session.agent_id != agent_id:
            raise HTTPException(404, "Session not found")
    else:
        session = start_session(db, agent)

    # Run agent
    try:
        response = await chat(
            agent=agent,
            messages=body.messages,
            system_prompt=body.system_prompt,
            runtime_override=body.runtime,
        )
    except RuntimeError as e:
        raise HTTPException(503, f"All runtimes unavailable: {e}")

    # Sign response for tamper chain (if private key provided)
    sig_id = None
    if body.private_key_hex:
        try:
            private_seed = bytes.fromhex(body.private_key_hex)
            if len(private_seed) == 32:
                entry = sign_message_entry(
                    db, agent, session, response.content.encode(), private_seed
                )
                sig_id = entry.sig_id
        except Exception:
            pass   # Signing failure doesn't break chat

    return ChatResponseOut(
        content=response.content,
        model=response.model,
        runtime=response.runtime,
        session_id=session.session_id,
        sig_id=sig_id,
        latency_ms=response.latency_ms,
    )


@router.get("/{agent_id}/sessions")
def list_sessions(agent_id: uuid.UUID, current_user: CurrentUser, db: DbDep) -> list[dict]:
    agent = get_agent(db, agent_id, current_user)
    if not agent:
        raise HTTPException(404, "Agent not found")
    sessions = (
        db.query(AgentSession)
        .filter(AgentSession.agent_id == agent_id)
        .order_by(AgentSession.started_at.desc())
        .limit(50)
        .all()
    )
    return [
        {
            "session_id": str(s.session_id),
            "started_at": s.started_at.isoformat(),
            "ended_at": s.ended_at.isoformat() if s.ended_at else None,
            "interaction_count": s.interaction_count,
            "merkle_root": s.merkle_root,
        }
        for s in sessions
    ]
