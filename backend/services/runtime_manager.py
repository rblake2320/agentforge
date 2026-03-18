"""
Runtime Manager — unified interface for agent chat across NIM, Ollama, and 21st.dev.

Priority order: NIM (self-hosted RTX 5090) → Ollama (local fallback) → 21st.dev (cloud)
All runtimes produce the same output format, feeding into the signing/tamper pipeline.

Data Flywheel integration: every prompt/response pair is logged for continuous improvement.
LLM Router: intent classification routes to the optimal model tier.

NIM API notes (as of 2025/2026):
  - Fully OpenAI-compatible: POST /v1/chat/completions, GET /v1/models
  - Health check: GET /v1/health/ready  → 200 OK when ready
  - Auth header: "Authorization: Bearer <NGC_API_KEY>" (omit if no key configured)
  - Deployed via Docker with --runtime=nvidia; default port 8000
  - Recommended RTX 5090 (32GB) models:
      nvcr.io/nim/meta/llama-3.1-8b-instruct:latest        (~16GB BF16)
      nvcr.io/nim/deepseek-ai/deepseek-r1-distill-llama-8b:latest  (~16GB INT4 AWQ)
      nvcr.io/nim/meta/llama-3.2-3b-instruct:latest        (~8GB BF16)
  - Bring-your-own model: nvcr.io/nim/nvidia/llm-nim:latest + NIM_MODEL_NAME=hf://...
"""

import httpx
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import AsyncIterator
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models.agent_identity import AgentIdentity

settings = get_settings()
logger = logging.getLogger(__name__)

# NIM health-check timeout — short so fallback is fast when NIM is down
_NIM_HEALTH_TIMEOUT = 3.0
# NIM inference timeout — generous for first-token latency on large models
_NIM_INFERENCE_TIMEOUT = 120.0


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

def _nim_headers() -> dict:
    """Build NIM request headers. NGC_API_KEY is optional for local deployments."""
    if settings.ngc_api_key:
        return {"Authorization": f"Bearer {settings.ngc_api_key}"}
    return {}


async def nim_available() -> bool:
    """
    Health-check NIM via GET /v1/health/ready.

    Returns True only when NIM is reachable and fully loaded (model warm).
    Uses a short timeout so callers fall back to Ollama quickly when NIM is down.

    NIM returns HTTP 200 when ready, 503 while still loading the model.
    """
    try:
        async with httpx.AsyncClient(timeout=_NIM_HEALTH_TIMEOUT) as client:
            resp = await client.get(
                f"{settings.nim_base_url}/v1/health/ready",
                headers=_nim_headers(),
            )
            return resp.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPError):
        return False
    except Exception as exc:
        logger.debug("NIM health check failed with unexpected error: %s", exc)
        return False


async def nim_list_models() -> list[str]:
    """
    Query GET /v1/models and return the list of model IDs served by NIM.
    Returns an empty list if NIM is unavailable.
    """
    try:
        async with httpx.AsyncClient(timeout=_NIM_HEALTH_TIMEOUT) as client:
            resp = await client.get(
                f"{settings.nim_base_url}/v1/models",
                headers=_nim_headers(),
            )
            resp.raise_for_status()
            data = resp.json()
            return [m["id"] for m in data.get("data", [])]
    except Exception:
        return []


