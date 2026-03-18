"""
Phase 2 tests — Wallet encryption and tamper detection chain.
"""

import pytest
import uuid
from backend.crypto.ed25519 import generate_keypair, sign_message
from backend.services.wallet import (
    get_or_create_wallet, store_agent_key, retrieve_agent_key,
    rotate_agent_key, export_wallet, import_wallet,
)
from backend.services.tamper import (
    start_session, end_session, sign_message_entry, verify_message_entry,
    get_session_chain, verify_full_chain, issue_challenge,
    submit_challenge_response, trigger_kill_switch,
)
from backend.models.user import User
from backend.models.agent_identity import AgentIdentity


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def test_user(db_session):
    from argon2 import PasswordHasher
    ph = PasswordHasher()
    user = User(
        email=f"wallet-test-{uuid.uuid4()}@example.com",
        password_hash=ph.hash("TestPass1234!"),
        name="Wallet Tester",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_agent(db_session, test_user):
    from backend.crypto.ed25519 import generate_keypair, fingerprint
    from backend.crypto.did import generate_did, create_did_document
    kp = generate_keypair()
    agent_uuid = str(uuid.uuid4())
    agent = AgentIdentity(
        agent_id=uuid.UUID(agent_uuid),
        owner_id=test_user.id,
        did_uri=generate_did(agent_uuid),
        display_name="Test Agent",
        agent_type="assistant",
        model_version="",
        purpose="Testing",
        capabilities=[],
        public_key=kp.public_key,
        key_algorithm="ed25519",
        key_fingerprint=fingerprint(kp.public_key),
        did_document=create_did_document(agent_uuid, kp.public_key),
        verifiable_credential={},
        behavioral_signature={},
        routing_config={},
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent, kp.private_key


# ── Wallet Tests ──────────────────────────────────────────────────────────────

class TestWallet:
    def test_create_wallet(self, db_session, test_user):
        wallet = get_or_create_wallet(db_session, test_user, "MyPassphrase123!")
        assert wallet.wallet_id is not None
        assert wallet.owner_id == test_user.id
        assert len(wallet.master_key_salt) == 16

    def test_wallet_idempotent(self, db_session, test_user):
        w1 = get_or_create_wallet(db_session, test_user, "pass1")
        w2 = get_or_create_wallet(db_session, test_user, "pass1")
        assert w1.wallet_id == w2.wallet_id

    def test_store_and_retrieve_key(self, db_session, test_user, test_agent):
        agent, private_seed = test_agent
        wallet = get_or_create_wallet(db_session, test_user, "pass123!")
        store_agent_key(db_session, wallet, agent, private_seed, "pass123!")
        recovered = retrieve_agent_key(db_session, wallet, agent.agent_id, "pass123!")
        assert recovered == private_seed

    def test_wrong_passphrase_fails_retrieval(self, db_session, test_user, test_agent):
        agent, private_seed = test_agent
        wallet = get_or_create_wallet(db_session, test_user, "correct!")
        store_agent_key(db_session, wallet, agent, private_seed, "correct!")
        with pytest.raises(Exception):
            retrieve_agent_key(db_session, wallet, agent.agent_id, "wrong!")

    def test_key_rotation(self, db_session, test_user, test_agent):
        agent, private_seed = test_agent
        wallet = get_or_create_wallet(db_session, test_user, "pass!")
        store_agent_key(db_session, wallet, agent, private_seed, "pass!")
        old_fp = agent.key_fingerprint

        new_seed, new_wk = rotate_agent_key(db_session, wallet, agent, "pass!")
        assert new_seed != private_seed
        assert new_wk.key_version == 2
        assert agent.key_fingerprint != old_fp

        # Can retrieve new key
        recovered = retrieve_agent_key(db_session, wallet, agent.agent_id, "pass!")
        assert recovered == new_seed

    def test_export_import_roundtrip(self, db_session, test_user, test_agent):
        agent, private_seed = test_agent
        wallet = get_or_create_wallet(db_session, test_user, "orig-pass!")
        store_agent_key(db_session, wallet, agent, private_seed, "orig-pass!")

        blob = export_wallet(db_session, wallet, test_user, "orig-pass!", "export-pass!")
        assert len(blob) > 32

        # Import into same wallet (already exists)
        imported = import_wallet(db_session, test_user, blob, "export-pass!", "new-pass!")
        assert imported.wallet_id is not None


# ── Tamper Detection Tests ────────────────────────────────────────────────────

class TestTamperDetection:
    def test_start_session(self, db_session, test_agent):
        agent, _ = test_agent
        session = start_session(db_session, agent)
        assert session.session_id is not None
        assert session.agent_id == agent.agent_id
        assert session.interaction_count == 0

    def test_sign_and_verify_message(self, db_session, test_agent):
        agent, private_seed = test_agent
        session = start_session(db_session, agent)
        entry = sign_message_entry(db_session, agent, session, b"hello world", private_seed)
        assert entry.sequence_num == 0
        assert entry.prev_hash is None
        assert len(entry.signature) == 64
        assert verify_message_entry(db_session, entry.sig_id, agent)

    def test_chain_linkage(self, db_session, test_agent):
        agent, private_seed = test_agent
        session = start_session(db_session, agent)
        e1 = sign_message_entry(db_session, agent, session, b"msg1", private_seed)
        e2 = sign_message_entry(db_session, agent, session, b"msg2", private_seed)
        e3 = sign_message_entry(db_session, agent, session, b"msg3", private_seed)

        assert e2.prev_hash == e1.message_hash
        assert e3.prev_hash == e2.message_hash
        assert e2.sequence_num == 1
        assert e3.sequence_num == 2

    def test_full_chain_verification(self, db_session, test_agent):
        agent, private_seed = test_agent
        session = start_session(db_session, agent)
        for i in range(5):
            sign_message_entry(db_session, agent, session, f"msg{i}".encode(), private_seed)

        result = verify_full_chain(db_session, agent, session.session_id)
        assert result["all_valid"]
        assert result["entry_count"] == 5

    def test_end_session_computes_merkle_root(self, db_session, test_agent):
        agent, private_seed = test_agent
        session = start_session(db_session, agent)
        for i in range(3):
            sign_message_entry(db_session, agent, session, f"msg{i}".encode(), private_seed)
        ended = end_session(db_session, session)
        assert ended.merkle_root is not None
        assert len(ended.merkle_root) == 64   # hex SHA-256

    def test_heartbeat_challenge_response(self, db_session, test_agent):
        agent, private_seed = test_agent
        hb = issue_challenge(db_session, agent)
        assert len(hb.challenge) == 64   # 32 bytes hex

        # Sign the challenge
        challenge_bytes = bytes.fromhex(hb.challenge)
        signature = sign_message(private_seed, challenge_bytes)

        verified = submit_challenge_response(db_session, hb, agent, signature.hex())
        assert verified
        assert hb.verified

    def test_wrong_signature_fails_heartbeat(self, db_session, test_agent):
        agent, private_seed = test_agent
        hb = issue_challenge(db_session, agent)
        wrong_sig = "ff" * 64
        verified = submit_challenge_response(db_session, hb, agent, wrong_sig)
        assert not verified

    def test_kill_switch(self, db_session, test_user, test_agent):
        agent, _ = test_agent
        assert agent.is_active
        event = trigger_kill_switch(db_session, agent, test_user, "Compromised")
        assert event.event_id is not None
        assert not agent.is_active
        assert event.reason == "Compromised"

    def test_session_chain_retrieval(self, db_session, test_agent):
        agent, private_seed = test_agent
        session = start_session(db_session, agent)
        for i in range(3):
            sign_message_entry(db_session, agent, session, f"msg{i}".encode(), private_seed)
        chain = get_session_chain(db_session, agent.agent_id, session.session_id)
        assert len(chain) == 3
        assert chain[0]["sequence_num"] == 0
        assert chain[1]["prev_hash"] == chain[0]["message_hash"]
