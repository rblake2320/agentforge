"""
Runtime Manager — unified interface for agent chat across NIM, Ollama, and 21st.dev.

Priority order: NIM (self-hosted RTX 5090) → Ollama (local fallback) → 21st.dev (cloud)
All runtimes produce the same output format, feeding into the signing/tamper pipeline.

Data Flywheel integration: every prompt/response pair is logged for continuous improvement.
LLM Router: intent classification routes to the optimal model tier.
"""

import httpx
import json
import time
import uuid
from datetime import datetime, timezone
from typing import AsyncIterator
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models.agent_identity import AgentIdentity

settings = get_settings()


class ChatMessage:
    def __init__(self, role: str, content: str):
        self.role = role
        self.content = content

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content}


class ChatResponse:
    def __init__(
        self,
        content: str,
        model: str,
        runtime: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        latency_ms: float = 0,
    ):
        self.content = content
        self.model = model
        self.runtime = runtime
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.latency_ms = latency_ms


# ── NIM Runtime ────────────────────────────────────────────────────────────────

async def _chat_nim(
    messages: list[dict],
    model: str | None = None,
    system_prompt: str | None = None,
) -> ChatResponse:
    """Call self-hosted NVIDIA NIM (OpenAI-compatible API on localhost:8000)."""
    model_name = model or settings.nim_model_name
    all_messages = []
    if system_prompt:
        all_messages.append({"role": "system", "content": system_prompt})
    all_messages.extend(messages)

    start = time.time()
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{settings.nim_base_url}/v1/chat/completions",
            json={
                "model": model_name,
                "messages": all_messages,
                "temperature": 0.7,
                "max_tokens": 2048,
            },
            headers={"Authorization": f"Bearer {settings.ngc_api_key}"} if settings.ngc_api_key else {},
        )
        resp.raise_for_status()

    latency = (time.time() - start) * 1000
    data = resp.json()
    choice = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})
    return ChatResponse(
        content=choice,
        model=data.get("model", model_name),
        runtime="nim",
        prompt_tokens=usage.get("prompt_tokens", 0),
        completion_tokens=usage.get("completion_tokens", 0),
        latency_ms=latency,
    )


# ── Ollama Runtime ─────────────────────────────────────────────────────────────

async def _chat_ollama(
    messages: list[dict],
    model: str = "gemma3:latest",
    system_prompt: str | None = None,
) -> ChatResponse:
    """Call local Ollama (fallback runtime)."""
    all_messages = []
    if system_prompt:
        all_messages.append({"role": "system", "content": system_prompt})
    all_messages.extend(messages)

    start = time.time()
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            "http://localhost:11434/api/chat",
            json={
                "model": model,
                "messages": all_messages,
                "stream": False,
            },
        )
        resp.raise_for_status()

    latency = (time.time() - start) * 1000
    data = resp.json()
    content = data.get("message", {}).get("content", "")
    return ChatResponse(
        content=content,
        model=model,
        runtime="ollama",
        latency_ms=latency,
    )


# ── Intent Classification (LLM Router) ────────────────────────────────────────

def _classify_intent(message: str) -> str:
    """
    Simple keyword-based intent classifier.
    Phase 3+ replaces with actual NVIDIA LLM Router (intent classification model).
    Returns: "complex" | "simple" | "code" | "multimodal"
    """
    msg_lower = message.lower()

    code_keywords = ["code", "function", "debug", "implement", "write", "program", "script", "algorithm"]
    complex_keywords = ["analyze", "research", "explain", "compare", "strategy", "design", "architecture"]
    simple_keywords = ["hello", "hi", "thanks", "yes", "no", "ok", "what is", "define", "when"]

    if any(k in msg_lower for k in code_keywords):
        return "code"
    if any(k in msg_lower for k in complex_keywords):
        return "complex"
    if any(k in msg_lower for k in simple_keywords):
        return "simple"
    return "complex"   # default to complex for safety


