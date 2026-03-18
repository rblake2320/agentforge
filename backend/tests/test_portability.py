"""
Phase 5 tests: Device registration, memory layers, session handoff.
"""

import uuid
import pytest
from sqlalchemy.orm import Session

from ..services import portability as svc
from ..models.portability import MemoryLayer, HandoffStatus


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_public_key() -> bytes:
    """Generate a fake 32-byte public key for tests."""
    import os
    return os.urandom(32)


def _make_fingerprint() -> str:
    import os
    return os.urandom(16).hex()


# ── Device Tests ───────────────────────────────────────────────────────────────

class TestDeviceRegistration:
    def test_register_new_device(self, db_session: Session, test_user):
        pk = _make_public_key()
        fp = _make_fingerprint()
        device = svc.register_device(db_session, test_user, "My Laptop", "desktop", fp, pk)

        assert device.device_id is not None
        assert device.device_name == "My Laptop"
        assert device.device_type == "desktop"
        assert device.device_fingerprint == fp
        assert device.owner_id == test_user.id
        assert device.public_key == pk

    def test_re_register_same_fingerprint_updates(self, db_session: Session, test_user):
        fp = _make_fingerprint()
        pk1 = _make_public_key()
        pk2 = _make_public_key()

        d1 = svc.register_device(db_session, test_user, "Laptop v1", "desktop", fp, pk1)
        d2 = svc.register_device(db_session, test_user, "Laptop v2", "desktop", fp, pk2)

        assert d1.device_id == d2.device_id  # same device
        assert d2.device_name == "Laptop v2"
        assert d2.public_key == pk2

    def test_different_user_cannot_claim_fingerprint(self, db_session: Session, test_user, second_user):
        fp = _make_fingerprint()
        svc.register_device(db_session, test_user, "Laptop", "desktop", fp, _make_public_key())

        with pytest.raises(ValueError, match="already registered to another user"):
            svc.register_device(db_session, second_user, "Hacked", "desktop", fp, _make_public_key())

    def test_list_devices(self, db_session: Session, test_user):
        svc.register_device(db_session, test_user, "Phone", "mobile", _make_fingerprint(), _make_public_key())
        svc.register_device(db_session, test_user, "Tablet", "tablet", _make_fingerprint(), _make_public_key())

        devices = svc.list_devices(db_session, test_user)
        assert len(devices) >= 2

    def test_deregister_device(self, db_session: Session, test_user):
        device = svc.register_device(
            db_session, test_user, "TempDevice", "desktop", _make_fingerprint(), _make_public_key()
        )
        device_id = device.device_id
        svc.deregister_device(db_session, device, test_user)

        fetched = db_session.get(type(device), device_id)
        assert fetched is None

    def test_touch_device_updates_last_seen(self, db_session: Session, test_user):
        import time
        device = svc.register_device(
            db_session, test_user, "TouchMe", "desktop", _make_fingerprint(), _make_public_key()
        )
        original_seen = device.last_seen
        time.sleep(0.01)
        updated = svc.touch_device(db_session, device)
        assert updated.last_seen >= original_seen


# ── Memory Layer Tests ─────────────────────────────────────────────────────────

class TestMemoryLayers:
    def test_write_hot_memory(self, db_session: Session, test_user, test_agent):
        content = b"The quick brown fox"
        mem = svc.write_memory(db_session, test_agent, "hot", content, "testpass", summary="fox story", priority=7)

        assert mem.memory_id is not None
        assert mem.layer == MemoryLayer.hot
        assert mem.summary == "fox story"
        assert mem.priority == 7
        assert mem.content_hash is not None

    def test_read_memory_decrypts_correctly(self, db_session: Session, test_user, test_agent):
        original = b"Secret agent context data"
        mem = svc.write_memory(db_session, test_agent, "warm", original, "mypassphrase")
        recovered = svc.read_memory(db_session, mem, "mypassphrase")
        assert recovered == original

    def test_wrong_passphrase_fails(self, db_session: Session, test_agent):
        mem = svc.write_memory(db_session, test_agent, "hot", b"private", "correct")
        with pytest.raises(Exception):
            svc.read_memory(db_session, mem, "wrong_passphrase")

    def test_list_memories_by_layer(self, db_session: Session, test_agent):
        svc.write_memory(db_session, test_agent, "hot", b"hot data", "pw")
        svc.write_memory(db_session, test_agent, "warm", b"warm data", "pw")
        svc.write_memory(db_session, test_agent, "cold", b"cold data", "pw")

        hot = svc.list_memories(db_session, test_agent, layer="hot")
        warm = svc.list_memories(db_session, test_agent, layer="warm")
        all_mems = svc.list_memories(db_session, test_agent)

        assert len(hot) >= 1
        assert len(warm) >= 1
        assert len(all_mems) >= 3

    def test_promote_cold_to_warm(self, db_session: Session, test_agent):
        mem = svc.write_memory(db_session, test_agent, "cold", b"archive", "pw")
        promoted = svc.promote_memory(db_session, mem, "warm")
        assert promoted.layer == MemoryLayer.warm

    def test_promote_warm_to_hot(self, db_session: Session, test_agent):
        mem = svc.write_memory(db_session, test_agent, "warm", b"warm", "pw")
        promoted = svc.promote_memory(db_session, mem, "hot")
        assert promoted.layer == MemoryLayer.hot

    def test_cannot_demote_memory(self, db_session: Session, test_agent):
        mem = svc.write_memory(db_session, test_agent, "hot", b"hot", "pw")
        with pytest.raises(ValueError, match="hotter layer"):
            svc.promote_memory(db_session, mem, "cold")

    def test_delete_memory(self, db_session: Session, test_user, test_agent):
        mem = svc.write_memory(db_session, test_agent, "hot", b"delete me", "pw")
        mem_id = mem.memory_id
        svc.delete_memory(db_session, mem, test_user)

        from ..models.portability import AgentMemoryLayer
        assert db_session.get(AgentMemoryLayer, mem_id) is None

    def test_evict_cold_moves_hot_to_warm(self, db_session: Session, test_agent):
        """Hot memories older than threshold should be evicted to warm."""
        import time
        # Write a memory, then artificially age its accessed_at
        mem = svc.write_memory(db_session, test_agent, "hot", b"old data", "pw")
        from datetime import timedelta, timezone
        from datetime import datetime
        # Age the memory artificially
        mem.accessed_at = datetime.now(timezone.utc) - timedelta(hours=72)
        db_session.commit()

        count = svc.evict_cold_memories(db_session, test_agent, before_hours=48)
        assert count >= 1
        db_session.refresh(mem)
        assert mem.layer == MemoryLayer.warm


