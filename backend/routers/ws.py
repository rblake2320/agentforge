"""
WebSocket endpoints for real-time agent communication.

WS /ws/heartbeat/{agent_id} — Bidirectional signed heartbeat
  Server sends: {"type": "challenge", "challenge": "<hex>", "heartbeat_id": "<uuid>"}
  Client sends: {"type": "response", "heartbeat_id": "<uuid>", "signature": "<hex>"}
  Server sends: {"type": "ack", "verified": true/false, "status": "alive/missed"}
  Server sends: {"type": "kill", "reason": "<str>"} when agent is killed

Heartbeat cycle: 30 seconds
"""

import json
import uuid
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..services.identity import get_agent
from ..services.tamper import issue_challenge, submit_challenge_response
from ..models.tamper import Heartbeat

router = APIRouter(tags=["websocket"])

# Active WebSocket connections: agent_id -> WebSocket
_connections: dict[str, WebSocket] = {}


@router.websocket("/ws/heartbeat/{agent_id}")
async def heartbeat_ws(
    websocket: WebSocket,
    agent_id: uuid.UUID,
    token: str = Query(...),
):
    """
    Bidirectional heartbeat WebSocket.
    Auth: pass JWT as ?token= query param.
    """
    import jwt as pyjwt
    from ..config import get_settings
    settings = get_settings()

    # Verify JWT
    try:
        payload = pyjwt.decode(
            token,
            settings.jwt_public_key,
            algorithms=["EdDSA"],
            options={"require": ["sub", "exp", "jti"]},
        )
        user_id = uuid.UUID(payload["sub"])
    except Exception:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await websocket.accept()
    _connections[str(agent_id)] = websocket

    db: Session = SessionLocal()
    try:
        # Verify agent ownership
        from ..models.user import User
        user = db.get(User, user_id)
        if not user:
            await websocket.close(code=4001, reason="User not found")
            return

        agent = get_agent(db, agent_id, user)
        if not agent or not agent.is_active:
            await websocket.send_text(json.dumps({"type": "error", "detail": "Agent not found or inactive"}))
            await websocket.close(code=4004, reason="Agent not found")
            return

        # Issue initial challenge
        hb = issue_challenge(db, agent)
        await websocket.send_text(json.dumps({
            "type": "challenge",
            "heartbeat_id": str(hb.heartbeat_id),
            "challenge": hb.challenge,
        }))

        while True:
            try:
                raw = await websocket.receive_text()
                msg = json.loads(raw)
            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({"type": "error", "detail": "Invalid JSON"}))
                continue

            if msg.get("type") == "response":
                hb_id = msg.get("heartbeat_id")
                sig_hex = msg.get("signature", "")
                hb = db.get(Heartbeat, uuid.UUID(hb_id)) if hb_id else None
                if not hb:
                    await websocket.send_text(json.dumps({"type": "error", "detail": "Heartbeat not found"}))
                    continue

                # Re-query agent to get fresh state
                db.refresh(agent)
                if not agent.is_active:
                    await websocket.send_text(json.dumps({
                        "type": "kill",
                        "reason": "Agent has been deactivated",
                    }))
                    break

                verified = submit_challenge_response(db, hb, agent, sig_hex)
                await websocket.send_text(json.dumps({
                    "type": "ack",
                    "heartbeat_id": hb_id,
                    "verified": verified,
                    "status": hb.status.value,
                }))

                # Issue next challenge after successful ack
                if verified:
                    new_hb = issue_challenge(db, agent)
                    await websocket.send_text(json.dumps({
                        "type": "challenge",
                        "heartbeat_id": str(new_hb.heartbeat_id),
                        "challenge": new_hb.challenge,
                    }))
            else:
                await websocket.send_text(json.dumps({"type": "error", "detail": "Unknown message type"}))

    except WebSocketDisconnect:
        pass
    finally:
        _connections.pop(str(agent_id), None)
        db.close()


async def broadcast_kill(agent_id: str, reason: str):
    """Broadcast kill signal to connected WebSocket for an agent."""
    ws = _connections.get(agent_id)
    if ws:
        try:
            await ws.send_text(json.dumps({"type": "kill", "reason": reason}))
            await ws.close(code=1000, reason="Kill switch triggered")
        except Exception:
            pass
        _connections.pop(agent_id, None)
