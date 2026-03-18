"""
Runtime manager tests — intent classification, system prompt injection, flywheel logging.

HTTP calls to NIM/Ollama are mocked so these tests run fully offline.
"""

import json
import os
import uuid
import asyncio
import tempfile
import shutil
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from ..services.runtime_manager import (
    _classify_intent,
    chat,
    ChatResponse,
)


# ── Helpers ─────────────────────────────────────────────────────────────────────

def _fake_openai_response(content: str = "Hello from mock", model: str = "test-model") -> MagicMock:
    """Build a mock httpx.Response that looks like an OpenAI-compatible chat completion."""
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "choices": [{"message": {"content": content}}],
        "model": model,
        "usage": {"prompt_tokens": 10, "completion_tokens": 20},
    }
    return resp


def _fake_ollama_response(content: str = "Hello from ollama") -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "message": {"content": content},
    }
    return resp


# ── Intent Classification Tests ─────────────────────────────────────────────────

class TestRuntimeManager:
    def test_intent_classify_complex(self):
        msg = (
            "Please analyze the architectural trade-offs between microservices and monoliths "
            "and provide a detailed strategy for migrating our legacy platform."
        )
        result = _classify_intent(msg)
        assert result == "complex"

    def test_intent_classify_simple(self):
        result = _classify_intent("hi")
        assert result == "chit_chat"  # Very short messages → chit_chat fast path

    def test_intent_classify_code(self):
        result = _classify_intent("write python function to parse JSON")
        assert result == "code"

    # ── System prompt injection ─────────────────────────────────────────────────

    def test_system_prompt_includes_agent_identity(self, db_session: Session, test_agent):
        """chat() should inject agent DID into the system prompt sent to the model."""
        captured_calls = []

        async def fake_post(url, *, json=None, headers=None, **kwargs):
            if json and "messages" in json:
                captured_calls.append(json["messages"])
            return _fake_openai_response("agent response")

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=fake_post)

        with patch("backend.services.runtime_manager.httpx.AsyncClient", return_value=mock_client):
            # Force NIM runtime so we control exactly which path is taken
            response = asyncio.run(
                chat(
                    agent=test_agent,
                    messages=[{"role": "user", "content": "analyze this architecture"}],
                    runtime_override="nim",
                )
            )

        assert len(captured_calls) > 0
        # The system message (first message) should contain the agent's DID
        system_msgs = [
            m for call in captured_calls for m in call if m.get("role") == "system"
        ]
        assert system_msgs, "No system message was injected"
        system_content = system_msgs[0]["content"]
        assert test_agent.did_uri in system_content, (
            f"Expected DID {test_agent.did_uri!r} in system prompt, got: {system_content!r}"
        )

    # ── Data Flywheel logging ───────────────────────────────────────────────────

    def test_flywheel_log_created(self, db_session: Session, test_agent, monkeypatch):
        """After chat(), a JSONL entry should exist in flywheel_logs/{agent_id}.jsonl."""
        # Use a real temp directory (avoids Windows pytest-tmp permission issues)
        log_dir = Path(tempfile.mkdtemp())
        try:
            async def fake_post(url, *, json=None, headers=None, **kwargs):
                return _fake_openai_response("logged response")

            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(side_effect=fake_post)

            # Patch _log_for_flywheel to write into our controlled temp dir
            import backend.services.runtime_manager as rm_module

            def patched_log(agent_id, messages, response, intent):
                log_path = log_dir / f"{agent_id}.jsonl"
                entry = {
                    "agent_id": str(agent_id),
                    "intent": intent,
                    "model": response.model,
                    "runtime": response.runtime,
                    "messages": messages,
                    "response": response.content,
                }
                with open(log_path, "a") as f:
                    f.write(json.dumps(entry) + "\n")

            monkeypatch.setattr(rm_module, "_log_for_flywheel", patched_log)

            with patch("backend.services.runtime_manager.httpx.AsyncClient", return_value=mock_client):
                asyncio.run(
                    chat(
                        agent=test_agent,
                        messages=[{"role": "user", "content": "analyze something complex"}],
                        runtime_override="nim",
                    )
                )

            log_file = log_dir / f"{test_agent.agent_id}.jsonl"
            assert log_file.exists(), f"Flywheel log not created at {log_file}"

            lines = log_file.read_text().strip().splitlines()
            assert len(lines) >= 1

            entry = json.loads(lines[0])
            assert entry["agent_id"] == str(test_agent.agent_id)
            assert "intent" in entry
            assert "model" in entry
        finally:
            shutil.rmtree(log_dir, ignore_errors=True)
