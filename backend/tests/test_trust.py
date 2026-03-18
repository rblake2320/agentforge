"""
Phase 6 tests: Trust Engine + Skill Connectors.
"""

import uuid
import pytest
from sqlalchemy.orm import Session

from ..services import trust as svc
from ..models.trust import TrustLevel, SkillConnector, AgentSkillBinding


class TestTrustScoring:
    def test_get_trust_profile_creates_on_first_access(self, db_session: Session, test_agent):
        profile = svc.get_trust_profile(db_session, test_agent)
        assert profile is not None
        assert profile.agent_id == test_agent.agent_id
        assert 0.0 <= profile.overall_score <= 100.0

    def test_new_agent_gets_provisional_or_better(self, db_session: Session, test_agent):
        profile = svc.calculate_trust_score(db_session, test_agent)
        # New agents with no violations should be at least provisional (20+)
        assert profile.overall_score >= 20.0
        assert profile.trust_level in [
            TrustLevel.provisional, TrustLevel.trusted, TrustLevel.verified, TrustLevel.elite
        ]

    def test_trust_levels_map_correctly(self):
        from ..services.trust import _score_to_level
        assert _score_to_level(0) == TrustLevel.untrusted
        assert _score_to_level(19) == TrustLevel.untrusted
        assert _score_to_level(20) == TrustLevel.provisional
        assert _score_to_level(39) == TrustLevel.provisional
        assert _score_to_level(40) == TrustLevel.trusted
        assert _score_to_level(69) == TrustLevel.trusted
        assert _score_to_level(70) == TrustLevel.verified
        assert _score_to_level(89) == TrustLevel.verified
        assert _score_to_level(90) == TrustLevel.elite
        assert _score_to_level(100) == TrustLevel.elite

    def test_kill_switch_events_reduce_score(self, db_session: Session, test_user, test_agent):
        from ..models.tamper import KillSwitchEvent, HeartbeatStatus
        # Add 5 kill switch events (75-point technical penalty)
        for _ in range(5):
            ev = KillSwitchEvent(
                agent_id=test_agent.agent_id,
                triggered_by=test_user.id,
                reason="test violation",
            )
            db_session.add(ev)
        db_session.commit()

        profile = svc.calculate_trust_score(db_session, test_agent)
        # 5 kills = 75 penalty → technical_trust should be 25 or lower
        assert profile.technical_trust <= 25.0
        assert profile.tamper_violations == 5

    def test_recalculate_updates_profile(self, db_session: Session, test_agent):
        p1 = svc.calculate_trust_score(db_session, test_agent)
        t1 = p1.calculated_at

        import time
        time.sleep(0.01)

        p2 = svc.calculate_trust_score(db_session, test_agent)
        assert p2.calculated_at >= t1  # Updated

    def test_batch_recalculate(self, db_session: Session, test_user, test_agent):
        count = svc.batch_recalculate(db_session, owner=test_user)
        assert count >= 1

    def test_component_scores_in_range(self, db_session: Session, test_agent):
        profile = svc.calculate_trust_score(db_session, test_agent)
        assert 0.0 <= profile.technical_trust <= 100.0
        assert 0.0 <= profile.reliability_trust <= 100.0
        assert 0.0 <= profile.security_trust <= 100.0
        assert 0.0 <= profile.overall_score <= 100.0


class TestSkillConnectors:
    def test_create_connector(self, db_session: Session, test_user):
        connector = svc.create_skill_connector(
            db_session,
            name=f"web-search-{uuid.uuid4().hex[:6]}",
            category="search",
            description="DuckDuckGo web search",
            endpoint_url="https://api.duckduckgo.com/search",
            auth_type="api_key",
            schema_definition={"query": "string"},
            is_public=True,
            created_by=test_user.id,
        )
        assert connector.connector_id is not None
        assert connector.category == "search"
        assert connector.auth_type.value == "api_key"

    def test_list_connectors_public_only(self, db_session: Session, test_user):
        name_pub = f"pub-{uuid.uuid4().hex[:6]}"
        name_priv = f"priv-{uuid.uuid4().hex[:6]}"
        svc.create_skill_connector(db_session, name_pub, "util", "", "https://pub.example.com", is_public=True, created_by=test_user.id)
        svc.create_skill_connector(db_session, name_priv, "util", "", "https://priv.example.com", is_public=False, created_by=test_user.id)

        public = svc.list_skill_connectors(db_session, public_only=True)
        names = [c.name for c in public]
        assert name_pub in names
        assert name_priv not in names

    def test_list_connectors_by_category(self, db_session: Session, test_user):
        svc.create_skill_connector(db_session, f"email-{uuid.uuid4().hex[:4]}", "email", "", "https://smtp.example.com", created_by=test_user.id)
        email_connectors = svc.list_skill_connectors(db_session, category="email")
        assert len(email_connectors) >= 1
        assert all(c.category == "email" for c in email_connectors)

    def test_bind_skill_to_agent(self, db_session: Session, test_user, test_agent):
        connector = svc.create_skill_connector(
            db_session,
            name=f"search-{uuid.uuid4().hex[:6]}",
            category="search",
            description="",
            endpoint_url="https://search.example.com",
            created_by=test_user.id,
        )
        binding = svc.bind_skill(db_session, test_agent, connector, permissions={"max_results": 10})

        assert binding.binding_id is not None
        assert binding.agent_id == test_agent.agent_id
        assert binding.connector_id == connector.connector_id
        assert binding.permissions == {"max_results": 10}
        assert binding.enabled is True

    def test_rebind_skill_updates_permissions(self, db_session: Session, test_user, test_agent):
        connector = svc.create_skill_connector(
            db_session, f"rebind-{uuid.uuid4().hex[:4]}", "util", "", "https://rebind.example.com", created_by=test_user.id
        )
        b1 = svc.bind_skill(db_session, test_agent, connector, {"limit": 5})
        b2 = svc.bind_skill(db_session, test_agent, connector, {"limit": 20})

        assert b1.binding_id == b2.binding_id  # Same binding
        assert b2.permissions == {"limit": 20}

    def test_list_agent_skills(self, db_session: Session, test_user, test_agent):
        c1 = svc.create_skill_connector(db_session, f"s1-{uuid.uuid4().hex[:4]}", "util", "", "https://s1.example.com", created_by=test_user.id)
        c2 = svc.create_skill_connector(db_session, f"s2-{uuid.uuid4().hex[:4]}", "util", "", "https://s2.example.com", created_by=test_user.id)
        svc.bind_skill(db_session, test_agent, c1)
        svc.bind_skill(db_session, test_agent, c2)

        skills = svc.list_agent_skills(db_session, test_agent)
        assert len(skills) >= 2

    def test_unbind_skill(self, db_session: Session, test_user, test_agent):
        connector = svc.create_skill_connector(
            db_session, f"unbind-{uuid.uuid4().hex[:4]}", "util", "", "https://unbind.example.com", created_by=test_user.id
        )
        svc.bind_skill(db_session, test_agent, connector)
        svc.unbind_skill(db_session, test_agent, connector)

        skills = svc.list_agent_skills(db_session, test_agent)
        connector_ids = [s.connector_id for s in skills]
        assert connector.connector_id not in connector_ids

    def test_unbind_nonexistent_raises(self, db_session: Session, test_user, test_agent):
        connector = svc.create_skill_connector(
            db_session, f"nobound-{uuid.uuid4().hex[:4]}", "util", "", "https://nb.example.com", created_by=test_user.id
        )
        with pytest.raises(ValueError, match="not bound"):
            svc.unbind_skill(db_session, test_agent, connector)