async def _chat_nim(
    messages: list[dict],
    model: str | None = None,
    system_prompt: str | None = None,
) -> ChatResponse:
    """
    Call self-hosted NVIDIA NIM (OpenAI-compatible API).

    NIM uses the standard OpenAI /v1/chat/completions format verbatim.
    The model name must match what NIM is serving — query nim_list_models()
    if you're unsure of the exact identifier (e.g. "meta/llama-3.1-8b-instruct").

    Raises:
        httpx.ConnectError: NIM container not running / wrong port.
        httpx.HTTPStatusError: NIM returned 4xx/5xx (e.g. 503 still loading).
        KeyError: Unexpected response shape (NIM API changed).
    """
    model_name = model or settings.nim_model_name
    all_messages = []
    if system_prompt:
        all_messages.append({"role": "system", "content": system_prompt})
    all_messages.extend(messages)

    start = time.time()
    try:
        async with httpx.AsyncClient(timeout=_NIM_INFERENCE_TIMEOUT) as client:
            resp = await client.post(
                f"{settings.nim_base_url}/v1/chat/completions",
                json={
                    "model": model_name,
                    "messages": all_messages,
                    "temperature": 0.7,
                    "max_tokens": 2048,
                },
                headers=_nim_headers(),
            )
            resp.raise_for_status()
    except httpx.ConnectError as exc:
        raise httpx.ConnectError(
            f"NIM not reachable at {settings.nim_base_url}. "
            "Is the Docker container running? See NVIDIA_SETUP.md."
        ) from exc
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        if status == 503:
            raise httpx.HTTPStatusError(
                f"NIM returned 503 — model is still loading. "
                f"Wait ~2 minutes after container start, then retry.",
                request=exc.request,
                response=exc.response,
            ) from exc
        if status == 401:
            raise httpx.HTTPStatusError(
                "NIM returned 401 — check NGC_API_KEY in .env.",
                request=exc.request,
                response=exc.response,
            ) from exc
        raise

    latency = (time.time() - start) * 1000
    data = resp.json()

    try:
        choice = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise KeyError(
            f"Unexpected NIM response shape — 'choices[0].message.content' missing. "
            f"Raw response: {json.dumps(data)[:300]}"
        ) from exc

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
#
# Phase 2 (current): keyword trie — zero latency, no extra GPU memory.
# Phase 3 upgrade: replace with NVIDIA LLM Router blueprint, which uses a
#   Qwen 1.7B classifier served at http://localhost:8001/sfc_router/chat/completions.
#   The response body's choices[0].message.content carries the target model name.
#   See: https://github.com/NVIDIA-AI-Blueprints/llm-router
#
# Intent categories and their model tier:
#   "chit_chat"   → small/fast model (Llama 3.2 3B, gemma3:latest)
#   "simple"      → small/fast model
#   "code"        → code-specialised model (deepseek-r1:32b, deepseek-r1-distill-llama-8b)
#   "complex"     → largest available model (llama-3.1-8b, qwen2.5-32b)
#   "reasoning"   → reasoning-optimised model (deepseek-r1 family)
#   "multimodal"  → vision-capable model (future; routed to complex for now)

def _classify_intent(message: str) -> str:
    """
    Keyword-based intent classifier aligned with NVIDIA LLM Router intent categories.

    Precedence (highest to lowest):
      code > reasoning > complex > simple/chit_chat

    Phase 3+ upgrade path: swap body for a call to the NIM LLM Router microservice
    (POST http://nim-router:8001/sfc_router/chat/completions) which runs Qwen 1.7B
    and returns the optimal model name directly.

    Returns: "code" | "reasoning" | "complex" | "simple" | "chit_chat"
    """
    msg_lower = message.lower()

    # Code generation / debugging — route to deepseek-r1 or code-specialised NIM
    _CODE = {
        "code", "function", "debug", "implement", "write a", "program", "script",
        "algorithm", "class", "method", "refactor", "unit test", "pytest", "unittest",
        "compile", "syntax", "import", "module", "library", "api", "endpoint",
        "sql", "query", "schema", "migration", "dockerfile", "yaml", "json",
        "regex", "parse", "serializ", "deserializ",
    }

    # Multi-step reasoning / math — route to reasoning-optimised model
    _REASONING = {
        "step by step", "think through", "reasoning", "proof", "derive", "calculate",
        "math", "equation", "solve", "theorem", "logic", "inference", "deduce",
        "chain of thought", "let's think",
    }

    # Complex analytical tasks — route to largest available model
    _COMPLEX = {
        "analyze", "analyse", "research", "explain", "compare", "contrast",
        "strategy", "design", "architecture", "plan", "evaluate", "assess",
        "summarize", "summarise", "review", "critique", "recommend", "suggest",
        "investigate", "diagnose", "forecast", "predict", "estimate",
        "write a report", "write a document", "draft", "outline",
    }

    # Chit-chat / greetings — route to smallest/fastest model
    _CHIT_CHAT = {
        "hello", "hi ", "hey ", "good morning", "good afternoon", "good evening",
        "how are you", "what's up", "thanks", "thank you", "cheers", "bye",
        "goodbye", "nice to meet",
    }

    # Simple factual lookups — also fast-path
    _SIMPLE = {
        "what is ", "what are ", "define ", "when did ", "who is ", "where is ",
        "how many ", "yes", "no", "ok", "sure", "correct", "wrong",
    }

    # Very short messages (≤8 chars) are almost certainly chit-chat
    if len(message.strip()) <= 8:
        return "chit_chat"

    if any(k in msg_lower for k in _CODE):
        return "code"
    if any(k in msg_lower for k in _REASONING):
        return "reasoning"
    if any(k in msg_lower for k in _COMPLEX):
        return "complex"
    if any(k in msg_lower for k in _CHIT_CHAT):
        return "chit_chat"
    if any(k in msg_lower for k in _SIMPLE):
        return "simple"

    # Default: treat unknown intent as complex so the best available model handles it
    return "complex"