# ── Session Handoff Tests ──────────────────────────────────────────────────────

class TestSessionHandoff:
    def _make_device(self, db, user):
        return svc.register_device(db, user, "TestDevice", "desktop", _make_fingerprint(), _make_public_key())

    def test_create_handoff(self, db_session: Session, test_user, test_agent):
        snapshot = b'{"messages": [], "context": "test"}'
        handoff = svc.create_handoff(db_session, test_agent, None, None, snapshot, "handoffpass")

        assert handoff.handoff_id is not None
        assert handoff.handoff_token.startswith("HO-")
        assert handoff.status == HandoffStatus.pending
        assert handoff.expires_at > handoff.created_at

    def test_accept_handoff_roundtrip(self, db_session: Session, test_user, test_agent):
        snapshot = b'{"context": "important session state"}'
        handoff = svc.create_handoff(db_session, test_agent, None, None, snapshot, "roundtrippass")

        to_device = self._make_device(db_session, test_user)
        accepted, recovered = svc.accept_handoff(
            db_session, handoff.handoff_token, to_device, None, "roundtrippass"
        )

        assert accepted.status == HandoffStatus.accepted
        assert accepted.to_device_id == to_device.device_id
        assert recovered == snapshot

    def test_accept_with_wrong_passphrase_fails(self, db_session: Session, test_user, test_agent):
        snapshot = b"session state"
        handoff = svc.create_handoff(db_session, test_agent, None, None, snapshot, "correctpass")
        to_device = self._make_device(db_session, test_user)

        with pytest.raises(Exception):
            svc.accept_handoff(db_session, handoff.handoff_token, to_device, None, "wrongpass")

    def test_cannot_accept_same_token_twice(self, db_session: Session, test_user, test_agent):
        snapshot = b"state"
        handoff = svc.create_handoff(db_session, test_agent, None, None, snapshot, "pw")
        to_device = self._make_device(db_session, test_user)

        svc.accept_handoff(db_session, handoff.handoff_token, to_device, None, "pw")

        with pytest.raises(ValueError, match="accepted"):
            svc.accept_handoff(db_session, handoff.handoff_token, to_device, None, "pw")

    def test_invalid_token_raises(self, db_session: Session, test_user, test_agent):
        to_device = self._make_device(db_session, test_user)
        with pytest.raises(ValueError, match="not found"):
            svc.accept_handoff(db_session, "HO-fakeinvalidtoken", to_device, None, "pw")

    def test_expired_handoff_raises(self, db_session: Session, test_user, test_agent):
        from datetime import timedelta, timezone
        from datetime import datetime

        snapshot = b"state"
        handoff = svc.create_handoff(db_session, test_agent, None, None, snapshot, "pw")
        # Artificially expire it
        handoff.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db_session.commit()

        to_device = self._make_device(db_session, test_user)
        with pytest.raises(ValueError, match="expired"):
            svc.accept_handoff(db_session, handoff.handoff_token, to_device, None, "pw")

    def test_expire_stale_handoffs(self, db_session: Session, test_user, test_agent):
        from datetime import timedelta, timezone
        from datetime import datetime

        snapshot = b"stale"
        h1 = svc.create_handoff(db_session, test_agent, None, None, snapshot, "pw")
        h2 = svc.create_handoff(db_session, test_agent, None, None, snapshot, "pw")

        # Age both
        for h in [h1, h2]:
            h.expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        db_session.commit()

        count = svc.expire_stale_handoffs(db_session)
        assert count >= 2

    def test_list_handoffs(self, db_session: Session, test_user, test_agent):
        snapshot = b"state"
        svc.create_handoff(db_session, test_agent, None, None, snapshot, "pw")
        svc.create_handoff(db_session, test_agent, None, None, snapshot, "pw")

        handoffs = svc.list_handoffs(db_session, test_agent)
        assert len(handoffs) >= 2