def _select_model_for_intent(intent: str, agent: AgentIdentity) -> tuple[str, str]:
    """
    Select runtime + model based on intent and agent preferences.
    Returns (runtime, model_name)
    """
    preferred = agent.routing_config.get("preferred_runtime", agent.preferred_runtime)

    if preferred == "nim":
        if intent in ("complex", "code"):
            return "nim", agent.routing_config.get("nim_large_model", settings.nim_model_name)
        else:
            return "nim", agent.routing_config.get("nim_small_model", "qwen2.5-7b")
    elif preferred == "ollama":
        if intent == "code":
            return "ollama", "deepseek-r1:32b"
        return "ollama", "gemma3:latest"
    else:
        return "ollama", "gemma3:latest"


# ── Data Flywheel Logging ─────────────────────────────────────────────────────

def _log_for_flywheel(
    agent_id: uuid.UUID,
    messages: list[dict],
    response: ChatResponse,
    intent: str,
):
    """
    Log prompt/response pairs for Data Flywheel analysis.
    Phase 3: Wire to NVIDIA Data Flywheel pipeline (background task).
    For now, logs to a JSONL file for later ingestion.
    """
    import os
    log_path = f"D:/agentvault/flywheel_logs/{agent_id}.jsonl"
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "agent_id": str(agent_id),
        "intent": intent,
        "model": response.model,
        "runtime": response.runtime,
        "latency_ms": response.latency_ms,
        "prompt_tokens": response.prompt_tokens,
        "completion_tokens": response.completion_tokens,
        "messages": messages,
        "response": response.content,
    }
    with open(log_path, "a") as f:
        f.write(json.dumps(entry) + "\n")


# ── Main Interface ─────────────────────────────────────────────────────────────

async def chat(
    agent: AgentIdentity,
    messages: list[dict],
    system_prompt: str | None = None,
    runtime_override: str | None = None,
) -> ChatResponse:
    """
    Primary chat interface. Auto-routes to optimal runtime via LLM Router.
    Falls back through: NIM → Ollama → error.

    Args:
        agent: AgentIdentity with preferred_runtime + routing_config
        messages: List of {"role": ..., "content": ...} dicts
        system_prompt: Optional system prompt prepended to messages
        runtime_override: Force a specific runtime ("nim"|"ollama"|"21st")

    Returns:
        ChatResponse with content, model, runtime, latency
    """
    # Inject agent identity into system prompt
    agent_identity_prefix = (
        f"You are {agent.display_name}, a {agent.agent_type} agent. "
        f"Your purpose: {agent.purpose}. "
        f"Your capabilities: {', '.join(agent.capabilities) if agent.capabilities else 'general'}. "
        f"Your DID: {agent.did_uri}."
    )
    full_system = (
        f"{agent_identity_prefix}\n\n{system_prompt}" if system_prompt else agent_identity_prefix
    )

    # Classify intent for routing
    last_user_message = next(
        (m["content"] for m in reversed(messages) if m.get("role") == "user"), ""
    )
    intent = _classify_intent(last_user_message)
    runtime, model = _select_model_for_intent(intent, agent)
    if runtime_override:
        runtime = runtime_override

    # Try runtimes in priority order
    errors = []
    for attempt_runtime in _get_fallback_chain(runtime):
        try:
            if attempt_runtime == "nim":
                response = await _chat_nim(messages, model=model, system_prompt=full_system)
            elif attempt_runtime == "ollama":
                ollama_model = "gemma3:latest" if intent == "simple" else "deepseek-r1:32b"
                response = await _chat_ollama(messages, model=ollama_model, system_prompt=full_system)
            else:
                continue

            # Log for Data Flywheel
            _log_for_flywheel(agent.agent_id, messages, response, intent)
            return response

        except Exception as e:
            errors.append(f"{attempt_runtime}: {e}")
            continue

    raise RuntimeError(f"All runtimes failed. Errors: {'; '.join(errors)}")


def _get_fallback_chain(primary: str) -> list[str]:
    """Return runtime fallback order starting from primary."""
    order = ["nim", "ollama"]
    if primary in order:
        idx = order.index(primary)
        return order[idx:] + order[:idx]
    return order