def _select_model_for_intent(intent: str, agent: AgentIdentity) -> tuple[str, str]:
    """
    Select runtime + model based on intent classification and agent preferences.

    NIM model mapping (RTX 5090 / 32GB VRAM):
      complex / reasoning → nim_large_model (default: llama-3.1-8b-instruct, 16GB BF16)
      code                → nim_code_model  (default: deepseek-r1-distill-llama-8b, INT4 AWQ)
      simple / chit_chat  → nim_small_model (default: llama-3.2-3b-instruct, 8GB BF16)

    Ollama fallback model mapping:
      code / reasoning    → deepseek-r1:32b
      complex             → llama3.1:70b  (requires Spark-1 or sufficient local VRAM)
      simple / chit_chat  → gemma3:latest

    Returns (runtime, model_name)
    """
    preferred = agent.routing_config.get("preferred_runtime", agent.preferred_runtime)

    if preferred == "nim":
        if intent in ("complex", "reasoning"):
            model = agent.routing_config.get("nim_large_model", settings.nim_model_name)
        elif intent == "code":
            model = agent.routing_config.get(
                "nim_code_model",
                "deepseek-ai/deepseek-r1-distill-llama-8b",
            )
        else:  # simple, chit_chat, unknown
            model = agent.routing_config.get("nim_small_model", "meta/llama-3.2-3b-instruct")
        return "nim", model

    elif preferred == "ollama":
        if intent in ("code", "reasoning"):
            return "ollama", "deepseek-r1:32b"
        if intent == "complex":
            return "ollama", "llama3.1:70b"
        return "ollama", "gemma3:latest"

    # Unknown preferred runtime — safe default
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

    # Try runtimes in priority order, with a fast pre-flight check for NIM
    errors = []
    for attempt_runtime in _get_fallback_chain(runtime):
        try:
            if attempt_runtime == "nim":
                # Fast health check (3s timeout) before committing to a long inference call.
                # This avoids hanging for 120s when NIM is simply not running.
                if not await nim_available():
                    errors.append("nim: health check failed — container not ready (see NVIDIA_SETUP.md)")
                    logger.info("NIM unavailable, skipping to next runtime in fallback chain.")
                    continue
                response = await _chat_nim(messages, model=model, system_prompt=full_system)

            elif attempt_runtime == "ollama":
                if intent in ("code", "reasoning"):
                    ollama_model = "deepseek-r1:32b"
                elif intent == "complex":
                    ollama_model = "llama3.1:70b"
                else:
                    ollama_model = "gemma3:latest"
                response = await _chat_ollama(messages, model=ollama_model, system_prompt=full_system)

            else:
                continue

            # Log for Data Flywheel
            _log_for_flywheel(agent.agent_id, messages, response, intent)
            return response

        except Exception as e:
            errors.append(f"{attempt_runtime}: {e}")
            logger.warning("Runtime %s failed: %s", attempt_runtime, e)
            continue

    raise RuntimeError(f"All runtimes failed. Errors: {'; '.join(errors)}")


def _get_fallback_chain(primary: str) -> list[str]:
    """Return runtime fallback order starting from primary."""
    order = ["nim", "ollama"]
    if primary in order:
        idx = order.index(primary)
        return order[idx:] + order[:idx]
    return order
